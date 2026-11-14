# Recover integration milestone

Status: verified local synthetic vertical slice; L1 release NOT approved.

The lead integrated the backend, optimizer and Next.js worktrees and independently
reran actual tests against PostgreSQL 18.6 and Redis 8.2.3, then the standalone Node
production build against the real API and separately running durable worker.

Commands/results on 2026-11-10:

- `BACKEND_TEST_DATABASE_URL=.../cargopulse_backend_test python -m pytest -q --tb=short`:
  **101 passed**, 33.56s; one upstream Starlette/httpx test-client deprecation warning.
- `npm run typecheck` and `npm run build`: exit 0; Next.js 16.4.6 standalone build.
- `CARGOPULSE_E2E_URL=http://localhost:3000 CARGOPULSE_BROWSER_CHANNEL=chrome npm run e2e`:
  **2 passed**, 25.1s total; the authenticated 140-ULD flow took 23.0s.
- Ruff correctness and security-rule checks: exit 0. The benchmark CLI's fixed
  developer-only `git rev-parse HEAD` is a documented S607 exception; the safety
  outcome string `PASS` is explicitly not a hard-coded credential.
- `pip-audit`: exit 0, no known vulnerabilities reported at scan time. This is a
  package-database result, not a penetration test or a container scan.

The browser flow performed login, fixture load, JSON validation, immutable import
commit, scenario creation, candidate and urgency inspection, asynchronous solve,
durable job polling, plan/validator review, exact-hash/action confirmation, in-app
approval receipt and audit navigation. It observed no page errors or CSP violations.
The second browser test checked anonymous redirect and Traditional Chinese switching.

Integration defects found and repaired:

- Initial development login incorrectly requested session-bound CSRF before a
  session existed. Only that explicitly development-only Origin-checked login is
  exempted in the client; authenticated commands retain server CSRF enforcement.
  Client commands reuse the current session token instead of rotating it on every
  command and causing parallel-request races.
- The Next proxy originally buffered an unbounded chunked body. It now checks
  chunks while reading, cancels above 8 MiB and enforces a 15-second body deadline.
- Minimum database grants exposed tenant-directory `FOR UPDATE` requirements.
  API/audit/worker serialization now uses per-tenant transaction advisory locks;
  a real PostgreSQL regression verifies commands and worker processing with
  INSERT/UPDATE/DELETE revoked on tenant/identity directories.
- One intermediate lead edit omitted an import: 13 failures/87 passes were observed.
  The missing import was restored, then the full suite passed. No failed run is
  presented as passing evidence.
- Browser selectors originally included exact labels while visible buttons had
  decorative arrows/navigation numbers. Those selectors were corrected after
  inspecting the actual accessible UI; no application outcome was mocked.
- Urgency uses a step curve and explains that expired evidence can close options;
  proposed departures within 48h are explicitly distinct from approved protection
  and physical arrival. The escalation policy now affects the secondary objective.

Scope limits: this is a local standalone build with explicit development identities.
It does not verify a real enterprise IdP, hosted TLS, real S3 encryption/access,
public domain, availability/SLA, exhaustive WCAG conformance or user acceptance.
The 90 benchmark runs are exploratory synthetic instances, not the unpublished
competition simulator; their actual time-limit statuses and sparse samples remain
in the raw evidence. Docker/restore/independent release review are separate gates.
