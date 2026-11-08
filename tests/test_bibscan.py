"""Tests for the position-recording BibTeX scanner."""

from bibtex_doi_doctor.bibscan import field_indent, find_matching, parse_value, scan_entries


def test_find_matching_handles_nesting_and_escapes():
    text = r"{a {b} \} c}"
    assert find_matching(text, 0, "{") == len(text) - 1


def test_parse_value_braces():
    text = "{Hello {World}}, next"
    vstart, vend, value, _ = parse_value(text, 0)
    assert value == "Hello {World}"
    assert text[vstart:vend] == "{Hello {World}}"


def test_parse_value_quotes_bare_and_concatenation():
    assert parse_value('"A {"}B" ,', 0)[2] == 'A {"}B'
    assert parse_value("2010,", 0)[2] == "2010"
    assert parse_value('"one " # "two",', 0)[2] == "one two"


def test_scan_skips_string_comment_preamble():
    text = """
@string{j = "J"}
@comment{nothing}
@preamble{"x"}
@article{Key1, title = {T}, year = 2001}
"""
    entries = list(scan_entries(text))
    assert [e.key for e in entries] == ["Key1"]
    assert entries[0].type == "article"


def test_scan_records_field_positions():
    text = "@article{K,\n  title = {T},\n  doi = {doi:10.1/x}\n}\n"
    (e,) = scan_entries(text)
    f = e.fields["doi"]
    assert text[f["vstart"]:f["vend"]] == "{doi:10.1/x}"
    assert text[f["name_start"]:f["name_start"] + 3] == "doi"
    assert e.get("DOI") == "doi:10.1/x"
    assert e.get("missing", "default") == "default"


def test_scan_handles_parentheses_and_uppercase_type():
    text = "@ARTICLE(K2, title = {T})"
    (e,) = scan_entries(text)
    assert (e.type, e.key, e.get("title")) == ("article", "K2", "T")


def test_scan_survives_unclosed_entry():
    text = "@article{Good, title={T}}\n@article{Bad, title={unclosed"
    assert [e.key for e in scan_entries(text)] == ["Good"]


def test_field_indent_detects_tabs_and_spaces():
    tabbed = "@article{K,\n\ttitle = {T}\n}"
    spaced = "@article{K,\n    title = {T}\n}"
    oneline = "@article{K, title = {T}}"
    assert field_indent(tabbed, next(scan_entries(tabbed))) == "\t"
    assert field_indent(spaced, next(scan_entries(spaced))) == "    "
    assert field_indent(oneline, next(scan_entries(oneline))) == "  "


def test_edge_cases_file_scans(edge_bib):
    text = edge_bib.read_text()
    keys = [e.key for e in scan_entries(text)]
    assert keys == ["Sici1997", "Pasted2025", "Placeholder2011", "Artn2018",
                    "Concat2005", "Note2003", "Quoted1999"]
