"""Crossref and doi.org access, plus a thread-safe JSON cache."""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__


class Net:
    """Polite HTTP client for Crossref and the doi.org handle service.

    Requests from all threads share one throttle, so the request rate stays
    near ``1 / min_interval`` per second however many workers run.
    """

    def __init__(self, mailto=None, min_interval=0.12, timeout=30):
        ua = f"bibtex-doi-doctor/{__version__}"
        if mailto:
            ua += f" (mailto:{mailto})"
        self.headers = {"User-Agent": ua}
        self.mailto = mailto
        self.min_interval = min_interval
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last = 0.0

    def _throttle(self):
        with self._lock:
            wait = self._last + self.min_interval - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()

    def get_json(self, url, tries=4):
        """GET ``url`` and decode JSON. Returns None on 404."""
        for attempt in range(tries):
            self._throttle()
            req = urllib.request.Request(url, headers=self.headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None
                if exc.code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt * 2)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                time.sleep(2 ** attempt)
        raise RuntimeError(f"giving up on {url}")

    def doi_resolves(self, doi):
        """True when doi.org knows ``doi``."""
        url = "https://doi.org/api/handles/" + urllib.parse.quote(doi, safe="/")
        data = self.get_json(url)
        return bool(data) and data.get("responseCode") == 1

    def crossref(self, title, author_last=None, year=None, rows=5):
        """Crossref works that best match a title and first author."""
        q = {
            "query.bibliographic": title,
            "rows": str(rows),
            "select": "DOI,title,subtitle,author,issued,type",
        }
        if author_last:
            q["query.author"] = author_last
        if self.mailto:
            q["mailto"] = self.mailto
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(q)
        data = self.get_json(url)
        return (data or {}).get("message", {}).get("items", [])


class Cache:
    """A dict saved as JSON, safe to update from several threads."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def __contains__(self, key):
        with self._lock:
            return key in self._data

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def __setitem__(self, key, value):
        with self._lock:
            self._data[key] = value

    def save(self):
        with self._lock:
            text = json.dumps(self._data)
        self.path.write_text(text)
