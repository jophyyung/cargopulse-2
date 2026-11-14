"""Fail-closed runtime configuration; production secrets come from the environment."""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    environment: str = "production"
    database_url: str = "sqlite:///./cargopulse.db"
    redis_url: str = "redis://localhost:6379/0"
    development_auth: bool = False
    app_base_url: str = "http://localhost:3000"
    object_root: str = ".local/objects"
    object_bucket: str = ""
    object_endpoint: str = ""
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:3000/api/v1/auth/callback"
    oidc_required_acr: str = ""
    session_seconds: int = 3600
    max_body_bytes: int = 8_000_000
    max_pending_jobs: int = 8
    auto_create: bool = False
    otel_endpoint: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            environment=os.getenv("APP_ENV", "production"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./cargopulse.db"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            development_auth=os.getenv("ENABLE_DEVELOPMENT_AUTH", "false").lower() == "true",
            app_base_url=os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/"),
            object_root=os.getenv("OBJECT_STORE_ROOT", ".local/objects"),
            object_bucket=os.getenv("OBJECT_STORE_BUCKET", ""),
            object_endpoint=os.getenv("OBJECT_STORE_ENDPOINT", ""),
            oidc_issuer=os.getenv("OIDC_ISSUER", ""),
            oidc_client_id=os.getenv("OIDC_CLIENT_ID", os.getenv("OIDC_AUDIENCE", "")),
            oidc_client_secret=os.getenv("OIDC_CLIENT_SECRET", ""),
            oidc_redirect_uri=os.getenv(
                "OIDC_REDIRECT_URI", "http://localhost:3000/api/v1/auth/callback"
            ),
            oidc_required_acr=os.getenv("OIDC_REQUIRED_ACR", ""),
            otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/"),
            auto_create=os.getenv("AUTO_CREATE_SCHEMA", "false").lower() == "true",
            max_pending_jobs=int(os.getenv("MAX_PENDING_JOBS_PER_TENANT", "8")),
        )

    def validate(self):
        if not 1 <= self.max_pending_jobs <= 128:
            raise RuntimeError("MAX_PENDING_JOBS_PER_TENANT must be between 1 and 128")
        if self.otel_endpoint:
            endpoint = urlsplit(self.otel_endpoint)
            local_http = (
                self.environment == "development"
                and endpoint.scheme == "http"
                and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            )
            if (
                not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
                or not (endpoint.scheme == "https" or local_http)
            ):
                raise RuntimeError("OTLP requires HTTPS; loopback HTTP is development-only")
        if self.development_auth and self.environment != "development":
            raise RuntimeError("Development authentication requires APP_ENV=development")
        if self.environment != "development":
            if not self.database_url.startswith("postgresql"):
                raise RuntimeError("Production requires PostgreSQL")
            if not all(
                (
                    self.oidc_issuer.startswith("https://"),
                    self.oidc_client_id,
                    self.oidc_required_acr,
                    self.app_base_url.startswith("https://"),
                    self.oidc_redirect_uri.startswith("https://"),
                    self.object_bucket,
                )
            ):
                raise RuntimeError(
                    "Production OIDC, MFA, TLS and private object storage are required"
                )
        for flag in ("ENABLE_EXTERNAL_WRITE", "ENABLE_LIVE_CONNECTORS", "ENABLE_PROTECT"):
            if os.getenv(flag, "false").lower() == "true":
                raise RuntimeError(f"{flag} is unavailable in the synthetic L1 runtime")
