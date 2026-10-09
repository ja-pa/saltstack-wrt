"""Inventory an IPK or compare it with a saved, checksummed r2 inventory."""
import collections
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

def inventory(path):
    with tarfile.open(path) as outer:
        member = next(m for m in outer if m.name.endswith('data.tar.gz'))
        with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as data:
            files = {m.name.removeprefix('./'): m.size for m in data if m.isfile()}
    groups = collections.Counter()
    prefix = 'usr/lib/python3.11/site-packages/salt/'
    for name, size in files.items():
        group = name[len(prefix):].split('/')[0] if name.startswith(prefix) else 'metadata'
        groups[group] += size
    return {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'ipk_bytes': path.stat().st_size, 'unpacked_file_bytes': sum(files.values()),
            'file_count': len(files), 'groups': dict(sorted(groups.items())), 'files': files}

mode, source, destination = sys.argv[1:4]
destination = Path(destination)
if mode == 'baseline':
    result = inventory(Path(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + '\n')
elif mode == 'compare':
    baseline = json.loads(Path(source).read_text())
    current = inventory(Path(sys.argv[4]))
    removed = sorted(set(baseline['files']) - set(current['files']))
    added = sorted(set(current['files']) - set(baseline['files']))
    result = {'baseline': {k: v for k, v in baseline.items() if k != 'files'},
              'current': {k: v for k, v in current.items() if k != 'files'},
              'saved_ipk_bytes': baseline['ipk_bytes'] - current['ipk_bytes'],
              'saved_unpacked_file_bytes': baseline['unpacked_file_bytes'] - current['unpacked_file_bytes'],
              'removed_file_count': len(removed), 'added_files': added}
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'salt-size-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    (destination / 'salt-removed-files.txt').write_text('\n'.join(removed) + '\n')
else:
    raise ValueError(mode)
