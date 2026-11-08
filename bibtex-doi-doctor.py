#!/usr/bin/env python3
"""bibtex-doi-doctor: repair and fill in DOI fields in a BibTeX file.

The script does two jobs.

1. Format repair. litdb accepts a DOI field only when it starts with '10.'
   or 'http'. Values such as 'doi:10.1107/...', 'DOI 10.1107/...',
   'doi.org/10.1093/...' or 'https://dx.doi.org/10...' are rewritten to the
   bare form '10.xxxx/yyyy'. A field that holds no DOI at all (an ISSN, say)
   is reported. With --drop-bad it is renamed to 'baddoi' so litdb skips it.

2. DOI lookup. For entries without a DOI, the script first looks for a DOI
   inside the url, note, eprint and howpublished fields. If none is there,
   it queries Crossref with the title, first author and year. A candidate is
   accepted only when the titles agree closely, the year is within one, and
   the first author's last name appears among the Crossref authors. Every
   accepted DOI is then checked at doi.org before it is written.

Only the DOI fields are touched. Every other byte of the file is kept as it
was, including comments, @string blocks, field order and indentation.

The input file is never overwritten unless you pass --in-place, which first
writes a timestamped backup. Lookups are cached in a JSON file, so you can
stop the script and run it again without repeating finished queries.

Standard library only. Python 3.8 or later.

Examples
  # Dry run on the first 50 entries that lack a DOI
  python bibtex-doi-doctor.py ~/globalbibtex/global.bib --limit 50

  # Full run, writing global-doctored.bib next to the input
  python bibtex-doi-doctor.py ~/globalbibtex/global.bib

  # Only repair the format of existing DOI fields (no network)
  python bibtex-doi-doctor.py ~/globalbibtex/global.bib --no-lookup

Outputs (next to the input file by default)
  <stem>-doctored.bib     the repaired BibTeX file
  <stem>-doi-report.tsv   one line per change, candidate, or problem
  <stem>-doi-cache.json   Crossref and doi.org results, reused on later runs
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import difflib
import json
import re
import shutil
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------
# DOI text handling
# --------------------------------------------------------------------------

# A DOI is '10.' + registrant + '/' + suffix. Old Wiley SICI DOIs contain
# '<', '>', ';' and '()', so those characters are allowed in the suffix.
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s{}\"@]+")
# Same thing with the leading '1' lost, as in '0.1038/s41467-...'.
DOI_NO_ONE_RE = re.compile(r"(?<![\w.])0\.(\d{4,9}/[^\s{}\"@]+)")

# Publisher URL tails that follow a DOI but are not part of it.
URL_TAIL_RE = re.compile(
    r"(https?:|[?#&]|/asset/|/abstract$|/full$|/fulltext$|/pdf$|/epdf$|"
    r"/pdfplus$|/meta$|/suppl\w*$|\.pdf$|/references$|/figures$).*",
    re.I)

# Entry types for which a Crossref lookup is worth trying. Use --types all to
# try every type.
DEFAULT_TYPES = {
    "article", "inproceedings", "conference", "incollection", "inbook",
    "book", "proceedings", "techreport", "phdthesis", "mastersthesis",
}

SKIP_TYPES = {"string", "comment", "preamble"}

# Fields in which a DOI sometimes hides when the doi field is missing.
HARVEST_FIELDS = ("url", "note", "eprint", "howpublished", "annote", "annotation")


def _trim(doi, from_url):
    doi = doi.rstrip(".,;:")
    if from_url:
        prev = None
        while prev != doi:
            prev = doi
            doi = URL_TAIL_RE.sub("", doi).rstrip(".,;:/")
    else:
        doi = re.split(r"https?:", doi)[0]
    # an unbalanced closing parenthesis or bracket is punctuation, not DOI
    while doi and doi[-1] in ")]" and doi.count(doi[-1]) > doi.count("(" if doi[-1] == ")" else "["):
        doi = doi[:-1]
    return doi or None


def extract_doi(text, from_url=False):
    """Return the bare DOI found in text, or None."""
    if not text:
        return None
    if from_url:
        text = urllib.parse.unquote(text)
    m = DOI_RE.search(text)
    if m:
        return _trim(m.group(0), from_url)
    m = DOI_NO_ONE_RE.search(text)
    if m:
        return _trim("10." + m.group(1), from_url)
    return None


def is_litdb_ready(value):
    """True when value is already a clean bare DOI."""
    return bool(re.fullmatch(r"10\.\d{4,9}/\S+", value or "")) and extract_doi(value) == value


def leftover_text(value, doi):
    """Text in a doi field besides the DOI and the usual prefixes."""
    rest = value.replace(doi, " ", 1)
    rest = re.sub(r"(?i)https?://(dx\.)?doi\.org/?|doi\.org/?|\bdoi\b\s*:?|\bartn\b", " ", rest)
    rest = re.sub(r"https?://\S*", " ", rest)  # a trailing publisher URL
    return rest.strip(" \t\r\n/:,;.")


# --------------------------------------------------------------------------
# Minimal BibTeX scanner that records character positions
# --------------------------------------------------------------------------

HEADER_RE = re.compile(r"@\s*([A-Za-z]+)\s*([{(])", re.M)
FIELD_NAME_RE = re.compile(r"([A-Za-z][\w:.+-]*)\s*=\s*")


def find_matching(text, start, open_ch):
    """Index of the bracket that closes text[start] (which is open_ch)."""
    close_ch = "}" if open_ch == "{" else ")"
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{" or (open_ch == "(" and c == "("):
            depth += 1
        elif c == "}" or (open_ch == "(" and c == ")"):
            depth -= 1
            if depth == 0 and c == close_ch:
                return i
        i += 1
    return -1


def parse_value(text, i):
    """Parse one field value starting at text[i].

    Returns (value_start, value_end, inner_text, end_index) where value_start
    and value_end bound the whole value including delimiters, and inner_text
    is the content without the outer braces or quotes.
    """
    n = len(text)
    parts = []
    vstart = i
    while i < n:
        c = text[i]
        if c == "{":
            j = find_matching(text, i, "{")
            if j < 0:
                return vstart, n, "".join(parts), n
            parts.append(text[i + 1:j])
            i = j + 1
        elif c == '"':
            j = i + 1
            depth = 0
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                elif text[j] == '"' and depth == 0:
                    break
                j += 1
            parts.append(text[i + 1:j])
            i = j + 1
        else:
            m = re.match(r"[^,#}\s)]+", text[i:])
            if not m:
                break
            parts.append(m.group(0))
            i += m.end()
        # string concatenation with '#'
        k = i
        while k < n and text[k] in " \t\r\n":
            k += 1
        if k < n and text[k] == "#":
            i = k + 1
            while i < n and text[i] in " \t\r\n":
                i += 1
            continue
        break
    return vstart, i, "".join(parts), i


class Entry:
    __slots__ = ("type", "key", "start", "end", "body_start", "fields", "header_end")

    def __init__(self):
        self.fields = {}  # lower name -> dict(name_start, vstart, vend, value)


def scan_entries(text):
    """Yield Entry objects with field positions."""
    pos = 0
    n = len(text)
    while True:
        m = HEADER_RE.search(text, pos)
        if not m:
            return
        etype = m.group(1).lower()
        open_idx = m.end() - 1
        close_idx = find_matching(text, open_idx, m.group(2))
        if close_idx < 0:
            return
        pos = close_idx + 1
        if etype in SKIP_TYPES:
            continue
        e = Entry()
        e.type = etype
        e.start = m.start()
        e.end = close_idx
        km = re.match(r"\s*([^,\s]+)\s*,", text[open_idx + 1:close_idx])
        if not km:
            continue
        e.key = km.group(1)
        e.header_end = open_idx + 1 + km.end()
        i = e.header_end
        while i < close_idx:
            fm = FIELD_NAME_RE.search(text, i, close_idx)
            if not fm:
                break
            name = fm.group(1).lower()
            vstart, vend, value, i = parse_value(text, fm.end())
            e.fields.setdefault(name, {
                "name_start": fm.start(), "vstart": vstart, "vend": vend,
                "value": value,
            })
            # move past the separating comma
            while i < close_idx and text[i] in " \t\r\n":
                i += 1
            if i < close_idx and text[i] == ",":
                i += 1
        yield e


# --------------------------------------------------------------------------
# Text normalisation for matching
# --------------------------------------------------------------------------

LATEX_ACCENT_RE = re.compile(r"\\[`'^\"~=.uvHtcdbk]\s*\{?([A-Za-z])\}?")
LATEX_CMD_RE = re.compile(r"\\[A-Za-z]+\*?\s*")


def delatex(s):
    s = LATEX_ACCENT_RE.sub(r"\1", s or "")
    s = s.replace("\\&", "&").replace("~", " ").replace("--", "-")
    s = LATEX_CMD_RE.sub("", s)
    s = s.replace("{", "").replace("}", "").replace("$", "")
    return re.sub(r"\s+", " ", s).strip()


def fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def norm(s):
    return re.sub(r"[^a-z0-9]", "", fold(delatex(s)).lower())


def first_author_last(author_field):
    if not author_field:
        return None
    first = re.split(r"\s+and\s+", delatex(author_field), maxsplit=1)[0].strip()
    if not first or first.lower() in {"others", "anonymous"}:
        return None
    if "," in first:
        last = first.split(",")[0]
    else:
        last = first.split()[-1]
    return norm(last) or None


def year_of(e):
    for name in ("year", "date"):
        if name in e.fields:
            m = re.search(r"(1[5-9]\d\d|20\d\d)", e.fields[name]["value"])
            if m:
                return int(m.group(1))
    return None


# --------------------------------------------------------------------------
# Network helpers
# --------------------------------------------------------------------------

class Net:
    def __init__(self, mailto, min_interval=0.12):
        ua = "bibtex-doi-doctor/1.0"
        if mailto:
            ua += f" (mailto:{mailto})"
        self.headers = {"User-Agent": ua}
        self.mailto = mailto
        self.lock = threading.Lock()
        self.last = 0.0
        self.min_interval = min_interval

    def _throttle(self):
        with self.lock:
            wait = self.last + self.min_interval - time.time()
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()

    def get_json(self, url, tries=4):
        for attempt in range(tries):
            self._throttle()
            req = urllib.request.Request(url, headers=self.headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.load(r)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None
                if exc.code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt * 2)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                time.sleep(2 ** attempt)
        raise RuntimeError(f"giving up on {url}")

    def doi_resolves(self, doi):
        url = "https://doi.org/api/handles/" + urllib.parse.quote(doi, safe="/")
        data = self.get_json(url)
        return bool(data) and data.get("responseCode") == 1

    def crossref(self, title, author_last, year, rows=5):
        q = {"query.bibliographic": title, "rows": str(rows),
             "select": "DOI,title,subtitle,author,issued,type"}
        if author_last:
            q["query.author"] = author_last
        if self.mailto:
            q["mailto"] = self.mailto
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(q)
        data = self.get_json(url)
        return (data or {}).get("message", {}).get("items", [])


def score_candidate(item, ntitle, author_last, year):
    """Return (title_ratio, year_ok, author_ok) for a Crossref item."""
    titles = item.get("title") or [""]
    subs = item.get("subtitle") or []
    best = 0.0
    for t in titles:
        options = [t] + [f"{t} {s}" for s in subs]
        for opt in options:
            r = difflib.SequenceMatcher(None, ntitle, norm(opt)).ratio()
            best = max(best, r)
    cy = None
    parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    if parts and parts[0] and parts[0][0]:
        cy = int(parts[0][0])
    year_ok = year is None or cy is None or abs(cy - year) <= 1
    families = [norm(a.get("family") or a.get("name") or "") for a in item.get("author") or []]
    author_ok = author_last is None or not families or author_last in families
    return best, year_ok, author_ok


# --------------------------------------------------------------------------
# Main work
# --------------------------------------------------------------------------

def lookup(e, net, cache, threshold, candidate_floor):
    """Find a DOI for entry e. Returns a result dict and caches it."""
    title = e.fields.get("title", {}).get("value") or e.fields.get("booktitle", {}).get("value")
    if not title:
        return {"status": "no-title"}
    ntitle = norm(title)
    if len(ntitle) < 12:
        return {"status": "title-too-short"}
    author_last = first_author_last(
        e.fields.get("author", {}).get("value") or e.fields.get("editor", {}).get("value"))
    year = year_of(e)

    ckey = f"{e.key}|{ntitle}"
    if ckey in cache:
        return cache[ckey]

    try:
        items = net.crossref(delatex(title), author_last, year)
    except Exception as exc:  # network trouble: do not cache, try next run
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
        info = {"doi": doi, "score": round(ratio, 3),
                "crossref_title": (item.get("title") or [""])[0][:150]}
        if doi and ratio >= threshold and year_ok and author_ok:
            try:
                ok = net.doi_resolves(doi)
            except Exception as exc:
                return {"status": "error", "detail": str(exc)}
            res = dict(info, status="found" if ok else "unresolvable")
        elif doi and ratio >= candidate_floor:
            why = []
            if ratio < threshold:
                why.append("title")
            if not year_ok:
                why.append("year")
            if not author_ok:
                why.append("author")
            res = dict(info, status="candidate", detail="weak " + "+".join(why))
        else:
            res = {"status": "no-match", "score": round(ratio, 3)}
    cache[ckey] = res
    return res


def field_indent(text, e):
    """Indentation used by the entry's fields."""
    for f in e.fields.values():
        line_start = text.rfind("\n", 0, f["name_start"]) + 1
        indent = text[line_start:f["name_start"]]
        if indent.strip() == "":
            return indent
    return "  "


def main():
    ap = argparse.ArgumentParser(
        description="Repair DOI fields for litdb and look up missing DOIs via Crossref.")
    ap.add_argument("bibfile")
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
                    help="title similarity needed to accept a Crossref match")
    ap.add_argument("--candidate-floor", type=float, default=0.80,
                    help="report weaker matches as candidates for review")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--mailto", default=None,
                    help="email for the Crossref polite pool (default: litdb.toml if present)")
    args = ap.parse_args()

    src = Path(args.bibfile).expanduser()
    stem = src.with_suffix("")
    out = Path(args.output).expanduser() if args.output else Path(f"{stem}-doctored.bib")
    report_path = Path(f"{stem}-doi-report.tsv")
    cache_path = Path(f"{stem}-doi-cache.json")

    mailto = args.mailto
    if mailto is None:
        for toml in (Path("litdb.toml"), Path.home() / "global-litdb" / "litdb.toml"):
            if toml.exists():
                m = re.search(r'email\s*=\s*"([^"]+)"', toml.read_text())
                if m:
                    mailto = m.group(1)
                    break

    raw = src.read_bytes()
    text = raw.decode("utf-8", errors="surrogateescape")
    entries = list(scan_entries(text))
    types = None if args.types.strip().lower() == "all" else {
        t.strip().lower() for t in args.types.split(",")}

    edits = []    # ("span", start, end, text) or ("insert", entry, doi)
    report = []   # rows for the TSV
    counts = dict(entries=len(entries), had_doi=0, reformatted=0, reformat_unres=0,
                  bad=0, manual=0, harvested=0, harvest_unres=0, found=0,
                  candidate=0, nomatch=0, skipped_type=0, error=0, unresolvable=0)
    to_verify = []   # (entry, doi, kind, field name)
    to_lookup = []   # (entry, mode) where mode is "insert" or "replace"
    bad_fields = {}  # citekey -> entry, for doi fields that hold no DOI

    def want_lookup(e):
        if args.no_lookup:
            return False
        if types is not None and e.type not in types:
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
                    # Something else (often a pasted entry) lives in this field.
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
            if name in e.fields:
                harvested = extract_doi(e.fields[name]["value"], from_url=True)
                if harvested:
                    hname = name
                    break
        if harvested:
            counts["harvested"] += 1
            if args.no_lookup:
                edits.append(("insert", e, harvested))
                report.append((e.key, f"from-{hname} (not verified)", "", harvested, ""))
            else:
                to_verify.append((e, harvested, "harvest", hname))
            continue

        if want_lookup(e):
            to_lookup.append((e, "insert"))

    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            cache = {}
    net = None if args.no_lookup else Net(mailto)

    def resolves(doi):
        key = f"resolve|{doi}"
        if key not in cache:
            try:
                cache[key] = net.doi_resolves(doi)
            except Exception:
                return None  # unknown: network trouble
        return cache[key]

    # Pass 2: check DOIs we rewrote or pulled out of other fields
    if net and to_verify:
        print(f"Checking {len(to_verify)} DOIs at doi.org ...", file=sys.stderr)
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
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
        cache_path.write_text(json.dumps(cache))

    if args.limit:
        to_lookup = to_lookup[:args.limit]

    # Pass 3: Crossref lookups
    if net and to_lookup:
        print(f"Looking up {len(to_lookup)} entries at Crossref"
              f"{' as ' + mailto if mailto else ''} ...", file=sys.stderr)
        done = 0
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(lookup, e, net, cache, args.threshold,
                                args.candidate_floor): (e, mode) for e, mode in to_lookup}
            for fut in cf.as_completed(futs):
                e, mode = futs[fut]
                res = fut.result()
                st = res["status"]
                if st == "found":
                    counts["found"] += 1
                    if mode == "replace":
                        f = e.fields["doi"]
                        edits.append(("span", f["vstart"], f["vend"], "{" + res["doi"] + "}"))
                        bad_fields.pop(e.key, None)
                    else:
                        edits.append(("insert", e, res["doi"]))
                    report.append((e.key, "found" + (" (replaced bad field)" if mode == "replace" else ""),
                                   "", res["doi"],
                                   f"score={res['score']} | {res.get('crossref_title', '')}"))
                elif st == "candidate":
                    counts["candidate"] += 1
                    report.append((e.key, "candidate (not written)", "", res["doi"],
                                   f"score={res['score']} {res.get('detail', '')} | "
                                   f"{res.get('crossref_title', '')}"))
                elif st == "unresolvable":
                    counts["unresolvable"] += 1
                    report.append((e.key, "unresolvable (not written)", "", res["doi"], ""))
                elif st == "error":
                    counts["error"] += 1
                    report.append((e.key, "error", "", "", res.get("detail", "")))
                else:
                    counts["nomatch"] += 1
                done += 1
                if done % 100 == 0:
                    cache_path.write_text(json.dumps(cache))
                    print(f"  {done}/{len(to_lookup)}", file=sys.stderr)
        cache_path.write_text(json.dumps(cache))

    if args.drop_bad:
        for e in bad_fields.values():
            f = e.fields["doi"]
            edits.append(("span", f["name_start"], f["name_start"] + 3, "baddoi"))

    # Apply edits from the end of the file backwards so offsets stay valid
    resolved = []
    for ed in edits:
        if ed[0] == "insert":
            _, e, doi = ed
            indent = field_indent(text, e)
            pos = e.header_end
            nl = "\r\n" if "\r\n" in text[e.start:e.end] else "\n"
            resolved.append((pos, pos, f"{nl}{indent}doi = {{{doi}}},"))
        else:
            resolved.append(ed[1:])
    resolved.sort(key=lambda t: t[0], reverse=True)
    new_text = text
    for start, end, rep in resolved:
        new_text = new_text[:start] + rep + new_text[end:]

    if args.in_place:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = src.with_name(f"{src.name}.{stamp}.bak")
        shutil.copy2(src, backup)
        out = src
        print(f"Backup written to {backup}", file=sys.stderr)
    out.write_bytes(new_text.encode("utf-8", errors="surrogateescape"))

    with report_path.open("w", encoding="utf-8") as fh:
        fh.write("citekey\taction\told\tnew\tdetail\n")
        for row in sorted(report):
            fh.write("\t".join(str(c).replace("\t", " ").replace("\n", " ") for c in row) + "\n")

    print(f"""
Entries scanned:              {counts['entries']}
Had a DOI field:              {counts['had_doi']}
  reformatted for litdb:      {counts['reformatted']}
    of which do not resolve:  {counts['reformat_unres']}
  held no DOI (bad field):    {counts['bad']}
  NEED HAND FIX (see report): {counts['manual']}
DOI taken from url/note/etc.: {counts['harvested']}
  rejected (did not resolve): {counts['harvest_unres']}
Crossref lookups:             {len(to_lookup)}
  DOI found and verified:     {counts['found']}
  candidates to review:       {counts['candidate']}
  found but not resolvable:   {counts['unresolvable']}
  no match:                   {counts['nomatch']}
  network errors (retry):     {counts['error']}
Skipped by entry type:        {counts['skipped_type']}

Wrote {out}
Report {report_path}""")


if __name__ == "__main__":
    main()
