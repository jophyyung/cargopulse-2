"""Recheck only already-exported archives; never talks to Docker or executes ELF."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import posixpath
import struct
import tarfile

out = Path(__file__).resolve().parent
script = out / 'run_review.py'
tree = ast.parse(script.read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {'elf_info', 'extra_archive_checks'}]
exec(compile(ast.Module(body=functions, type_ignores=[]), str(script), 'exec'))
report = json.loads((out / 'review.json').read_text())
for label, image in report['images'].items():
    image['extra_checks'] = extra_archive_checks(out / (label + '-rootfs.tar'), image)
    image['failures'].extend(image['extra_checks']['failures'])
    report['failures'].extend({'image': label, **failure} for failure in image['extra_checks']['failures'])
report['offline_finalized_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
report['passed'] = not report['failures'] and len(report['images']) == 2 and len(report['cleanup']) == 2 and all(item['removed'] for item in report['cleanup'])
report['reviewer_script_sha256'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (script, out / 'archive_checker.py', Path(__file__))}
(out / 'review-final.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'passed': report['passed'], 'failures': report['failures'], 'images': {label: {'hashes': image['manifest_file_hashes_checked'], 'elf': image['extra_checks']['elf_count'], 'runtime_account': image['extra_checks']['runtime_account'], 'forbidden_executable_commands': image['extra_checks']['forbidden_executable_commands'], 'setid': image['extra_checks']['setuid_or_setgid_entries']} for label, image in report['images'].items()}}, indent=2))
raise SystemExit(0 if report['passed'] else 1)
