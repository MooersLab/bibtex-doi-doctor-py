# How it works

## Why the file is edited in place

Most BibTeX libraries for Python read the whole file into objects and write it out again. That round trip changes spacing, field order and quoting, and it can drop comments and `@string` blocks. On a library of 12,000 entries kept under version control, the result is a diff that touches every line.

bibtex-doi-doctor works like a careful copy editor with a red pen rather than a typist who retypes the page. Its scanner (`bibscan.py`) records only where each entry and each field starts and ends. All changes are collected as small edits, either "replace characters 1520 to 1556" or "insert a doi line after this entry's key", and applied from the end of the file backwards so that earlier positions stay valid. Every byte outside the edited DOI fields is left alone, including bytes that are not valid UTF-8.

## The three passes

### Pass 1. Look at every entry (no network)

For an entry **with** a doi field:

1. If the value is already a bare DOI such as `10.1107/S0907444910007493`, nothing happens.
2. Otherwise the DOI is pulled out of the text. Prefixes such as `doi:`, `DOI `, `https://doi.org/`, `http://dx.doi.org/` and `ARTN e5954` are dropped, as is trailing punctuation. A value such as `0.1038/s41467-...` gets its lost leading `1` back.
3. If a lot of other text remains besides the DOI, or that text contains `@` or `=`, someone probably pasted an entry into the field. The field is flagged for a hand fix and left unchanged.
4. If no DOI can be found at all, the field is reported as bad and the entry joins the Crossref queue.

For an entry **without** a doi field, the tool looks in `url`, `note`, `eprint`, `howpublished`, `annote` and `annotation`, in that order. URL debris is removed, for example `/asset/...pdf?v=1`, `?download=true`, `/abstract` or a second URL glued onto the first. If nothing is found, the entry joins the Crossref queue (when its type is in `--types`).

### Pass 2. Check recovered DOIs at doi.org

Every DOI that was rewritten or recovered is checked against the doi.org handle service. A recovered DOI that does not resolve is not written. The entry goes to the Crossref queue instead. A rewritten DOI that does not resolve is still written, because it came from your own doi field, but it is flagged in the report.

### Pass 3. Ask Crossref

For each entry in the queue, the tool sends the title (with LaTeX markup removed) and the first author's last name to Crossref's `query.bibliographic` search and examines the top five results. A result is accepted only when all of these hold.

- **Title.** After lower-casing and removing accents, punctuation and LaTeX, the similarity ratio (Python's `difflib`) is at least `--threshold` (0.92). The Crossref subtitle is tried both with and without the main title.
- **Year.** The years differ by at most one. This allows for online-first versus print dates.
- **Author.** The entry's first-author last name appears among the Crossref family names.
- **doi.org.** The DOI resolves.

Close calls are written to the report as candidates and never to the file. A missed DOI costs you one manual lookup later. A wrong DOI silently attaches the wrong paper to your citation, which is much harder to notice.

Titles shorter than twelve letters after normalization (for example `{XDS}`) are not looked up because a short query matches too many papers.

## Rate limits and the cache

All worker threads share one throttle of about eight requests per second, and 429 or 5xx answers are retried with increasing waits. Every Crossref answer and doi.org check is stored in `<stem>-doi-cache.json`, which is saved every hundred lookups and at the end. If you stop a long run with Ctrl-C and start it again, finished lookups come from the cache. Network errors are never cached, so those entries are tried again.

Delete the cache file to force fresh lookups, for example after changing `--threshold`.

## Code layout

| Module | Role |
|--------|------|
| `doi.py` | Regular expressions that find, trim and judge DOIs. |
| `bibscan.py` | The position-recording BibTeX scanner. |
| `matching.py` | LaTeX removal, name and title normalization, candidate scoring. |
| `network.py` | The throttled Crossref and doi.org client, and the thread-safe cache. |
| `cli.py` | The three-pass pipeline (`doctor()`), edit application and the command line. |

`doctor(text, options, net, cache)` takes and returns plain text and does no file input or output. That makes it easy to call from your own Python code or a notebook.

```python
from bibtex_doi_doctor.cli import Options, doctor
from bibtex_doi_doctor.network import Net

text = open("refs.bib", encoding="utf-8").read()
result = doctor(text, Options(limit=20), net=Net("you@example.edu"))
print(result.counts)
for row in result.report:
    print(row)
```
