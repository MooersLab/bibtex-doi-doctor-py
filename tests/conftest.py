"""Shared test helpers.

``FakeNet`` stands in for Crossref and doi.org, so the tests run offline and
always give the same answers.
"""

import shutil
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"
EXAMPLES = Path(__file__).parent.parent / "examples"


class FakeNet:
    """Answers Crossref queries from a table instead of the network.

    ``works`` maps a word that appears in a query title to the list of
    Crossref items to return. ``resolving`` is the set of DOIs that doi.org
    should accept; None means every DOI resolves.
    """

    def __init__(self, works=None, resolving=None, fail=False):
        self.works = works or {}
        self.resolving = resolving
        self.fail = fail
        self.crossref_calls = []
        self.resolve_calls = []

    def crossref(self, title, author_last=None, year=None, rows=5):
        self.crossref_calls.append(title)
        if self.fail:
            raise RuntimeError("network down")
        for word, items in self.works.items():
            if word.lower() in title.lower():
                return items
        return []

    def doi_resolves(self, doi):
        self.resolve_calls.append(doi)
        if self.fail:
            raise RuntimeError("network down")
        return self.resolving is None or doi in self.resolving


def crossref_item(doi, title, families, year):
    """Build a minimal Crossref work record."""
    return {
        "DOI": doi,
        "title": [title],
        "author": [{"family": f} for f in families],
        "issued": {"date-parts": [[year]]},
    }


SAMPLE_WORKS = {
    "PHENIX": [crossref_item(
        "10.1107/S0907444909052925",
        "PHENIX: a comprehensive Python-based system for macromolecular structure solution",
        ["Adams", "Afonine"], 2010)],
    "AlphaFold": [crossref_item(
        "10.1038/s41586-021-03819-2",
        "Highly accurate protein structure prediction with AlphaFold",
        ["Jumper", "Evans"], 2021)],
}


@pytest.fixture
def fake_net():
    return FakeNet(works=SAMPLE_WORKS)


@pytest.fixture
def sample_bib(tmp_path):
    """A copy of examples/sample.bib in a temporary folder."""
    dest = tmp_path / "sample.bib"
    shutil.copy(EXAMPLES / "sample.bib", dest)
    return dest


@pytest.fixture
def edge_bib(tmp_path):
    """A copy of tests/data/edge_cases.bib in a temporary folder."""
    dest = tmp_path / "edge_cases.bib"
    shutil.copy(DATA / "edge_cases.bib", dest)
    return dest
