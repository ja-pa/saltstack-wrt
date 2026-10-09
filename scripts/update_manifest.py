"""Content-addressed playground update manifests, derived from exported IPKs."""
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

MANAGED = ('python3-salt', 'salt-minion', 'minion-opkg', 'minion-uci', 'minion-service', 'minion-openwrt')
ARCHES = {'omnia': 'arm_cortex-a9_vfpv3-d16', 'x86_64': 'x86_64'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fields(text):
    result, key = {}, None
    for line in text.splitlines():
        if line.startswith((' ', '\t')) and key:
            result[key] += '\n' + line
        elif ': ' in line:
            key, value = line.split(': ', 1)
            result[key] = value
    return result


def read_ipk(path):
    with tarfile.open(path) as outer:
        def part(name):
            matches = [m for m in outer if m.name.removeprefix('./') == name]
            if len(matches) != 1 or not matches[0].isfile():
                raise ValueError('Invalid IPK archive: ' + path.name)
            return tarfile.open(fileobj=io.BytesIO(outer.extractfile(matches[0]).read()))
        with part('control.tar.gz') as control:
            entry = next(m for m in control if m.name.removeprefix('./') == 'control')
            record = fields(control.extractfile(entry).read().decode())
        functions = {'execution': [], 'state': []}
        unpacked = 0
        with part('data.tar.gz') as data:
            for member in data:
                name = member.name.removeprefix('./')
                if name and (PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts):
                    raise ValueError('Unsafe IPK member')
                unpacked += member.size
                match = re.search(r'/salt/(modules|states)/([^/]+)\.py$', name)
                if not match or record['Package'] not in ('minion-opkg', 'minion-uci', 'minion-service'):
                    continue
                tree = ast.parse(data.extractfile(member).read())
                module, aliases = match[2], {}
                for node in tree.body:
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id in ('__virtualname__', '__func_alias__'):
                                value = ast.literal_eval(node.value)
                                if target.id == '__virtualname__':
                                    module = value
                                else:
                                    aliases = value
                kind = 'execution' if match[1] == 'modules' else 'state'
                functions[kind].extend(module + '.' + aliases.get(n.name, n.name)
                    for n in tree.body if isinstance(n, ast.FunctionDef)
                    and not n.name.startswith('_') and n.name != 'mod_init')
    return record, functions, unpacked


def create(directory, target):
    directory = Path(directory)
    packages, functions = [], {'execution': set(), 'state': set()}
    for path in sorted(directory.glob('*.ipk')):
        control, expected, unpacked = read_ipk(path)
        if control['Architecture'] not in ('all', ARCHES[target]):
            raise ValueError('Wrong package architecture: ' + path.name)
        packages.append({'name': control['Package'], 'version': control['Version'],
                         'architecture': control['Architecture'], 'file': path.name,
                         'sha256': digest(path.read_bytes()), 'size': path.stat().st_size,
                         'unpacked_size': unpacked, 'depends': control.get('Depends', ''),
                         'provides': control.get('Provides', '')})
        for kind in functions:
            functions[kind].update(expected[kind])
    selected = {p['name']: p for p in packages}
    if not set(MANAGED) <= selected.keys() or len(selected) != len(packages):
        raise ValueError('Export must contain the complete managed package set without duplicates')
    versions = {selected[n]['version'] for n in MANAGED}
    if len(versions) != 1:
        raise ValueError('Managed packages must have one consistent release')
    manifest = {'schema': 1, 'target': target, 'architecture': ARCHES[target],
                'salt_version': next(iter(versions)).rsplit('-r', 1)[0],
                'managed': list(MANAGED), 'packages': packages,
                'expected_functions': {k: sorted(v) for k, v in functions.items()}}
    manifest['build_id'] = digest(canonical(manifest))
    (directory / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    import sys
    create(sys.argv[1], sys.argv[2])
