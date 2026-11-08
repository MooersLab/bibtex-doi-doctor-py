"""Tests for finding and cleaning DOI strings."""

import pytest

from bibtex_doi_doctor.doi import extract_doi, is_litdb_ready, leftover_text

SICI = "10.1002/(SICI)1096-987X(199709)18:12<1463::AID-JCC4>3.0.CO;2-H"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("10.1107/S0907444910007493", "10.1107/S0907444910007493"),
        ("doi:10.1107/S0907444905005743", "10.1107/S0907444905005743"),
        ("DOI:10.2174/1568005023342506", "10.2174/1568005023342506"),
        ("doi: 10.1093/bioinformatics/btaa944", "10.1093/bioinformatics/btaa944"),
        ("Doi 10.1107/S0907444905005743", "10.1107/S0907444905005743"),
        ("https://doi.org/10.1002/jcc.26556", "10.1002/jcc.26556"),
        ("http://dx.doi.org/10.1107/S1600576716005471", "10.1107/S1600576716005471"),
        ("doi.org/10.1371/journal.pcbi.1006411", "10.1371/journal.pcbi.1006411"),
        ("/10.1145/3548562.3548569", "10.1145/3548562.3548569"),
        ("ARTN e5954\n10.7717/peerj.5954", "10.7717/peerj.5954"),
        ("10.1016/0022-2836(82)90515-0", "10.1016/0022-2836(82)90515-0"),
        ("10.1021/bi9517998.", "10.1021/bi9517998"),
        (SICI, SICI),
    ],
)
def test_extract_doi_from_doi_field(raw, expected):
    assert extract_doi(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0.1038/s41467-021-21511-x", "10.1038/s41467-021-21511-x"),
        ("0.4236/csta.2013.22008", "10.4236/csta.2013.22008"),
    ],
)
def test_extract_doi_restores_lost_leading_one(raw, expected):
    assert extract_doi(raw) == expected


@pytest.mark.parametrize("raw", ["ISSN: 2052-2525", "00", "${2:ReplaceMe}", "", None])
def test_extract_doi_returns_none_without_doi(raw):
    assert extract_doi(raw) is None


@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://onlinelibrary.wiley.com/store/10.1002/bip.20816/asset/20816_ftp.pdf?v=1&t=h",
         "10.1002/bip.20816"),
        ("https://onlinelibrary.wiley.com/doi/pdf/10.1107/S0907444910045749?download=true",
         "10.1107/S0907444910045749"),
        ("10.1093/nar/gki943http://pubmedcentralcanada.ca/picrender.cgi?accid=PMC1298919",
         "10.1093/nar/gki943"),
        ("https://www.tandfonline.com/doi/full/10.1080/0889311X.2011.631919?scroll=top",
         "10.1080/0889311X.2011.631919"),
        ("https://joss.theoj.org/papers/10.21105/joss.01541.pdf", "10.21105/joss.01541"),
        ("https://journals.plos.org/x?id=10.1371/journal.pcbi.1004084&type=printable",
         "10.1371/journal.pcbi.1004084"),
        ("https://doi.org/10.1002%2Fpro.3781", "10.1002/pro.3781"),
        ("https://www.nature.com/articles/nature11783/abstract", None),
    ],
)
def test_extract_doi_from_url(url, expected):
    assert extract_doi(url, from_url=True) == expected


def test_doi_stops_before_pasted_entry():
    raw = "10.1107/s2052252524011862@article{, author = {B}}"
    assert extract_doi(raw) == "10.1107/s2052252524011862"


@pytest.mark.parametrize(
    "value, ready",
    [
        ("10.1107/S0907444910007493", True),
        (SICI, True),
        ("doi:10.1107/S0907444910007493", False),
        ("https://doi.org/10.1107/S0907444910007493", False),
        ("10.1021/bi9517998.", False),
        ("", False),
    ],
)
def test_is_litdb_ready(value, ready):
    assert is_litdb_ready(value) is ready


@pytest.mark.parametrize(
    "value, doi, leftover",
    [
        ("doi:10.1/abc", "10.1/abc", ""),
        ("https://dx.doi.org/10.1/abc", "10.1/abc", ""),
        ("ARTN e5954 10.1/abc", "10.1/abc", "e5954"),
        ("10.1/abc\nhttps://www.nature.com/articles/x#supp", "10.1/abc", ""),
    ],
)
def test_leftover_text(value, doi, leftover):
    assert leftover_text(value, doi) == leftover


def test_leftover_text_flags_pasted_entry():
    value = "10.1/abc@article{, author = {B}, title = {Pasted}}"
    rest = leftover_text(value, "10.1/abc")
    assert "@" in rest and "=" in rest
