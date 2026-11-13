"""Command-line interface and the main repair pipeline.

The pipeline has three passes.

1. Scan every entry. Repair the format of existing DOI fields, flag doi
   fields that hold no DOI, and pull DOIs out of url, note and similar fields.
2. Check the rewritten and pulled-out DOIs at doi.org.
3. Ask Crossref about entries that still lack a DOI, and accept only strong
   matches that doi.org also confirms.

All changes are collected as text edits and applied from the end of the file
backwards, so every byte outside the DOI fields stays the same.
"""

import argparse
import concurrent.futures as cf
import datetime as dt
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .bibscan import field_indent, scan_entries
from .doi import DOI_RE, extract_doi, is_litdb_ready, leftover_text
from .matching import delatex, first_author_last, norm, score_candidate, year_of
from .network import Cache, Net

# Entry types for which a Crossref lookup is worth trying.
DEFAULT_TYPES = frozenset({
    "article", "inproceedings", "conference", "incollection", "inbook",
    "book", "proceedings", "techreport", "phdthesis", "mastersthesis",
})

# Fields in which a DOI sometimes hides when the doi field is missing.
HARVEST_FIELDS = ("url", "note", "eprint", "howpublished", "annote", "annotation")

COUNT_KEYS = (
    "entries", "had_doi", "reformatted", "reformat_unres", "bad", "manual",
    "harvested", "harvest_unres", "lookups", "found", "candidate", "nomatch",
    "skipped_type", "error", "unresolvable",
)


@dataclass
class Options:
    """Settings for one run. The command line fills these in."""

    #: Contact Crossref and doi.org. False means format repair only.
    lookup: bool = True
    #: Rename doi fields that hold no DOI to ``baddoi`` when no DOI is found.
    drop_bad: bool = False
    #: Entry types to look up at Crossref. An empty frozenset means every type.
    types: frozenset = DEFAULT_TYPES
    #: Look up at most this many entries. 0 means no limit.
    limit: int = 0
    #: Title similarity (0 to 1) needed to accept a Crossref match.
    threshold: float = 0.92
    #: Weaker matches down to this similarity are reported as candidates.
    candidate_floor: float = 0.80
    #: Number of parallel requests. All workers share one rate limit.
    workers: int = 4


@dataclass
class Result:
    """What a run produced."""

    #: The repaired BibTeX text.
    text: str
    #: Report rows as ``(citekey, action, old, new, detail)`` tuples, sorted by citekey.
    report: list = field(default_factory=list)
    #: Tallies such as ``reformatted``, ``found`` and ``candidate``, as shown in the summary.
    counts: dict = field(default_factory=lambda: dict.fromkeys(COUNT_KEYS, 0))


def lookup(entry, net, cache, threshold=0.92, candidate_floor=0.80):
    """Ask Crossref for a DOI for ``entry``. Returns a result dict.

    ``status`` is one of found, candidate, unresolvable, no-match, no-title,
    title-too-short or error. Network errors are not cached, so a later run
    tries again.
    """
    title = entry.get("title") or entry.get("booktitle")
    if not title:
        return {"status": "no-title"}
    ntitle = norm(title)
    if len(ntitle) < 12:
        return {"status": "title-too-short"}
    author_last = first_author_last(entry.get("author") or entry.get("editor"))
    year = year_of(entry)

    ckey = f"{entry.key}|{ntitle}"
    if ckey in cache:
        return cache.get(ckey)

    try:
        items = net.crossref(delatex(title), author_last, year)
    except Exception as exc:  # noqa: BLE001 - any network failure
        return {"status": "error", "detail": str(exc)}

    best = None
    for item in items:
        ratio, year_ok, author_ok = score_candidate(item, ntitle, author_last, year)
        if best is None or ratio > best[0]:
            best = (ratio, year_ok, author_ok, item)

    if best is None:
        res = {"status": "no-match"}
    else:
        ratio, year_ok, author_ok, item = best
        doi = extract_doi(item.get("DOI", ""))
        info = {
            "doi": doi,
            "score": round(ratio, 3),
            "crossref_title": (item.get("title") or [""])[0][:150],
        }
        if doi and ratio >= threshold and year_ok and author_ok:
            try:
                ok = net.doi_resolves(doi)
            except Exception as exc:  # noqa: BLE001
                return {"status": "error", "detail": str(exc)}
            res = dict(info, status="found" if ok else "unresolvable")
        elif doi and ratio >= candidate_floor:
            why = [w for w, bad in (("title", ratio < threshold),
                                    ("year", not year_ok),
                                    ("author", not author_ok)) if bad]
            res = dict(info, status="candidate", detail="weak " + "+".join(why))
        else:
            res = {"status": "no-match", "score": round(ratio, 3)}
    cache[ckey] = res
    return res


def doctor(text, opts=None, net=None, cache=None, log=None):
    """Repair the BibTeX ``text`` and return a ``Result``.

    ``net`` is a ``Net`` (or any object with ``crossref`` and
    ``doi_resolves`` methods). Leave it None to work offline. ``cache`` is a
    ``Cache`` or a plain dict. ``log`` is a function for progress messages.
    """
    opts = opts or Options()
    cache = cache if cache is not None else {}
    log = log or (lambda msg: None)
    if not opts.lookup:
        net = None

    entries = list(scan_entries(text))
    res = Result(text=text)
    counts, report = res.counts, res.report
    counts["entries"] = len(entries)

    edits = []      # ("span", start, end, text) or ("insert", entry, doi)
    to_verify = []  # (entry, doi, kind, field name)
    to_lookup = []  # (entry, mode) where mode is "insert" or "replace"
    bad_fields = {}

    def want_lookup(e):
        if net is None:
            return False
        if opts.types and e.type not in opts.types:
            counts["skipped_type"] += 1
            return False
        return True

    # Pass 1: existing DOI fields, and DOIs hiding in other fields
    for e in entries:
        f = e.fields.get("doi")
        if f and f["value"].strip():
            counts["had_doi"] += 1
            old = f["value"]
            if is_litdb_ready(old.strip()):
                continue
            new = extract_doi(old)
            if new:
                extra = leftover_text(old, new)
                if "@" in extra or "=" in extra or len(extra) > 60:
                    counts["manual"] += 1
                    report.append((e.key, "NEEDS HAND FIX (other text in doi field)",
                                   old, new, "not changed"))
                    continue
                edits.append(("span", f["vstart"], f["vend"], "{" + new + "}"))
                counts["reformatted"] += 1
                detail = f"removed: {extra}" if extra else ""
                if not DOI_RE.search(old):
                    detail = "restored leading 1"
                report.append((e.key, "reformatted", old, new, detail))
                to_verify.append((e, new, "reformatted", "doi"))
            else:
                counts["bad"] += 1
                bad_fields[e.key] = e
                report.append((e.key, "bad-doi-field", old, "", ""))
                if want_lookup(e):
                    to_lookup.append((e, "replace"))
            continue

        harvested, hname = None, None
        for name in HARVEST_FIELDS:
            value = e.get(name)
            if value:
                harvested = extract_doi(value, from_url=True)
                if harvested:
                    hname = name
                    break
        if harvested:
            counts["harvested"] += 1
            if net is None:
                edits.append(("insert", e, harvested))
                report.append((e.key, f"from-{hname} (not verified)", "", harvested, ""))
            else:
                to_verify.append((e, harvested, "harvest", hname))
            continue

        if want_lookup(e):
            to_lookup.append((e, "insert"))

    # Pass 2: check DOIs that were rewritten or pulled out of other fields
    if net is not None and to_verify:
        log(f"Checking {len(to_verify)} DOIs at doi.org ...")

        def resolves(doi):
            key = f"resolve|{doi}"
            if key not in cache:
                try:
                    cache[key] = net.doi_resolves(doi)
                except Exception:  # noqa: BLE001
                    return None  # unknown because of network trouble
            return cache.get(key)

        with cf.ThreadPoolExecutor(max_workers=opts.workers) as pool:
            results = list(pool.map(lambda t: resolves(t[1]), to_verify))
        for (e, doi, kind, fname), ok in zip(to_verify, results):
            if kind == "harvest":
                if ok:
                    edits.append(("insert", e, doi))
                    report.append((e.key, f"from-{fname}", "", doi, "verified"))
                else:
                    counts["harvest_unres"] += 1
                    report.append((e.key, f"from-{fname} rejected", "", doi,
                                   "does not resolve" if ok is False else "network error"))
                    if want_lookup(e):
                        to_lookup.append((e, "insert"))
            elif ok is False:
                counts["reformat_unres"] += 1
                report.append((e.key, "reformatted but DOES NOT RESOLVE", "", doi,
                               "check by hand"))
        counts["harvested"] -= counts["harvest_unres"]

    if opts.limit:
        to_lookup = to_lookup[:opts.limit]
    counts["lookups"] = len(to_lookup)

    # Pass 3: Crossref lookups
    if net is not None and to_lookup:
        log(f"Looking up {len(to_lookup)} entries at Crossref ...")
        done = 0
        with cf.ThreadPoolExecutor(max_workers=opts.workers) as pool:
            futs = {
                pool.submit(lookup, e, net, cache, opts.threshold,
                            opts.candidate_floor): (e, mode)
                for e, mode in to_lookup
            }
            for fut in cf.as_completed(futs):
                e, mode = futs[fut]
                r = fut.result()
                st = r["status"]
                if st == "found":
                    counts["found"] += 1
                    if mode == "replace":
                        f = e.fields["doi"]
                        edits.append(("span", f["vstart"], f["vend"], "{" + r["doi"] + "}"))
                        bad_fields.pop(e.key, None)
                    else:
                        edits.append(("insert", e, r["doi"]))
                    action = "found (replaced bad field)" if mode == "replace" else "found"
                    report.append((e.key, action, "", r["doi"],
                                   f"score={r['score']} | {r.get('crossref_title', '')}"))
                elif st == "candidate":
                    counts["candidate"] += 1
                    report.append((e.key, "candidate (not written)", "", r["doi"],
                                   f"score={r['score']} {r.get('detail', '')} | "
                                   f"{r.get('crossref_title', '')}"))
                elif st == "unresolvable":
                    counts["unresolvable"] += 1
                    report.append((e.key, "unresolvable (not written)", "", r["doi"], ""))
                elif st == "error":
                    counts["error"] += 1
                    report.append((e.key, "error", "", "", r.get("detail", "")))
                else:
                    counts["nomatch"] += 1
                done += 1
                if done % 100 == 0:
                    if hasattr(cache, "save"):
                        cache.save()
                    log(f"  {done}/{len(to_lookup)}")

    if opts.drop_bad:
        for e in bad_fields.values():
            f = e.fields["doi"]
            edits.append(("span", f["name_start"], f["name_start"] + 3, "baddoi"))

    res.text = apply_edits(text, edits)
    report.sort()
    return res


def apply_edits(text, edits):
    """Apply span replacements and DOI insertions, last position first."""
    resolved = []
    for ed in edits:
        if ed[0] == "insert":
            _, e, doi = ed
            indent = field_indent(text, e)
            nl = "\r\n" if "\r\n" in text[e.start:e.end] else "\n"
            resolved.append((e.header_end, e.header_end, f"{nl}{indent}doi = {{{doi}}},"))
        else:
            resolved.append(ed[1:])
    resolved.sort(key=lambda t: t[0], reverse=True)
    for start, end, rep in resolved:
        text = text[:start] + rep + text[end:]
    return text


def write_report(path, report):
    """Write the report rows as a tab-separated file."""
    with Path(path).open("w", encoding="utf-8") as fh:
        fh.write("citekey\taction\told\tnew\tdetail\n")
        for row in report:
            cells = (str(c).replace("\t", " ").replace("\r", " ").replace("\n", " ")
                     for c in row)
            fh.write("\t".join(cells) + "\n")


def summary(counts, out, report_path):
    """Human-readable summary of a run."""
    c = counts
    return f"""
Entries scanned:              {c['entries']}
Had a DOI field:              {c['had_doi']}
  reformatted for litdb:      {c['reformatted']}
    of which do not resolve:  {c['reformat_unres']}
  held no DOI (bad field):    {c['bad']}
  NEED HAND FIX (see report): {c['manual']}
DOI taken from url/note/etc.: {c['harvested']}
  rejected (did not resolve): {c['harvest_unres']}
Crossref lookups:             {c['lookups']}
  DOI found and verified:     {c['found']}
  candidates to review:       {c['candidate']}
  found but not resolvable:   {c['unresolvable']}
  no match:                   {c['nomatch']}
  network errors (retry):     {c['error']}
Skipped by entry type:        {c['skipped_type']}

Wrote {out}
Report {report_path}"""


def find_mailto():
    """Email for the Crossref polite pool, taken from a litdb.toml if one exists."""
    for toml in (Path("litdb.toml"), Path.home() / "global-litdb" / "litdb.toml"):
        try:
            m = re.search(r'email\s*=\s*"([^"]+)"', toml.read_text())
        except OSError:
            continue
        if m:
            return m.group(1)
    return None


def build_parser():
    ap = argparse.ArgumentParser(
        prog="bibtex-doi-doctor",
        description="Repair DOI fields for litdb and look up missing DOIs via Crossref.",
        epilog="Outputs go next to the input: <stem>-doctored.bib, "
               "<stem>-doi-report.tsv and <stem>-doi-cache.json.",
    )
    ap.add_argument("bibfile", help="BibTeX file to repair")
    ap.add_argument("-o", "--output", help="output .bib (default <stem>-doctored.bib)")
    ap.add_argument("--in-place", action="store_true",
                    help="overwrite the input after writing a timestamped backup")
    ap.add_argument("--no-lookup", action="store_true",
                    help="only repair existing DOI fields; no network")
    ap.add_argument("--drop-bad", action="store_true",
                    help="rename doi fields that hold no DOI to 'baddoi'")
    ap.add_argument("--types", default=",".join(sorted(DEFAULT_TYPES)),
                    help="comma list of entry types to look up, or 'all'")
    ap.add_argument("--limit", type=int, default=0,
                    help="look up at most N entries (for a trial run)")
    ap.add_argument("--threshold", type=float, default=0.92,
                    help="title similarity needed to accept a Crossref match (default 0.92)")
    ap.add_argument("--candidate-floor", type=float, default=0.80,
                    help="report weaker matches as candidates for review (default 0.80)")
    ap.add_argument("--workers", type=int, default=4, help="parallel requests (default 4)")
    ap.add_argument("--mailto", default=None,
                    help="email for the Crossref polite pool (default: from litdb.toml)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return ap


def main(argv=None, net_factory=Net):
    """Run the command line. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    src = Path(args.bibfile).expanduser()
    if not src.is_file():
        print(f"bibtex-doi-doctor: no such file: {src}", file=sys.stderr)
        return 2
    stem = src.with_suffix("")
    out = Path(args.output).expanduser() if args.output else Path(f"{stem}-doctored.bib")
    report_path = Path(f"{stem}-doi-report.tsv")
    cache_path = Path(f"{stem}-doi-cache.json")

    types_arg = args.types.strip().lower()
    opts = Options(
        lookup=not args.no_lookup,
        drop_bad=args.drop_bad,
        types=frozenset() if types_arg == "all"
        else frozenset(t.strip() for t in types_arg.split(",") if t.strip()),
        limit=args.limit,
        threshold=args.threshold,
        candidate_floor=args.candidate_floor,
        workers=args.workers,
    )

    net = None
    if opts.lookup:
        mailto = args.mailto if args.mailto is not None else find_mailto()
        net = net_factory(mailto)
        if mailto:
            print(f"Using {mailto} for the Crossref polite pool", file=sys.stderr)

    # surrogateescape keeps any bytes that are not valid UTF-8 exactly as they were
    text = src.read_bytes().decode("utf-8", errors="surrogateescape")
    cache = Cache(cache_path)
    res = doctor(text, opts, net, cache, log=lambda m: print(m, file=sys.stderr))
    if net is not None:
        cache.save()

    if args.in_place:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = src.with_name(f"{src.name}.{stamp}.bak")
        shutil.copy2(src, backup)
        out = src
        print(f"Backup written to {backup}", file=sys.stderr)
    out.write_bytes(res.text.encode("utf-8", errors="surrogateescape"))
    write_report(report_path, res.report)
    print(summary(res.counts, out, report_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
