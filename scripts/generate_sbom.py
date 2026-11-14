"""Inventory resolved Python and Node packages as a scoped CycloneDX 1.6 SBOM."""

import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
components = []
for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
    name, version = dist.metadata["Name"], dist.version
    components.append(
        {
            "type": "library",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name.lower().replace('_', '-')}@{version}",
            "properties": [
                {
                    "name": "cargopulse:scope",
                    "value": "local-python-environment-including-development",
                }
            ],
        }
    )
lock = json.loads((root / "package-lock.json").read_text())
for key, item in sorted(lock.get("packages", {}).items()):
    if "node_modules/" not in key or "version" not in item:
        continue
    name = key.rsplit("node_modules/", 1)[-1]
    component = {
        "type": "library",
        "name": name,
        "version": item["version"],
        "purl": f"pkg:npm/{name}@{item['version']}",
        "properties": [{"name": "cargopulse:scope", "value": "npm-lockfile"}],
    }
    if item.get("integrity"):
        component["properties"].append({"name": "npm:integrity", "value": item["integrity"]})
    components.append(component)
result = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "version": 1,
    "metadata": {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": {"type": "application", "name": "CargoPulse", "version": "0.1.0"},
        "properties": [
            {
                "name": "cargopulse:verification",
                "value": "dependency inventory; not a built-container SBOM or vulnerability clearance",
            }
        ],
    },
    "components": components,
}
(root / "SBOM.json").write_text(json.dumps(result, indent=2) + "\n")
hashes = {
    name: hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in ["uv.lock", "requirements.lock", "package-lock.json"]
}
(root / "docs/evidence/lock-hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
print(f"Inventoried {len(components)} locked/environment components; no container build asserted.")
