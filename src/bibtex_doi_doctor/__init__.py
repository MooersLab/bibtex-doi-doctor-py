"""bibtex-doi-doctor: repair and fill in DOI fields in BibTeX files.

The package cleans DOI fields so that litdb (https://github.com/jkitchin/litdb)
can load the entries, and it looks up missing DOIs at Crossref.
"""

__version__ = "0.1.0"

from .doi import extract_doi, is_litdb_ready, leftover_text  # noqa: E402

__all__ = ["__version__", "extract_doi", "is_litdb_ready", "leftover_text"]
