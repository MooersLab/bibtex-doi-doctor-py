"""Find, clean and judge DOI strings."""

import re
import urllib.parse

# A DOI is '10.' + registrant + '/' + suffix. Old Wiley SICI DOIs contain
# '<', '>', ';' and '()', so those characters are allowed in the suffix.
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s{}\"@]+")

# The same pattern with the leading '1' lost, as in '0.1038/s41467-...'.
DOI_NO_ONE_RE = re.compile(r"(?<![\w.])0\.(\d{4,9}/[^\s{}\"@]+)")

# Publisher URL tails that follow a DOI but are not part of it.
URL_TAIL_RE = re.compile(
    r"(https?:|[?#&]|/asset/|/abstract$|/full$|/fulltext$|/pdf$|/epdf$|"
    r"/pdfplus$|/meta$|/suppl\w*$|\.pdf$|/references$|/figures$).*",
    re.I,
)

LITDB_READY_RE = re.compile(r"10\.\d{4,9}/\S+")


def _trim(doi, from_url):
    """Remove punctuation and URL debris from the end of a DOI match."""
    doi = doi.rstrip(".,;:")
    if from_url:
        prev = None
        while prev != doi:
            prev = doi
            doi = URL_TAIL_RE.sub("", doi).rstrip(".,;:/")
    else:
        doi = re.split(r"https?:", doi)[0]
    # An unbalanced closing parenthesis or bracket is punctuation, not DOI.
    while doi and doi[-1] in ")]":
        opener = "(" if doi[-1] == ")" else "["
        if doi.count(doi[-1]) > doi.count(opener):
            doi = doi[:-1]
        else:
            break
    return doi or None


def extract_doi(text, from_url=False):
    """Return the bare DOI found in ``text``, or None.

    Set ``from_url`` when ``text`` comes from a url, note or similar field.
    The text is then URL-decoded, and publisher tails such as
    ``/asset/...pdf?v=1`` are removed.
    """
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
    """True when ``value`` is already a clean bare DOI."""
    value = value or ""
    return bool(LITDB_READY_RE.fullmatch(value)) and extract_doi(value) == value


def leftover_text(value, doi):
    """Text in a doi field besides the DOI itself and the usual prefixes.

    A large leftover means the field holds something else as well, such as
    a whole BibTeX entry pasted by mistake.
    """
    rest = value.replace(doi, " ", 1)
    rest = re.sub(
        r"(?i)https?://(dx\.)?doi\.org/?|doi\.org/?|\bdoi\b\s*:?|\bartn\b", " ", rest
    )
    rest = re.sub(r"https?://\S*", " ", rest)  # a trailing publisher URL
    return rest.strip(" \t\r\n/:,;.")
