"""Strict XML boundary for owned S3 protocol parsers, not object/blob contents.

The instance hook is verified against pinned botocore 1.43.127. Revalidate this
private integration when upgrading the SDK. The byte budget applies after the
SDK buffers a protocol response; it is not an HTTP streaming/download limit.
"""

from types import MethodType
from xml.etree import ElementTree

from botocore.handlers import _handle_200_error
from botocore.parsers import BaseXMLResponseParser, ResponseParserError, ResponseParserFactory

MAX_PROTOCOL_XML_BYTES = 1_048_576
REJECTED_XML_MESSAGE = "Rejected S3 protocol XML response"


class NoDTDTreeBuilder(ElementTree.TreeBuilder):
    def doctype(self, name, pubid, system):
        # Parser events cover BOM/encoding variations and run before entity use.
        raise ElementTree.ParseError("DTD declarations are not permitted")


def parse_protocol_xml(xml_string, encoding="utf-8"):
    if not isinstance(xml_string, (bytes, bytearray, str)):
        raise ResponseParserError(REJECTED_XML_MESSAGE)
    size = len(xml_string.encode("utf-8")) if isinstance(xml_string, str) else len(xml_string)
    if size > MAX_PROTOCOL_XML_BYTES:
        raise ResponseParserError(REJECTED_XML_MESSAGE)
    try:
        target = NoDTDTreeBuilder()
        # The bounded custom target rejects every DTD before entity expansion.
        xml_parser = ElementTree.XMLParser(target=target, encoding=encoding)  # noqa: S314
        xml_parser.feed(xml_string)
        return xml_parser.close()
    except (ElementTree.ParseError, ValueError, LookupError):
        # Neither the received XML nor parser diagnostics cross this boundary.
        raise ResponseParserError(REJECTED_XML_MESSAGE) from None


def _strict_xml_to_dom(parser, xml_string):
    return parse_protocol_xml(xml_string, encoding=parser.DEFAULT_ENCODING)


def _guard_before_s3_parse(operation_model, response_dict, **kwargs):
    body = response_dict.get("body")
    status = response_dict["status_code"]
    shape = operation_model.output_shape
    protocol_body = status >= 300
    if not protocol_body and shape and not operation_model.has_event_stream_output:
        payload = shape.serialization.get("payload")
        protocol_body = payload is None or shape.members[payload].type_name not in {"blob", "string"}
    if body and protocol_body:
        parse_protocol_xml(body)
    # Preserve the SDK's embedded-200-error detection and bounded retry behavior.
    return _handle_200_error(operation_model, response_dict, **kwargs)


def register_s3_xml_guard(session):
    # The SDK builtin also parses XML before ResponseParserFactory is consulted.
    # Appending register_first alone still runs after its existing first handler.
    # Replace only this owned session's registration with a guarded wrapper.
    emitter = session.get_component("event_emitter")
    registry = getattr(getattr(emitter, "_emitter", None), "_handlers", None)
    lookup = getattr(registry, "prefix_search", None)
    if not callable(lookup):
        raise ResponseParserError("Incompatible S3 XML event boundary")
    registered = list(lookup("before-parse.s3.HeadBucket"))
    if not registered or registered[0] is not _handle_200_error or registered.count(_handle_200_error) != 1:
        raise ResponseParserError("Incompatible S3 XML event boundary")
    emitter.unregister("before-parse.s3.*", _handle_200_error)
    emitter.register_first("before-parse.s3.*", _guard_before_s3_parse)
    for operation in ("HeadBucket", "PutObject", "GetObject"):
        registered = list(lookup("before-parse.s3." + operation))
        if not registered or registered[0] is not _guard_before_s3_parse or _handle_200_error in registered:
            raise ResponseParserError("Incompatible S3 XML event boundary")


class StrictResponseParserFactory(ResponseParserFactory):
    def create_parser(self, protocol_name):
        # Preserve normal SDK classes, parser defaults, JSON and streaming paths.
        parser = super().create_parser(protocol_name)
        if isinstance(parser, BaseXMLResponseParser):
            if not callable(getattr(parser, "_parse_xml_string_to_dom", None)):
                raise ResponseParserError("Incompatible S3 XML response parser")
            parser._parse_xml_string_to_dom = MethodType(_strict_xml_to_dom, parser)
        return parser
