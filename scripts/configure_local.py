"""Create or complete ignored development configuration without logging secrets."""

import os
import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / ".env"
fd = os.open(target, os.O_RDWR | os.O_CREAT, 0o600)
with os.fdopen(fd, "r+") as output:
    value = output.read()
    keys = {line.split("=", 1)[0] for line in value.splitlines() if "=" in line}
    for key in ("POSTGRES_PASSWORD", "REDIS_PASSWORD"):
        if key not in keys:
            if value and not value.endswith("\n"):
                output.write("\n")
            output.write(key + "=" + secrets.token_hex(24) + "\n")
            value = "\n"
os.chmod(target, 0o600)
print("Private local configuration is ready; existing values were preserved.")
