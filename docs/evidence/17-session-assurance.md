# OIDC Session Assurance Across Local Role Changes

## Defect and correction

At baseline `1b003eb22427c784fe1b59fff6bfe650be120909`, the OIDC callback
checked MFA only against the local roles present at login. Subsequent requests
loaded current local roles without retaining the verified authentication context.
A password-only `load_analyst` session could therefore acquire manager policy
draft access after a local role promotion, without another OIDC exchange.

The session now persists a nullable `String(64)`
`authentication_context_hash`. Only the successful OIDC callback supplies this
value, after the existing signature, issuer, audience, expiry, nonce and authorized
party checks. The value is `canonical_hash({"issuer": verified_iss, "acr": acr})`,
where `acr` retains the original value only when it is a JSON string; missing,
null or any other JSON type is recorded as `None`. String coercion is prohibited
because malformed values such as integer `2` must not satisfy a later policy
requiring the string `"2"`. The application stores neither
the ID token nor its raw claims in this field.

The callback and every authenticated request share the fixed privileged role set:
`controller`, `manager`, `data_steward`, `tenant_admin`. For an OIDC session with
any current local privileged role, authentication requires a configured required
ACR and a stored context hash matching the active issuer and required ACR.
Otherwise the request returns `401 MFA_REQUIRED` and requires fresh sign-in.
Token role and tenant claims remain ignored. A previously verified strong session
already satisfying the active policy may use newly granted local privileges.
Development sessions retain the existing environment and adapter restrictions.

Disabling an enabled identity now transactionally deletes every session for that
identity and tenant. Re-enabling the account cannot revive those cookies, even
when no HTTP request occurred while it was disabled. A database trigger covers
raw SQL and ORM updates, while the deletion rolls back if the disable transaction
rolls back. It does not delete another identity's or tenant's sessions.
`create_session` also acquires the existing tenant transaction advisory lock and
re-reads the enabled identity before inserting a session. The PostgreSQL disable
trigger takes that same lock before deleting sessions. Session creation uses a
plain directory SELECT to preserve the application's read-only identity grants;
it also checks the newly read roles against the trusted OIDC context before
creating a cookie. It does not trust a stale ORM identity or a callback role check
performed before a concurrent local promotion.

## Migration and rollout

Alembic `0005` adds the nullable column and disable trigger without backfilling authentication
evidence. Existing privileged OIDC sessions therefore require fresh sign-in.
Readiness explicitly selects the new column, so a pre-0005 database is not ready.
Run the migration before directing traffic to the new application version.

The PostgreSQL trigger function is `SECURITY INVOKER`, explicitly addresses
`public.sessions`, and fixes `search_path` to `pg_catalog`. Its trigger addresses
`public.identities`; the deployment therefore uses the existing public-schema
contract. The updater must have the session DELETE privilege and matching tenant
visibility (or the existing controlled owner/admin permissions). Insufficient
privilege fails the entire disable transaction rather than silently retaining
sessions. No elevated definer privilege or new database grant is introduced.
Development/test metadata creation installs equivalent PostgreSQL/SQLite DDL;
the migration embeds its own DDL and does not import mutable ORM definitions.
The function retains PostgreSQL's default `VOLATILE` behavior. It acquires
`pg_advisory_xact_lock(hashtextextended(OLD.tenant_id, 0))` using explicitly
qualified `pg_catalog` functions, matching the existing tenant lock contract.

The migration rejects downgrade with an explicit `RuntimeError`: removing stored
assurance and rolling back to the vulnerable authentication behavior is unsafe.
Use a separately restored database only with a reviewed application rollback and
fresh authentication; this change does not authorize a security downgrade.

## Verification performed in this worktree

All commands ran from the isolated `mfa-session` worktree using the repository
root virtual environment. The tests use in-memory SQLite, actual generated RSA
keys and signed JWTs, and the existing recorded OIDC/JWKS provider fixture.

Baseline command, before changing application code:

```sh
/Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest \
  tests/backend/test_oidc_session_assurance.py::test_weak_session_role_promotion_requires_strong_reauthentication -q
```

Result: **4 failed**, as expected for the uncorrected code. The manager case
returned policy draft `201` where the regression requires `401`; the other three
roles returned route-level RBAC `403` without the required authentication denial.
This is evidence of a reproduced defect, not a passing security check.

Post-correction command:

```sh
/Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest \
  tests/backend/test_oidc_session_assurance.py tests/backend/test_oidc.py \
  tests/backend/test_api.py -q
```

Initial correction result: **49 passed**, with one existing Starlette/httpx deprecation warning.
The initial new file contributed 13 cases covering all privileged role promotions,
strong reauthentication and cookie rotation, already-strong promotion, legacy
NULL evidence, changed issuer/ACR and removed ACR policy, missing/null ACR,
ignored token grants, readiness, actual SQLite migration and guarded downgrade.
After strong reauthentication, the manager policy write succeeds; other roles
retain their existing route permissions.

```sh
/Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m ruff check \
  services/api/cargopulse_api/security.py services/api/cargopulse_api/tables.py \
  services/api/cargopulse_api/main.py \
  services/api/alembic/versions/0005_session_assurance.py \
  tests/backend/test_oidc_session_assurance.py
```

Result: **All checks passed**.

Ignored local raw evidence:

- `.local/session-assurance/baseline-expected-secure.txt`
- `.local/session-assurance/targeted-tests.txt`
- `.local/session-assurance/ruff.txt`

## Follow-up verification: strict ACR types and account disable revocation

Before these follow-up corrections, the following expected-secure regression
command produced **10 failed, 13 deselected**:

```sh
/Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest \
  tests/backend/test_oidc_session_assurance.py -k 'nonstring_acr or disable' -q
```

The five actual RSA-signed malformed ACR cases (`2`, `2.5`, `true`, an array and
an object) incorrectly passed privilege assurance after a local role/configuration
change. The other failures showed session revival following raw SQL
disable/re-enable, missing deletion of all target identity sessions, missing
transactional deletion before rollback, and session creation from a stale enabled
ORM identity. These failures were captured before changing the relevant code.

After the follow-up corrections, the same three-file targeted command shown
above produces **59 passed**, with the same existing deprecation warning. The
assurance test file now contributes **23 cases**. The added cases prove raw SQL
disable/re-enable cannot revive a cookie with or without an intervening request,
all target identity sessions are removed while other identities/tenants survive,
deletion rolls back atomically, stale ORM instances cannot create sessions, and
non-string ACR cannot collide with configured strings. The SQLite migration test
now removes the adapter trigger before executing `0005`, then verifies the
migration-installed trigger deletes sessions. Ruff and `git diff --check` pass.

Additional ignored raw evidence:

- `.local/session-assurance/followup-baseline-expected-secure.txt`
- `.local/session-assurance/followup-targeted-tests.txt`
- `.local/session-assurance/followup-ruff.txt`

Pending PostgreSQL integration must exercise an actual `0004` to `0005` upgrade,
retained NULL legacy assurance, schema readiness, invoker privilege/RLS behavior,
raw SQL disabled-account revocation and isolation, rollback atomicity, and both
orderings of concurrent session creation/account disable. SQLite passing results
do not prove PostgreSQL locking or concurrency behavior.

## Follow-up verification: preserve least privilege and recheck fresh roles

The integration lead's real PostgreSQL probe found that the production app role
does not have identity UPDATE permission and receives SQLSTATE `42501` for
`SELECT identities ... FOR UPDATE`. The earlier row-lock approach was therefore
replaced with the existing tenant advisory lock and an ordinary enabled-identity
SELECT. No identity UPDATE grant is added. The disable trigger acquires the same
lock before its DELETE; actual concurrent PostgreSQL transaction ordering remains
an integration-lead verification requirement.

A shared assurance helper is now called both by `authenticate` and by
`create_session` after its fresh identity read. A new two-case regression changes
local roles through raw SQL after an ORM identity was loaded: weak assurance must
be denied before session creation, while already-strong assurance succeeds with
the refreshed roles. Before this helper correction, the new cases produced
**1 failed, 1 passed** (weak assurance incorrectly created a session).

Final targeted verification with the same three-file command above produces
**61 passed**, with the same existing deprecation warning. The assurance file now
contains **25 cases**, including the prior stale disabled-identity regression.
Ruff and whitespace checks pass. Raw evidence is retained in:

- `.local/session-assurance/privilege-recheck-baseline.txt`
- `.local/session-assurance/advisory-lock-targeted-tests.txt`
- `.local/session-assurance/advisory-lock-ruff.txt`

The lead must still verify production-role non-owner login without identity
UPDATE permission and both concurrency orderings: session creation before
disable, and disable before session creation. Passing SQLite tests do not establish
PostgreSQL advisory-lock, MVCC or RLS correctness.

## Limits and pending integration checks

This worktree did not exercise a live enterprise IdP, external MFA behavior,
PostgreSQL migration/RLS, browser reauthentication UX, deployment, or a full
repository test run. The integration lead must verify those relevant local
integration paths separately. No source database, root service data, remote
deployment, Git commit or push was changed by this worktree task.

The new comparison proves compatibility with the configured exact ACR value; it
does not independently establish an enterprise provider's real-world MFA
strength, freshness, device policy, session revocation or authentication policy.
Issuer/ACR changes intentionally invalidate privileged use of older sessions.
