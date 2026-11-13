"""Sphinx configuration for the bibtex-doi-doctor documentation.

Build locally with 'make docs'. Read the Docs builds it from .readthedocs.yaml.
"""

import sys
from pathlib import Path

# Make the package importable for autodoc without installing it.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bibtex_doi_doctor import __version__  # noqa: E402

# -- Project information -----------------------------------------------------

project = "bibtex-doi-doctor"
author = "Blaine Mooers"
copyright = "2026, Blaine Mooers and the University of Oklahoma Health Campus"
version = __version__
release = __version__

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",            # Markdown pages
    "sphinx.ext.autodoc",     # API reference from docstrings
    "sphinx.ext.napoleon",    # Google- and NumPy-style docstrings
    "sphinx.ext.viewcode",    # [source] links in the API reference
    "sphinx_copybutton",      # copy button on code blocks
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = [
    "colon_fence",   # ::: fenced directives
    "deflist",
    "fieldlist",
]
# Give every heading down to level 3 an anchor, so pages can link to sections.
myst_heading_anchors = 3

autodoc_member_order = "bysource"
autodoc_typehints = "signature"
autodoc_default_options = {"members": True}

# Do not copy shell prompts or output lines when the copy button is used.
copybutton_prompt_text = r"\$ |>>> "
copybutton_prompt_is_regexp = True

# -- HTML output -------------------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_title = f"bibtex-doi-doctor {release}"
html_static_path = []
html_theme_options = {
    "navigation_depth": 3,
    "collapse_navigation": False,
}
html_context = {
    "display_github": True,
    "github_user": "MooersLab",
    "github_repo": "bibtex-doi-doctor-py",
    "github_version": "main",
    "conf_py_path": "/docs/",
}
