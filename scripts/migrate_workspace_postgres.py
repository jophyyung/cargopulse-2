"""Logically migrate this owned synthetic workspace to a fresh Alpine volume.

This deliberately supports only the provisioned local development workspace.
It preserves the original volume, private backups and exact rollback wiring, and
exercises database rollback before allowing application writes on the new volume.
"""

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from psycopg import sql

parser = argparse.ArgumentParser()
parser.add_argument("--execute", action="store_true")
parser.add_argument(
    "--project",
    choices=("cargopulse-local", "cargopulse-migration-probe"),
    default="cargopulse-local",
)
parser.add_argument("--exercise-post-start-failure", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
if not args.execute:
    raise SystemExit(
        "Use --execute only for the owned synthetic workspace described in RUNNING.md."
    )
marker = root / ".local/runtime-owned.json"
if not marker.is_file() or marker.stat().st_uid != os.getuid():
    raise SystemExit("A workspace-owned local runtime is required.")
if os.environ.get("DOCKER_HOST") != f"unix://{Path.home()}/.colima/default/docker.sock":
    raise SystemExit("Only the documented local Colima socket is supported.")
project = args.project
port = "3000" if project == "cargopulse-local" else "3114"
if args.exercise_post_start_failure and project != "cargopulse-migration-probe":
    raise SystemExit("Fault injection is prohibited against the original workspace.")
if os.environ.get("CARGOPULSE_PORT", "3000") != port or os.environ.get("COMPOSE_FILE"):
    raise SystemExit("Refuse alternate ports or implicit Compose overrides.")
if os.environ.get("COMPOSE_PROJECT_NAME", project) != project:
    raise SystemExit("This helper is restricted to the original workspace project.")
docker = root / ".local/tools/docker/docker"
compose = root / ".local/tools/docker-compose"
prefix = [
    str(compose),
    "--project-directory",
    str(root),
    "-p",
    project,
    "-f",
    str(root / "compose.yaml"),
]
stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
private = root / ".local/backups" / ("runtime-migration_" + stamp)
private.mkdir(parents=True, mode=0o700)
log_path = private / "operations.log"
log_path.touch(mode=0o600)


def run(command, **kwargs):
    result = subprocess.run(  # noqa: S603 - fixed workspace-local operator tools, never HTTP input.
        command, cwd=root, stderr=subprocess.PIPE, **kwargs
    )
    with log_path.open("ab") as log:
        log.write(result.stderr or b"")
    if result.returncode:
        raise RuntimeError(f"Local migration operation failed; inspect private log {log_path}")
    return result.stdout


def cp(*arguments, override=None, **kwargs):
    command = [*prefix]
    if override:
        command.extend(["-f", str(override)])
    return run([*command, *arguments], **kwargs)


def inspect(service):
    identifier = cp("ps", "-q", service, stdout=subprocess.PIPE).decode().strip()
    if not identifier or "\n" in identifier:
        raise RuntimeError(f"Exactly one existing {service} container is required.")
    return json.loads(run([str(docker), "inspect", identifier], stdout=subprocess.PIPE))[0]


def query(statement):
    return (
        cp(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "cargopulse",
            "-d",
            "cargopulse",
            input=statement.encode(),
            stdout=subprocess.PIPE,
        )
        .decode()
        .strip()
    )


def inventory():
    result = {}
    for name in query(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    ).splitlines():
        statement = (
            sql.SQL(
                "SELECT json_build_object('rows',count(*),'digest',md5(coalesce("
                "string_agg(md5(row_to_json(t)::text),'' ORDER BY md5(row_to_json(t)::text)),''))) "
                "FROM {} t"
            )
            .format(sql.Identifier(name))
            .as_string()
        )
        result[name] = json.loads(query(statement))
    return result


def objects():
    code = (
        "import json,hashlib; from pathlib import Path; "
        "p=Path('/var/lib/cargopulse/objects'); "
        "print(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() "
        "for f in p.rglob('*') if f.is_file()},sort_keys=True))"
    )
    return json.loads(
        cp("run", "--rm", "--no-deps", "-T", "api", "python", "-c", code, stdout=subprocess.PIPE)
    )


def wait_database():
    for _ in range(60):
        try:
            if query("SELECT 1") == "1":
                return
        except RuntimeError:
            pass
        time.sleep(1)
    raise RuntimeError("The workspace database did not become ready.")


def locale():
    return json.loads(
        query(
            "SELECT row_to_json(t) FROM (SELECT datlocprovider,datcollate,datctype,datcollversion,"
            "pg_encoding_to_char(encoding) AS encoding FROM pg_database WHERE datname=current_database()) t"
        )
    )


api = inspect("api")
environment = dict(value.split("=", 1) for value in api["Config"]["Env"] if "=" in value)
if (
    environment.get("APP_ENV") != "development"
    or environment.get("ENABLE_DEVELOPMENT_AUTH") != "true"
):
    raise SystemExit("Refuse a non-development application.")
if any(
    environment.get(name) != "false"
    for name in ("ENABLE_EXTERNAL_WRITE", "ENABLE_LIVE_CONNECTORS", "ENABLE_PROTECT")
):
    raise SystemExit("External integrations must be disabled.")
postgres = inspect("postgres")
source_mounts = [m for m in postgres["Mounts"] if m["Destination"] == "/var/lib/postgresql"]
if len(source_mounts) != 1 or source_mounts[0].get("Name") != project + "_postgres":
    raise SystemExit("The original named Debian volume is required; refusing a repeated migration.")
configuration = json.loads(cp("config", "--format", "json", stdout=subprocess.PIPE))
target_volume = configuration["volumes"]["postgres_alpine"]["name"]
known_volumes = (
    run([str(docker), "volume", "ls", "--format", "{{.Name}}"], stdout=subprocess.PIPE)
    .decode()
    .splitlines()
)
if target_volume in known_volumes:
    raise SystemExit("Target volume already exists; preserve it and investigate before retrying.")
original_images = {"postgres": postgres["Image"], "api": api["Image"]}
for service in ("worker", "migrate", "web"):
    # The completed migration service is not returned by `compose ps -q`.
    if service == "migrate":
        original_images[service] = api["Image"]
    else:
        original_images[service] = inspect(service)["Image"]
rollback = private / "rollback.compose.json"
rollback.write_text(
    json.dumps(
        {
            "services": {
                **{name: {"image": image} for name, image in original_images.items()},
                "postgres": {
                    "image": original_images["postgres"],
                    "volumes": ["rollback_postgres:/var/lib/postgresql"],
                },
            },
            "volumes": {"rollback_postgres": {"external": True, "name": source_mounts[0]["Name"]}},
        },
        indent=2,
    )
    + "\n"
)
rollback.chmod(0o600)
started = time.monotonic()
writes_may_have_started = False
try:
    cp("stop", "web", "api", stdout=subprocess.DEVNULL)
    for _ in range(30):
        if (
            query(
                "SELECT count(*) FROM solve_jobs WHERE status IN ('QUEUED','RUNNING','VALIDATING')"
            )
            == "0"
        ):
            break
        time.sleep(1)
    else:
        raise RuntimeError("Pending work did not drain; refusing to migrate live jobs.")
    cp("stop", "worker", stdout=subprocess.DEVNULL)
    before, source_locale = inventory(), locale()
    object_hashes = objects()
    if any(name != digest for name, digest in object_hashes.items()):
        raise RuntimeError("A source object does not match its content-addressed key.")
    for name, command in (
        (
            "database.dump",
            ["exec", "-T", "postgres", "pg_dump", "-U", "cargopulse", "-d", "cargopulse", "-Fc"],
        ),
        (
            "objects.tar",
            [
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "api",
                "python",
                "-c",
                "import sys,tarfile; a=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); a.add('/var/lib/cargopulse/objects',arcname='.'); a.close()",
            ],
        ),
    ):
        fd = os.open(private / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            cp(*command, stdout=output)
    policy_order = query(
        "SELECT coalesce(json_agg(policy_name ORDER BY policy_name),'[]') FROM solution_plans"
    )
    cp("up", "--no-build", "-d", "postgres", stdout=subprocess.DEVNULL)
    wait_database()
    cp("up", "--no-build", "-d", "migrate", stdout=subprocess.DEVNULL)
    cp("wait", "migrate", stdout=subprocess.DEVNULL)
    with (private / "database.dump").open("rb") as source:
        cp(
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "--exit-on-error",
            "--clean",
            "--if-exists",
            "-U",
            "cargopulse",
            "-d",
            "cargopulse",
            stdin=source,
            stdout=subprocess.DEVNULL,
        )
    if inventory() != before:
        raise RuntimeError("Restored row counts/digests differ; rolling back.")
    target_locale = locale()
    if (
        query(
            "SELECT coalesce(json_agg(policy_name ORDER BY policy_name),'[]') FROM solution_plans"
        )
        != policy_order
    ):
        raise RuntimeError("Application policy ordering changed.")
    if query("SELECT count(*) FROM pg_index WHERE NOT indisvalid OR NOT indisready") != "0":
        raise RuntimeError("An index is invalid after logical restore.")
    role = json.loads(
        query(
            "SELECT json_build_object('superuser',rolsuper,'bypassrls',rolbypassrls) FROM pg_roles WHERE rolname='cargopulse_app'"
        )
    )
    if role != {"superuser": False, "bypassrls": False}:
        raise RuntimeError("The application database role is privileged.")
    forced_rls = int(
        query(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relrowsecurity AND c.relforcerowsecurity"
        )
    )
    if (
        forced_rls != 12
        or query(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner='cargopulse_app'"
        )
        != "0"
    ):
        raise RuntimeError("Forced RLS or non-owner table privileges changed.")
    if query("SELECT count(*) FROM pg_constraint WHERE NOT convalidated") != "0":
        raise RuntimeError("A restored constraint is not validated.")
    # Exercise rollback before any new application writes, then return to Alpine.
    cp("up", "--no-build", "-d", "postgres", override=rollback, stdout=subprocess.DEVNULL)
    wait_database()
    if inventory() != before:
        raise RuntimeError("Original volume changed during rollback exercise.")
    cp("up", "--no-build", "-d", "postgres", stdout=subprocess.DEVNULL)
    wait_database()
    if inventory() != before or objects() != object_hashes:
        raise RuntimeError("Forward return changed data/object bytes.")
    # Starting even one writer crosses the boundary: failures from this point
    # must retain the new database, not silently discard potentially new writes.
    writes_may_have_started = True
    cp("up", "--no-build", "--wait", "-d", "api", "worker", "web", stdout=subprocess.DEVNULL)
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/login", timeout=3) as response:
                if response.status == 200:
                    break
        except OSError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("The local login did not become available.")
    if args.exercise_post_start_failure:
        request = urllib.request.Request(
            f"http://localhost:{port}/api/v1/auth/development",
            data=json.dumps({"identity_id": "manager"}).encode(),
            headers={"Content-Type": "application/json", "Origin": f"http://localhost:{port}"},
            method="POST",
        )
        # The request above is restricted to this fixed loopback fault-probe URL.
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            if response.status != 200:
                raise RuntimeError("The fault probe could not produce its actual login write.")
        raise RuntimeError("Injected post-start failure after an actual authenticated login write.")
    report = {
        "status": "PASS",
        "scope": "quiesced owned local synthetic glibc-to-musl logical migration",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "source_volume_preserved": source_mounts[0]["Name"],
        "target_volume": target_volume,
        "source_images": original_images,
        "target_images": {
            name: inspect(name)["Image"] for name in ("postgres", "api", "worker", "web")
        },
        "source_locale": source_locale,
        "target_locale": target_locale,
        "before": before,
        "all_row_counts_and_digests_identical": True,
        "private_objects_verified": len(object_hashes),
        "application_role": role,
        "forced_rls_tables": forced_rls,
        "application_owned_tables": 0,
        "constraints_validated": True,
        "policy_order_preserved": True,
        "indexes_valid": True,
        "database_rollback_exercised": True,
        "forward_return_verified": True,
        "login_http_status": 200,
        "seconds": round(time.monotonic() - started, 3),
        "private_backup_directory": str(private.relative_to(root)),
        "backup_sha256": hashlib.sha256((private / "database.dump").read_bytes()).hexdigest(),
        "object_archive_sha256": hashlib.sha256((private / "objects.tar").read_bytes()).hexdigest(),
        "limits": [
            "local development only",
            "not online/PITR or hosted recovery",
            "locale names do not prove universal collation equivalence",
            "rollback exercise occurred before new writes",
        ],
    }
    (root / "docs/evidence/runtime-migration-20261111.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps({key: value for key, value in report.items() if key != "before"}, indent=2))
except Exception as error:
    failure = private / "failure.json"
    failure.write_text(
        json.dumps(
            {
                "project": project,
                "writes_may_have_started": writes_may_have_started,
                "automatic_old_volume_rollback": not writes_may_have_started,
                "recovery": "stop writers and preserve new volume"
                if writes_may_have_started
                else "restore original wiring",
                "exception_type": type(error).__name__,
                "fault_injection_requested": args.exercise_post_start_failure,
            },
            indent=2,
        )
        + "\n"
    )
    failure.chmod(0o600)
    if writes_may_have_started:
        cp("stop", "web", "api", "worker", stdout=subprocess.DEVNULL)
    else:
        cp("up", "--no-build", "--wait", "-d", override=rollback, stdout=subprocess.DEVNULL)
    raise
