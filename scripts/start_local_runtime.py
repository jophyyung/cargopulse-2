"""Restart this workspace's already-provisioned local Colima VM.

Other hosts should use their installed Docker Engine/Compose. This helper never
downloads tools, replaces another runtime directory or activates a Docker context.
"""

import json
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
marker = root / ".local/runtime-owned.json"
if not marker.is_file():
    raise SystemExit("No workspace-owned runtime is provisioned; use your installed Docker Engine.")
metadata = json.loads(marker.read_text())
persistent = root / ".local/lima"
if metadata.get("persistent_directory") != str(persistent) or not persistent.is_dir():
    raise SystemExit("Runtime metadata does not identify this workspace's persistent VM.")
if persistent.stat().st_uid != os.getuid() or marker.stat().st_uid != os.getuid():
    raise SystemExit("Refuse a runtime directory owned by another user.")

executable = root / ".local/tools/colima"
if not executable.is_file():
    raise SystemExit("Workspace-local Colima is missing; use your installed Docker Engine.")
env = dict(os.environ, LIMA_HOME=str(persistent), DOCKER_CONFIG=str(root / ".local/docker-config"))
env.pop("COLIMA_HOME", None)
env["PATH"] = (
    ":".join(
        str(root / path)
        for path in (".local/tools/lima/bin", ".local/tools/docker", ".local/tools")
    )
    + ":"
    + env["PATH"]
)
subprocess.run(  # noqa: S603 - fixed task-owned, checksum-verified CLI and constant flags.
    [
        str(executable),
        "start",
        "--cpu",
        "2",
        "--memory",
        "3",
        "--disk",
        "20",
        "--vm-type",
        "vz",
        "--runtime",
        "docker",
        "--mount",
        "none",
        "--ssh-agent=false",
        "--ssh-config=false",
        "--activate=false",
        "--binfmt=false",
    ],
    env=env,
    check=True,
)
print("Local runtime is ready; persistent VM data remains under ignored .local/lima.")
