# Tutorial

This tutorial uses `examples/sample.bib`, a file with seven entries. Each entry shows one kind of problem. By the end you will have repaired it offline, read the report, filled in the missing DOIs from Crossref, and seen the safe way to run the tool on a large library.

## Set up a scratch folder

Work on a copy, so the example stays clean.

```console
$ mkdir -p ~/tmp/doi-tutorial
$ cp examples/sample.bib ~/tmp/doi-tutorial/
$ cd ~/tmp/doi-tutorial
```

If you installed with uv or pip and have no clone, download [`sample.bib`](https://github.com/MooersLab/bibtex-doi-doctor-py/blob/main/examples/sample.bib) from GitHub instead.

The seven entries are these.

| Citekey | Problem |
|---------|---------|
| `Emsley2010FeaturesDevelopmentCoot` | DOI written as `doi:10.1107/...` |
| `Kabsch2010Xds` | DOI written as a full `https://doi.org/...` URL |
| `Berman2000ProteinDataBank` | DOI lost its leading `1` (`0.1093/nar/28.1.235`) |
| `Winn2011OverviewCcp4SuiteCurrentDevelopments` | No doi field, but the DOI is inside a Wiley PDF link |
| `Adams2010PhenixComprehensivePythonBasedSystem` | No DOI anywhere |
| `Jumper2021HighlyAccurateProteinStructurePrediction` | doi field holds an ISSN |
| `Litdb2026Repository` | A `@misc` web page with no DOI |

## Step 1. Repair formats offline

```console
$ bibtex-doi-doctor sample.bib --no-lookup
```

The summary lists what was done.

```text
Entries scanned:              7
Had a DOI field:              4
  reformatted for litdb:      3
    of which do not resolve:  0
  held no DOI (bad field):    1
  NEED HAND FIX (see report): 0
DOI taken from url/note/etc.: 1
  rejected (did not resolve): 0
Crossref lookups:             0
  ...
Wrote sample-doctored.bib
Report sample-doi-report.tsv
```

Compare the input with the output.

```console
$ diff sample.bib sample-doctored.bib
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
2. The XDS entry lost its `https://doi.org/` prefix. litdb would have accepted this one, but the bare form is cleaner and consistent.
3. The Protein Data Bank entry got back the leading `1` of its DOI.
4. The CCP4 entry had no doi field. Its `url` field pointed to `https://onlinelibrary.wiley.com/doi/pdf/10.1107/S0907444910045749?download=true`. The tool pulled out the DOI, dropped the `?download=true` tail, and added a `doi` line just after the citekey, using the same indentation as the entry's other fields.

Nothing else changed. The comments at the top of the file and the `@string{actad = ...}` line are untouched.

## Step 2. Read the report

```console
$ column -t -s$'\t' sample-doi-report.tsv
```

| citekey | action | old | new |
|---------|--------|-----|-----|
| Berman2000ProteinDataBank | reformatted | 0.1093/nar/28.1.235 | 10.1093/nar/28.1.235 |
| Emsley2010FeaturesDevelopmentCoot | reformatted | doi:10.1107/S0907444910007493 | 10.1107/S0907444910007493 |
| Jumper2021HighlyAccurateProteinStructurePrediction | bad-doi-field | ISSN: 0028-0836 | |
| Kabsch2010Xds | reformatted | https://doi.org/10.1107/S0907444909047337 | 10.1107/S0907444909047337 |
| Winn2011OverviewCcp4SuiteCurrentDevelopments | from-url (not verified) | | 10.1107/S0907444910045749 |

The AlphaFold entry has an ISSN where its DOI should be. An offline run can only report that. The PHENIX entry has no DOI anywhere, so it does not appear at all. The next step fixes both. {doc}`report` explains every action you can meet in a report.

## Step 3. Look up missing DOIs at Crossref

Run the tool again without `--no-lookup`. Give Crossref an email address so your requests go to its faster "polite pool". If you use litdb, the tool reads the address from your `litdb.toml` automatically.

```console
$ bibtex-doi-doctor sample.bib --mailto you@example.edu
```

```text
Using you@example.edu for the Crossref polite pool
Checking 4 DOIs at doi.org ...
Looking up 2 entries at Crossref ...
...
Crossref lookups:             2
  DOI found and verified:     2
  candidates to review:       0
  ...
Skipped by entry type:        1
```

Now `sample-doctored.bib` has two more changes.

- The PHENIX entry gained `doi = {10.1107/S0907444909052925}`. Crossref matched its title, first author (Adams) and year (2010), and doi.org confirmed the DOI.
- The AlphaFold entry's `ISSN: 0028-0836` was replaced with `10.1038/s41586-021-03819-2`.

Also, the four DOIs from Step 1 were checked at doi.org this time, and the `@misc` web page was skipped. Types such as `misc` are not looked up unless you pass `--types all`, because Crossref seldom has them and a wrong match is more likely.

:::{note}
When the title, the year or the author does not agree, the DOI is **not** written. It goes into the report as a `candidate`, together with the Crossref title, so that you can decide. A missed DOI costs one manual lookup. A wrong DOI silently attaches the wrong paper to your citation.
:::

## Step 4. Run it on your own library

The same steps scale to a large library. The example below uses `~/globalbibtex/global.bib`.

```console
$ cd ~/globalbibtex
$ bibtex-doi-doctor global.bib --no-lookup        # 1. offline repair, seconds
$ grep 'HAND FIX' global-doi-report.tsv           #    fix these entries by hand
$ bibtex-doi-doctor global.bib --limit 50         # 2. trial run; skim the report
$ bibtex-doi-doctor global.bib                    # 3. full run; an hour or two
$ grep candidate global-doi-report.tsv            # 4. review the close calls
$ bibtex-doi-doctor global.bib --in-place         # 5. replace the library
```

Step 3 can be stopped with Ctrl-C at any time. The next run continues from `global-doi-cache.json`. Step 5 is quick for the same reason, because every answer is already cached. It writes `global.bib.<date-time>.bak` before it overwrites the library.

If you keep the library under git, `git diff global.bib` then shows exactly which DOI lines changed.

## Step 5. Load the library into litdb

```console
$ cd ~/global-litdb
$ HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 litdb add ~/globalbibtex/global.bib
```

{doc}`litdb` explains the Hugging Face variables and what to do with entries that still have no DOI.

## Next steps

- {doc}`usage` lists every option.
- {doc}`faq` answers common questions, such as why a DOI you know exists was not written.
- {doc}`how-it-works` explains the matching rules.
