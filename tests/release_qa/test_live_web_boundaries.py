"""Actual Next standalone server checks; opt in with CARGOPULSE_QA_WEB_URL."""

import os
import socket
import time
from urllib.parse import urlsplit

import httpx
import pytest


@pytest.fixture
def web_url():
    value = os.environ.get("CARGOPULSE_QA_WEB_URL")
    if not value:
        pytest.skip("Standalone web URL not configured")
    assert urlsplit(value).hostname in ("localhost", "127.0.0.1"), "Synthetic localhost review only"
    return value


def test_every_console_page_and_rsc_requires_a_session(web_url):
    with httpx.Client(base_url=web_url, follow_redirects=False) as client:
        for path in (
            "/operations",
            "/plans/00000000-0000-4000-8000-000000000001",
            "/audit",
            "/evidence",
            "/policies",
            "/integrations",
            "/protect",
        ):
            for headers in ({}, {"RSC": "1"}):
                response = client.get(path, headers=headers, follow_redirects=True)
                # Next embeds a redirect in a streamed RSC response.
                assert (response.url.path == "/login" and response.status_code == 200) or (
                    "NEXT_REDIRECT" in response.text and "/login" in response.text
                ), (path, response.status_code, response.text[:100])
                assert "no-store" in response.headers.get("cache-control", "")
                assert "frame-ancestors 'none'" in response.headers.get(
                    "content-security-policy", ""
                )


def test_proxy_allowlist_and_chunked_body_cap(web_url):
    with httpx.Client(base_url=web_url, timeout=20) as client:
        assert client.get("/api/v1/not-enabled").status_code == 404
        assert client.post("/api/v1/me", json={}).status_code == 404
        assert client.delete("/api/v1/scenarios").status_code == 405
        response = client.post(
            "/api/v1/imports/validate",
            content=(b"x" * 65536 for _ in range(130)),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413, response.text
    # Cancelling an oversized streamed body closes that HTTP connection.
    with httpx.Client(base_url=web_url) as health:
        assert health.get("/api/v1/health/live").status_code == 200


def test_proxy_slow_chunked_body_deadline(web_url):
    url = urlsplit(web_url)
    assert url.scheme == "http"
    started = time.monotonic()
    with socket.create_connection((url.hostname, url.port or 80), timeout=20) as connection:
        connection.sendall(
            (
                f"POST /api/v1/imports/validate HTTP/1.1\r\nHost: {url.netloc}\r\nTransfer-Encoding: chunked\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n1\r\nx\r\n"
            ).encode()
        )
        status = connection.recv(4096).split(b"\r\n", 1)[0]
    elapsed = time.monotonic() - started
    assert b"408" in status, (status, elapsed)
    assert 14 <= elapsed < 19, elapsed
