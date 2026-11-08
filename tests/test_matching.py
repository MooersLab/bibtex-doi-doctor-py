"""Tests for title normalization and Crossref candidate scoring."""

import pytest

from bibtex_doi_doctor.bibscan import scan_entries
from bibtex_doi_doctor.matching import (
    delatex,
    first_author_last,
    fold,
    norm,
    score_candidate,
    year_of,
)

from conftest import crossref_item


def test_delatex_and_fold():
    assert delatex(r"Bunk{\'o}czi and \textit{in situ} {RNA}") == "Bunkoczi and in situ RNA"
    assert fold("Pritišanac Kolarić") == "Pritisanac Kolaric"


def test_norm_ignores_case_markup_and_punctuation():
    assert norm(r"{PHENIX}: a {Python}-based system") == norm("PHENIX - A python based System")


@pytest.mark.parametrize(
    "author, expected",
    [
        ("Emsley, Paul and Lohkamp, Bernhard", "emsley"),
        ("Paul Emsley and Bernhard Lohkamp", "emsley"),
        (r"Bunk{\'o}czi, G{\'a}bor", "bunkoczi"),
        ("Abad-Zapatero, C.", "abadzapatero"),
        ("others", None),
        ("", None),
        (None, None),
    ],
)
def test_first_author_last(author, expected):
    assert first_author_last(author) == expected


def test_year_of_reads_year_or_date():
    (e1,) = scan_entries("@article{A, year = {2010}}")
    (e2,) = scan_entries("@article{B, date = {2019-04-01}}")
    (e3,) = scan_entries("@article{C, title = {T}}")
    assert (year_of(e1), year_of(e2), year_of(e3)) == (2010, 2019, None)


TITLE = norm("Features and development of Coot")


def test_score_exact_match():
    item = crossref_item("10.1/x", "Features and development of Coot", ["Emsley"], 2010)
    ratio, year_ok, author_ok = score_candidate(item, TITLE, "emsley", 2010)
    assert ratio == pytest.approx(1.0)
    assert year_ok and author_ok


def test_score_allows_one_year_difference():
    item = crossref_item("10.1/x", "Features and development of Coot", ["Emsley"], 2009)
    assert score_candidate(item, TITLE, "emsley", 2010)[1] is True
    item = crossref_item("10.1/x", "Features and development of Coot", ["Emsley"], 2007)
    assert score_candidate(item, TITLE, "emsley", 2010)[1] is False


def test_score_rejects_wrong_author():
    item = crossref_item("10.1/x", "Features and development of Coot", ["Smith"], 2010)
    assert score_candidate(item, TITLE, "emsley", 2010)[2] is False


def test_score_uses_subtitle():
    item = crossref_item("10.1/x", "Coot", ["Emsley"], 2010)
    item["subtitle"] = ["model-building tools"]
    ratio, _, _ = score_candidate(item, norm("Coot: model-building tools"), "emsley", 2010)
    assert ratio == pytest.approx(1.0)


def test_score_unrelated_title_is_low():
    item = crossref_item("10.1/x", "Lipid membranes of archaea", ["Emsley"], 2010)
    assert score_candidate(item, TITLE, "emsley", 2010)[0] < 0.6
