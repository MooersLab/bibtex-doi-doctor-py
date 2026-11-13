# Installation

## Requirements

- Python 3.9 or newer.
- No third-party packages. The tool uses only the Python standard library.
- Network access to `api.crossref.org` and `doi.org` for the lookup step. Format repair works offline.

## Choose an installation route

| Route | Best for | Command you get |
|-------|----------|-----------------|
| [uv tool](#with-uv-recommended) | Everyday use | `bibtex-doi-doctor` on your PATH |
| [pip](#with-pip) | Systems without uv | `bibtex-doi-doctor` on your PATH |
| [Clone without installing](#from-a-clone-without-installing) | Trying it out, or a locked-down machine | `python3 bibtex-doi-doctor.py` |
| [Development install](#for-development) | Changing the code or the documentation | `make` targets |

### With uv (recommended)

[uv](https://docs.astral.sh/uv/) installs the tool into a private environment and puts the command on your PATH. Think of it as an app sealed in its own box with only the command sticking out, so nothing it installs can clash with your other Python projects.

```console
$ uv tool install git+https://github.com/MooersLab/bibtex-doi-doctor-py.git
$ bibtex-doi-doctor --version
bibtex-doi-doctor 0.1.0
```

Upgrade or remove it later with these commands.

```console
$ uv tool upgrade bibtex-doi-doctor
$ uv tool uninstall bibtex-doi-doctor
```

### With pip

```console
$ python3 -m pip install --user git+https://github.com/MooersLab/bibtex-doi-doctor-py.git
$ bibtex-doi-doctor --version
```

If the shell then says `command not found`, the user scripts folder is not on your PATH. On macOS it is usually `~/Library/Python/3.X/bin`. On Linux it is `~/.local/bin`.

### From a clone, without installing

```console
$ git clone https://github.com/MooersLab/bibtex-doi-doctor-py.git
$ cd bibtex-doi-doctor-py
$ python3 bibtex-doi-doctor.py --version
```

The script at the top of the repository runs the code in `src/`, so keep it inside the clone.

### For development

```console
$ git clone https://github.com/MooersLab/bibtex-doi-doctor-py.git
$ cd bibtex-doi-doctor-py
$ make dev      # .venv with an editable install, pytest and ruff
$ make check    # lint and run the tests
$ make docs     # build this documentation
```

See {doc}`development` for every `make` target.

## Check the installation

The bundled example file makes a good smoke test. From a clone, run the following.

```console
$ make demo
```

Without a clone, download [`examples/sample.bib`](https://github.com/MooersLab/bibtex-doi-doctor-py/blob/main/examples/sample.bib) and run `bibtex-doi-doctor sample.bib --no-lookup`. The summary should report three reformatted DOIs and one DOI taken from a url field.
