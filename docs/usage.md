# Command reference

```
bibtex-doi-doctor BIBFILE [options]
```

Without `--in-place`, the input file is only read. Three files are written next to it.

| File | Contents |
|------|----------|
| `<stem>-doctored.bib` | The repaired BibTeX file. |
| `<stem>-doi-report.tsv` | One row per change, candidate or problem. See [report.md](report.md). |
| `<stem>-doi-cache.json` | Crossref and doi.org answers, reused by later runs. |

For `global.bib`, the stem is `global`, so the outputs are `global-doctored.bib` and so on.

## Options

| Option | Default | Effect |
|--------|---------|--------|
| `-o FILE`, `--output FILE` | `<stem>-doctored.bib` | Write the repaired file somewhere else. |
| `--in-place` | off | Overwrite the input. A copy named `<file>.<YYYYMMDD-HHMMSS>.bak` is written first. |
| `--no-lookup` | off | Repair formats and recover DOIs from other fields, with no network access. DOIs recovered from url or note fields are then written without a doi.org check. |
| `--drop-bad` | off | Rename a `doi` field that holds no DOI (and for which Crossref found nothing) to `baddoi`, so litdb skips it. |
| `--types LIST` | see below | Comma-separated entry types to look up at Crossref, or `all`. |
| `--limit N` | 0 (no limit) | Look up at most N entries. Useful for a trial run. |
| `--threshold X` | 0.92 | Title similarity (0 to 1) needed to accept a Crossref match. |
| `--candidate-floor X` | 0.80 | Matches between this value and the threshold, or matches that fail the year or author check, are listed as candidates and not written. |
| `--workers N` | 4 | Parallel requests. All workers share one rate limit of about eight requests per second. |
| `--mailto EMAIL` | from `litdb.toml` | Email sent to Crossref so that requests go to its "polite pool". |
| `--version` | | Print the version and exit. |

The default `--types` list is `article`, `book`, `conference`, `inbook`, `incollection`, `inproceedings`, `mastersthesis`, `phdthesis`, `proceedings` and `techreport`. Types such as `misc`, `online`, `manual` and `software` are skipped because Crossref rarely has them, and a wrong match is more likely.

## Where the email comes from

When `--mailto` is not given, the tool looks for `email = "..."` in `./litdb.toml` and then in `~/global-litdb/litdb.toml`. This is the same address litdb sends to OpenAlex. If neither file exists, requests go out without an email. Crossref still answers, but more slowly when it is busy.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Finished. Problems with individual entries are in the report, not in the exit code. |
| 2 | The input file does not exist, or the command line was wrong. |

## Running without installing

From a clone of the repository:

```sh
python3 bibtex-doi-doctor.py ~/globalbibtex/global.bib --limit 50
python3 -m bibtex_doi_doctor ...   # works after 'pip install .'
```
