# saltstack-wrt

This documentation describes the Salt minion add-ons for OpenWrt and Turris OS.
Each guide includes requirements, supported operations, limits, and Salt examples.

## Module guides

| Module | Use it to | Guide |
| --- | --- | --- |
| `pkg` with the opkg provider | Install missing packages and remove installed packages. | [opkg: Package management](opkg.md) |
| `uci` | Read configuration, prepare changes, and commit them in a separate step. | [UCI: Explicit commit](uci.md) |
| `wrt_config` | Manage and save one UCI configuration in one state. | [wrt_config: Automatic commit](wrt-config.md) |
| `service` with the procd provider | Manage services and reload them after a configuration change. | [service: procd management](service.md) |

Use `wrt_config.managed` for a declaration that includes an automatic commit.
Use `uci.*` when you need separate change and commit steps.
Use a service state to apply a saved configuration to a running service.

## Edit the documentation

The Markdown source files are in `docs/`.
The root `mkdocs.yml` file defines the navigation.
When you add a page, add it to the `nav` setting as well.

Execute documentation commands from the package repository root.
If the repository is a submodule of the test repository, first execute:

```sh
cd saltstack-wrt
```

Create a Python environment:

```sh
python -m venv .venv-docs
```

On Linux or WSL, activate it with:

```sh
. .venv-docs/bin/activate
```

On PowerShell, activate it with:

```powershell
.\.venv-docs\Scripts\Activate.ps1
```

Install the documentation dependencies:

```sh
python -m pip install -r requirements-docs.txt
```

Start the local preview:

```sh
python -m mkdocs serve
```

Open `http://127.0.0.1:8000/` in a browser.
The preview updates when you edit the source files.

## Build the documentation

```sh
python -m mkdocs build --strict
```

The default output directory is `site/`. Git ignores this directory.
To use another output directory, add `--site-dir /path/to/output`.
Publishing is not configured.

For more information, see the [MkDocs guide](https://www.mkdocs.org/getting-started/)
and the [configuration reference](https://www.mkdocs.org/user-guide/configuration/).
