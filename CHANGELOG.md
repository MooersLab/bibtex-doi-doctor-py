# Changelog

## 0.1.0 (2026-11-08)

First packaged release.

- Repairs DOI fields so that litdb accepts them. Handles `doi:`, `DOI `,
  `https://doi.org/`, `dx.doi.org`, `ARTN` prefixes, trailing punctuation,
  and DOIs that lost their leading `1`.
- Keeps old Wiley SICI DOIs intact (they contain `<`, `>` and `;`).
- Flags a doi field that has other text pasted into it and leaves it unchanged.
- Recovers DOIs from `url`, `note`, `eprint`, `howpublished`, `annote` and
  `annotation` fields, removing publisher download tails.
- Looks up missing DOIs at Crossref and accepts a match only when title, year
  and first author agree. Weaker matches are listed as candidates.
- Checks every new or recovered DOI at doi.org before writing it.
- Changes only DOI fields and leaves every other byte of the file as it was.
- Caches lookups so that an interrupted run can resume.
- Installable package with a `bibtex-doi-doctor` command, a Makefile, a test
  suite and documentation.
- Fixed: the LaTeX cleaner read `\textit` as the tie accent `\t`, which spoiled
  title matching for titles with italics.
