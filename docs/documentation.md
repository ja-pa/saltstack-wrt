# Build and edit the documentation

Use `build-docs.py` on your workstation. Do not install MkDocs on the router.
The script requires Python 3 with `venv` and pip support.
Its first run needs access to the Python package index.

## Build

From the package repository root, execute:

```sh
python build-docs.py
```

On systems where Python is named `python3`, use `python3 build-docs.py`.
In the test repository, the script is `saltstack-wrt/build-docs.py`.

The script creates `.venv-docs` and installs `requirements-docs.txt` when MkDocs is missing.
It then executes `mkdocs build --strict`.
The output is `site/` in the package repository.
A failed dependency installation or build returns a nonzero exit code.

Open `site/index.html` to read the generated documentation directly from disk.
Page links use `.html` filenames, so Next and Previous also work without a web server.

The script finds the repository from its own path.
You can call it from another working directory.
You do not need to activate the environment.

## Preview

```sh
python build-docs.py serve
```

Open `http://127.0.0.1:8000/` in a browser.
The preview updates when you edit the source files.
Press Ctrl+C to stop the preview.

## Update dependencies or show help

After you change the dependency file, execute:

```sh
python build-docs.py setup
```

To show command help, execute:

```sh
python build-docs.py --help
```

`--help` does not create an environment or install packages.
The script installs dependencies only for `setup` or when MkDocs is missing.

## Edit pages and change the output directory

Edit the Markdown files in `docs/`.
Add new pages to `nav` in `mkdocs.yml`.
Use short sentences, consistent technical terms, and one instruction per sentence.

The documentation uses MkDocs' built-in Read the Docs theme.
Table borders and spacing are set in `docs/assets/stylesheets/extra.css`.

The `site_dir` setting in `mkdocs.yml` selects the output directory.
Its default is `site/`, which Git ignores.
Use a dedicated build directory. MkDocs cleans that directory before each build.
Publishing is not configured.

For more information, see the [MkDocs guide](https://www.mkdocs.org/getting-started/)
and [configuration reference](https://www.mkdocs.org/user-guide/configuration/).
