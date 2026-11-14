# CargoPulse verification report

## Current executed checks

On 2026-11-12 (Hong Kong), Python 3.12.16 ran the full integrated suite against
three isolated PostgreSQL 18.6 databases, actual Redis and the standalone candidate
web boundary: **263 passed, zero failed/skipped/xfail, 87.16s**. One existing
Starlette/httpx TestClient deprecation warning remains. Raw output and JUnit:
`docs/evidence/security-final/pytest.txt` and `pytest.xml`.

On the same date, the lead reran the full suite from clean commit
`97cc22cfe7f3cd3b2e560b3c02555b0dbce3d2f2`: **263 passed, zero failures/errors/
skips, 91.52s**, one upstream warning. Actual imports came from the clean
worktree; it remained clean before/after. Its31 runtime Python sources,45 web
inputs and packaging matched the deployed images. The existing locked Python
environment and isolated PostgreSQL/Redis were reused, with the live main web
boundary at localhost:3000. Raw output/JUnit/binding are in
`docs/evidence/security-final/clean-checkout`; no new-host install or additional
Chrome execution is inferred.

The suite contains 135 backend, 11 contract, 17 observability, 34 optimizer,
9 final numerical review, 16 numerical QA, 21 release QA and 20 validation tests.
The 83 added backend cases comprise 25 OIDC-assurance, 13 cookie/CSRF, 5 actual
PostgreSQL session-security, 14 input/privacy, 2 expiry-metadata and 24 SDK XML cases.
SQLite/ASGI tests are not represented as PostgreSQL concurrency or real IdP tests.

Final immutable local API/web images passed **14 Chrome/Playwright tests** on
http://localhost:3000; CLI reported 1.0m. The original five use real service state:
140-ULD intake/commit/scenario/solve/independent-PASS/review/decision/audit/PDF,
anonymous/Chinese guards, four viewport widths, keyboard/focus and public notices.
Actual backend/worker/database traffic supplies their results, without mocked API
answers. Axe checks on tested states found zero violations; this is automated
coverage, not a complete accessibility assessment. Native macOS select popup
keyboard behavior remains the previously documented automation limitation.

Eight session cases exercise real login/logout/401, cross-tab and offline behavior,
with explicit injected logout transport failure, four-second TTL metadata,
persisted-page events and recorded provider navigation. DOM nodes detach, old
sessions stay hidden after reconnect/reload, JSON CSRF ignores a wrong cookie, and
a failed logout never says revoked. The TTL probe leaves the real server session
valid; it is not a full-duration expiry test. Event injection is not native BFCache
admission, and a callback-equivalent fresh development session is not live OIDC.
The remaining real-browser case verifies no-referrer and actual CSP base blocking.
Raw output: `docs/evidence/security-final/browser-main.txt`.

The final downloaded two-page PDF was rendered and both pages visually inspected:
synthetic/no-write labels, four metrics/denominators/lineage and complete hashes
remain readable without clipping or metric-block splitting. PDF is untagged;
screen-reader accessibility is not established. Actual screenshots/download are
in `apps/web/evidence`; renderer metadata is in `security-final/pdf-info.txt`.

## Authentication, parser and database evidence

Independent base reproductions CP-ASVS-001/002 were actual defects, not passing
security controls. Corrected source retains only verified issuer/ACR assurance and
rechecks it after role changes. Missing/weak/stale legacy context fails privileged
requests. Raw SQL disable transactionally deletes sessions, preserving other
identities/tenants and rollback semantics. Actual PostgreSQL locks demonstrate
both creation/disable orderings; restricted operators fail/roll back without
session DELETE rights. The app retains read-only directory privileges. Schema
0004-to-0005 upgrade, NULL legacy values and guarded downgrade are exercised.

Production prefix/path/domain/secure cookie transitions and read-only stable CSRF
are tested. New metadata never renews expiry. Filename/content checks and callback
log/span/referrer canaries are separate executable evidence. Recorded S3 HTTP
responses run through actual pinned SDK clients, including the earlier embedded-
error parse, DTD/entity/encoding/malformed/oversize cases and unaffected raw blobs.
They establish neither real S3/IAM/TLS/SSE nor every third-party debug-log path.
Reports 17, 18, 19 and 21 retain implementation and scope details.

All existing nonowner FORCE-RLS/immutable-history, known-ID BOLA, role, exact hash,
lease/idempotency races, policy provenance, physical/metric mutations and real
separate-process OTLP receiver tests remain enabled. No skipped integration test
is counted as a pass. The original contracts/types regenerated without drift.

## Runtime, image and recovery evidence

All four exact final images passed full Trivy scans and separate HIGH/CRITICAL
exit-code gates, retaining detected OS packages, with no ignore/unfixed waiver.
Raw findings, scanner DB metadata and image SBOMs are retained. Remaining findings
are documented in SECURITY_REVIEW.md; package audits do not clear OS findings.
Fresh pip-audit/npm audit report no known advisories within their package scope.

The image/package advisory checks were refreshed on2026-11-13 against the same
images: all four HIGH/CRITICAL gates and pip/npm audits passed again. This
evidence-only refresh did not modify application source or rerun/re-date the
263-case or14-case executions; see `security-final/revalidation-20261113.json`.

Actual minimal API/web builds, TypeScript, Ruff standard/selected security checks,
contract generation and local actionlint pass. The bounded DTD-rejecting XMLParser
has one explained S314 line annotation; no global parser rule is disabled. CI now
builds the same hardened PostgreSQL fixture on loopback rather than the previous
Debian image. Hosted CI has not run. Production Compose parses with reserved
placeholders only; no production service is started.

The local glibc-to-musl logical migration, pre-write rollback and post-write fault
preservation are separate from the final schema0005 promotion. All main table/
object digests were compared before new traffic. Final restart durability passed;
new isolated restore matched all 15 tables and 11 objects, then an ASGI app using
only restored objects/DB read 11 scenarios and blocked 23 stale plans. No cloud
PITR, intended-region RPO/RTO or host-reboot claim follows. See RESTORE_DRILL.md.
Independent final offline artifact review checks every manifest hash, static ELF
closure, metadata/license, NSS/CA/timezone and nonroot file access; it never starts
a container and is not runtime E2E. See evidence22.

## Failed checks retained and corrected

The first integrated run had **259 passes, 4 failures**: the historical migration
test expected current ORM assurance in frozen0001 and still expected head0004;
its early failure left two later observability cases without oidc_flows. The test
now explicitly distinguishes later columns, checks head0005/nullable assurance and
still validates the entire frozen schema. The corrected full run passes all263.

The first candidate browser run had **13 passes, 1 failure**: Chrome represented
an omitted referrer as an empty string rather than undefined. The assertion now
requires no referrer content and the actual header/CSP case passes; the full final
main run then passes all14. Initial default-browser launch, native build/dependency
copy, minimal-runtime/CA and SDK guard-ordering failures remain separately labelled.
An initial restored-ASGI probe called unsupported GET/scenarios and received405;
it now uses the documented events feed and passed on both tenants. A contract-
export attempt omitted documented PYTHONPATH; it was rerun correctly without DTO
drift. These are not hidden, waived, or counted as application/security passes.

## Historical computation and release limits

The preserved 2026-11-10 native benchmark contains **585 complete independently
validated plans**: 450 mixed and 135 negative controls. It was not rerun on the
new images. Optimizer/independent verifier source is unchanged; no hosted/cold/
concurrent/SLA claim is inferred. Earlier 90-run archives retain their old scope.
The independent e40c676 clean install and numerical review remain historical;
new exact-image second-person installation in evidence23 passed fresh0005/RLS,
the8-ULD real HTTP journey, known-ID denials, byte-identical restart persistence
and one Chrome supplement. The operator's frontend authorship is disclosed;
their Chrome execution is not independent security review of their own code.

Public L1 remains BLOCKED: real IdP, intended hosting/TLS/private storage/encryption,
hosted CI/alerts/cloud restore, legal/retention, accountable remediation ownership
and final release acceptance are unverified. ASVS triage is not compliance. No
Protect, airline feed or external operational write was enabled or performed.
