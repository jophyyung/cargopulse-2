# Local CSV security increment evidence

Historical initial checkpoint. These results and source hashes predate the later
nested-JSON review fix and reconciliation with main. Current local review evidence
is in `../2026-11-14-pr-review/`; hosted CI status is linked from the PR.

Date: 2026-11-14. Base: `08733f67d49394879f4438644c7ecd29a773f617`.
Branch: `codex/team-b-backend-01`. No commit, push, deployment or independent review.

Final result: **292 passed, 20 skipped, 0 failed** from the available
Python suite. Two PostgreSQL durable-race tests were explicitly excluded because
their database is unavailable. `41` new CSV/security cases are included.
There are also `9` new shared-numeric/JSON validation cases.
The import → worker → independent verifier → JSON/CSV export case ran locally.
Ruff, security lint, tracked-file pattern checks and exact runtime OpenAPI equality
passed. See `summary.json` for commands, hashes, skip reasons and scope.

`backend-baseline.txt`, `csv-security-before.txt` and `python-regression.txt`
preserve real earlier failures. `csv-security-initial-fixture-error.txt` is a
separately labelled fixture-setup mistake, not defect evidence. Intermediate
results are retained without treating them as the final candidate result.

Absolute user/runtime/temp paths in these copies are sanitized. Original raw
logs remain in the workspace's `work/` directory. The shared historical release
reports and security findings were not overwritten.

The environment uses locked packages with Python 3.12.14 on Windows; pinned uv
could not download Python 3.12.16 for Windows. Database/browser/cloud/provider,
malware-scanning and final release gates remain open. See
`../../../team-notes/B/2026-11-14-csv-intake.md` for behavior, compatibility,
cross-lane portability changes and the shared decimal-validation correction.
