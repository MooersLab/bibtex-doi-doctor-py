# Frequently asked questions

## Will it change anything besides DOIs?

No. The tool records where each DOI field sits in the file and edits only those characters, plus one inserted `doi = {...},` line for an entry that gains a DOI. Everything else, including bytes that are not valid UTF-8, is written back unchanged. The test suite checks this. {doc}`how-it-works` explains how.

## Can I undo a run?

Without `--in-place`, the input is never touched, so there is nothing to undo. With `--in-place`, the original is saved as `<file>.<YYYYMMDD-HHMMSS>.bak` next to it. Copy that file back to undo the run.

## Why was a DOI I know exists not written?

Look the citekey up in the report.

- **`candidate (not written)`.** Crossref found something, but one check failed. The detail column names it. `weak title` usually means the BibTeX title differs from the published title (an old working title, a missing subtitle, or a typo). `weak year` means the years differ by more than one. `weak author` means the first author's last name is spelled differently, or the first author in your entry is not the first author at Crossref.
- **No row at all.** Crossref returned nothing close enough, or the entry was skipped. Check the summary for "Skipped by entry type" (see `--types`) and remember that titles shorter than twelve letters, such as `{XDS}`, are not looked up.
- **`error`.** A network problem. Run the tool again.

You can lower `--threshold` (for example to `0.88`), but read the extra matches carefully. Delete the cache file first, because cached answers were judged with the old threshold.

## How long does a large library take?

Format repair takes seconds, even for 12,000 entries. Lookups run at about eight requests per second in total, and each looked-up entry needs one Crossref request and usually one doi.org check. Several thousand entries therefore take an hour or two. A second run over the same file takes seconds because answers are cached.

## Do I need to give an email address?

No, but it helps. Crossref puts requests that include a contact address into its "polite pool", which is faster and more reliable when the service is busy. The tool takes the address from `--mailto`, or from the `email` line under `[openalex]` in a `litdb.toml` in the current folder or in `~/global-litdb`. The address is sent only to Crossref and doi.org, in the User-Agent header and the `mailto` query parameter.

## What does "NEEDS HAND FIX" mean?

The doi field contains a DOI plus a lot of other text. In practice this is usually a whole second BibTeX entry pasted into the field by accident. The tool does not delete text it cannot account for, so it leaves the field alone. Open the entry, move the extra text out (often into an entry of its own), and run the tool again.

## Why are some doi fields renamed to `baddoi`?

Only when you pass `--drop-bad`. A doi field that holds no DOI (an ISSN, `00`, or an editor snippet placeholder such as `${2:ReplaceMe}`) makes litdb print a warning. Renaming the field keeps the text for you to inspect while letting litdb skip it quietly. If Crossref finds the real DOI, the field is fixed instead of renamed.

## Does it handle old Wiley "SICI" DOIs?

Yes. DOIs such as `10.1002/(SICI)1096-987X(199709)18:12<1463::AID-JCC4>3.0.CO;2-H` contain `<`, `>`, `;` and parentheses. They are recognized whole and left as they are.

## Can I use it from Python?

Yes. The core function, `doctor()`, takes and returns text and does no file input or output. See {doc}`api`.

## Does it work on Windows?

It should, because it is pure Python. The file is read and written as bytes, so Windows line endings are kept, and an inserted doi line uses the entry's own line ending. The automated tests run on Linux and macOS only.
