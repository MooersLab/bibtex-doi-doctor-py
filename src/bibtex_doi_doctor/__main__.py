"""Allow ``python -m bibtex_doi_doctor``."""

import sys

from .cli import main

sys.exit(main())
