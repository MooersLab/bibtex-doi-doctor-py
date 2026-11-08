"""A small BibTeX scanner that records character positions.

Full BibTeX parsers rebuild the file when they write it, which changes
spacing, field order and comments. This scanner only finds where each entry
and field sits in the text, so the rest of the file can be left untouched.
"""

import re

HEADER_RE = re.compile(r"@\s*([A-Za-z]+)\s*([{(])", re.M)
FIELD_NAME_RE = re.compile(r"([A-Za-z][\w:.+-]*)\s*=\s*")

SKIP_TYPES = {"string", "comment", "preamble"}


def find_matching(text, start, open_ch):
    """Index of the bracket that closes ``text[start]``, or -1."""
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
    """Parse one field value that starts at ``text[i]``.

    Returns ``(value_start, value_end, inner_text, end_index)``. The first two
    bound the whole value including its braces or quotes. ``inner_text`` is
    the content without the outer delimiters, with ``#`` concatenations joined.
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
    """One BibTeX entry and the positions of its fields."""

    __slots__ = ("type", "key", "start", "end", "header_end", "fields")

    def __init__(self, etype, key, start, end, header_end):
        self.type = etype
        self.key = key
        self.start = start
        self.end = end
        self.header_end = header_end
        # lower-case field name -> dict(name_start, vstart, vend, value)
        self.fields = {}

    def get(self, name, default=None):
        """Value of field ``name`` (case-insensitive), or ``default``."""
        f = self.fields.get(name.lower())
        return f["value"] if f else default

    def __repr__(self):
        return f"Entry({self.type!r}, {self.key!r})"


def scan_entries(text):
    """Yield an ``Entry`` for every regular entry in ``text``.

    ``@string``, ``@comment`` and ``@preamble`` blocks are skipped.
    """
    pos = 0
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
        km = re.match(r"\s*([^,\s]+)\s*,", text[open_idx + 1:close_idx])
        if not km:
            continue
        e = Entry(etype, km.group(1), m.start(), close_idx, open_idx + 1 + km.end())
        i = e.header_end
        while i < close_idx:
            fm = FIELD_NAME_RE.search(text, i, close_idx)
            if not fm:
                break
            name = fm.group(1).lower()
            vstart, vend, value, i = parse_value(text, fm.end())
            e.fields.setdefault(
                name,
                {"name_start": fm.start(), "vstart": vstart, "vend": vend, "value": value},
            )
            while i < close_idx and text[i] in " \t\r\n":
                i += 1
            if i < close_idx and text[i] == ",":
                i += 1
        yield e


def field_indent(text, entry):
    """The indentation that ``entry`` uses for its fields (two spaces if unknown)."""
    for f in entry.fields.values():
        line_start = text.rfind("\n", 0, f["name_start"]) + 1
        indent = text[line_start:f["name_start"]]
        if indent.strip() == "":
            return indent
    return "  "
