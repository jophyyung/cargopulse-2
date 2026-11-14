"""The client receives a bounded server TTL without extending its session."""

from datetime import timedelta

from cargopulse_api.db import aware, utcnow
from cargopulse_api.tables import SessionRow
from sqlalchemy import select

from .conftest import login


def test_csrf_read_reports_existing_expiry_without_renewal(client):
    login(client)
    expires = utcnow() + timedelta(seconds=60)
    with client.app.state.factory.begin() as db:
        row = db.scalar(select(SessionRow))
        row.expires_at = expires
        token_hash = row.csrf_hash
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    assert 0 < int(response.headers["X-Session-Expires-In"]) <= 60
    with client.app.state.factory() as db:
        row = db.scalar(select(SessionRow))
        assert aware(row.expires_at) == expires
        assert row.csrf_hash == token_hash


def test_expired_session_cannot_receive_fresh_expiry_metadata(client):
    login(client)
    with client.app.state.factory.begin() as db:
        db.scalar(select(SessionRow)).expires_at = utcnow() - timedelta(seconds=1)
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 401
    assert "X-Session-Expires-In" not in response.headers
