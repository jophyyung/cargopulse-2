"""Read-only offline tar review; only create/export/remove this script's stopped containers."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import posixpath
import struct
import subprocess
import tarfile
import uuid

from archive_checker import inspect_archive

OUT = Path(__file__).resolve().parent
DOCKER = '/Users/pie/CargoPulse_Production_Build_Package/.local/tools/docker/docker'
ENV = dict(os.environ, DOCKER_HOST='unix:///Users/pie/.colima/default/docker.sock', DOCKER_CONFIG='/Users/pie/CargoPulse_Production_Build_Package/.local/docker-config')
IMAGES = {
    'api': 'sha256:9cf0c09fa13a647693567599f5451ca519cf2047efe104c0c753d4ef3693be34',
    'web': 'sha256:863d7eced8da07b5970629c6dbcad1c466ae456b985af5abc122d09e99139d8f',
}
ASSEMBLER = Path('/Users/pie/CargoPulse_Production_Build_Package/infra/assemble_runtime.py')
EXPECTED_ASSEMBLER = 'afc35320e1c0c0b305620438bc0c2a49e05fdd12baef94d3e2b34e92c337bae1'
report = {
    'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'assembler_sha256': hashlib.sha256(ASSEMBLER.read_bytes()).hexdigest(),
    'images': {}, 'commands': [], 'failures': [], 'cleanup': [],
}


def run(*args):
    result = subprocess.run([DOCKER, *args], env=ENV, capture_output=True, text=True)
    report['commands'].append({'args': list(args), 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    if result.returncode:
        raise RuntimeError(f'Docker command failed: {args[0]} ({result.returncode})')
    return result.stdout


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def elf_info(raw):
    if raw[:4] != b'\x7fELF':
        return None
    if raw[4:6] != b'\x02\x01':
        raise ValueError('Unexpected ELF class/data; this review targets arm64 ELF64 little-endian')
    header = struct.unpack_from('<HHIQQQIHHHHHH', raw, 16)
    file_type, machine, _, _, phoff, _, _, _, phsize, phcount, *_ = header
    segments = [struct.unpack_from('<IIQQQQQQ', raw, phoff + index * phsize) for index in range(phcount)]
    needed, rpath, runpath, interpreter = [], [], [], None
    dynamic = []
    for segment in segments:
        kind, _, offset, _, _, file_size, _, _ = segment
        if kind == 3:
            interpreter = raw[offset:offset + file_size].split(b'\x00')[0].decode()
        if kind == 2:
            for at in range(offset, offset + file_size, 16):
                tag, value = struct.unpack_from('<qQ', raw, at)
                if tag == 0:
                    break
                dynamic.append((tag, value))
    string_address = next((value for tag, value in dynamic if tag == 5), None)
    if string_address is not None:
        string_offset = next(
            offset + string_address - address
            for kind, _, offset, address, _, file_size, _, _ in segments
            if kind == 1 and address <= string_address < address + file_size
        )
        def string(at):
            start = string_offset + at
            return raw[start:raw.index(b'\x00', start)].decode()
        needed = [string(value) for tag, value in dynamic if tag == 1]
        rpath = [part for tag, value in dynamic if tag == 15 for part in string(value).split(':')]
        runpath = [part for tag, value in dynamic if tag == 29 for part in string(value).split(':')]
    return {'type': file_type, 'machine': machine, 'needed': needed, 'rpath': rpath, 'runpath': runpath, 'interpreter': interpreter}


def extra_archive_checks(path, prior):
    nodes, elf, manifest = {}, {}, None
    license_files = []
    accounts = {}
    with tarfile.open(path) as archive:
        for entry in archive:
            name = posixpath.normpath('/' + entry.name).lstrip('/')
            nodes[name] = {'type': entry.type.decode(), 'mode': entry.mode, 'link': entry.linkname}
            if not entry.isfile():
                continue
            source = archive.extractfile(entry)
            magic = source.read(4)
            if name == 'usr/share/cargopulse/runtime-files.json':
                manifest = json.loads(magic + source.read())
            if name in {'etc/passwd', 'etc/group'}:
                accounts[name] = (magic + source.read()).decode()
            if magic == b'\x7fELF':
                elf[name] = elf_info(magic + source.read())
            if '/site-packages/' in '/' + name and any(word in posixpath.basename(name).lower() for word in ('license', 'copying', 'copyright')):
                license_files.append(name)

    def resolve(path, depth=0):
        if depth >= 50:
            raise ValueError('Filesystem link loop')
        path = posixpath.normpath('/' + path).lstrip('/')
        parts = path.split('/')
        for index in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:index])
            node = nodes.get(prefix)
            if node and node['type'] == '2':
                target = node['link']
                base = target if target.startswith('/') else posixpath.join(posixpath.dirname(prefix), target)
                return resolve(posixpath.join(base, *parts[index:]), depth + 1)
        if nodes.get(path, {}).get('type') == '1':
            return resolve(nodes[path]['link'], depth + 1)
        return path

    covered = {resolve(name): info for name, info in manifest['files'].items()}
    manifest_elf = []
    unmatched = []
    for name, info in elf.items():
        info['origin'] = covered.get(name, {}).get('origin')
        if name not in covered:
            unmatched.append(name)
        else:
            manifest_elf.append(name)
    setid = [name for name, node in nodes.items() if node['mode'] & 0o6000]
    forbidden = {'sh', 'ash', 'bash', 'dash', 'zsh', 'ksh', 'csh', 'tcsh', 'fish', 'busybox', 'toybox', 'apt', 'apt-get', 'apt-cache', 'dpkg', 'dpkg-query', 'apk', 'rpm', 'dnf', 'microdnf', 'yum', 'pacman', 'npm', 'npx', 'corepack', 'yarn', 'yarnpkg', 'pnpm', 'pip', 'pip3', 'pip3.12', 'pipx', 'uv', 'poetry', 'pipenv', 'easy_install'}
    forbidden_tools = [name for name in nodes if posixpath.basename(name) in forbidden and nodes.get(resolve(name), {}).get('type') != '5' and nodes.get(resolve(name), {}).get('mode', 0) & 0o111]
    installer_modules = [name for name in nodes if '/site-packages/pip/' in '/' + name or '/site-packages/pip-' in '/' + name or name.startswith('usr/local/lib/python3.12/ensurepip/')]
    passwd = {line.split(':')[0]: line.split(':') for line in accounts['etc/passwd'].splitlines()}
    expected_name = 'cargopulse' if prior['kind'] == 'python' else 'node'
    expected_uid = '10001' if prior['kind'] == 'python' else '1000'
    user = passwd.get(expected_name, [])
    account_errors = [] if len(user) >= 4 and user[2:4] == [expected_uid, expected_uid] else [expected_name]
    library_paths = ['/usr/local/lib', '/lib/aarch64-linux-gnu', '/usr/lib/aarch64-linux-gnu', '/lib', '/usr/lib']
    unresolved, context_required = [], []
    for name, info in elf.items():
        if info['machine'] != 183:
            unresolved.append({'path': name, 'unexpected_machine': info['machine']})
        interpreter = info['interpreter']
        if interpreter and resolve(interpreter) not in nodes:
            unresolved.append({'path': name, 'interpreter': interpreter})
        origin = '/' + posixpath.dirname(name)
        search = [part.replace('${ORIGIN}', origin).replace('$ORIGIN', origin) for part in (info['runpath'] or info['rpath'])] + library_paths
        dependencies = []
        for dependency in info['needed']:
            candidates = [resolve(dependency)] if dependency.startswith('/') else [resolve(posixpath.join(folder, dependency)) for folder in search]
            match = next((candidate for candidate in candidates if candidate in elf), None)
            if match:
                dependencies.append({'needed': dependency, 'resolved': match})
                continue
            anywhere = [candidate for candidate in elf if posixpath.basename(candidate) == dependency]
            record = {'path': name, 'needed': dependency, 'present_candidates': anywhere}
            if anywhere:
                context_required.append(record)
            else:
                unresolved.append(record)
        info['resolved_dependencies'] = dependencies
    checks = {
        'elf_count': len(elf), 'manifest_elf_count': len(manifest_elf),
        'elf': elf, 'unmanifested_elf': unmatched,
        'missing_static_dependencies_or_interpreters': unresolved,
        'loader_context_required': context_required,
        'setuid_or_setgid_entries': setid,
        'forbidden_command_names_checked': sorted(forbidden),
        'forbidden_executable_commands': forbidden_tools,
        'installer_modules': installer_modules,
        'runtime_account': {'name': expected_name, 'uid': user[2] if len(user) > 2 else None, 'gid': user[3] if len(user) > 3 else None},
        'python_installed_license_file_count': len(license_files),
        'python_installed_license_files': license_files,
    }
    failures = []
    for label, values in [('unmanifested_elf', unmatched), ('missing_static_dependencies_or_interpreters', unresolved), ('setuid_or_setgid_entries', setid), ('forbidden_executable_commands', forbidden_tools), ('installer_modules', installer_modules), ('nonroot_account_mapping', account_errors)]:
        if values:
            failures.append({'check': label, 'problems': values})
    records = {record['Package'] for record in prior['dpkg_records']}
    origin_failures = [name for name, info in elf.items() if name.startswith(('usr/lib/', 'lib/')) and (not info['origin'] or info['origin'].split(':')[0] not in records)]
    if origin_failures:
        failures.append({'check': 'copied_os_elf_without_dpkg_metadata', 'problems': origin_failures})
    checks['failures'] = failures
    return checks


try:
    assert report['assembler_sha256'] == EXPECTED_ASSEMBLER, 'Assembler source hash differs'
    image_format = '{"Id":{{json .Id}},"User":{{json .Config.User}},"Os":{{json .Os}},"Architecture":{{json .Architecture}},"Volumes":{{json (index .Config "Volumes")}}}'
    container_format = '{"Id":{{json .Id}},"Image":{{json .Image}},"Status":{{json .State.Status}},"Running":{{json .State.Running}},"Pid":{{json .State.Pid}},"StartedAt":{{json .State.StartedAt}},"NetworkMode":{{json .HostConfig.NetworkMode}},"MountCount":{{len .Mounts}}}'
    for label, image in IMAGES.items():
        metadata = json.loads(run('image', 'inspect', '--format', image_format, image))
        assert metadata['Id'] == image and metadata['Os'] == 'linux' and metadata['Architecture'] == 'arm64'
        assert not metadata['Volumes'], 'Refuse image-declared volume creation'
        name = 'cargopulse-final-review-' + label + '-' + uuid.uuid4().hex[:8]
        container_id = None
        try:
            container_id = run('create', '--name', name, '--network', 'none', '--pull', 'never', image).strip()
            state = json.loads(run('inspect', '--format', container_format, container_id))
            assert state['Id'] == container_id and state['Image'] == image
            assert state['Status'] == 'created' and state['Running'] is False and state['Pid'] == 0
            assert state['StartedAt'].startswith('0001-') and state['NetworkMode'] == 'none' and state['MountCount'] == 0
            target = OUT / (label + '-rootfs.tar')
            run('export', '--output', str(target), container_id)
            result = inspect_archive(target)
            result['extra_checks'] = extra_archive_checks(target, result)
            result['failures'].extend(result['extra_checks']['failures'])
            result.update(image_id=image, image_metadata=metadata, unstarted_container=state, export_sha256=file_sha(target))
            expected_user = '10001:10001' if label == 'api' else 'node'
            if metadata['User'] != expected_user:
                result['failures'].append({'check': 'nonroot_image_user', 'actual': metadata['User']})
            report['images'][label] = result
            report['failures'].extend({'image': label, **failure} for failure in result['failures'])
        finally:
            if container_id:
                removed = run('rm', container_id).strip()
                report['cleanup'].append({'container_id': container_id, 'removed': removed == container_id})
except BaseException as error:
    report['failures'].append({'exception_type': type(error).__name__, 'message': str(error)})
finally:
    report['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report['passed'] = not report['failures'] and len(report['images']) == 2 and len(report['cleanup']) == 2 and all(item['removed'] for item in report['cleanup'])
    (OUT / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
summary = {
    'passed': report['passed'], 'failures': report['failures'], 'cleanup': report['cleanup'],
    'images': {label: {
        'image_id': result['image_id'], 'hashes': result['manifest_file_hashes_checked'],
        'links': result['link_count'], 'packages': len(result['dpkg_records']),
        'elf': result['extra_checks']['elf_count'],
        'loader_context_required': result['extra_checks']['loader_context_required'],
        'failures': result['failures'],
    } for label, result in report['images'].items()},
}
print(json.dumps(summary, indent=2))
raise SystemExit(0 if report['passed'] else 1)
