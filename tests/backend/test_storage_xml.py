"""Actual botocore parser/client paths with recorded HTTP, never real S3 or credentials."""

import hashlib
import io
import logging
import socket
import urllib.request
from types import SimpleNamespace

import boto3
import botocore
import pytest
from botocore.awsrequest import AWSResponse
from botocore.exceptions import ClientError
from botocore.parsers import BaseXMLResponseParser, ResponseParserError, ResponseParserFactory
from cargopulse_api.storage import PrivateObjects

TENANT = "10000000-0000-4000-8000-000000000001"
MAX_XML = 1_048_576
XML_ERROR = b"<Error><Code>NoSuchKey</Code><Message>missing</Message></Error>"
ORIGINAL_XML_PARSE = BaseXMLResponseParser._parse_xml_string_to_dom


class RecordedBody(io.BytesIO):
    def stream(self, amt=65536, decode_content=False):
        while chunk := self.read(amt):
            yield chunk


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    # Explicitly fake credentials; isolated empty config prevents user-secret reads.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "CARGOPULSE_TEST_ONLY_NOT_A_REAL_ACCESS_KEY")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "CARGOPULSE_TEST_ONLY_NOT_A_REAL_SECRET")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "empty-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "empty-credentials"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_PROFILE", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)

    def network_forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network access in recorded S3 test")

    monkeypatch.setattr(socket.socket, "connect", network_forbidden)
    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", network_forbidden)
    settings = SimpleNamespace(
        object_root=str(tmp_path / "objects"),
        object_bucket="synthetic-private-test",
        object_endpoint="https://recorded-s3.invalid",
    )
    objects = PrivateObjects(settings)
    state = SimpleNamespace(status=200, body=b"", headers={}, requests=[])

    def send(request):
        assert request.url.startswith("https://recorded-s3.invalid/")
        state.requests.append(request)
        headers = {"content-length": str(len(state.body)), **state.headers}
        return AWSResponse(request.url, state.status, headers, RecordedBody(state.body))

    monkeypatch.setattr(objects.s3._endpoint.http_session, "send", send)
    yield objects, state
    objects.s3.close()


def assert_generic_xml_failure(call, marker="PRIVATE_XML_CANARY"):
    with pytest.raises(ResponseParserError) as rejected:
        call()
    assert marker not in str(rejected.value)
    assert "<!DOCTYPE" not in str(rejected.value)
    assert "<Error>" not in str(rejected.value)


@pytest.mark.parametrize("operation", ["probe", "put"])
def test_internal_dtd_is_rejected_on_success_xml_response(recorded, operation):
    objects, state = recorded
    state.body = b'<!DOCTYPE Result [<!ENTITY x "PRIVATE_XML_CANARY">]><Result>&x;</Result>'
    call = objects.probe if operation == "probe" else lambda: objects.put(TENANT, b"payload")
    assert_generic_xml_failure(call)


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-16-be"])
def test_dtd_rejection_is_encoding_aware_not_a_byte_regex(recorded, encoding):
    objects, state = recorded
    declaration = "utf-8" if encoding == "utf-8-sig" else "utf-16"
    xml = (
        f'<?xml version="1.0" encoding="{declaration}"?>'
        '<!DOCTYPE Result [<!ENTITY x "PRIVATE_XML_CANARY">]><Result>&x;</Result>'
    )
    state.body = xml.encode(encoding)
    assert_generic_xml_failure(objects.probe)


def test_external_file_entity_canary_is_not_read_and_dtd_is_rejected(recorded, tmp_path):
    objects, state = recorded
    canary = tmp_path / "synthetic-canary.txt"
    canary.write_text("SYNTHETIC_FILE_CONTENT_MUST_NOT_APPEAR")
    state.body = (
        f'<!DOCTYPE Result [<!ENTITY x SYSTEM "{canary.as_uri()}">]><Result>&x;</Result>'
    ).encode()
    assert_generic_xml_failure(objects.probe, marker=str(canary))


def test_external_http_entity_cannot_fetch(recorded):
    objects, state = recorded
    state.body = (
        b'<!DOCTYPE Result [<!ENTITY x SYSTEM "https://entity-canary.invalid/PRIVATE_XML_CANARY">]>'
        b"<Result>&x;</Result>"
    )
    assert_generic_xml_failure(objects.probe)
    assert len(state.requests) == 1


def test_internal_entity_amplification_is_rejected_before_expansion(recorded):
    objects, state = recorded
    state.body = (
        b'<!DOCTYPE Result [<!ENTITY a "PRIVATE_XML_CANARY">'
        b'<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">'
        b'<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;">]><Result>&c;</Result>'
    )
    assert_generic_xml_failure(objects.probe)


def test_malformed_xml_exception_does_not_echo_protocol_body(recorded):
    objects, state = recorded
    state.body = b"<Result>PRIVATE_XML_CANARY<Unclosed>"
    assert_generic_xml_failure(objects.probe)


def test_protocol_xml_parse_budget_is_enforced(recorded):
    objects, state = recorded
    state.body = b"<Result>" + b"x" * MAX_XML + b"</Result>"
    assert_generic_xml_failure(objects.probe)


def test_normal_head_put_and_raw_get_preserve_sdk_behavior(recorded, monkeypatch):
    from cargopulse_api import storage_xml

    objects, state = recorded
    assert objects.probe() == "ok"
    raw = b'<!DOCTYPE opaque [<!ENTITY x "not protocol XML">]><blob>&x;</blob>\x00\xff' + b"x" * MAX_XML
    key = objects.put(TENANT, raw)
    assert state.requests[-1].headers["x-amz-server-side-encryption"] == b"AES256"
    assert state.requests[-1].headers["Content-Type"] == b"application/octet-stream"
    state.body = raw

    def xml_guard_must_not_parse_blob(*args, **kwargs):
        raise AssertionError("Raw GetObject contents entered the XML guard")

    monkeypatch.setattr(storage_xml, "parse_protocol_xml", xml_guard_must_not_parse_blob)
    assert objects.verify(TENANT, key) is True
    assert len(state.requests) == 3
    config = objects.s3.meta.config
    assert config.connect_timeout == 3 and config.read_timeout == 3
    assert config.retries["total_max_attempts"] == 2
    assert objects.s3._endpoint.http_session._verify is True


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16"])
def test_valid_namespaced_xml_and_builtin_entities_work(recorded, encoding):
    objects, state = recorded
    declaration = "utf-16" if encoding == "utf-16" else "utf-8"
    state.body = (
        f'<?xml version="1.0" encoding="{declaration}"?>'
        '<Result xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        "<Ignored>&amp;&lt;&gt;&apos;&quot;</Ignored></Result>"
    ).encode(encoding)
    assert objects.probe() == "ok"


def test_normal_s3_xml_error_is_retained_and_verify_fails_closed(recorded):
    objects, state = recorded
    state.status, state.body = 404, XML_ERROR
    with pytest.raises(ClientError) as error:
        objects.probe()
    assert error.value.response["Error"] == {"Code": "NoSuchKey", "Message": "missing"}
    key = TENANT + "/imports/" + hashlib.sha256(b"missing").hexdigest()
    assert objects.verify(TENANT, key) is False


@pytest.mark.parametrize(
    "body",
    [
        b'<!DOCTYPE Error [<!ENTITY x "PRIVATE_XML_CANARY">]>'
        b"<Error><Code>NoSuchKey</Code><Message>&x;</Message></Error>",
        b"<Error>PRIVATE_XML_CANARY<Unclosed>",
    ],
)
def test_bad_xml_error_fails_closed_without_raw_body_in_exception(recorded, body):
    objects, state = recorded
    state.status, state.body = 404, body
    with pytest.raises((ClientError, ResponseParserError)) as error:
        objects.probe()
    assert "PRIVATE_XML_CANARY" not in str(error.value)
    key = TENANT + "/imports/" + hashlib.sha256(b"missing").hexdigest()
    assert objects.verify(TENANT, key) is False


def test_verify_catches_parser_error_instead_of_escaping(recorded, monkeypatch):
    objects, _ = recorded

    def failed_parse(**kwargs):
        raise ResponseParserError("Rejected S3 protocol XML")

    monkeypatch.setattr(objects.s3, "get_object", failed_parse)
    key = TENANT + "/imports/" + hashlib.sha256(b"missing").hexdigest()
    assert objects.verify(TENANT, key) is False


def test_owned_factory_preserves_defaults_json_and_global_parser(recorded):
    from cargopulse_api.storage_xml import StrictResponseParserFactory

    assert boto3.__version__ == botocore.__version__ == "1.43.127"
    assert BaseXMLResponseParser._parse_xml_string_to_dom is ORIGINAL_XML_PARSE
    strict = StrictResponseParserFactory()
    timestamp, blob = lambda value: ("time", value), lambda value: ("blob", value)
    strict.set_parser_defaults(timestamp_parser=timestamp, blob_parser=blob)
    xml = strict.create_parser("rest-xml")
    assert xml._timestamp_parser is timestamp and xml._blob_parser is blob
    json_parser = strict.create_parser("json")
    assert not isinstance(json_parser, BaseXMLResponseParser)
    assert json_parser.parse({"status_code": 200, "headers": {}, "body": b"{}"}, None) == {
        "ResponseMetadata": {"HTTPStatusCode": 200, "HTTPHeaders": {}}
    }
    # Unowned SDK parsers retain their original behavior: no global monkeypatch.
    ordinary = ResponseParserFactory().create_parser("rest-xml")
    root = ordinary._parse_xml_string_to_dom(b'<!DOCTYPE Result [<!ENTITY x "ok">]><Result>&x;</Result>')
    assert root.text == "ok"
    assert_generic_xml_failure(
        lambda: xml._parse_xml_string_to_dom(b'<!DOCTYPE Result [<!ENTITY x "x">]><Result>&x;</Result>')
    )


@pytest.mark.parametrize("oversize", [False, True])
def test_guard_runs_before_unsafe_sdk_embedded_error_detection(recorded, monkeypatch, oversize):
    import botocore.handlers

    objects, state = recorded
    state.body = b'<!DOCTYPE Result [<!ENTITY x "PRIVATE_XML_CANARY">]><Result>&x;</Result>'
    if oversize:
        state.body = b"<Result>" + b"x" * MAX_XML + b"</Result>"

    def unsafe_parser_must_not_run(*args, **kwargs):
        raise AssertionError("Unsafe builtin XML parser ran before strict guard")

    monkeypatch.setattr(botocore.handlers, "_looks_like_special_case_error", unsafe_parser_must_not_run)
    assert_generic_xml_failure(objects.probe)
    assert len(state.requests) == 1


def test_normal_embedded_200_s3_error_keeps_sdk_retry_semantics(recorded):
    objects, state = recorded
    state.body = b"<Error><Code>InternalError</Code><Message>retry-me</Message></Error>"
    with pytest.raises(ClientError) as error:
        objects.put(TENANT, b"payload")
    assert error.value.response["Error"]["Code"] == "InternalError"
    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 500
    assert len(state.requests) == 2


def test_rejected_protocol_xml_is_not_emitted_by_sdk_debug_logging(recorded, caplog):
    objects, state = recorded
    state.body = b"<Result>PRIVATE_XML_CANARY<Unclosed>"
    with caplog.at_level(logging.DEBUG, logger="botocore"):
        assert_generic_xml_failure(objects.probe)
    assert "PRIVATE_XML_CANARY" not in caplog.text


def test_missing_expected_pinned_builtin_handler_fails_closed(recorded):
    from botocore.handlers import _handle_200_error
    from botocore.session import Session
    from cargopulse_api.storage_xml import register_s3_xml_guard

    session = Session()
    session.unregister("before-parse.s3.*", _handle_200_error)
    with pytest.raises(ResponseParserError, match="Incompatible S3 XML event boundary"):
        register_s3_xml_guard(session)
