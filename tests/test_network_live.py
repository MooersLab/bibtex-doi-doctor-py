"""Live tests against Crossref and doi.org.

These are skipped unless you run them on purpose, because they need the
network and depend on outside services:

    make test-network
"""

import os

import pytest

from bibtex_doi_doctor.cli import Options, doctor
from bibtex_doi_doctor.network import Net

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(not os.environ.get("BDD_NETWORK"),
                       reason="set BDD_NETWORK=1 (or run 'make test-network')"),
]


def test_doi_org_knows_coot():
    assert Net().doi_resolves("10.1107/S0907444910007493")


def test_doi_org_rejects_nonsense():
    assert not Net().doi_resolves("10.9999/this-doi-does-not-exist-12345")


def test_sample_file_end_to_end(sample_bib):
    res = doctor(sample_bib.read_text(), Options(workers=2),
                 net=Net(os.environ.get("BDD_MAILTO")))
    assert "10.1107/S0907444909052925" in res.text   # PHENIX, from Crossref
    assert "10.1038/s41586-021-03819-2" in res.text  # AlphaFold, replaced ISSN
