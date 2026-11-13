# Makefile for bibtex-doi-doctor
#
# Run 'make' or 'make help' to list the targets.
# Development targets use a private virtual environment in .venv, so nothing
# is installed into your system Python.

PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin
STAMP  := $(VENV)/.installed
DEMO   := build/demo
DOCS_STAMP := $(VENV)/.docs-installed
DOCS_OUT   := docs/_build/html
BIB    ?= examples/sample.bib

.DEFAULT_GOAL := help

.PHONY: help venv dev test test-network coverage lint format check \
        demo demo-live run install install-uv uninstall-uv build clean distclean \
        docs docs-open docs-linkcheck docs-clean

help:  ## Show this list of targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(STAMP): pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --quiet --upgrade pip
	$(BIN)/python -m pip install --quiet -e ".[dev]"
	@touch $(STAMP)

venv: $(STAMP)  ## Create .venv with the package (editable) and the dev tools

dev: venv  ## Alias for venv

test: $(STAMP)  ## Run the offline test suite
	$(BIN)/pytest

test-network: $(STAMP)  ## Also run the live Crossref and doi.org tests
	BDD_NETWORK=1 $(BIN)/pytest -m network -v

coverage: $(STAMP)  ## Run the tests with a coverage report
	$(BIN)/pytest --cov=bibtex_doi_doctor --cov-report=term-missing

lint: $(STAMP)  ## Check style and common mistakes with ruff
	$(BIN)/ruff check src tests bibtex-doi-doctor.py

format: $(STAMP)  ## Fix import order and lint issues that ruff can fix
	$(BIN)/ruff check --fix src tests bibtex-doi-doctor.py

check: lint test  ## Lint and test (what CI runs)

demo: $(STAMP)  ## Repair examples/sample.bib offline into build/demo/
	@mkdir -p $(DEMO)
	cp examples/sample.bib $(DEMO)/sample.bib
	$(BIN)/bibtex-doi-doctor $(DEMO)/sample.bib --no-lookup
	@echo
	@echo "Differences between the input and the repaired file:"
	@diff $(DEMO)/sample.bib $(DEMO)/sample-doctored.bib || true

demo-live: $(STAMP)  ## Same as demo, but with Crossref lookups (needs network)
	@mkdir -p $(DEMO)
	cp examples/sample.bib $(DEMO)/sample.bib
	$(BIN)/bibtex-doi-doctor $(DEMO)/sample.bib
	@echo
	@diff $(DEMO)/sample.bib $(DEMO)/sample-doctored.bib || true

run: $(STAMP)  ## Run on any file: make run BIB=~/globalbibtex/global.bib ARGS="--limit 50"
	$(BIN)/bibtex-doi-doctor $(BIB) $(ARGS)

install:  ## Install the command for your user with pip
	$(PYTHON) -m pip install --user .

install-uv:  ## Install the command as an isolated uv tool
	uv tool install --force .

uninstall-uv:  ## Remove the uv tool
	uv tool uninstall bibtex-doi-doctor

build: $(STAMP)  ## Build the sdist and wheel into dist/
	$(BIN)/python -m pip install --quiet build
	$(BIN)/python -m build

$(DOCS_STAMP): $(STAMP) pyproject.toml
	$(BIN)/python -m pip install --quiet -e ".[docs]"
	@touch $(DOCS_STAMP)

docs: $(DOCS_STAMP)  ## Build the HTML documentation into docs/_build/html
	$(BIN)/sphinx-build -W --keep-going -b html docs $(DOCS_OUT)
	@echo "Open $(DOCS_OUT)/index.html, or run 'make docs-open'."

docs-open: docs  ## Build the documentation and open it in a browser
	$(BIN)/python -m webbrowser -t "file://$(CURDIR)/$(DOCS_OUT)/index.html"

docs-linkcheck: $(DOCS_STAMP)  ## Check external links in the documentation (needs network)
	$(BIN)/sphinx-build -b linkcheck docs docs/_build/linkcheck

docs-clean:  ## Remove the built documentation
	rm -rf docs/_build

clean:  ## Remove build output and caches
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache .coverage htmlcov docs/_build
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

distclean: clean  ## Also remove the virtual environment
	rm -rf $(VENV)
