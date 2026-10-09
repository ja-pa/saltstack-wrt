"""Read actual IPK payloads; produce reproducible size/import evidence (no writes to IPKs)."""
import argparse
import ast
import collections
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile


def read_package(path):
    with tarfile.open(path) as outer:
        member = next(m for m in outer if m.name.endswith('data.tar.gz'))
        with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as data:
            files = {m.name.removeprefix('./'): data.extractfile(m).read()
                     for m in data if m.isfile()}
    return files


def analyze(output):
    records = json.loads((output / 'packages.json').read_text())
    packages, sources, allfiles, providers = {}, {}, {}, {}
    for record in records:
        path = output / record['file']
        payload = read_package(path)
        packages[record['Package']] = {
            'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'ipk_bytes': path.stat().st_size,
            'file_bytes': sum(map(len, payload.values())), 'file_count': len(payload),
            'depends': record.get('Depends', ''),
        }
        for provided in record.get('Provides', '').split(','):
            if provided.strip():
                providers[provided.strip().split(' ')[0]] = record['Package']
        if record['Package'] == 'python3-salt':
            allfiles = {n: len(b) for n, b in payload.items()}
            sources = {n: b.decode('utf-8-sig') for n, b in payload.items() if n.endswith('.py')}
    prefix = next(n[:n.index('/salt/') + 6] for n in allfiles if '/salt/' in n)
    saltfiles = {n[len(prefix):]: b for n, b in allfiles.items() if n.startswith(prefix)}
    sources = {n[len(prefix):]: b for n, b in sources.items() if n.startswith(prefix)}
    groups = collections.Counter()
    types = collections.Counter()
    pairs = collections.Counter()
    for name, size in saltfiles.items():
        groups[name.split('/')[0] if '/' in name else '(root)'] += size
        types[Path(name).suffix or '(no suffix)'] += size
        pairs[name[:-1] if name.endswith('.pyc') else name] += size
    imports = []
    for name, source in sources.items():
        tree = ast.parse(source, filename=name)
        current = 'salt.' + name[:-3].replace('/', '.')
        package = current.removesuffix('.__init__') if name.endswith('__init__.py') else current.rsplit('.', 1)[0]
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                if node.level:
                    base = '.'.join(package.split('.')[:len(package.split('.')) - node.level + 1]) + ('.' + base if base else '')
                targets = [base] + [base + '.' + a.name for a in node.names if a.name != '*']
            for target in targets:
                if target.startswith('salt.'):
                    imports.append((name, node.lineno, target))

    def selection(directories=(), stems=(), patterns=()):
        return sorted(n for n in saltfiles if
                      any(n.startswith(d + '/') for d in directories) or
                      any(n in (s + '.py', s + '.pyc') for s in stems) or
                      any(re.search(p, n) for p in patterns))

    candidates = {
        'bytecode': sorted(n for n in saltfiles if n.endswith('.pyc')),
        'network-vendors': selection(stems=[
            'modules/' + s for s in ('arista_pyeapi', 'iosconfig', 'junos', 'nxos', 'nxos_api', 'nxos_upgrade', 'textfsm_mod')
        ] + ['states/' + s for s in ('netacl', 'netconfig', 'netntp', 'netsnmp', 'netusers')], patterns=[r'^modules/napalm_']),
        'server-integrations': selection(stems=[
            'modules/' + s for s in ('ansiblegate', 'apache', 'artifactory', 'cassandra_cql', 'celery', 'chef', 'chronos', 'etcd_mod', 'idem', 'oracle', 'osquery', 'puppet', 'rabbitmq', 'slack_notify', 'supervisord', 'vagrant', 'zk_concurrency')
        ], patterns=[r'^states/(ansiblegate|apache.*|etcd_mod|idem|rabbitmq_.*)\.pyc?$']),
        'certificates': selection(stems=[d + '/' + s for d in ('modules', 'states') for s in ('x509', 'x509_v2', 'tls', 'ssh_pki')] + ['utils/x509', 'utils/sshpki']),
        'storage': selection(stems=[d + '/' + s for d in ('modules', 'states') for s in ('mdadm_raid', 'quota', 'mount')] + ['modules/' + s for s in ('bcache', 'cryptdev', 'extfs', 'nfs3', 'parted_partition', 'scsi', 'snapper', 'xfs')]),
        'python-tooling': selection(stems=[d + '/' + s for d in ('modules', 'states') for s in ('pip', 'pip_state', 'pyenv', 'virtualenv_mod', 'npm', 'nixpkg', 'pkgbuild')]),
        'windows-utils': selection(patterns=[r'^utils/(win.*|powershell)\.pyc?$']),
        'cloud-virtual-utils': selection(stems=['utils/' + s for s in ('aws', 'boto_elb_tag', 'boto3mod', 'botomod', 'cloud', 'iam', 's3', 'vmware', 'vsan', 'virt', 'virtualbox')]),
        'returners': selection(directories=['returners']),
        'renderers': selection(directories=['renderers']),
        'beacons': selection(directories=['beacons'], stems=['modules/beacons', 'states/beacon', 'utils/beacons']),
        'engines': selection(directories=['engines']),
        'sdb': selection(directories=['sdb']),
        'pillar': selection(directories=['pillar']),
        'master-ssh': selection(directories=['client', 'cloud', 'runners', 'wheel', 'roster'], stems=['master']),
    }
    candidates['storage-except-mount'] = [n for n in candidates['storage']
                                          if n not in ('modules/mount.py', 'modules/mount.pyc', 'states/mount.py', 'states/mount.pyc')]
    # x509 utility also serves the retained asymmetric signature API.
    candidates['certificates-light'] = sorted(set(candidates['certificates']) -
        {'utils/x509.py', 'utils/x509.pyc'} | set(selection(stems=[
            'client/ssh/wrapper/x509_v2', 'client/ssh/wrapper/ssh_pki'])))
    light_keys = ('network-vendors', 'server-integrations', 'python-tooling',
                  'storage-except-mount', 'certificates-light', 'returners')
    candidates['minion-light'] = sorted(set().union(*(set(candidates[k]) for k in light_keys)))
    evidence = {}
    for key, selected in candidates.items():
        modules = {'salt.' + n[:-3].replace('/', '.').removesuffix('.__init__') for n in selected if n.endswith('.py')}
        incoming = sorted(set((src, line, target) for src, line, target in imports
                              if src not in selected and any(target == m or target.startswith(m + '.') for m in modules)))
        evidence[key] = {'file_bytes': sum(saltfiles[n] for n in selected),
                         'files': selected, 'incoming_imports': incoming}

    def closure(root, python_light=False, extra=()):
        seen = set()
        def visit(name):
            name = name if name in packages else providers.get(name, name)
            if name in seen:
                return
            if name not in packages:
                raise ValueError('Unresolved dependency: ' + name)
            seen.add(name)
            depends = packages[name]['depends']
            for dep in depends.split(','):
                dep = dep.strip().split(' ')[0]
                if dep:
                    visit('python3-light' if python_light and dep == 'python3' else dep)
        visit(root)
        for name in extra:
            visit(name)
        return sorted(seen)

    profiles = {root: closure(root) for root in ('salt-minion', 'minion-openwrt')}
    profiles['salt-minion-python-light-hypothesis'] = closure('salt-minion', True)
    profiles['salt-minion-python-curated-hypothesis'] = closure('salt-minion', True, (
        'python3-multiprocessing', 'python3-openssl', 'python3-uuid',
        'python3-xml', 'python3-decimal', 'ca-bundle'))
    # Comparison model: same tar/gzip settings for baseline and selected cut.
    # These are data.tar.gz sizes, not freshly built deployable IPKs.
    def compressed_payload(removed):
        path = output / packages['python3-salt']['file']
        buf = io.BytesIO()
        with tarfile.open(path) as outer:
            member = next(m for m in outer if m.name.endswith('data.tar.gz'))
            with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as data:
                with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=9, mtime=0, filename='') as zipped:
                    with tarfile.open(fileobj=zipped, mode='w', format=tarfile.GNU_FORMAT) as dest:
                        for entry in data:
                            if entry.name.removeprefix('./') not in removed:
                                dest.addfile(entry, data.extractfile(entry) if entry.isfile() else None)
        return len(buf.getvalue())
    model_before = compressed_payload(set())
    model_after = compressed_payload({prefix + n for n in candidates['minion-light']})
    return {'packages': packages, 'salt_prefix': prefix, 'salt_groups': dict(groups),
            'salt_types': dict(types), 'salt_files': saltfiles,
            'largest_pairs': sorted(pairs.items(), key=lambda x: x[1], reverse=True)[:30],
            'candidates': evidence, 'profiles': profiles, 'light_keys': light_keys,
            'compression_model': {'before_bytes': model_before, 'after_bytes': model_after,
                                  'saved_bytes': model_before - model_after,
                                  'settings': 'GNU tar, gzip level 9, mtime 0; empty directories retained'}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    result = analyze(args.output)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Wrote', args.destination)
