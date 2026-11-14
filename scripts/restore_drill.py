"""Quiesce a local synthetic stack, back it up and restore to a NEW isolated DB.

This never replaces the application database. Backups remain in ignored private
local storage; the evidence report contains only counts, digests and measurements.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

from psycopg import sql

parser = argparse.ArgumentParser()
parser.add_argument("--compose", default="docker")
args = parser.parse_args()
executable = shutil.which(args.compose)
if not executable:
    raise SystemExit("Compose executable is unavailable")
prefix = (
    [executable] if Path(executable).name.startswith("docker-compose") else [executable, "compose"]
)


def run(*arguments, **kwargs):
    return subprocess.run(  # noqa: S603 - local operator CLI; no HTTP input or shell interpolation.
        [*prefix, *arguments], check=True, stderr=subprocess.PIPE, **kwargs
    )


def query(statement, database="cargopulse"):
    return (
        run(
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
            database,
            input=statement.encode(),
            stdout=subprocess.PIPE,
        )
        .stdout.decode()
        .strip()
    )


def inventory(database):
    names = query(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename", database
    ).splitlines()
    result = {}
    for name in names:
        if not name.replace("_", "").isalnum():
            raise RuntimeError("Unexpected table identifier")
        row = query(
            sql.SQL(
                "SELECT json_build_object('rows', count(*), 'digest', md5(coalesce(string_agg(md5(row_to_json(t)::text), '' ORDER BY md5(row_to_json(t)::text)), ''))) FROM {} t"
            )
            .format(sql.Identifier(name))
            .as_string(),
            database,
        )
        result[name] = json.loads(row)
    return result


stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
restored_name = "cargopulse_restore_drill_" + stamp
assert restored_name.replace("_", "").isalnum()
private = Path(".local/backups") / stamp
private.mkdir(parents=True, mode=0o700)
started = time.monotonic()
run("stop", "web", "api", "worker", stdout=subprocess.DEVNULL)
try:
    before = inventory("cargopulse")
    pending_before = int(
        query("SELECT count(*) FROM solve_jobs WHERE status IN ('QUEUED','RUNNING','VALIDATING')")
    )
    backup = private / "database.dump"
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        run(
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            "cargopulse",
            "-d",
            "cargopulse",
            "-Fc",
            stdout=output,
        )
    # A one-shot read-only Python service shares the private volume. The minimal
    # runtime has no shell/tar CLI; its output remains a private host backup.
    objects = private / "objects.tar"
    fd = os.open(objects, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        run(
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "api",
            "python",
            "-c",
            "import sys, tarfile; "
            "archive = tarfile.open(fileobj=sys.stdout.buffer, mode='w|'); "
            "archive.add('/var/lib/cargopulse/objects', arcname='.'); archive.close()",
            stdout=output,
        )
    backed_up_seconds = time.monotonic() - started
    query(f'CREATE DATABASE "{restored_name}" OWNER cargopulse', "postgres")
    with backup.open("rb") as source:
        run(
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "--exit-on-error",
            "-U",
            "cargopulse",
            "-d",
            restored_name,
            stdin=source,
            stdout=subprocess.DEVNULL,
        )
    restored = inventory(restored_name)
    assert restored == before, "Restored rows or canonical row digests differ"
    extracted = private / "restored-objects"
    extracted.mkdir(mode=0o700)
    with tarfile.open(objects) as archive:
        archive.extractall(extracted, filter="data")
    count = 0
    for path in extracted.rglob("*"):
        if not path.is_file():
            continue
        assert len(path.name) == 64
        assert hashlib.sha256(path.read_bytes()).hexdigest() == path.name
        count += 1
    imports = json.loads(
        query("SELECT coalesce(json_agg(object_key), '[]') FROM ingest_batches", restored_name)
    )
    assert all((extracted / key).is_file() for key in imports)
    recovery_started = time.monotonic()
    # Historical decisions/audit/snapshots/plan payloads remain unchanged. Pending
    # work is cancelled, proposals made stale, and restored sessions invalidated.
    query(
        """
BEGIN;
DELETE FROM sessions;
DELETE FROM oidc_flows;
UPDATE solve_jobs SET status='CANCELLED', error_code='RESTORE_REQUIRES_RECONCILIATION',
    lease_owner=NULL, lease_until=NULL, finished_at=now()
    WHERE status IN ('QUEUED','RUNNING','VALIDATING');
DELETE FROM outbox_events WHERE published_at IS NULL;
UPDATE scenarios SET current=false, state=CASE WHEN state IN
    ('APPROVED','REJECTED','ESCALATED','CLOSED') THEN state ELSE 'STALE' END;
UPDATE solution_plans SET state='STALE' WHERE state='PROPOSED';
COMMIT;
""",
        restored_name,
    )
    after = inventory(restored_name)
    for table in ("snapshots", "plan_decisions", "audit_events", "ingest_batches", "policy_sets"):
        assert before[table] == after[table], table
    assert query("SELECT count(*) FROM sessions", restored_name) == "0"
    assert query("SELECT count(*) FROM scenarios WHERE current", restored_name) == "0"
    assert (
        query(
            "SELECT count(*) FROM solve_jobs WHERE status IN ('QUEUED','RUNNING','VALIDATING')",
            restored_name,
        )
        == "0"
    )
    report = {
        "scope": "quiesced local synthetic container restore; not managed PITR or S3 recovery",
        "status": "PASS",
        "started_utc": stamp,
        "isolated_restored_database": restored_name,
        "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        "object_archive_sha256": hashlib.sha256(objects.read_bytes()).hexdigest(),
        "private_object_count": count,
        "pending_jobs_cancelled": pending_before,
        "referenced_import_objects": len(imports),
        "backup_seconds": round(backed_up_seconds, 3),
        "restore_and_verify_seconds": round(recovery_started - started - backed_up_seconds, 3),
        "total_seconds": round(time.monotonic() - started, 3),
        "quiesced_data_loss_rows": 0,
        "before": before,
        "after_reconciliation": after,
        "checks": [
            "all restored table counts and row digests identical before reconciliation",
            "every restored private object matches SHA-256 key",
            "all referenced source objects restored",
            "sessions and transient OIDC flows invalidated",
            "pending jobs cancelled and outbox reconciled",
            "no restored scenario is current",
            "historical decisions, audit, snapshots and policies unchanged",
        ],
        "limits": [
            "source stack is deliberately quiesced",
            "not an online backup or multi-region test",
            "no 15-minute PITR RPO or four-hour production RTO established",
            "isolated restored database is retained for inspection; it is never promoted",
        ],
    }
    Path("docs/evidence/restore-drill.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"before", "after_reconciliation"}},
            indent=2,
        )
    )
finally:
    run("start", "api", "worker", "web", stdout=subprocess.DEVNULL)
