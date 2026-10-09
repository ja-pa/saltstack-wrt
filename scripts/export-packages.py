"""Export built IPKs, with architecture and dependency inventory."""
import io
import json
import re
from pathlib import Path
import shutil
import sys
import tarfile

sdk, output = map(Path, sys.argv[1:3])
target = sys.argv[3]
architecture = {'omnia': 'arm_cortex-a9_vfpv3-d16', 'x86_64': 'x86_64'}[target]
output.mkdir(parents=True, exist_ok=True)
latest = {}
for package in sorted((sdk / 'bin').rglob('*.ipk'), key=lambda p: p.stat().st_mtime):
    with tarfile.open(package) as outer:
        member = next(m for m in outer.getmembers() if m.name.endswith('control.tar.gz'))
        with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as inner:
            control = next(m for m in inner.getmembers() if m.name.lstrip('./') == 'control')
            fields = dict(line.split(': ', 1) for line in inner.extractfile(control).read().decode().splitlines() if ': ' in line and not line.startswith(' '))
    assert fields['Architecture'] in ('all', architecture), fields
    latest[fields['Package']] = (package, fields)
assert 'salt-minion' in latest, 'No minion package built'
providers = {}
for name, (_, fields) in latest.items():
    for provided in fields.get('Provides', '').split(','):
        if provided.strip():
            providers[provided.strip().split()[0]] = name
needed = set()
missing = set()
def visit(name):
    name = name if name in latest else providers.get(name, name)
    if name not in latest:
        missing.add(name)
        return
    if name in needed:
        return
    needed.add(name)
    for dependency in latest[name][1].get('Depends', '').split(','):
        if dependency.strip():
            visit(re.split(r'[ (]', dependency.strip())[0])
assert 'minion-openwrt' in latest, 'No OpenWrt profile built'
visit('minion-openwrt')
base_runtime = {'kernel', 'base-files', 'busybox', 'libc', 'libgcc1', 'libpthread', 'librt'}
assert not missing - base_runtime, ('Unbuilt target dependencies', sorted(missing - base_runtime))
for old in output.glob('*.ipk'):
    old.unlink()
records = []
local_files = []
for name, (package, fields) in sorted(latest.items()):
    if name not in needed:
        continue
    local = package.parent.name == 'salt'
    records.append({'file': package.name, 'local_feed': local, **fields})
    shutil.copy2(package, output / package.name)
    if local and not name.endswith('-src'):
        local_files.append(package.name)
(output / 'packages.json').write_text(json.dumps(records, indent=2) + '\n')
# Fresh-install order; upgrades of exact-version addons are installed together.
order = ('python3-zipp', 'python3-importlib-metadata', 'python3-looseversion', 'python3-salt', 'salt-minion', 'minion-opkg', 'minion-uci', 'minion-service', 'minion-openwrt')
local_files.sort(key=lambda filename: order.index(filename.split('_')[0]))
(output / 'install-local.txt').write_text('\n'.join(local_files) + '\n')
# Install dependency IPKs before their consumers. opkg's wildcard install
# otherwise fetches dependencies from remote feeds before processing later IPKs.
install_order = []
visited = set()
active = set()
def order_dependency(name):
    name = name if name in latest else providers.get(name, name)
    if name not in needed or name in visited or name in active:
        return
    active.add(name)
    for dependency in latest[name][1].get('Depends', '').split(','):
        if dependency.strip():
            order_dependency(re.split(r'[ (]', dependency.strip())[0])
    active.remove(name)
    visited.add(name)
    install_order.append(latest[name][0].name)
for name in sorted(needed):
    order_dependency(name)
(output / 'install-all.txt').write_text('\n'.join(install_order) + '\n')
if target == 'x86_64':
    # Derive the x86 pruning reference from this build's unpruned installation,
    # never from an ARM package inventory or architecture-specific bytecode.
    version = latest['python3-salt'][1]['Version'].rsplit('-r', 1)[0]
    roots = [p.parent for p in (sdk / 'build_dir').glob(f'target-*/pypi/salt-{version}/ipkg-install/usr/lib/python*/site-packages/salt/minion.py')]
    assert len(roots) == 1, ('Expected one unpruned Salt install', roots)
    root = roots[0]
    source_files = sorted(p.relative_to(root).as_posix() for p in root.rglob('*.py') if p.is_file())
    (output / 'salt-source-files.json').write_text(json.dumps(source_files, indent=2) + '\n')

# Update identity includes archive content, dependencies and loader expectations.
from update_manifest import create
create(output, target)
