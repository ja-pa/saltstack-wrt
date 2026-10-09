"""Content-addressed build metadata, derived from exported IPKs."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
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
        unpacked = 0
        with part('data.tar.gz') as data:
            for member in data:
                name = member.name.removeprefix('./')
                if name and (PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts):
                    raise ValueError('Unsafe IPK member')
                unpacked += member.size
    return record, unpacked


def create(directory, target):
    directory = Path(directory)
    packages = []
    for path in sorted(directory.glob('*.ipk')):
        control, unpacked = read_ipk(path)
        if control['Architecture'] not in ('all', ARCHES[target]):
            raise ValueError('Wrong package architecture: ' + path.name)
        packages.append({'name': control['Package'], 'version': control['Version'],
                         'architecture': control['Architecture'], 'file': path.name,
                         'sha256': digest(path.read_bytes()), 'size': path.stat().st_size,
                         'unpacked_size': unpacked, 'depends': control.get('Depends', ''),
                         'provides': control.get('Provides', '')})
    selected = {p['name']: p for p in packages}
    if not set(MANAGED) <= selected.keys() or len(selected) != len(packages):
        raise ValueError('Export must contain the complete managed package set without duplicates')
    versions = {selected[n]['version'] for n in MANAGED}
    if len(versions) != 1:
        raise ValueError('Managed packages must have one consistent release')
    manifest = {'schema': 2, 'target': target, 'architecture': ARCHES[target],
                'salt_version': next(iter(versions)).rsplit('-r', 1)[0],
                'managed': list(MANAGED), 'packages': packages}
    manifest['build_id'] = digest(canonical(manifest))
    (directory / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    import sys
    create(sys.argv[1], sys.argv[2])
