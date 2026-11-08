"""End-to-end tests of the repair pipeline and the command line."""

import json

import pytest

from bibtex_doi_doctor import __version__
from bibtex_doi_doctor.bibscan import scan_entries
from bibtex_doi_doctor.cli import Options, doctor, lookup, main
from bibtex_doi_doctor.network import Cache

from conftest import FakeNet, crossref_item


def dois(text):
    """Map citekey -> doi field value for every entry in text."""
    return {e.key: e.get("doi") for e in scan_entries(text)}


def actions(result):
    return {(row[0], row[1]) for row in result.report}


# ---------------------------------------------------------------- offline


def test_offline_repairs_formats_only(sample_bib):
    res = doctor(sample_bib.read_text(), Options(lookup=False))
    d = dois(res.text)
    assert d["Emsley2010FeaturesDevelopmentCoot"] == "10.1107/S0907444910007493"
    assert d["Kabsch2010Xds"] == "10.1107/S0907444909047337"
    assert d["Berman2000ProteinDataBank"] == "10.1093/nar/28.1.235"
    assert d["Winn2011OverviewCcp4SuiteCurrentDevelopments"] == "10.1107/S0907444910045749"
    assert d["Adams2010PhenixComprehensivePythonBasedSystem"] is None
    assert d["Jumper2021HighlyAccurateProteinStructurePrediction"] == "ISSN: 0028-0836"
    assert res.counts["reformatted"] == 3
    assert res.counts["harvested"] == 1
    assert res.counts["bad"] == 1
    assert res.counts["lookups"] == 0


def test_only_doi_lines_change(sample_bib):
    old = sample_bib.read_text()
    res = doctor(old, Options(lookup=False))
    old_lines = [ln for ln in old.splitlines() if "doi" not in ln.lower()]
    new_lines = [ln for ln in res.text.splitlines() if "doi" not in ln.lower()]
    assert old_lines == new_lines


def test_clean_file_is_unchanged():
    text = "@article{A,\n  title = {T},\n  doi = {10.1234/abc}\n}\n"
    res = doctor(text, Options(lookup=False))
    assert res.text == text
    assert res.report == []


def test_edge_cases_offline(edge_bib):
    res = doctor(edge_bib.read_text(), Options(lookup=False))
    d = dois(res.text)
    assert d["Sici1997"].endswith("3.0.CO;2-H")          # untouched, not truncated
    assert d["Pasted2025"].startswith("10.1107/s2052252524011862@article")  # untouched
    assert d["Artn2018"] == "10.7717/peerj.5954"
    assert d["Concat2005"] == "10.1093/nar/gki943"
    assert d["Note2003"] == "10.1021/bi9517998"
    assert d["Quoted1999"] == "10.1007/978-1-60327-241-4_11"
    assert d["Placeholder2011"] == "${2:ReplaceMe}"
    assert ("Pasted2025", "NEEDS HAND FIX (other text in doi field)") in actions(res)
    assert res.counts["manual"] == 1
    assert "@comment{This comment block must survive unchanged.}" in res.text


def test_inserted_doi_uses_entry_indentation():
    text = "@article{A,\n\ttitle = {T},\n\turl = {https://doi.org/10.1234/abc}\n}\n"
    res = doctor(text, Options(lookup=False))
    assert res.text == "@article{A,\n\tdoi = {10.1234/abc},\n\ttitle = {T},\n" \
                       "\turl = {https://doi.org/10.1234/abc}\n}\n"


def test_crlf_line_endings_are_kept():
    text = "@article{A,\r\n  title = {T},\r\n  url = {https://doi.org/10.1234/abc}\r\n}\r\n"
    res = doctor(text, Options(lookup=False))
    assert "\r\n  doi = {10.1234/abc}," in res.text
    assert "\n" not in res.text.replace("\r\n", "")


def test_drop_bad_renames_field(edge_bib):
    res = doctor(edge_bib.read_text(), Options(lookup=False, drop_bad=True))
    assert "baddoi = {${2:ReplaceMe}}" in res.text


# ---------------------------------------------------------------- with a fake network


def test_lookup_fills_and_replaces(sample_bib, fake_net):
    res = doctor(sample_bib.read_text(), Options(), net=fake_net)
    d = dois(res.text)
    assert d["Adams2010PhenixComprehensivePythonBasedSystem"] == "10.1107/S0907444909052925"
    assert d["Jumper2021HighlyAccurateProteinStructurePrediction"] == \
        "10.1038/s41586-021-03819-2"
    assert ("Jumper2021HighlyAccurateProteinStructurePrediction",
            "found (replaced bad field)") in actions(res)
    assert res.counts["found"] == 2
    # misc entries are not looked up by default
    assert res.counts["skipped_type"] == 1
    assert not any("litdb" in t.lower() for t in fake_net.crossref_calls)


def test_types_all_looks_up_misc(sample_bib, fake_net):
    doctor(sample_bib.read_text(), Options(types=frozenset()), net=fake_net)
    assert any("litdb" in t.lower() for t in fake_net.crossref_calls)


def test_short_titles_are_not_looked_up(sample_bib, fake_net):
    text = "@article{K, author = {Kabsch, W.}, title = {{XDS}}, year = 2010}"
    res = doctor(text, Options(), net=fake_net)
    assert fake_net.crossref_calls == []
    assert res.counts["nomatch"] == 1


def test_wrong_paper_is_not_written():
    net = FakeNet(works={"Lipid": [crossref_item(
        "10.1234/wrong", "Something about proteins", ["Smith"], 2010)]})
    text = "@article{W, author = {Smith, J.}, title = {Lipid membranes of archaea}, year = 2010}"
    res = doctor(text, Options(), net=net)
    assert dois(res.text)["W"] is None
    assert res.counts["nomatch"] == 1


def test_year_mismatch_becomes_candidate():
    net = FakeNet(works={"precipitants": [crossref_item(
        "10.1107/S1744309110027639",
        "Alternative polymer precipitants for protein crystallization", ["Lee"], 2010)]})
    text = ("@article{L, author = {Lee, K.}, year = 2015,\n"
            " title = {Alternative polymer precipitants for protein crystallization}}")
    res = doctor(text, Options(), net=net)
    assert dois(res.text)["L"] is None
    (row,) = [r for r in res.report if r[0] == "L"]
    assert row[1] == "candidate (not written)"
    assert "weak year" in row[4]


def test_unresolvable_doi_is_not_written(sample_bib):
    net = FakeNet(works={"PHENIX": [crossref_item(
        "10.9999/fake",
        "PHENIX: a comprehensive Python-based system for macromolecular structure solution",
        ["Adams"], 2010)]}, resolving=set())
    res = doctor(sample_bib.read_text(), Options(), net=net)
    assert dois(res.text)["Adams2010PhenixComprehensivePythonBasedSystem"] is None
    assert res.counts["unresolvable"] == 1


def test_harvested_doi_that_does_not_resolve_is_rejected(sample_bib):
    net = FakeNet(resolving={"10.1107/S0907444910007493"})
    res = doctor(sample_bib.read_text(), Options(), net=net)
    assert dois(res.text)["Winn2011OverviewCcp4SuiteCurrentDevelopments"] is None
    assert res.counts["harvest_unres"] == 1
    assert res.counts["harvested"] == 0


def test_network_errors_are_reported_not_cached(sample_bib):
    net = FakeNet(fail=True)
    cache = {}
    res = doctor(sample_bib.read_text(), Options(), net=net, cache=cache)
    assert res.counts["error"] >= 1
    assert not any(isinstance(v, dict) and v.get("status") == "error" for v in cache.values())


def test_limit_caps_lookups(sample_bib, fake_net):
    res = doctor(sample_bib.read_text(), Options(limit=1), net=fake_net)
    assert res.counts["lookups"] == 1
    assert len(fake_net.crossref_calls) == 1


def test_cache_prevents_repeat_queries(sample_bib, fake_net, tmp_path):
    cache = Cache(tmp_path / "c.json")
    doctor(sample_bib.read_text(), Options(), net=fake_net, cache=cache)
    cache.save()
    first = len(fake_net.crossref_calls)
    again = FakeNet(works=fake_net.works)
    doctor(sample_bib.read_text(), Options(), net=again, cache=Cache(tmp_path / "c.json"))
    assert first > 0 and again.crossref_calls == []


def test_lookup_function_statuses(fake_net):
    (e,) = scan_entries("@article{N, year = 2001}")
    assert lookup(e, fake_net, {})["status"] == "no-title"


# ---------------------------------------------------------------- command line


def run_cli(args, capsys, net=None):
    code = main([str(a) for a in args], net_factory=lambda mailto: net)
    return code, capsys.readouterr()


def test_cli_writes_outputs(sample_bib, capsys):
    code, out = run_cli([sample_bib, "--no-lookup"], capsys)
    assert code == 0
    doctored = sample_bib.with_name("sample-doctored.bib")
    report = sample_bib.with_name("sample-doi-report.tsv")
    assert doctored.exists() and report.exists()
    assert report.read_text().splitlines()[0] == "citekey\taction\told\tnew\tdetail"
    assert "reformatted for litdb:      3" in out.out
    # the input is untouched
    assert "doi:10.1107/S0907444910007493" in sample_bib.read_text()


def test_cli_in_place_makes_backup(sample_bib, capsys):
    original = sample_bib.read_bytes()
    code, _ = run_cli([sample_bib, "--no-lookup", "--in-place"], capsys)
    assert code == 0
    backups = list(sample_bib.parent.glob("sample.bib.*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    assert "doi:10.1107" not in sample_bib.read_text()


def test_cli_lookup_with_fake_net_writes_cache(sample_bib, fake_net, capsys):
    code, out = run_cli([sample_bib, "--mailto", "me@example.org"], capsys, net=fake_net)
    assert code == 0
    assert "DOI found and verified:     2" in out.out
    cache = json.loads(sample_bib.with_name("sample-doi-cache.json").read_text())
    assert any(k.startswith("Adams2010") for k in cache)


def test_cli_output_option(sample_bib, tmp_path, capsys):
    target = tmp_path / "clean.bib"
    run_cli([sample_bib, "--no-lookup", "-o", target], capsys)
    assert target.exists()


def test_cli_preserves_non_utf8_bytes(tmp_path, capsys):
    bib = tmp_path / "latin.bib"
    bib.write_bytes(b"@article{A, title = {Caf\xe9}, doi = {doi:10.1234/x}}\n")
    run_cli([bib, "--no-lookup"], capsys)
    out = tmp_path / "latin-doctored.bib"
    assert out.read_bytes() == b"@article{A, title = {Caf\xe9}, doi = {10.1234/x}}\n"


def test_cli_missing_file(tmp_path, capsys):
    code, out = run_cli([tmp_path / "nope.bib", "--no-lookup"], capsys)
    assert code == 2
    assert "no such file" in out.err


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
