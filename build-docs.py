#!/usr/bin/env python3
"""Build or preview documentation in an isolated local Python environment."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


ROOT = Path(__file__).resolve().parent
ENVIRONMENT = ROOT / ".venv-docs"
REQUIREMENTS = ROOT / "requirements-docs.txt"
CONFIG = ROOT / "mkdocs.yml"


def main():
    parser = argparse.ArgumentParser(
        description="Build the documentation. Create .venv-docs and install MkDocs if needed.",
        epilog="Run this script on your workstation, not on the router.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="build",
        choices=("build", "serve", "setup"),
        help="build: generate site/ with strict checks (default); serve: preview at "
        "http://127.0.0.1:8000; setup: install or update documentation dependencies",
    )
    args = parser.parse_args()
    python = ENVIRONMENT / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    try:
        if not python.is_file():
            print(f"Create documentation environment: {ENVIRONMENT}", flush=True)
            venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)

        probe = subprocess.run(
            [str(python), "-c", "import mkdocs"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if args.command == "setup" or probe.returncode:
            subprocess.run(
                [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
                cwd=ROOT,
                check=True,
            )
        if args.command == "setup":
            return 0

        command = [str(python), "-m", "mkdocs", args.command, "--config-file", str(CONFIG)]
        if args.command == "build":
            command.append("--strict")
        subprocess.run(command, cwd=ROOT, check=True)
        return 0
    except subprocess.CalledProcessError as error:
        return error.returncode
    except OSError as error:
        print(f"Documentation command failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
