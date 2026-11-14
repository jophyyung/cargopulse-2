import hashlib
import json
import posixpath
import tarfile

def inspect_archive(path):
    nodes = {}
    hashes = {}
    content = {}
    needed = {'var/lib/dpkg/status', 'usr/share/cargopulse/runtime-files.json', 'etc/nsswitch.conf', 'etc/passwd', 'etc/group', 'etc/ssl/certs/ca-certificates.crt'}
    with tarfile.open(path) as archive:
        for entry in archive:
            name = entry.name.lstrip('./')
            nodes[name] = {'type': entry.type.decode(), 'link': entry.linkname, 'mode': entry.mode, 'uid': entry.uid, 'gid': entry.gid, 'size': entry.size}
            if entry.isfile():
                src = archive.extractfile(entry)
                if name in needed:
                    content[name] = src.read()
                    hashes[name] = hashlib.sha256(content[name]).hexdigest()
                else:
                    h = hashlib.sha256()
                    for chunk in iter(lambda: src.read(1024*1024), b''):
                        h.update(chunk)
                    hashes[name] = h.hexdigest()

    def resolve(path, depth=0):
        assert depth < 50, path
        path = posixpath.normpath('/' + path).lstrip('/')
        parts = path.split('/')
        for index in range(1, len(parts)+1):
            prefix = '/'.join(parts[:index])
            node = nodes.get(prefix)
            if node and node['type'] == '2':
                target = node['link']
                base = target if target.startswith('/') else posixpath.join(posixpath.dirname(prefix), target)
                return resolve(posixpath.join(base, *parts[index:]), depth+1)
        if nodes.get(path, {}).get('type') == '1':
            return resolve(nodes[path]['link'], depth+1)
        return path

    manifest = json.loads(content['usr/share/cargopulse/runtime-files.json'])
    records = {}
    unique_records = []
    for block in content['var/lib/dpkg/status'].decode().strip().split('\n\n'):
        fields = dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line and not line[0].isspace())
        assert fields.get('Status') == 'install ok installed'
        assert fields.get('Version') and fields.get('Architecture')
        package = fields['Package']
        records[package] = fields
        records[package+':'+fields['Architecture']] = fields
        unique_records.append(fields)
    failures = []
    broken_links = []
    links = []
    runtime_mount_links = []
    for name, entry in nodes.items():
        if entry['type'] in ('1','2'):
            resolved = resolve(name)
            links.append({'path': name, 'target': entry['link'], 'resolved': resolved})
            if name == 'etc/mtab' and entry['link'] == '/proc/mounts':
                runtime_mount_links.append(links[-1])
            elif resolved not in nodes:
                broken_links.append(name)
    mismatches = []
    for path, info in manifest['files'].items():
        if hashes.get(resolve(path)) != info['sha256']:
            mismatches.append(path)
    missing_packages = [p for p in manifest['system_packages'] if p not in records]
    missing_origins = []
    os_libraries = []
    unknown_os_libraries = []
    for path, info in manifest['files'].items():
        origin = info['origin']
        distribution = origin == 'pinned language distribution or hash-locked Python/npm package'
        if not distribution and origin not in records:
            missing_origins.append({'path':path, 'origin':origin})
        if path.startswith(('/usr/lib/','/lib/')):
            os_libraries.append({'path':path, 'origin':origin, 'package_record':records.get(origin)})
            if distribution:
                unknown_os_libraries.append(path)
    absent_copyrights = []
    for package in manifest['system_packages']:
        name = records.get(package, {}).get('Package', package.split(':')[0])
        if resolve('usr/share/doc/'+name+'/copyright') not in nodes:
            absent_copyrights.append(package)
    forbidden_names = {'sh','ash','bash','dash','busybox','apt','apt-get','apt-cache','dpkg','npm','npx','corepack','yarn','yarnpkg','pip','pip3','pip3.12'}
    executable_tools = [p for p, e in nodes.items() if posixpath.basename(p) in forbidden_names and nodes.get(resolve(p), {}).get('mode',0) & 0o111 and nodes.get(resolve(p),{}).get('type') != '5']
    pip_modules = [p for p in nodes if '/site-packages/pip/' in '/'+p or '/site-packages/pip-' in '/'+p]
    required = ['etc/ssl/certs/ca-certificates.crt','etc/ssl/openssl.cnf','usr/share/zoneinfo/UTC','usr/share/zoneinfo/Etc/UTC','etc/nsswitch.conf','etc/passwd','etc/group']
    required.append('usr/local/lib/python3.12/LICENSE.txt' if manifest['kind']=='python' else 'usr/local/LICENSE')
    absent_required = [p for p in required if resolve(p) not in nodes]
    assert len(content['etc/ssl/certs/ca-certificates.crt']) > 100000
    assert content['etc/nsswitch.conf'] == b'passwd: files\ngroup: files\nhosts: files dns\n'
    merged = {p:nodes.get(p) for p in ('bin','sbin','lib')}
    for p,target in [('bin','usr/bin'),('sbin','usr/sbin'),('lib','usr/lib')]:
        assert merged[p]['type']=='2' and merged[p]['link']==target
    permissions = {p:nodes.get(p) for p in ['tmp','var/lib/cargopulse/objects']}
    assert permissions['tmp']['mode'] == 0o1777
    assert permissions['var/lib/cargopulse/objects']['mode'] == 0o700
    assert permissions['var/lib/cargopulse/objects']['uid'] == 10001 and permissions['var/lib/cargopulse/objects']['gid'] == 10001
    uid = 10001 if manifest['kind'] == 'python' else 1000
    inaccessible = []
    def permits(entry, bits):
        shift = 6 if entry['uid'] == uid else 3 if entry['gid'] == uid else 0
        return bool((entry['mode'] >> shift) & bits)
    for path, entry in nodes.items():
        if entry['type'] != '0':
            continue
        if not permits(entry, 4):
            inaccessible.append(path)
        parent = posixpath.dirname(path)
        while parent:
            node = nodes.get(parent)
            if node and node['type'] == '5' and not permits(node, 1):
                inaccessible.append(path + ' (parent ' + parent + ')')
                break
            parent = posixpath.dirname(parent)
    assert not inaccessible, inaccessible[:10]
    for label, problems in [('broken_links',broken_links),('hash_mismatches',mismatches),('missing_packages',missing_packages),('missing_origins',missing_origins),('unknown_os_libraries',unknown_os_libraries),('absent_copyrights',absent_copyrights),('executable_tools',executable_tools),('pip_modules',pip_modules),('absent_required',absent_required)]:
        if problems:
            failures.append({'check':label,'problems':problems})
    return {'kind':manifest['kind'], 'exported_entries':len(nodes), 'manifest_file_hashes_checked':len(manifest['files']), 'link_count':len(links), 'links':links, 'runtime_mount_links':runtime_mount_links, 'nonroot_regular_file_access':{'uid':uid,'gid':uid,'unreadable_files_or_unsearchable_parents':inaccessible}, 'system_packages':manifest['system_packages'], 'dpkg_records':unique_records, 'os_libraries':os_libraries, 'required_files':{p:nodes.get(resolve(p)) for p in required}, 'permissions':permissions, 'merged_usr':merged, 'failures':failures, 'runtime_manifest_sha256':hashlib.sha256(content['usr/share/cargopulse/runtime-files.json']).hexdigest(), 'dpkg_status_sha256':hashlib.sha256(content['var/lib/dpkg/status']).hexdigest()}
