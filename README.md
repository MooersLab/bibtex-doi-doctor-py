![Version](https://img.shields.io/static/v1?label=bibtex-doi-doctor-py&message=0.1.0&color=brightcolor)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
# bibtex-doi-doctor-py

This script cleans up a BibTeX library file, so Dr. John Kitchin's [litdb](https://github.com/jkitchin/litdb) package can use the entries. 


The script does two jobs.

## 1. Format repair
   litdb accepts a DOI field only when it starts with '10.' or 'http'. 
   Values such as 'doi:10.1107/...', 'DOI 10.1107/...', 'doi.org/10.1093/...' or 'https://dx.doi.org/10...' are rewritten to the bare form '10.xxxx/yyyy'. 
   A field with no DOI at all (an ISSN, an ISSN) is reported. 
   With --drop-bad, the DOI is renamed to 'baddoi', so litdb skips it.

## 2.DOI lookup 
   For entries without a DOI, the script first looks for a DOI inside the url, note, eprint, and howpublished fields. 
   If none is there, it queries Crossref with the title, first author, and year. 
   A candidate is accepted only when the titles agree closely, the year is within one, and the first author's last name appears among the Crossref authors. 
   We then check every accepted DOI at doi.org before writing it.
