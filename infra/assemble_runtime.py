"""Assemble an auditable Debian runtime without a shell or package manager.

This runs only inside the pinned build image. Every copied system library keeps
its original Debian package/version metadata; the file manifest records hashes.
The final image contains runtime dependencies rather than a mutable installation.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("kind", choices=("python", "node"))
parser.add_argument("destination", type=Path)
args = parser.parse_args()
destination = args.destination
destination.mkdir(parents=True, exist_ok=False)
for folder in ("usr/bin", "usr/sbin", "usr/lib"):
    (destination / folder).mkdir(parents=True)
for name, target in (("bin", "usr/bin"), ("sbin", "usr/sbin"), ("lib", "usr/lib")):
    (destination / name).symlink_to(target)
copied = {}
packages = set()
ownership = {}

for listing in Path("/var/lib/dpkg/info").glob("*.list"):
    package = listing.name.removesuffix(".list")
    for item in listing.read_text().splitlines():
        path = Path(item)
        if path.is_absolute():
            ownership[str(path.resolve())] = package


def copy_file(source):
    """Copy bytes and record their package owner, including resolved link targets."""
    source = Path(source)
    if not source.exists():
        raise RuntimeError(f"Missing runtime dependency: {source}")
    target = destination / source.relative_to("/")
    if target.is_file() or target.is_symlink():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    resolved = source.resolve()
    package = ownership.get(str(resolved))
    if package:
        packages.add(package)
    if source.is_symlink():
        link = os.readlink(source)
        target.symlink_to(link)
        immediate = Path(os.path.abspath(link if link.startswith("/") else source.parent / link))
        if immediate.is_dir():
            copy_tree(immediate.resolve())
        else:
            copy_file(immediate)
    else:
        shutil.copy2(source, target)
        copied[str(source)] = {
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "origin": package or "pinned language distribution or hash-locked Python/npm package",
        }


def copy_tree(source):
    source = Path(source)
    for path in sorted(source.rglob("*")):
        if path.is_file() or path.is_symlink():
            copy_file(path)


if args.kind == "python":
    library = Path("/usr/local/lib/python3.12")
    # These optional interactive/database bindings are outside the PostgreSQL-only
    # service profile. uuid.py retains its documented pure-Python fallback.
    for pattern in ("_curses*.so", "readline*.so", "_sqlite3*.so", "_uuid*.so", "_tkinter*.so"):
        for path in (library / "lib-dynload").glob(pattern):
            path.unlink()
    for name in ("curses", "sqlite3", "ensurepip", "idlelib", "tkinter", "turtledemo"):
        shutil.rmtree(library / name, ignore_errors=True)
    for pattern in ("pip", "pip-*.dist-info"):
        for path in (library / "site-packages").glob(pattern):
            shutil.rmtree(path)
    copy_tree(library)
    copy_file("/usr/local/bin/python")
else:
    copy_file("/usr/local/bin/node")
    copy_tree("/app")
    if Path("/usr/local/LICENSE").is_file():
        copy_file("/usr/local/LICENSE")

# Discover the actual ELF closure, including wheel/Node native extensions. All
# inputs are from the pinned, trusted build stage, never user-uploaded binaries.
pending = list(copied)
checked = set()
while pending:
    path = Path(pending.pop())
    if str(path) in checked:
        continue
    checked.add(str(path))
    with path.open("rb") as source:
        if source.read(4) != b"\x7fELF":
            continue
    result = subprocess.run(  # noqa: S603 - fixed build-time tool, trusted installed binaries.
        ["/usr/bin/ldd", str(path)], capture_output=True, text=True, check=False
    )
    output = result.stdout + result.stderr
    if "not found" in output:
        raise RuntimeError(f"Unresolved ELF dependency for {path}: {output}")
    for name in re.findall(r"(?:=>\s+)?(/[^\s(]+)", output):
        dependency = Path(name)
        if dependency.is_file():
            before = set(copied)
            copy_file(dependency)
            pending.extend(set(copied) - before)

for name in ("/etc/os-release", "/etc/debian_version", "/etc/ssl/openssl.cnf"):
    if Path(name).exists():
        copy_file(name)
copy_file("/etc/ssl/certs/ca-certificates.crt")
packages.add("ca-certificates")  # update-ca-certificates generates this bundle.
copy_tree("/usr/share/zoneinfo")

# Keep scanner-visible original source/version fields for every copied system
# file. No status entry is removed while retaining its owned binary/library.
status = Path("/var/lib/dpkg/status").read_text().strip().split("\n\n")
records = {}
for block in status:
    fields = dict(
        line.split(": ", 1) for line in block.splitlines() if ": " in line and not line[0].isspace()
    )
    name = fields.get("Package", "")
    records[name] = (name, block)
    records[f"{name}:{fields.get('Architecture', '')}"] = (name, block)
licensed = set()
while packages - licensed:
    for package in sorted(packages - licensed):
        if package not in records:
            raise RuntimeError(f"Copied system package has no original status record: {package}")
        name, _ = records[package]
        copyright_file = Path("/usr/share/doc") / name / "copyright"
        if copyright_file.is_file():
            copy_file(copyright_file)
        licensed.add(package)
selected = sorted({records[package][1] for package in packages})
status_path = destination / "var/lib/dpkg/status"
status_path.parent.mkdir(parents=True, exist_ok=True)
status_path.write_text("\n\n".join(selected) + "\n")

for folder in ("usr/bin", "usr/sbin", "usr/lib", "tmp", "etc", "var/lib/cargopulse/objects"):
    (destination / folder).mkdir(parents=True, exist_ok=True)
for name, target in (("bin", "usr/bin"), ("sbin", "usr/sbin"), ("lib", "usr/lib")):
    link = destination / name
    if not link.exists():
        link.symlink_to(target)
(destination / "tmp").chmod(0o1777)
objects = destination / "var/lib/cargopulse/objects"
objects.chmod(0o700)
os.chown(objects, 10001, 10001)
(destination / "etc/passwd").write_text(
    "root:x:0:0:root:/root:/sbin/nologin\n"
    "node:x:1000:1000:node:/tmp:/sbin/nologin\n"
    "cargopulse:x:10001:10001:CargoPulse:/tmp:/sbin/nologin\n"
)
(destination / "etc/group").write_text("root:x:0:\nnode:x:1000:\ncargopulse:x:10001:\n")
(destination / "etc/nsswitch.conf").write_text("passwd: files\ngroup: files\nhosts: files dns\n")
manifest = destination / "usr/share/cargopulse/runtime-files.json"
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text(
    json.dumps(
        {"kind": args.kind, "system_packages": sorted(packages), "files": copied},
        indent=2,
        sort_keys=True,
    )
    + "\n"
)
print(f"Assembled {args.kind}: {len(copied)} files, {len(selected)} original Debian package records")
