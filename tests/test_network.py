"""Offline tests of the HTTP client and the cache, with urlopen replaced."""

import io
import json
import urllib.error
import urllib.parse

import pytest

from bibtex_doi_doctor import network
from bibtex_doi_doctor.network import Cache, Net


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def calls(monkeypatch):
    """Replace urlopen and sleep. Push responses onto the returned list."""
    state = {"responses": [], "requests": []}

    def fake_urlopen(req, timeout=None):
        state["requests"].append(req)
        resp = state["responses"].pop(0)
        if isinstance(resp, Exception):
            raise resp
        return FakeResponse(json.dumps(resp).encode())

    monkeypatch.setattr(network.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(network.time, "sleep", lambda s: None)
    return state


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, None)


def test_user_agent_carries_mailto():
    assert "mailto:me@example.org" in Net("me@example.org").headers["User-Agent"]
    assert "mailto" not in Net().headers["User-Agent"]


def test_get_json_returns_none_on_404(calls):
    calls["responses"] = [http_error(404)]
    assert Net(min_interval=0).get_json("http://x") is None


def test_get_json_retries_after_429_and_timeouts(calls):
    calls["responses"] = [http_error(429), urllib.error.URLError("down"), {"ok": 1}]
    assert Net(min_interval=0).get_json("http://x") == {"ok": 1}
    assert len(calls["requests"]) == 3


def test_get_json_gives_up(calls):
    calls["responses"] = [http_error(503)] * 4
    with pytest.raises(RuntimeError):
        Net(min_interval=0).get_json("http://x")


def test_get_json_raises_on_other_http_errors(calls):
    calls["responses"] = [http_error(400)]
    with pytest.raises(urllib.error.HTTPError):
        Net(min_interval=0).get_json("http://x")


def test_doi_resolves(calls):
    calls["responses"] = [{"responseCode": 1}, {"responseCode": 100}, http_error(404)]
    net = Net(min_interval=0)
    assert net.doi_resolves("10.1107/S0907444910007493") is True
    assert net.doi_resolves("10.9999/nothing") is False
    assert net.doi_resolves("10.9999/missing") is False
    assert calls["requests"][0].full_url.endswith("/api/handles/10.1107/S0907444910007493")


def test_crossref_query(calls):
    items = [{"DOI": "10.1234/x"}]
    calls["responses"] = [{"message": {"items": items}}]
    got = Net("me@example.org", min_interval=0).crossref("A title", "emsley", 2010)
    assert got == items
    query = urllib.parse.parse_qs(urllib.parse.urlparse(calls["requests"][0].full_url).query)
    assert query["query.bibliographic"] == ["A title"]
    assert query["query.author"] == ["emsley"]
    assert query["mailto"] == ["me@example.org"]


def test_throttle_spaces_requests(monkeypatch):
    slept = []
    monkeypatch.setattr(network.time, "sleep", slept.append)
    net = Net(min_interval=10)
    net._throttle()
    net._throttle()
    assert slept and slept[0] > 9


def test_cache_round_trip(tmp_path):
    path = tmp_path / "c.json"
    c = Cache(path)
    c["a"] = {"status": "found"}
    assert "a" in c and c.get("a")["status"] == "found"
    c.save()
    assert Cache(path).get("a") == {"status": "found"}


def test_cache_ignores_corrupt_file(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{not json")
    assert Cache(path).get("anything") is None
