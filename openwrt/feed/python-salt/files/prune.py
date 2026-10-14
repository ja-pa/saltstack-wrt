"""Remove the Makefile's explicit paths and their bytecode, before CompileAll."""
import argparse
from pathlib import Path, PurePosixPath
import shutil


def validate_root(path):
    """Require an existing Salt package directory."""
    root = Path(path).resolve(strict=True)
    if not root.is_dir() or root.name != 'salt' or root.parent.name != 'site-packages':
        raise ValueError(f'Expected a site-packages/salt directory: {root}')
    return root


def validate_removal_path(root, entry):
    """Return the original path after checking its spelling and resolved location."""
    relative = PurePosixPath(entry)
    if relative.is_absolute() or '..' in relative.parts or '*' in entry:
        raise ValueError(f'Unsafe removal path: {entry}')
    target = root.joinpath(*relative.parts)
    resolved_target = target.resolve()
    if resolved_target == root or not resolved_target.is_relative_to(root):
        raise ValueError(f'Removal escapes Salt package: {entry}')
    if not target.exists():
        raise FileNotFoundError(f'Stale pruning entry: {entry}')
    return target


def remove_path_and_bytecode(target):
    """Remove a file, directory, or link, plus bytecode for a Python file."""
    # is_dir() follows symlinks, but rmtree() rejects a symlink to a directory.
    if target.is_symlink():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
        return
    else:
        target.unlink()

    if target.suffix == '.py':
        for suffix in ('.pyc', '.pyo'):
            target.with_suffix(suffix).unlink(missing_ok=True)
        for cached in (target.parent / '__pycache__').glob(target.stem + '.*.pyc'):
            cached.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', help='Salt package directory (site-packages/salt)')
    parser.add_argument('paths_to_remove', nargs='+', help='Explicit package-relative paths')
    args = parser.parse_args()

    root = validate_root(args.root)
    # Validate every entry before removing anything.
    targets = [validate_removal_path(root, entry) for entry in args.paths_to_remove]
    for target in targets:
        remove_path_and_bytecode(target)
    print(f'Pruned {len(targets)} explicit Salt package paths')


if __name__ == '__main__':
    main()
