# Run CargoPulse locally

This is a real synthetic recovery application, not a live airline connection.
Protect and all external operational writes are disabled. See `RELEASE_REPORT.md`
for the exact verification/release status; local success is not L1 publication.

## Docker path

Requirements: Docker Engine/Compose, at least 4 GB available memory, and loopback
port 3000. No airline or SaaS account is needed for explicit development identities.

```sh
python3 scripts/configure_local.py
docker compose up --build -d
docker compose logs --tail=100 migrate api worker web
```

Open http://localhost:3000 . The one-shot migration service provisions a separate
non-owner app database role and labelled development identities. The API/worker
use this role with per-transaction tenant context. Only the web port is published,
bound to loopback. JSON/CSV uploads and solver jobs persist in named volumes.

The local object adapter stores immutable private files with mode 0600 on a private
volume. Production uses the S3-compatible adapter with SSE and scoped workload
credentials; the local file adapter is not evidence of an S3 deployment test.

Login as `steward`, load the synthetic fixture or import a valid JSON/controlled
CSV, validate and commit it. Login as `controller` or `manager`, create the scenario,
inspect excluded arcs, run the solver, compare baselines and review the proposed
assignments. Confirm current snapshot/plan hashes and a reason to record an in-app
decision. Download JSON/CSV/PDF evidence and inspect the audit as auditor/manager.
Policy drafts require a different manager reviewer; the development profile has
`manager` and `manager-reviewer` for that test. Production has no built-in accounts.

```sh
docker compose stop
docker compose start
```

Stopping preserves volumes. Do not run `down --volumes` on any data you need.

## Runtime upgrades

The current local database is PostgreSQL18.6 on patched Alpine. Fresh checkouts
initialize the distinct `postgres_alpine` volume. An existing Debian/glibc cluster
must be logically dumped/restored into a new initialized Alpine volume; never
rename or physically mount the old cluster under the new image. This machine's
owned synthetic transition was executed and verified; its old
`cargopulse-local_postgres` volume and private backups remain preserved. The guarded
one-time `scripts/migrate_workspace_postgres.py --execute` is only for the original
documented owned workspace and refuses repeated migration or arbitrary projects.
Read evidence13 and `runtime-migration-20261111.json` before any similar transition.

Schema0005 adds nullable trusted session assurance and transactional disable
revocation. New readiness requires that schema. Existing privileged OIDC sessions
with NULL assurance must sign in again; past MFA evidence is not invented. Do not
downgrade or restart a known vulnerable prior app to bypass assurance enforcement.
Directory operators need scoped session DELETE rights for disable revocation;
missing rights roll back the disable operation. App directory writes stay denied.

The minimal API/web runtime has no shell/package managers. Use explicit
`docker compose exec -T api python ...` or database tooling, not `sh`/`tar` inside
the API container. The backup tool streams its archive through Python tarfile.
After any writer starts on a new volume, failure handling must retain that volume;
automatically falling back to an old database could discard accepted writes.

Private DOM is removed on logout attempt, offline, session401/expiry and cross-tab
boundaries. A failed/offline sign-out is explicitly unconfirmed. Reconnect/reload
does not reopen the same locked session; use a fresh sign-in. This does not cancel
backend work already accepted or erase downloaded files/browser memory.

## Isolate a second checkout

The default Compose project name is `cargopulse-local`. A second checkout must
use both another project name and another port; otherwise it can share the first
checkout's resources. Use the same values on every command:

```sh
python3 scripts/configure_local.py
CARGOPULSE_PORT=3112 docker compose -p cargopulse-install-check up --build -d
CARGOPULSE_PORT=3112 docker compose -p cargopulse-install-check ps
CARGOPULSE_PORT=3112 docker compose -p cargopulse-install-check stop
```

Open http://localhost:3112 . Named volumes remain isolated and are preserved on
stop. For the CLI durability/restore helpers, also set
`COMPOSE_PROJECT_NAME=cargopulse-install-check` and `CARGOPULSE_PORT=3112`, and pass
`--base-url http://localhost:3112` to the durability helper.

## Native development path

Use Python 3.12.16, Node 24.22.2, uv and npm. Install the Python interpreter first;
uv 0.12.19 may need `--python /path/to/python3.12` for this patch. Install exactly the locks:

```sh
uv sync --frozen
npm ci
export PYTHONPATH=packages/contracts/python:services/api:services/worker:.
```

Provision an isolated PostgreSQL database and Redis, then set `APP_ENV=development`,
`ENABLE_DEVELOPMENT_AUTH=true`, `APP_BASE_URL=http://localhost:3000`, `DATABASE_URL`,
`REDIS_URL`, `OBJECT_STORE_ROOT` and `API_INTERNAL_URL=http://127.0.0.1:8000`.
Set `CARGOPULSE_ENV=development` for the web development identity selector. Run
migrations as the schema owner, provision grants/identities, then run API/worker
with a non-owner, non-BYPASSRLS database role as described in the deployment runbook.

```sh
make migrate
make api
make worker
npm run dev
```

Use separate terminals for the long-running processes. `AUTO_CREATE_SCHEMA` is a
unit-test convenience, not a release migration path. Never enable development auth
or expose the local trust-authenticated PostgreSQL cluster on a public interface.

## Verification commands

```sh
uv run pytest
uv run ruff check services packages scripts tests
npm run typecheck
npm run build
make contracts
npm run e2e
```

Integration tests require the documented PostgreSQL/Redis environment; skipped tests
do not constitute passing integration evidence. E2E requires a real running API,
worker and web server. Browser screenshots are supplementary to API/database proof.

## Complete local test environment

Use a separate loopback PostgreSQL test server on port 55432 with the development
schema owner `cargopulse` and trust authentication confined to that isolated test
server. Redis tests use loopback port 56379. Never point these destructive fixture
suites at an application or production database.

```sh
export PYTHONPATH=packages/contracts/python:services/api:services/worker:.
uv run python scripts/provision_test_databases.py
export BACKEND_TEST_DATABASE_URL=postgresql+psycopg://cargopulse_app@127.0.0.1:55432/cargopulse_backend_test
export OBSERVABILITY_TEST_DATABASE_URL=postgresql+psycopg://cargopulse_app@127.0.0.1:55432/cargopulse_observability_backend_test
export CARGOPULSE_QA_WEB_URL=http://localhost:3000
uv run pytest
export CARGOPULSE_E2E_URL=http://localhost:3000
npx playwright install chromium
npm run e2e
```

On this machine, `CARGOPULSE_BROWSER_CHANNEL=chrome` selects the installed Google
Chrome used by the retained browser evidence. Without it, install the exact
Playwright Chromium revision as shown. A missing executable is a launch failure,
not a passing browser test.

The release QA fixture also uses its own `cargopulse_releaseqa_test`; the provision
script creates/migrates all three isolated databases. Observability tests explicitly
reset only their dedicated schema and decode real loopback OTLP protobuf requests.

With an isolated development Compose stack, the following drills stop/restart
services and therefore temporarily interrupt its local UI:

```sh
uv run python scripts/verify_runtime.py --base-url http://localhost:3000
uv run python scripts/restore_drill.py
```

The restore creates a new database and preserves the source database. It retains
private backups in `.local/backups`; never commit or publish backup contents.
See `RESTORE_DRILL.md` for measured scope and production recovery prerequisites.

Native destructive test resets are restricted to the exact documented loopback
host/port/database/application user, without query overrides or embedded passwords.
Do not run simultaneous full suites against the same three resettable databases.
Use a separate isolated server for another suite. A name merely containing
`backend_test` is not accepted as proof that a database is safe to truncate.

## Current workspace runtime

This machine uses task-local Docker/Compose/Colima tools rather than a system-wide
Docker CLI installation. Its VM disk now persists under ignored `.local/lima`;
a controlled actual VM restart preserved all recorded database/object hashes.
The former temporary alias is not required by the restart helper. No host project
mount or SSH agent is forwarded. These are local development settings.

From this repository root, after a normal machine restart:

```sh
python3 scripts/start_local_runtime.py
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
export DOCKER_CONFIG="$PWD/.local/docker-config"
.local/tools/docker-compose up -d
```

Open http://localhost:3000 . To stop only the application containers:

```sh
.local/tools/docker-compose stop
```

The helper requires the already provisioned, workspace-owned ignored runtime and
refuses another user's directory. It downloads nothing and does not activate the
user's Docker context. On another machine, install/use normal Docker Engine/Compose
and the portable setup at the top of this document instead. `.local` contains
runtime disks and private backups; deleting it can delete local evaluation state.
A physical-host reboot, new-host restore, automatic backup schedule and managed
production durability remain outside the measured local verification.
