# Development

## Setup

```sh
git clone https://github.com/MooersLab/bibtex-doi-doctor-py.git
cd bibtex-doi-doctor-py
make dev        # creates .venv and installs the package in editable mode
make check      # ruff, then the test suite
```

The package itself uses only the Python standard library. The `.venv` holds the development tools (pytest, pytest-cov and ruff).

## Make targets

Run `make` with no arguments to see this list with descriptions.

| Target | Purpose |
|--------|---------|
| `make dev` | Create `.venv` with an editable install and the dev tools. |
| `make test` | Run the offline tests. |
| `make test-network` | Run the live tests against Crossref and doi.org. |
| `make coverage` | Run the tests with a line-by-line coverage report. |
| `make lint` | Check the code with ruff. |
| `make format` | Let ruff fix what it can (mostly import order). |
| `make check` | `lint` then `test`. GitHub Actions runs this target. |
| `make demo` | Repair `examples/sample.bib` offline into `build/demo/` and show the diff. |
| `make demo-live` | The same with Crossref lookups. |
| `make run BIB=... ARGS=...` | Run the tool from `.venv` on any file. |
| `make install` | `pip install --user .` |
| `make install-uv` | `uv tool install .` |
| `make build` | Build a wheel and sdist into `dist/`. |
| `make clean` | Remove build output and caches. |
| `make distclean` | Also remove `.venv`. |

## Tests

| File | What it covers |
|------|----------------|
| `tests/test_doi.py` | DOI extraction from doi fields and URLs, the lost leading `1`, SICI DOIs, pasted-entry detection. |
| `tests/test_bibscan.py` | The scanner: braces, quotes, `#` concatenation, `@string` and `@comment`, positions, indentation. |
| `tests/test_matching.py` | LaTeX removal, author names, years, and candidate scoring. |
| `tests/test_network.py` | The HTTP client and cache, with `urlopen` replaced so no network is used. |
| `tests/test_doctor.py` | The whole pipeline and the command line, using a fake Crossref (`FakeNet` in `conftest.py`). |
| `tests/test_network_live.py` | Real requests. Skipped unless `BDD_NETWORK=1`. |

`tests/data/edge_cases.bib` collects problems found in a real 12,000-entry library: a SICI DOI, a second entry pasted into a doi field, a snippet placeholder, an article number before a DOI, two URLs glued together, a DOI in a note, and a book with quoted fields and string concatenation.

To add a regression test for a new problem, put a minimal entry into `edge_cases.bib` (or a string in the test itself), then assert on `doctor(...).text` or `doctor(...).report`.

## Releasing

1. Update `__version__` in `src/bibtex_doi_doctor/__init__.py`, the version badge in `README.md`, and `CHANGELOG.md`.
2. Run `make check` and `make test-network`.
3. Commit, tag (`git tag v0.1.1`) and push the tag.
