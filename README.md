# CargoPulse

CargoPulse is a persistent air-cargo recovery decision-support application with a
Next.js workspace, FastAPI, PostgreSQL, a durable leased worker, HiGHS optimisation
and an independent physical/metric verifier. All supplied operations are synthetic.
Every decision stays inside CargoPulse. Protect and airline connectors are disabled.

**Release status: Recover is implemented and running locally; public L1 release
is BLOCKED.** See [release evidence](RELEASE_REPORT.md) and
[security review](SECURITY_REVIEW.md). A running local app is not airline approval.
The latest local security milestone passed 263 Python tests, 14 Chrome tests and
all four exact-image HIGH/CRITICAL gates. Lower findings and external acceptance
remain open; see [the milestone evidence](docs/evidence/24-security-remediation.md).

## Start the actual application

Install Docker Engine/Compose, Python 3 and allow at least 4 GB for the stack.

```sh
python3 scripts/configure_local.py
docker compose up --build -d
```

Open [the local workspace](http://localhost:3000). For an alternate loopback port,
set `CARGOPULSE_PORT=3101` before every Compose command and use that browser port.
For a second checkout, also use a different Compose project (`-p`) as shown in
[the isolation example](docs/RUNNING.md#isolate-a-second-checkout).
The setup generates private random local database/Redis secrets. It publishes only
the web port on loopback; database, Redis, API and the worker remain private.

Use the explicitly labelled evaluation identities: `manager`, `steward`,
`controller`, `manager-reviewer`, `auditor`, or `controller-b` (a separate tenant).
No evaluation identity is available in a production configuration.

Load a synthetic source, validate/commit it, create a scenario, inspect candidate
exclusions and urgency, solve/compare, review full hashes and record a human
decision. Download JSON/CSV/PDF evidence and inspect the immutable audit trail.
A policy draft must be published by a different manager. Stopping/starting the
stack preserves database and private source volumes.

Detailed instructions: [running and verification](docs/RUNNING.md),
[operations](ops/01_DEPLOYMENT_AND_OPERATIONS.md),
[contracts](docs/CONTRACTS.md), [test report](TEST_REPORT.md),
[recovery drill](RESTORE_DRILL.md), [dependency provenance](docs/DEPENDENCIES.md).

## Repository

Source: [alpiex1336-code/CargoPulse](https://github.com/alpiex1336-code/CargoPulse),
default branch `main`. The user-authorized source upload was completed on
2026-11-14 with the existing commit history retained. Local configuration,
database volumes, backups and development environments remain excluded by Git.
Application deployment and public L1 release acceptance remain separate gates.

- `apps/web`: authenticated bilingual operator workspace and same-origin API proxy.
- `services/api`: tenant/role controls, ingestion, immutable history, policies,
  audited decisions, private object adapter and durable queue/outbox.
- `services/worker`: route enumeration, bounded HiGHS solver, fair reference
  policies, urgency analysis and separately implemented verification.
- `packages/contracts`: canonical Pydantic contracts, OpenAPI and generated TS.
- `tests`: contract, mutation/property, OIDC, PostgreSQL/RLS, browser, telemetry
  and independent QA evidence. Historical failing review outputs are labelled.
- `infra`: pinned container builds and development/production configuration.
- `specs`, `ops`, `agents`, `references`: the original authoritative planning
  package and PDFs. The [original package README](docs/PLANNING_PACKAGE_README.md)
  is preserved. PDF performance headlines are not computed application results.

## Verification

Python 3.12.16 and Node 24.22.2 are the selected runtime patches. Dependencies are
pinned in `uv.lock`, hash-checked `requirements.lock`, and `package-lock.json`.

```sh
uv sync --frozen
npm ci
make contracts
uv run ruff check services packages scripts tests infra
npm run typecheck
uv run pytest
npm run e2e
```

PostgreSQL/Redis integration tests require isolated test databases and a live web
stack; see `docs/RUNNING.md`. A skipped integration test is not passing evidence.
CI is defined in `.github/workflows/verify.yml`; no hosted CI run is claimed.
Image scans deliberately fail the release gate on unresolved HIGH/CRITICAL findings.
The current exact-image gate passes; this policy remains enabled. Existing Debian
PostgreSQL data must be logically migrated to a new Alpine volume before using
the new runtime; see [the migration notes](docs/RUNNING.md#runtime-upgrades).
The local setup does not deploy the application or authorize airline access or
operational writes. Source sharing uses the repository above.
