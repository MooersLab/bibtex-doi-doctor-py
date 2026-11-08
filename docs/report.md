# Reading the report

Every run writes `<stem>-doi-report.tsv`, a tab-separated table sorted by citekey. Open it in a spreadsheet, or search it with `grep`. It has five columns.

| Column | Meaning |
|--------|---------|
| `citekey` | The entry's key. |
| `action` | What happened. See the table below. |
| `old` | The previous value of the doi field, when there was one. |
| `new` | The DOI that was written or proposed. |
| `detail` | The match score, the Crossref title, or a note. |

Entries that needed no change do not appear.

## Actions

| Action | Written? | What to do |
|--------|----------|------------|
| `reformatted` | yes | Nothing. The detail column says `restored leading 1` when the DOI had lost its first digit, or `removed: ...` when extra text such as an article number was dropped. |
| `reformatted but DOES NOT RESOLVE` | yes | The field was cleaned, but doi.org does not know the DOI. It may have a typo. Check it by hand. |
| `bad-doi-field` | no | The doi field holds no DOI at all (an ISSN, a placeholder such as `${2:ReplaceMe}`, or `00`). If a Crossref match is found, a second row says `found (replaced bad field)`. Otherwise fix it by hand, or use `--drop-bad`. |
| `NEEDS HAND FIX (other text in doi field)` | no | The field contains a DOI plus a lot of other text, often a whole second entry pasted by accident. The tool will not delete text it does not understand. Move the extra text out and run again. |
| `from-url`, `from-note`, ... | yes | A DOI was recovered from that field and confirmed at doi.org. |
| `from-url (not verified)` | yes | The same, but from a `--no-lookup` run, so doi.org was not asked. |
| `from-url rejected` | no | The recovered string did not resolve at doi.org. The entry is then sent to Crossref instead. |
| `found` | yes | Crossref returned a strong match, and doi.org confirmed it. The detail column shows the score and the Crossref title. |
| `found (replaced bad field)` | yes | The same, for an entry whose doi field held something that was not a DOI. |
| `candidate (not written)` | no | A possible match that failed one check. The detail column says which one (`weak title`, `weak year` or `weak author`) and shows the Crossref title. Compare it with your entry and copy the DOI by hand if it is right. |
| `unresolvable (not written)` | no | Crossref offered a DOI that doi.org does not know. This is rare. |
| `error` | no | A network problem. Run the tool again. Errors are not cached, so only these entries are retried. |

Entries for which Crossref returned nothing useful are counted as "no match" in the summary but get no report row, which keeps the report short.

## Useful one-liners

```sh
# Everything that needs a person to look at it
grep -E 'HAND FIX|candidate|DOES NOT RESOLVE|bad-doi-field' global-doi-report.tsv

# Candidates, sorted by score (highest first)
grep candidate global-doi-report.tsv | sort -t$'\t' -k5 -r | less -S

# How many rows of each kind
cut -f2 global-doi-report.tsv | sort | uniq -c | sort -rn
```
