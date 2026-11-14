"""Destructive test fixtures must not trust a substring in a connection URL."""

import pytest

from tests.backend.test_postgres import isolated_database_urls


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://cargopulse_app@prod.example:55432/cargopulse_backend_test",
        "postgresql+psycopg://cargopulse_app@127.0.0.1:5432/cargopulse_backend_test",
        "postgresql+psycopg://cargopulse_app@127.0.0.1:55432/production?application_name=backend_test",
        "postgresql+psycopg://cargopulse_app@127.0.0.1:55432/production_backend_test",
        "postgresql+psycopg://cargopulse_app@127.0.0.1:55432/cargopulse_backend_test?host=prod.example",
        "postgresql+psycopg://cargopulse@127.0.0.1:55432/cargopulse_backend_test",
        "postgresql+psycopg://cargopulse_app:validation-only@127.0.0.1:55432/cargopulse_backend_test",
        "sqlite:///backend_test.db",
    ],
)
def test_reset_guard_refuses_nonisolated_urls_without_connecting(url):
    with pytest.raises(ValueError, match="isolated backend test"):
        isolated_database_urls(url)


def test_reset_guard_accepts_only_the_documented_loopback_fixture():
    url = "postgresql+psycopg://cargopulse_app@127.0.0.1:55432/cargopulse_backend_test"
    app, owner = isolated_database_urls(url)
    assert app == url
    assert owner == "postgresql+psycopg://cargopulse@127.0.0.1:55432/cargopulse_backend_test"
