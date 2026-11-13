![Version](https://img.shields.io/static/v1?label=bibtex-doi-doctor-py&message=0.1.0&color=brightgreen)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![tests](https://github.com/MooersLab/bibtex-doi-doctor-py/actions/workflows/tests.yml/badge.svg)](https://github.com/MooersLab/bibtex-doi-doctor-py/actions/workflows/tests.yml)
# bibtex-doi-doctor-py

This script cleans up a BibTeX library file, so Dr. John Kitchin's [litdb](https://github.com/jkitchin/litdb) package can use the entries.

The script does two jobs.

## 1. Format repair
   litdb accepts a DOI field only when it starts with '10.' or 'http'.
   Values such as 'doi:10.1107/...', 'DOI 10.1107/...', 'doi.org/10.1093/...' or 'https://dx.doi.org/10...' are rewritten to the bare form '10.xxxx/yyyy'.
   A field with no DOI at all (an ISSN, for example) is reported.
   With --drop-bad, the DOI field is renamed to 'baddoi', so litdb skips it.

## 2. DOI lookup
   For entries without a DOI, the script first looks for a DOI inside the url, note, eprint, and howpublished fields.
   If none are there, it queries Crossref with the title, first author, and year.
   We accept a candidate only when the titles match closely, the year is within one, and the first author's last name appears among the Crossref authors.
   We then check every accepted DOI at doi.org before writing it.

Only the DOI fields change.
Comments, `@string` blocks, field order, indentation, and line endings stay exactly as they were, so a `git diff` of your library shows only the DOI lines.
The input file is never overwritten unless you ask for it with `--in-place`, which first writes a timestamped backup.

## Requirements

- Python 3.9 or newer.
- No third-party packages. The tool uses only the Python standard library.
- Network access to `api.crossref.org` and `doi.org` for the lookup step. Format repair works offline.

## Installation

Pick one of the following.

### A. As a command-line tool with uv (recommended)

[uv](https://docs.astral.sh/uv/) installs the tool into its own environment and puts the `bibtex-doi-doctor` command on your PATH.

```sh
uv tool install git+https://github.com/MooersLab/bibtex-doi-doctor-py.git
bibtex-doi-doctor --version
```

To upgrade later, run `uv tool upgrade bibtex-doi-doctor`.

### B. With pip

```sh
python3 -m pip install --user git+https://github.com/MooersLab/bibtex-doi-doctor-py.git
bibtex-doi-doctor --version
```

### C. From a clone, without installing

```sh
git clone https://github.com/MooersLab/bibtex-doi-doctor-py.git
cd bibtex-doi-doctor-py
python3 bibtex-doi-doctor.py --version
```

The `bibtex-doi-doctor.py` script at the top of the repository runs the code in `src/` directly.

### D. For development

```sh
git clone https://github.com/MooersLab/bibtex-doi-doctor-py.git
cd bibtex-doi-doctor-py
make dev      # creates .venv with an editable install, pytest and ruff
make check    # lint and run the tests
```

Run `make` by itself to list all targets. See [docs/development.md](docs/development.md).

## Tutorial

This tutorial uses `examples/sample.bib`, which has seven entries.
Each entry shows one kind of problem.
Work in a scratch folder so the example stays clean.

```sh
mkdir -p ~/tmp/doi-tutorial
cp examples/sample.bib ~/tmp/doi-tutorial/
cd ~/tmp/doi-tutorial
```

(If you installed with uv or pip and have no clone, download [`examples/sample.bib`](examples/sample.bib) from GitHub instead.)

### Step 1. Repair formats offline

```sh
bibtex-doi-doctor sample.bib --no-lookup
```

The summary shows what was done.

```
Entries scanned:              7
Had a DOI field:              4
  reformatted for litdb:      3
    of which do not resolve:  0
  held no DOI (bad field):    1
  NEED HAND FIX (see report): 0
DOI taken from url/note/etc.: 1
  ...
Wrote sample-doctored.bib
Report sample-doi-report.tsv
```

Compare the two files.

```sh
diff sample.bib sample-doctored.bib
```

```diff
15c15
<   doi     = {doi:10.1107/S0907444910007493}
---
>   doi     = {10.1107/S0907444910007493}
27c27
<   doi     = {https://doi.org/10.1107/S0907444909047337}
---
>   doi     = {10.1107/S0907444909047337}
40c40
<   doi     = {0.1093/nar/28.1.235}
---
>   doi     = {10.1093/nar/28.1.235}
44a45
>   doi = {10.1107/S0907444910045749},
```

Four things happened.

1. The Coot entry lost its `doi:` prefix.
2. The XDS entry lost its `https://doi.org/` prefix.
3. The Protein Data Bank entry had lost the leading `1` of its DOI. The tool put it back.
4. The CCP4 entry had no DOI field, but its `url` field pointed to a Wiley PDF link that contained the DOI. The tool pulled the DOI out, dropped the `?download=true` tail, and added a `doi` line just after the citekey.

Nothing else in the file changed.
The comments at the top of the file and the `@string{actad = ...}` line are untouched.

### Step 2. Read the report

```sh
column -t -s$'\t' sample-doi-report.tsv
```

| citekey | action | old | new |
|---------|--------|-----|-----|
| Berman2000ProteinDataBank | reformatted | 0.1093/nar/28.1.235 | 10.1093/nar/28.1.235 |
| Emsley2010FeaturesDevelopmentCoot | reformatted | doi:10.1107/S0907444910007493 | 10.1107/S0907444910007493 |
| Jumper2021HighlyAccurateProteinStructurePrediction | bad-doi-field | ISSN: 0028-0836 | |
| Kabsch2010Xds | reformatted | https://doi.org/10.1107/S0907444909047337 | 10.1107/S0907444909047337 |
| Winn2011OverviewCcp4SuiteCurrentDevelopments | from-url (not verified) | | 10.1107/S0907444910045749 |

The AlphaFold entry has an ISSN where its DOI should be.
An offline run can only report that.
Two entries still have no DOI.
The next step fixes both.
[docs/report.md](docs/report.md) explains every action.

### Step 3. Look up missing DOIs at Crossref

Run the tool again without `--no-lookup`. Provide Crossref with an email address so your requests go to its faster "polite pool".

```sh
bibtex-doi-doctor sample.bib --mailto you@example.edu
```

```
Using you@example.edu for the Crossref polite pool
Checking 4 DOIs at doi.org ...
Looking up 2 entries at Crossref ...
...
Crossref lookups:             2
  DOI found and verified:     2
  Candidates to review:       0
  ...
Skipped by entry type:        1
```

Now `sample-doctored.bib` also has these changes.

- The PHENIX entry gained `doi = {10.1107/S0907444909052925}`. Crossref matched its title, first author (Adams) and year (2010), and doi.org confirmed the DOI.
- The AlphaFold entry's `ISSN: 0028-0836` was replaced with `10.1038/s41586-021-03819-2`.
- The `@misc` entry for the litdb repository was skipped. Entry types such as `misc` are not looked up unless you pass `--types all`, because Crossref seldom has them.

This time, we also checked all four DOIs from Step 1 at doi.org.

When the title, year, or author do not all agree, the DOI is not written.
It appears in the report as a `candidate` alongside the Crossref title, so you can decide.

### Step 4. Run it on your own library

```sh
cd ~/globalbibtex

# 1. Fast offline repair. Fix any "NEEDS HAND FIX" rows by hand.
bibtex-doi-doctor global.bib --no-lookup
grep 'HAND FIX' global-doi-report.tsv

# 2. Trial run with 50 Crossref lookups. Skim the report.
bibtex-doi-doctor global.bib --limit 50

# 3. Full run. Several thousand lookups take an hour or two.
#    Ctrl-C is safe: the next run continues from the cache.
bibtex-doi-doctor global.bib

# 4. Review the candidates, then replace the library (a backup is made).
grep candidate global-doi-report.tsv
bibtex-doi-doctor global.bib --in-place
```

Step 4 is quick because every answer comes from `global-doi-cache.json`.
If you keep `global.bib` under git, `git diff` shows exactly which DOI lines changed.

### Step 5. Load the library into litdb

```sh
cd ~/global-litdb
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 litdb add ~/globalbibtex/global.bib
```

See [docs/litdb.md](docs/litdb.md) for why the Hugging Face variables matter and what to do with entries that have no DOI.

## Command summary

```
bibtex-doi-doctor BIBFILE [-o OUT] [--in-place] [--no-lookup] [--drop-bad]
                  [--types LIST|all] [--limit N] [--threshold 0.92]
                  [--candidate-floor 0.80] [--workers 4] [--mailto EMAIL]
```

The full reference is in [docs/usage.md](docs/usage.md).

## Documentation

- [docs/usage.md](docs/usage.md). Every option, the output files, and exit codes.
- [docs/report.md](docs/report.md). What each report action means and what to do about it.
- [docs/how-it-works.md](docs/how-it-works.md). The three passes, the matching rules, and the code layout.
- [docs/litdb.md](docs/litdb.md). A workflow for loading a large library into litdb.
- [docs/development.md](docs/development.md). Build targets, run tests, and release.
- [CHANGELOG.md](CHANGELOG.md).

## Related repositories

- [litdb](https://github.com/jkitchin/litdb). The literature database that this tool prepares BibTeX files for.

## Funding
- NIH: R01 CA242845
- NIH: P30 CA225520 (PI: R. Mannel);
- P30GM145423 (PI: A. West)
  
