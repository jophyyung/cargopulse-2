# Team B increment: controlled CSV intake and report safety

Date: 2026-11-14. Base: `08733f67d49394879f4438644c7ecd29a773f617`.
Local branch: `codex/team-b-backend-01`. Job: CP-C05 / B1.

This initial checkpoint follows the supplied Team B handoff's application-security priority.
It improves the existing intake/export paths rather than replacing the implemented
Recover application. The handoff is planning material; no reviewer, source rights,
identity-provider acceptance or release approval is inferred from it. At this
initial checkpoint the work was local, uncommitted, unpublished and not deployed.
The later PR review is recorded below and in the separate review evidence folder.

## Implemented behavior

- CSV headers are unique, nonempty, exact canonical CargoUnit field names. Required
  fields must be present. Duplicate/unknown columns cannot silently discard values.
- CSV rows are processed incrementally with the existing 1,200-ULD and HTTP-body
  bounds. Malformed widths, quoting, UTF-8 and field-budget violations fail closed.
- Formula-leading cells, their full-width variants, and C0/DEL control characters
  are rejected before coercion. UTF-8 BOM, column reordering and optional empty
  fields still work. Nested JSON and metadata reject duplicate keys/nonfinite
  constants. Metadata cannot silently substitute a second cargo_units manifest.
- Invalid numeric conversions and schema failures return bounded INVALID_CSV
  problems. Uploaded values do not appear in public diagnostics or denial details.
  Rejections are audited and create no import, snapshot, idempotency row or artifact.
- The shared decimal converter now translates invalid strings into ordinary
  Pydantic validation errors. JSON imports consequently return INVALID_REQUEST/422
  instead of an uncaught decimal exception/500, without echoing private values.
- Retry identity includes the SHA-256 of the exact raw bytes, including a BOM.
  Canonical snapshot hashing and immutable raw-object storage remain separate.
- One report writer quotes every cell, prefixes formula-leading text once, and
  visibly escapes control characters. JSON retains exact values and lineage.
- Backend test clients use independent SQLite connections to per-test files.
  POSIX object-permission checks remain enforced on POSIX and explicitly skip on
  Windows; no Windows ACL assurance is claimed.

No public DTO/OpenAPI schema, RBAC, database schema, migration, dependency lock or
provider contract changed. The shared numeric validator implementation changed;
the runtime OpenAPI is compared directly with the frozen file.
The API README now describes stable CSRF retrieval and the exact destructive-test
database guard, correcting historical wording.

## Local portability work

The first wider run found three platform-dependent failures. The Windows Python
3.12 monotonic clock reports GetTickCount64 with 15.625 ms resolution: fast blocks
can measure zero, so duration/budget tests now use explicit deterministic clocks
while retaining the real SDK/solver and exact assertions. Git's core.autocrlf=true
also changed generator bytes, breaking the existing archived source hash check.
Python files now have an explicit LF checkout rule; local Python files were
normalized without changing their semantic contents. The historical archive and
its expected hashes were preserved.

These small compatibility edits and the shared numeric correction include
`.gitattributes`, optimizer/telemetry tests and the canonical validator outside the
Team B reservation table. They are local changes for review,
not a claim that another lane approved them. Production optimizer, verifier and
telemetry implementations were not changed.

## Compatibility and verification limits

Ambiguous files previously accepted are intentionally rejected. Reports now quote
all cells and escape controls; automated consumers needing exact values should use
JSON. A pre-upgrade idempotency entry for a BOM-bearing CSV used a normalized hash;
retrying that entry after upgrading can return 409. Use a new key for a new upload,
and account for outstanding retries during a rollout.

The local environment uses Python 3.12.14 and the unchanged dependency lock.
Pinned uv 0.12.19 could not download Python 3.12.16 for Windows. This does not
substitute for the project's intended Python 3.12.16/Linux verification.
Docker, PostgreSQL, Redis and the full web runtime were unavailable. The two
durable-race tests require PostgreSQL and were excluded explicitly; database/web
tests that skipped are not passing integration evidence. Browser and image scans
were not run. See the accompanying lane evidence for commands and actual results.

Spreadsheet quoting does not establish safety after editing/saving/reopening in
every spreadsheet application. This is presentation escaping, not malware scanning.
The original MALWARE_SCANNED requirement remains OPEN: no scanner or approved
disposition is supplied by this increment. Public release remains blocked.

## Next useful work

1. Review the shared numeric correction and compatibility changes with the
   integrator before merging. All nine direct-contract/JSON regression cases
   reproduced the uncaught decimal error before the correction.
2. Run the candidate with the pinned runtime and isolated PostgreSQL/Redis/web
   prerequisites, including the existing RLS, session, durable-lease and browser
   suites. Review the POSIX permission assertion in the Linux CI environment.
3. Implement a real malware-scan gate or obtain an accountable reviewed disposition
   before accepting the corresponding security requirement as complete.
4. Agree session inventory/revocation, idle/concurrency and service-grant semantics
   before adding identity APIs or migrations. Current OIDC/assurance controls remain.
5. Obtain a permitted provider contract/version, sanitized samples, scopes and data
   rights before implementing live normalization. Current synthetic/live/write
   guards remain enabled. No production tenant or customer policy was invented.

## Design references

- [Python 3.12 CSV documentation](https://docs.python.org/3.12/library/csv.html)
  describes dictionary mapping, row widths, quoting and parser field limits.
- [OWASP CSV Injection](https://community.owasp.org/attacks/CSV_Injection)
  describes formula/control prefixes and spreadsheet re-save limitations.

## Subsequent PR review

The candidate was reconciled with main at
`9fd6090acd711d934700c46cbd858e412342e6f7`. That upstream commit already contains
the file-backed SQLite fixture fix; its conftest was retained unchanged instead
of duplicating that implementation in this PR.

Review reproduced a bypass in the initial CSV implementation: JSON-escaped
tab/CR/LF characters inside numeric piece fields were decoded after the raw-cell
check and accepted by Decimal. Nested JSON cells now inspect decoded strings and
keys as well. Five additional regression cases cover tab, CR, LF, NUL and DEL.
Local paths were also removed from historical evidence before publication.

The reviewed local suite reports 297 passed and 20 skipped, with the two real
PostgreSQL durable-race tests explicitly excluded. Detailed commands and the
reviewed source hashes are in `docs/team-evidence/B/2026-11-14-pr-review/`.
The earlier results and hashes above describe the initial checkpoint, not the
later candidate. Hosted CI and actual release acceptance are separate evidence.
