"""Local grants, revocable sessions, OIDC code/PKCE and append-only audit."""

import hashlib
import hmac
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlparse
from uuid import uuid4

import httpx
import jwt
from cargopulse_contracts import Principal, canonical_hash
from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from .db import aware, lock_tenant, scope, utcnow
from .runtime_tables import OIDCFlow
from .tables import AuditRow, Identity, SessionRow

PRIVILEGED_ROLES = frozenset({"controller", "manager", "data_steward", "tenant_admin"})
CSRF_PURPOSE = b"cargopulse.csrf.v1"


class AppError(Exception):
    def __init__(self, status, code, detail, resource="", issues=None):
        self.status, self.code, self.detail = status, code, detail
        self.resource, self.issues = str(resource), issues or []


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def audit(db, tenant, actor, action, resource, outcome, correlation, details=""):
    scope(db, tenant)
    # Serialise the per-tenant hash chain, including the empty initial chain.
    lock_tenant(db, tenant)
    previous = db.scalar(
        select(AuditRow)
        .where(AuditRow.tenant_id == tenant)
        .order_by(AuditRow.occurred_at.desc(), AuditRow.id.desc())
        .limit(1)
    )
    event = dict(
        id=str(uuid4()),
        tenant_id=tenant,
        occurred_at=utcnow(),
        actor=actor,
        action=action[:100],
        resource_id=str(resource)[:100],
        outcome=outcome,
        correlation_id=correlation,
        previous_hash=previous.event_hash if previous else "",
        details=details[:2000],
    )
    event["event_hash"] = canonical_hash({**event, "occurred_at": event["occurred_at"].isoformat()})
    row = AuditRow(**event)
    db.add(row)
    db.flush()
    return row


def cookie_name(settings, kind):
    name = "cp_" + kind
    if settings.environment == "development":
        return name
    return ("__Secure-" if kind == "oidc_binding" else "__Host-") + name


def derived_csrf(secret):
    return hmac.new(secret.encode(), CSRF_PURPOSE, hashlib.sha256).hexdigest()


def csrf_cookie(response, token, settings):
    response.set_cookie(
        cookie_name(settings, "csrf"),
        token,
        secure=settings.environment != "development",
        httponly=False,
        samesite="strict",
        path="/",
        max_age=settings.session_seconds,
    )


def existing_csrf(request, row):
    settings = request.app.state.settings
    # Authentication already verified the server-selected session cookie. A GET
    # may recover its original token, but must never rotate server-side state.
    secret = request.cookies.get(cookie_name(settings, "session"), "").partition(".")[2]
    value = derived_csrf(secret)
    if secrets.compare_digest(digest(value), row.csrf_hash):
        return value
    legacy = request.cookies.get(cookie_name(settings, "csrf"), "")
    if legacy and secrets.compare_digest(digest(legacy), row.csrf_hash):
        return legacy
    raise AppError(401, "UNAUTHENTICATED", "Sign in again to establish a recoverable CSRF token")


def session_cookie(response, token, settings):
    response.set_cookie(
        cookie_name(settings, "session"),
        token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        max_age=settings.session_seconds,
        path="/",
    )


def require_session_assurance(mode, roles, authentication_context_hash, settings):
    if mode == "oidc" and PRIVILEGED_ROLES.intersection(roles):
        expected_context = canonical_hash(
            {"issuer": settings.oidc_issuer, "acr": settings.oidc_required_acr}
        )
        if (
            not settings.oidc_required_acr
            or not authentication_context_hash
            or not secrets.compare_digest(authentication_context_hash, expected_context)
        ):
            raise AppError(
                401, "MFA_REQUIRED", "Sign in again with the configured privileged MFA context"
            )


def create_session(
    db, identity, mode, response, settings, previous_token="", *, authentication_context_hash=None
):
    # Share the existing tenant transaction lock with account disable triggers.
    # A plain SELECT preserves the read-only directory grants of the app role.
    scope(db, identity.tenant_id)
    lock_tenant(db, identity.tenant_id)
    identity = db.scalar(
        select(Identity)
        .where(
            Identity.id == identity.id,
            Identity.tenant_id == identity.tenant_id,
            Identity.enabled.is_(True),
        )
        .execution_options(populate_existing=True)
    )
    if not identity:
        raise AppError(401, "UNAUTHENTICATED", "Identity is no longer enabled")
    require_session_assurance(mode, identity.roles, authentication_context_hash, settings)
    # Rotate the presenting browser session on every successful authentication.
    # Parse tenant context independently so a permitted account switch also revokes
    # the old cookie without granting cross-tenant directory access.
    try:
        from uuid import UUID

        previous_tenant, previous_secret = previous_token.split(".", 1)
        previous_tenant = str(UUID(previous_tenant))
    except (ValueError, AttributeError):
        pass
    else:
        scope(db, previous_tenant)
        previous = db.scalar(
            select(SessionRow).where(
                SessionRow.tenant_id == previous_tenant,
                SessionRow.token_hash == digest(previous_secret),
            )
        )
        if previous:
            db.delete(previous)
            db.flush()
    scope(db, identity.tenant_id)
    secret = secrets.token_urlsafe(40)
    csrf = derived_csrf(secret)
    db.add(
        SessionRow(
            tenant_id=identity.tenant_id,
            identity_id=identity.id,
            token_hash=digest(secret),
            csrf_hash=digest(csrf),
            expires_at=utcnow() + timedelta(seconds=settings.session_seconds),
            auth_mode=mode,
            authentication_context_hash=authentication_context_hash,
        )
    )
    session_cookie(response, identity.tenant_id + "." + secret, settings)
    csrf_cookie(response, csrf, settings)
    return Principal(
        subject=identity.subject, tenant_id=identity.tenant_id, roles=identity.roles, auth_mode=mode
    )


def authenticate(request: Request, db):
    settings = request.app.state.settings
    token = request.cookies.get(cookie_name(settings, "session"), "")
    try:
        tenant, secret = token.split(".", 1)
        from uuid import UUID

        tenant = str(UUID(tenant))
    except (ValueError, AttributeError):
        raise AppError(401, "UNAUTHENTICATED", "A valid server session is required") from None
    scope(db, tenant)
    row = db.scalar(
        select(SessionRow).where(
            SessionRow.tenant_id == tenant, SessionRow.token_hash == digest(secret)
        )
    )
    if not row or aware(row.expires_at) <= utcnow():
        raise AppError(401, "UNAUTHENTICATED", "Session is expired or revoked")
    if row.auth_mode == "development" and (
        settings.environment != "development" or not settings.development_auth
    ):
        raise AppError(401, "UNAUTHENTICATED", "Development session adapter is disabled")
    identity = db.scalar(
        select(Identity).where(
            Identity.tenant_id == tenant, Identity.id == row.identity_id, Identity.enabled.is_(True)
        )
    )
    if not identity:
        raise AppError(401, "UNAUTHENTICATED", "Identity is no longer enabled")
    # Live local grants may change after login. Privilege requires the assurance
    # verified at that login to satisfy the current issuer and MFA policy.
    require_session_assurance(
        row.auth_mode, identity.roles, row.authentication_context_hash, settings
    )
    principal = Principal(
        subject=identity.subject, tenant_id=tenant, roles=identity.roles, auth_mode=row.auth_mode
    )
    request.state.principal, request.state.session = principal, row
    return principal


def csrf_guard(request, row):
    settings = request.app.state.settings
    origin = request.headers.get("origin", "")
    token = request.headers.get("x-csrf-token", "")
    if origin != settings.app_base_url:
        raise AppError(
            403, "ORIGIN_REJECTED", "Mutation Origin must match the configured application"
        )
    if not token or not secrets.compare_digest(digest(token), row.csrf_hash):
        raise AppError(403, "CSRF_REJECTED", "A current CSRF token is required")


def require(principal, *roles):
    if not set(principal.roles).intersection(roles):
        raise AppError(403, "FORBIDDEN", "This locally provisioned role does not permit the action")


def oidc_metadata(settings):
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        result = client.get(settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration")
        result.raise_for_status()
        metadata = result.json()
    if metadata.get("issuer") != settings.oidc_issuer:
        raise AppError(503, "OIDC_UNAVAILABLE", "OIDC discovery issuer mismatch")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if urlparse(metadata.get(key, "")).scheme != "https":
            raise AppError(503, "OIDC_UNAVAILABLE", "OIDC endpoints require HTTPS")
    return metadata


def oidc_login(request, db):
    settings = request.app.state.settings
    if not settings.oidc_issuer or not settings.oidc_client_id:
        raise AppError(503, "OIDC_UNAVAILABLE", "OIDC provider is not configured")
    metadata = oidc_metadata(settings)
    state, nonce, verifier, binding = (secrets.token_urlsafe(40) for _ in range(4))
    import base64

    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    db.add(
        OIDCFlow(
            state_hash=digest(state),
            nonce=nonce,
            verifier=verifier,
            browser_hash=digest(binding),
            expires_at=utcnow() + timedelta(minutes=5),
        )
    )
    query = dict(
        response_type="code",
        scope="openid",
        client_id=settings.oidc_client_id,
        redirect_uri=settings.oidc_redirect_uri,
        state=state,
        nonce=nonce,
        code_challenge=challenge,
        code_challenge_method="S256",
    )
    if settings.oidc_required_acr:
        query["acr_values"] = settings.oidc_required_acr
    response = RedirectResponse(metadata["authorization_endpoint"] + "?" + urlencode(query), 302)
    response.set_cookie(
        cookie_name(settings, "oidc_binding"),
        binding,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=300,
        path="/api/v1/auth/callback",
    )
    return response


def oidc_callback(request, db, code, state):
    settings = request.app.state.settings
    flow = db.scalar(select(OIDCFlow).where(OIDCFlow.state_hash == digest(state)).with_for_update())
    if (
        not flow
        or aware(flow.expires_at) <= utcnow()
        or not secrets.compare_digest(
            flow.browser_hash, digest(request.cookies.get(cookie_name(settings, "oidc_binding"), ""))
        )
    ):
        raise AppError(401, "OIDC_STATE_INVALID", "OIDC state or browser binding is invalid")
    verifier, nonce = flow.verifier, flow.nonce
    db.delete(flow)
    db.commit()  # Consume state even when token exchange or signature verification fails.
    metadata = oidc_metadata(settings)
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            result = client.post(
                metadata["token_endpoint"],
                data=dict(
                    grant_type="authorization_code",
                    code=code,
                    redirect_uri=settings.oidc_redirect_uri,
                    client_id=settings.oidc_client_id,
                    code_verifier=verifier,
                ),
                auth=(settings.oidc_client_id, settings.oidc_client_secret)
                if settings.oidc_client_secret
                else None,
            )
            result.raise_for_status()
            token = result.json()["id_token"]
        # PyJWKClient refreshes its cache when an unknown key id is encountered.
        key = jwt.PyJWKClient(metadata["jwks_uri"], timeout=10).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer,
            options={"require": ["iss", "aud", "sub", "exp", "iat", "nonce"]},
        )
        if not secrets.compare_digest(claims["nonce"], nonce):
            raise ValueError("nonce")
        if ("azp" in claims and claims["azp"] != settings.oidc_client_id) or (
            isinstance(claims["aud"], list)
            and len(claims["aud"]) > 1
            and claims.get("azp") != settings.oidc_client_id
        ):
            raise ValueError("azp")
        # The deployment selects the tenant; no role or tenant comes from token claims.
        import os

        tenant = os.environ.get("OIDC_TENANT_ID", "")
        scope(db, tenant)
        identity = db.scalar(
            select(Identity).where(
                Identity.tenant_id == tenant,
                Identity.issuer == settings.oidc_issuer,
                Identity.subject == claims["sub"],
                Identity.enabled.is_(True),
            )
        )
        if not identity:
            raise AppError(
                403, "IDENTITY_NOT_PROVISIONED", "No approved local identity grant exists"
            )
        if PRIVILEGED_ROLES.intersection(identity.roles) and (
            not settings.oidc_required_acr or claims.get("acr") != settings.oidc_required_acr
        ):
            raise AppError(403, "MFA_REQUIRED", "The configured privileged MFA context is required")
        # Persist only a digest of validated assurance, never the JWT or raw claims.
        authentication_context_hash = canonical_hash(
            {
                "issuer": claims["iss"],
                "acr": claims["acr"] if isinstance(claims.get("acr"), str) else None,
            }
        )
    except AppError:
        raise
    except (jwt.PyJWTError, httpx.HTTPError, KeyError, ValueError, TypeError):
        raise AppError(401, "OIDC_TOKEN_INVALID", "OIDC token validation failed") from None
    response = RedirectResponse(settings.app_base_url + "/", 302)
    principal = create_session(
        db,
        identity,
        "oidc",
        response,
        settings,
        request.cookies.get(cookie_name(settings, "session"), ""),
        authentication_context_hash=authentication_context_hash,
    )
    audit(
        db,
        identity.tenant_id,
        principal.subject,
        "auth.login",
        identity.id,
        "SUCCESS",
        request.state.correlation_id,
    )
    response.delete_cookie(
        cookie_name(settings, "oidc_binding"),
        path="/api/v1/auth/callback",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response
