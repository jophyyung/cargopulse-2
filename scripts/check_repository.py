"""Check tracked text for conflict markers and common embedded-secret patterns.

This is a bounded repository check, not a replacement for provider secret scanning.
Only file paths and rule names are printed; matched content is never logged.
"""

import re
import shutil
import subprocess
from pathlib import Path

patterns = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "aws-access-key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "openai-key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b"),
    "merge-conflict": re.compile(rb"(?m)^(?:<{7} |>{7} )"),
}
git = shutil.which("git")
if not git:
    raise SystemExit("Git is required for the tracked-file check")
# Fixed local Git inventory; no request or user-controlled arguments.
files = subprocess.check_output([git, "ls-files", "-z"]).split(b"\0")  # noqa: S603
failures = []
for name in files:
    if not name:
        continue
    path = Path(name.decode())
    environment_file = (
        path.name == ".env"
        or path.name.endswith(".env")
        or path.name.startswith(".env.")
        or ".env." in path.name
    )
    if (environment_file and not path.name.endswith(".example")) or path.suffix in {".pem", ".key"}:
        failures.append((str(path), "credential-file"))
    if not path.is_file():
        continue
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        continue
    for rule, pattern in patterns.items():
        if pattern.search(data):
            failures.append((str(path), rule))
for file, rule in failures:
    print(f"{file}: {rule}")
if failures:
    raise SystemExit(1)
print("Tracked files passed the bounded conflict/secret-pattern check.")
