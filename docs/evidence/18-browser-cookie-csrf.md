# Browser Cookie Isolation and Read-Only CSRF Recovery

## Scope and behavior

This bounded phase builds on the core session-assurance patch whose targeted
suite passed 61 tests. It changes only the API security helpers and authentication
routes, adds `test_cookie_csrf_security.py`, and records this evidence. The core
`0005` migration and table definitions remain byte-identical to the core61
snapshot. No frontend, database migration, grants or deployment was changed.

Cookie names now come from one server-side helper:

- Development keeps `cp_session`, `cp_csrf` and `cp_oidc_binding`.
- Every other environment uses `__Host-cp_session` and `__Host-cp_csrf`, both
  `Secure`, `Path=/`, with no `Domain` attribute. The session is `HttpOnly` and
  `SameSite=Lax`; CSRF remains readable and `SameSite=Strict`.
- OIDC binding uses `__Secure-cp_oidc_binding` outside development, because its
  existing path is `/api/v1/auth/callback`. It is `Secure`, `HttpOnly`,
  `SameSite=Lax`, without `Domain`. The development binding also retains its
  existing `Secure` flag and callback path.

Authentication, prior-cookie rotation, OIDC binding validation and all relevant
cookie issuance/deletion use those selected names. Production does not fall back
to unprefixed session or binding cookies. Deletions retain the corresponding
path and Secure/HttpOnly/SameSite flags. Existing unprefixed production sessions
must sign in again after a coordinated deployment.

## CSRF recovery

New sessions derive their CSRF value as a hexadecimal
`HMAC-SHA256(key=raw_session_secret, message=b"cargopulse.csrf.v1")`. The existing
SHA-256 digest of that value is stored in `sessions.csrf_hash`; the raw session
secret continues to be stored only in the browser's HttpOnly session cookie,
with its digest in the database.

Authenticated `GET /api/v1/auth/csrf` reads the server-selected session cookie,
re-derives the original token and compares its digest with the stored hash.
On success it returns the existing `CsrfToken` DTO and sets the corresponding
CSRF cookie. Repeated or simultaneous reads return the same value, do not
rewrite `csrf_hash`, and do not invalidate another tab's token. Removing a new
session's CSRF cookie does not prevent recovery from the authenticated session.

For an older random CSRF value, the endpoint may reuse only a presented CSRF
cookie whose digest actually matches the session's stored hash. A missing or
incorrect legacy cookie returns `401 UNAUTHENTICATED`, requiring fresh sign-in.
It never rotates server-side CSRF state during GET. Existing Origin and CSRF
header checks for mutations are unchanged. Normal security denial auditing
remains active; “read-only” here refers to session/CSRF business state, not to
suppression of security logs or denial audit records.

Consumers must fetch `/auth/csrf` and use the returned body field `csrf` when
making an authenticated mutation. A synchronized frontend/backend deployment is
required; this worktree did not implement or verify the frontend consumer change.

## Verification

The new test file was run against the unchanged core61 source before this phase.
Result: **11 failed, 2 passed**, recorded in
`.local/browser-cookie-csrf/baseline-expected-secure.txt`. Prefix-dependent tests
failed because the required cookies were absent; CSRF cases demonstrated token
rotation or failure to preserve/recover the expected existing value. This is an
expected failing baseline, not a security pass.

After implementation:

```sh
/Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest \
  tests/backend/test_cookie_csrf_security.py \
  tests/backend/test_oidc_session_assurance.py tests/backend/test_oidc.py \
  tests/backend/test_api.py -q
```

Result: **74 passed**, including all prior 61 cases and **13 new cases**, with
one existing Starlette/httpx deprecation warning. Coverage includes:

- Production-mode issuance, prefix/path/domain/Secure/HttpOnly flags, callback
  binding validation, successful prefixed OIDC callback and session rotation.
- Secure logout and callback-binding deletion flags, no unprefixed production
  fallback, and development cookie exceptions.
- Stable repeated CSRF reads in development and production mode, 12 simultaneous
  reads without database hash changes or token invalidation, and a subsequent
  authenticated policy draft write using the original token.
- Recovery after deleting the CSRF cookie, legacy matching-token reuse, legacy
  missing/incorrect-token rejection, and unauthenticated rejection.

Ruff checks for the changed source/test files and `git diff --check` pass.
Raw outputs are ignored local artifacts:

- `.local/browser-cookie-csrf/targeted-tests.txt`
- `.local/browser-cookie-csrf/ruff.txt`
- `.local/browser-cookie-csrf/core61/manifest.json`

## Limits and integration handoff

All tests use isolated in-memory SQLite. Production-mode ASGI tests initialize a
development SQLite fixture and then select production request settings; they
exercise the actual application cookie branches and actual RSA-signed JWT
validation with recorded provider transport. They do not start production
infrastructure or establish real TLS, browser cookie-prefix enforcement, a live
enterprise IdP, real MFA policy, PostgreSQL locking/RLS, or end-to-end frontend
behavior. The integration lead must verify those relevant paths separately.

No root service data, native PostgreSQL fixture, remote deployment, Git commit or
push was changed. The incremental patch is relative to the saved core61 bytes;
it excludes the migration/table definitions and earlier session-assurance changes.
