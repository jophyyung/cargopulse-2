"""A real loopback OTLP/HTTP receiver; requests are decoded as OTLP protobuf."""

import gzip
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest


@pytest.fixture
def collector():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = self.rfile.read(int(self.headers["Content-Length"]))
            if self.headers.get("Content-Encoding") == "gzip":
                payload = gzip.decompress(payload)
            kind = {
                "/v1/traces": ExportTraceServiceRequest,
                "/v1/metrics": ExportMetricsServiceRequest,
            }[self.path]
            message = kind.FromString(payload)
            received.append((self.path, self.headers.get("Content-Type"), message))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def spans(received):
    return [
        (resource.resource, span)
        for path, _, message in received
        if path == "/v1/traces"
        for resource in message.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
    ]


def metrics(received):
    return [
        metric
        for path, _, message in received
        if path == "/v1/metrics"
        for resource in message.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    ]


def attributes(items):
    return {item.key: item.value.string_value or item.value.int_value for item in items}
