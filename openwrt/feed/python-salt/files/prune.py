"""Remove the Makefile's explicit paths and their bytecode, before CompileAll."""
from pathlib import Path, PurePosixPath
import shutil
import sys

root = Path(sys.argv[1]).resolve(strict=True)
assert root.name == 'salt' and root.parent.name == 'site-packages', root
for entry in sys.argv[2:]:
    relative = PurePosixPath(entry)
    if relative.is_absolute() or '..' in relative.parts or '*' in entry:
        raise ValueError(f'Unsafe removal path: {entry}')
    target = root.joinpath(*relative.parts)
    if target.resolve() == root or not target.resolve().is_relative_to(root):
        raise ValueError(f'Removal escapes Salt package: {entry}')
    if not target.exists():
        raise FileNotFoundError(f'Stale pruning entry: {entry}')
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
        if target.suffix == '.py':
            for suffix in ('.pyc', '.pyo'):
                target.with_suffix(suffix).unlink(missing_ok=True)
            for cached in (target.parent / '__pycache__').glob(target.stem + '.*.pyc'):
                cached.unlink()
print(f'Pruned {len(sys.argv) - 2} explicit Salt package paths')
