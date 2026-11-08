#!/usr/bin/env python3
"""Run bibtex-doi-doctor straight from a clone of the repository.

This lets you use the tool without installing it:

    python3 bibtex-doi-doctor.py ~/globalbibtex/global.bib --limit 50

After 'pip install .' or 'uv tool install .', the same tool is available
everywhere as the 'bibtex-doi-doctor' command.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from bibtex_doi_doctor.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
