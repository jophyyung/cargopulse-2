"""Exercise real development HTTP state across API, worker and Redis restarts.

Requires an isolated local Compose stack. No production identity or external write
is supported. The result records IDs/hashes and measurements, never session cookies.
"""

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from cargopulse_contracts import canonical_hash

from packages.domain_fixtures.generator import make_snapshot

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:3101")
parser.add_argument("--compose", default="docker")
args = parser.parse_args()
base = args.base_url.rstrip("/")
if urlsplit(base).hostname not in {"localhost", "127.0.0.1"}:
    raise SystemExit("This destructive-to-availability drill is restricted to a loopback stack")
executable = shutil.which(args.compose)
if not executable:
    raise SystemExit("Compose executable is not available")
prefix = (
    [executable] if Path(executable).name.startswith("docker-compose") else [executable, "compose"]
)


def compose(*arguments):
    subprocess.run(  # noqa: S603 - explicit local operator CLI; fixed service arguments only.
        [*prefix, *arguments], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def wait_for(operation, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = operation()
            if value:
                return value
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.3)
    raise TimeoutError("Local runtime did not reach the expected state")


result = {
    "scope": "local synthetic container durability drill",
    "started_utc": datetime.now(timezone.utc).isoformat(),
}
started = time.monotonic()
with httpx.Client(base_url=base + "/api/v1", timeout=20, headers={"Origin": base}) as client:
    response = client.post("/auth/development", json={"identity_id": "manager"})
    response.raise_for_status()
    assert response.json()["auth_mode"] == "development"
    client.headers["X-CSRF-Token"] = client.cookies["cp_csrf"]
    policy = client.get("/fixtures/recover").raise_for_status().json()["policy"]
    source = make_snapshot(8).model_dump(mode="json")
    source["policy"] = policy

    def post(path, body=None, key=None, etag=None):
        headers = {"Idempotency-Key": key or str(uuid4())}
        if etag:
            headers["If-Match"] = etag
        response = client.post(path, json=body, headers=headers)
        response.raise_for_status()
        return response.json()

    batch = post("/imports/validate", {"snapshot": source})
    receipt = post(f"/imports/{batch['id']}/commit")
    scenario = post(
        "/scenarios",
        {"source_snapshot_id": receipt["snapshot_id"], "title": "Local durability acceptance"},
    )
    compose("stop", "worker", "redis")
    try:
        health = client.get("/health/ready").raise_for_status().json()
        assert health["dependencies"]["redis_hint_broker"] == "degraded_durable_database_polling"
        body, key = {"max_wall_seconds": 10, "compare_baselines": False}, str(uuid4())
        queued = post(f"/scenarios/{scenario['id']}/solve", body, key, scenario["etag"])
        assert client.get(f"/jobs/{queued['id']}").json()["status"] == "QUEUED"
        compose("restart", "api")
        wait_for(lambda: client.get("/health/ready").status_code == 200)
        assert client.get("/me").status_code == 200
        retry = post(f"/scenarios/{scenario['id']}/solve", body, key, scenario["etag"])
        assert retry["id"] == queued["id"]
        assert client.get(f"/jobs/{queued['id']}").json()["status"] == "QUEUED"
    finally:
        compose("start", "redis", "worker")

    def finished():
        job = client.get(f"/jobs/{queued['id']}").raise_for_status().json()
        if job["status"] == "FAILED":
            raise RuntimeError(f"Durable job failed: {job.get('error_code')}")
        return job if job["status"] == "COMPLETED" else None

    job = wait_for(finished)
    plan = client.get(f"/plans/{job['plan_id']}").raise_for_status().json()
    assert plan["plan"]["independent_validation"]["status"] == "PASS"
    assert plan["approvable"]
    body = {
        "action": "APPROVE_IN_APP",
        "reason_code": "DURABILITY_DRILL",
        "comment": "Synthetic-only restart acceptance",
        "expected_snapshot_hash": scenario["snapshot_hash"],
        "expected_plan_hash": plan["plan_hash"],
    }
    key = str(uuid4())
    decision = post(f"/plans/{plan['id']}/decisions", body, key, plan["etag"])
    assert decision["external_write_performed"] is False
    compose("restart", "worker", "api")
    wait_for(lambda: client.get("/health/ready").status_code == 200)
    assert post(f"/plans/{plan['id']}/decisions", body, key, plan["etag"])["id"] == decision["id"]
    assert client.get(f"/jobs/{job['id']}").json()["plan_id"] == plan["id"]
    assert canonical_hash(client.get(f"/plans/{plan['id']}").json()["plan"]) == plan["plan_hash"]
    health = client.get("/health/ready").raise_for_status().json()
    assert health["dependencies"]["redis_hint_broker"] == "ok"
    result.update(
        {
            "status": "PASS",
            "scenario_id": scenario["id"],
            "job_id": job["id"],
            "plan_id": plan["id"],
            "decision_id": decision["id"],
            "snapshot_hash": scenario["snapshot_hash"],
            "plan_hash": plan["plan_hash"],
            "external_write_performed": False,
            "seconds": round(time.monotonic() - started, 3),
            "assertions": [
                "durable queue without Redis",
                "API restart preserves session and queued command",
                "idempotent solve returns original job",
                "worker resumes durable job",
                "independent validator PASS",
                "exact-hash decision persists across restart",
                "idempotent decision returns original receipt",
                "Redis recovers",
            ],
        }
    )
Path("docs/evidence/runtime-durability.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
