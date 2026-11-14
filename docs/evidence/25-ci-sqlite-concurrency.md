# Hosted CI repair: concurrent CSRF test fixture

Date: 2026-11-14. Scope: test infrastructure only; application authentication,
CSRF handling, database configuration and release gates are unchanged.

## Observed failure

Both hosted runs of source `08733f67d49394879f4438644c7ecd29a773f617`
failed `test_concurrent_csrf_reads_do_not_invalidate_an_existing_token`:

- [main run 43552068735](https://github.com/alpiex1336-code/CargoPulse/actions/runs/43552068735)
- [teammate branch run 43562137464](https://github.com/alpiex1336-code/CargoPulse/actions/runs/43562137464)

Each reported 262 passed and one failed Python test. Concurrent CSRF reads
unexpectedly returned 401 with `Identity is no longer enabled`. Browser tests
and subsequent audit/image-scan steps were not reached.

The original test also failed locally on the thirteenth independent invocation,
with a 401 `Session is expired or revoked`. Earlier successful invocations did
not establish stability.

## Cause and change

The backend test fixture used SQLite `:memory:` with the application's
single-connection `StaticPool`. Concurrent requests therefore used independent
ORM sessions over one physical connection and shared transaction state.
SQLAlchemy explicitly documents that this configuration requires serialized
access and does not support concurrent transactions:
[SQLite connection pooling documentation](https://docs.sqlalchemy.org/en/21/dialects/sqlite.html#using-a-memory-database-in-multiple-threads).

The fixture now uses a per-test SQLite file under pytest's private temporary
directory. SQLAlchemy can supply independent connections for overlapping
requests. Tests retain real concurrency and all original assertions: identical
CSRF values, unchanged stored hash, and a successful subsequent authorized write.
There is no retry, skip, authentication bypass or application serialization fix.
File-backed SQLite still does not establish PostgreSQL/RLS concurrency behavior.

## Executed local evidence

- Original regression after the change: 20 separate pytest invocations, all
  passed (240 concurrent CSRF reads and 20 subsequent authorized writes).
- Cookie/CSRF and OIDC session assurance modules: 38 passed.
- Both workflow Ruff commands, tracked secret-pattern check, TypeScript checking
  and `git diff --check`: passed.
- A broader Python invocation reported 242 passed, 19 skipped and two setup
  errors because the isolated PostgreSQL server on loopback port 55432 was not
  running. This is **not** a passing full-suite result. No test was weakened to
  hide that environment limitation.

The pinned local Python is 3.12.16, SQLAlchemy 2.1.8 and SQLite 3.53.1.
One existing Starlette/httpx deprecation warning remains; it is unrelated to
this failure and no dependency update is included.

## Hosted verification

The repair must pass the unchanged hosted workflow on the pushed commit. That
workflow provisions real isolated PostgreSQL/Redis, builds the actual containers,
runs the full Python/browser suites and retains audit, scan and SBOM artifacts.
Consult the run matching the repair commit in
[Verify Recover](https://github.com/alpiex1336-code/CargoPulse/actions/workflows/verify.yml).
Local fixture checks alone must not be reported as a hosted pass. A green run
also does not establish enterprise identity, deployment or public L1 acceptance.

Only the repair and this evidence record are intended for the repair commit.
Unrelated local handoff/integration guidance remains outside this change. No PR
creation, branch merge or history rewrite is part of this repair.
