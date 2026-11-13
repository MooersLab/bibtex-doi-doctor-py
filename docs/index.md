# bibtex-doi-doctor

**bibtex-doi-doctor** repairs the DOI fields in a BibTeX library and looks up the DOIs that are missing, so that John Kitchin's [litdb](https://github.com/jkitchin/litdb) can load every entry it is able to.

litdb reads a BibTeX file by sending each entry's DOI to OpenAlex. An entry whose DOI is written as `doi:10.1107/...` is skipped with a warning. An entry with no DOI is skipped without one. In a real 12,000-entry library, more than half of the entries were invisible to litdb for one of these two reasons.

## What it does

Format repair
: Rewrites values such as `doi:10.1107/...`, `DOI 10.1107/...`, `https://dx.doi.org/10...` and `ARTN e5954 10.7717/...` to the bare form `10.xxxx/yyyy`. Restores DOIs that lost their leading `1`. Flags doi fields that hold something other than a DOI.

DOI recovery
: Finds DOIs hidden in `url`, `note` and similar fields, and removes publisher download tails such as `/asset/...pdf?v=1`.

DOI lookup
: Asks Crossref about entries that still have no DOI. A match is accepted only when the title, the year and the first author all agree, and doi.org confirms the DOI.

## What it does not do

It never rewrites the rest of your file. Comments, `@string` blocks, field order, indentation and line endings stay exactly as they were, so `git diff` shows only the DOI lines. It never overwrites the input unless you pass `--in-place`, and then it makes a backup first. It never writes a DOI it is unsure about. Close calls go into a report for you to decide.

## Quick start

```console
$ uv tool install git+https://github.com/MooersLab/bibtex-doi-doctor-py.git
$ bibtex-doi-doctor refs.bib --no-lookup     # fast, offline format repair
$ bibtex-doi-doctor refs.bib --limit 50      # trial run with 50 Crossref lookups
$ bibtex-doi-doctor refs.bib                 # full run
```

Each run writes `refs-doctored.bib` and a report, `refs-doi-report.tsv`, next to the input. Start with the {doc}`tutorial`, which walks through a seven-entry example file.

```{toctree}
:maxdepth: 1
:caption: User guide

installation
tutorial
usage
report
litdb
faq
```

```{toctree}
:maxdepth: 1
:caption: Reference

how-it-works
api
```

```{toctree}
:maxdepth: 1
:caption: Project

development
changelog
GitHub repository <https://github.com/MooersLab/bibtex-doi-doctor-py>
```

## License and funding

bibtex-doi-doctor is free software under the GNU General Public License, version 3. Development was supported by NIH grants R01 CA242845, P30 CA225520 and P30 GM145423.
