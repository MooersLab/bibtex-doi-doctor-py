"""Normalize titles and names, and score Crossref candidates."""

import difflib
import re
import unicodedata

# Symbol accents such as \'{e} or \"o, and letter accents such as \v{c} or \c c.
# A letter accent needs a brace or a space after it, so that \textit or
# \cite are not mistaken for \t or \c.
LATEX_ACCENT_RE = re.compile(
    r"\\[`'^\"~=.]\s*\{?([A-Za-z])\}?|\\[uvHtcdbk](?:\s+|\{)([A-Za-z])\}?"
)
LATEX_CMD_RE = re.compile(r"\\[A-Za-z]+\*?\s*")


def delatex(s):
    """Strip common LaTeX markup, keeping the letters underneath."""
    s = LATEX_ACCENT_RE.sub(lambda m: m.group(1) or m.group(2), s or "")
    s = s.replace("\\&", "&").replace("~", " ").replace("--", "-")
    s = LATEX_CMD_RE.sub("", s)
    s = s.replace("{", "").replace("}", "").replace("$", "")
    return re.sub(r"\s+", " ", s).strip()


def fold(s):
    """Fold accented letters to plain ASCII."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def norm(s):
    """Lower-case ASCII letters and digits only, for fuzzy comparison."""
    return re.sub(r"[^a-z0-9]", "", fold(delatex(s)).lower())


def first_author_last(author_field):
    """Normalized last name of the first author, or None."""
    if not author_field:
        return None
    first = re.split(r"\s+and\s+", delatex(author_field), maxsplit=1)[0].strip()
    if not first or first.lower() in {"others", "anonymous"}:
        return None
    last = first.split(",")[0] if "," in first else first.split()[-1]
    return norm(last) or None


def year_of(entry):
    """Publication year from the year or date field, or None."""
    for name in ("year", "date"):
        value = entry.get(name)
        if value:
            m = re.search(r"(1[5-9]\d\d|20\d\d)", value)
            if m:
                return int(m.group(1))
    return None


def score_candidate(item, ntitle, author_last, year):
    """Compare one Crossref work with an entry.

    Returns ``(title_ratio, year_ok, author_ok)``. ``title_ratio`` is the best
    similarity between the entry title and the Crossref title, with or without
    its subtitle. ``year_ok`` allows a difference of one year (online-first
    versus print). ``author_ok`` needs the entry's first-author last name to be
    among the Crossref family names.
    """
    titles = item.get("title") or [""]
    subs = item.get("subtitle") or []
    best = 0.0
    for t in titles:
        for option in [t] + [f"{t} {s}" for s in subs]:
            ratio = difflib.SequenceMatcher(None, ntitle, norm(option)).ratio()
            best = max(best, ratio)

    cy = None
    parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    if parts and parts[0] and parts[0][0]:
        cy = int(parts[0][0])
    year_ok = year is None or cy is None or abs(cy - year) <= 1

    families = [
        norm(a.get("family") or a.get("name") or "") for a in item.get("author") or []
    ]
    author_ok = author_last is None or not families or author_last in families
    return best, year_ok, author_ok
