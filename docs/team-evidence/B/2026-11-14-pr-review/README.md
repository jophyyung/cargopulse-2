# PR review evidence

Date: 2026-11-14. Reviewed against main `9fd6090acd711d934700c46cbd858e412342e6f7`.

The review found and fixed a control-character bypass after nested JSON-cell
decoding. The before-fix log preserves five failing cases (three actual accepted
inputs and two inconsistent diagnostics). The reviewed suite passed **297**
tests and skipped **20**; two additional PostgreSQL durable-race cases were
explicitly excluded because the required server is unavailable locally. All 55
new intake/security regression cases are included in the passing result.

Upstream's SQLite fixture fix is retained without a conftest change. Canonical
schemas, migrations and dependency locks are unchanged. Both Ruff invocations,
new-file formatting, OpenAPI equality and diff whitespace checks passed locally.
The complete staged-file secret/conflict-pattern check runs before committing.

These are Windows/Python 3.12.14 results. No local Docker, database/browser,
POSIX-permission or pinned Linux runtime verification is claimed. The draft PR
will run the unchanged hosted workflow for full container, database, browser,
dependency/image and SBOM checks. Consult the PR for the actual result on its
current head; this pre-publication record does not claim a future CI pass.

`summary.json` binds the reviewed implementation to exact file hashes. Earlier
logs in `../2026-11-14-csv-intake/` remain labelled as historical. Absolute personal
paths are sanitized in the shared copies; raw originals remain in local work/.
Public release and provider/cloud/identity/malware-scan gates remain blocked.
