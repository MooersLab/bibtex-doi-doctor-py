# Using bibtex-doi-doctor with litdb

[litdb](https://github.com/jkitchin/litdb) adds the entries of a BibTeX file by looking up each DOI at OpenAlex.

```sh
litdb add ~/globalbibtex/global.bib
```

litdb uses only entries that have a `doi` field, and its `add_bibtex()` function accepts a value only when it starts with `10` or `http`. Anything else is skipped with a message such as:

```
I do not know what to do with "doi:10.1107/S0907444905005743"
```

Entries without a DOI are skipped silently. In one 12,390-entry library, about 7,000 entries had no DOI, so litdb could not see more than half of the library.

## Recommended order

1. **Repair formats first.** This step is fast and needs no network.

   ```sh
   bibtex-doi-doctor ~/globalbibtex/global.bib --no-lookup
   ```

   Read the report for rows marked `NEEDS HAND FIX` and fix those entries in `global.bib`.

2. **Fill in missing DOIs.** Do a trial run, read the report, then do the full run.

   ```sh
   bibtex-doi-doctor ~/globalbibtex/global.bib --limit 50
   bibtex-doi-doctor ~/globalbibtex/global.bib
   ```

3. **Replace the library** once you are satisfied.

   ```sh
   bibtex-doi-doctor ~/globalbibtex/global.bib --in-place
   ```

   This run is quick because every lookup comes from the cache.

4. **Load into litdb.** Run this from the folder that holds `litdb.toml`, with Hugging Face offline mode on, so that litdb does not query the Hub once per entry.

   ```sh
   cd ~/global-litdb
   HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 litdb add ~/globalbibtex/global.bib
   ```

## Entries that stay without a DOI

Books from small publishers, theses, software, web pages and older conference papers often have no DOI. litdb cannot add those from a BibTeX file. You can still add them to litdb as PDFs or URLs, for example `litdb add paper.pdf`.
