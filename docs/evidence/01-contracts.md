# Milestone 1: architecture contracts

Date: 2026-11-10. Status: contract gate PASS; application/release gates NOT PASSED.

Implemented: canonical decimal-string/UTC/safety DTOs, HTTP contract registry,
generated OpenAPI/TypeScript/JSON Schema, PostgreSQL ORM and initial Alembic draft,
seeded 140-ULD fixture, RBAC/worker/metric boundaries and ADRs.

Actual commands and results:

- `uv sync --python <bundled Python 3.12>`: exit 0; 72 locked packages installed.
- `python -m pytest tests/contracts -q`: 11 passed in 0.76s, exit 0.
- `python scripts/export_contracts.py`: exit 0, OpenAPI 3.1.0 generated.
- `npm run contracts`: exit 0, openapi-typescript 7.13.0 generated the TS file.
- `alembic -c services/api/alembic.ini upgrade head --sql`: exit 0; offline SQL
  compiled. This is NOT proof that a live database migration succeeds.
- `ruff check ... --fix` and `ruff format ...`: four import errors fixed, exit 0.

An initial run had 10 passes and one failure: current FastAPI no longer accepts
`openapi_version` in its constructor. Inspection confirmed the default is already
3.1.0. Removed the unsupported constructor argument and reran the failing suite.

Security/safety: fail-closed tests reject unknown fields, live-data labels,
unmapped mass, duplicate physical pieces, missing security proof, naive timestamps,
binary float measurements, invalid airport zones and self-reviewed policies.

Limits: no runtime API/UI/solver was implemented at this gate; no production OIDC,
database concurrency, worker durability or hosted behavior has been verified yet.
Next: isolated worktree integration, real Recover MILP and independent validator,
backend/worker persistence and authenticated web workflow.
