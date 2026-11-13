# Python API

The command line is a thin layer over a few functions that you can call from your own scripts or a Jupyter notebook. The central one is {func}`bibtex_doi_doctor.cli.doctor`. It takes the text of a BibTeX file and returns the repaired text together with the report rows and the counts. It reads and writes no files.

## Example

```python
from pathlib import Path

from bibtex_doi_doctor.cli import Options, doctor, write_report
from bibtex_doi_doctor.network import Cache, Net

text = Path("refs.bib").read_text(encoding="utf-8")

# Offline: format repair and DOI recovery only
result = doctor(text, Options(lookup=False))
print(result.counts["reformatted"], "DOI fields reformatted")

# Online, with a persistent cache and a trial limit
net = Net(mailto="you@example.edu")
cache = Cache("refs-doi-cache.json")
result = doctor(text, Options(limit=20), net=net, cache=cache, log=print)
cache.save()

Path("refs-doctored.bib").write_text(result.text, encoding="utf-8")
write_report("refs-doi-report.tsv", result.report)

for citekey, action, old, new, detail in result.report:
    if action.startswith("candidate"):
        print(citekey, new, detail)
```

The small helpers are useful on their own.

```python
>>> from bibtex_doi_doctor import extract_doi
>>> extract_doi("doi:10.1107/S0907444910007493")
'10.1107/S0907444910007493'
>>> extract_doi("0.1093/nar/28.1.235")
'10.1093/nar/28.1.235'
>>> extract_doi("https://onlinelibrary.wiley.com/doi/pdf/10.1107/S0907444910045749?download=true",
...             from_url=True)
'10.1107/S0907444910045749'
```

## Using your own network client

`doctor()` needs only an object with two methods, `crossref(title, author_last, year)` returning a list of Crossref work records, and `doi_resolves(doi)` returning `True` or `False`. The test suite uses this to run without a network (see `FakeNet` in `tests/conftest.py`). You can use it the same way to add logging, a different rate limit, or a local mirror.

## Pipeline and command line

```{eval-rst}
.. automodule:: bibtex_doi_doctor.cli
   :members: Options, Result, doctor, lookup, apply_edits, write_report, summary, find_mailto, main
```

## DOI strings

```{eval-rst}
.. automodule:: bibtex_doi_doctor.doi
   :members: extract_doi, is_litdb_ready, leftover_text
```

## BibTeX scanner

```{eval-rst}
.. automodule:: bibtex_doi_doctor.bibscan
   :members: Entry, scan_entries, parse_value, find_matching, field_indent
```

## Matching

```{eval-rst}
.. automodule:: bibtex_doi_doctor.matching
   :members: score_candidate, norm, delatex, fold, first_author_last, year_of
```

## Network and cache

```{eval-rst}
.. automodule:: bibtex_doi_doctor.network
   :members: Net, Cache
```
