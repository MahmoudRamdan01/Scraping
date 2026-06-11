"""Env-gated HTTP connection pool + on-disk cache.

Both features default OFF: with no env vars set, ``fetch_html`` calls a bare
``requests.get`` exactly as before (covered by test_http_retry.py). These tests
prove the opt-in paths work and stay isolated behind their env flags.
"""
import requests

from aol_leadfinder.scrapers import http


class _Resp:
    def __init__(self, status_code=200, text="<html>cached-me</html>"):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)


def test_cache_dir_unset_means_no_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("AOL_HTTP_CACHE_DIR", raising=False)
    calls = []
    monkeypatch.setattr(http, "_do_get", lambda url, **kw: calls.append(url) or _Resp())
    http.fetch_html("http://x")
    http.fetch_html("http://x")
    assert len(calls) == 2  # no caching -> fetched twice


def test_disk_cache_serves_second_fetch(monkeypatch, tmp_path):
    monkeypatch.setenv("AOL_HTTP_CACHE_DIR", str(tmp_path))
    calls = []
    monkeypatch.setattr(http, "_do_get", lambda url, **kw: calls.append(url) or _Resp(text="<html>v1</html>"))

    first = http.fetch_html("http://x")
    second = http.fetch_html("http://x")  # same URL -> served from disk, no new GET

    assert first == second == "<html>v1</html>"
    assert len(calls) == 1
    assert list(tmp_path.glob("*.html"))  # a cache file was written


def test_expired_cache_is_refetched(monkeypatch, tmp_path):
    monkeypatch.setenv("AOL_HTTP_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AOL_HTTP_CACHE_TTL", "0")  # everything is immediately stale
    calls = []
    monkeypatch.setattr(http, "_do_get", lambda url, **kw: calls.append(url) or _Resp())
    http.fetch_html("http://x")
    http.fetch_html("http://x")
    assert len(calls) == 2  # TTL=0 -> cache never considered fresh


def test_pool_path_uses_session(monkeypatch):
    monkeypatch.setenv("AOL_HTTP_POOL", "1")
    monkeypatch.delenv("AOL_HTTP_CACHE_DIR", raising=False)

    session_calls = []

    class _FakeSession:
        def get(self, url, **kw):
            session_calls.append(url)
            return _Resp()

    monkeypatch.setattr(http, "_session", lambda: _FakeSession())

    def _boom(*a, **k):  # the bare path must NOT be used when pooling is on
        raise AssertionError("requests.get should not be called when AOL_HTTP_POOL=1")

    monkeypatch.setattr(http.requests, "get", _boom)

    assert http.fetch_html("http://x") == "<html>cached-me</html>"
    assert session_calls == ["http://x"]
