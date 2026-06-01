"""fetch_html resilience: retry transient failures, fail fast on terminal ones."""
import pytest
import requests

from aol_leadfinder.scrapers import http


class _Resp:
    def __init__(self, status_code=200, text="<html>ok</html>"):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Record sleeps and never actually wait, so tests stay fast."""
    slept: list[float] = []
    monkeypatch.setattr(http.time, "sleep", lambda s: slept.append(s))
    return slept


def _seq_get(monkeypatch, items):
    """Patch requests.get to walk a scripted sequence of responses/exceptions."""
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        item = items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(http.requests, "get", fake_get)
    return calls


def test_retries_network_then_5xx_then_succeeds(monkeypatch, _no_real_sleep):
    calls = _seq_get(monkeypatch, [requests.ConnectionError("boom"), _Resp(503), _Resp(200, "<html>good</html>")])
    assert http.fetch_html("http://x", retries=3) == "<html>good</html>"
    assert len(calls) == 3
    assert len(_no_real_sleep) == 2  # one backoff before each retry


def test_does_not_retry_404(monkeypatch, _no_real_sleep):
    calls = _seq_get(monkeypatch, [_Resp(404)])
    with pytest.raises(requests.HTTPError):
        http.fetch_html("http://x", retries=3)
    assert len(calls) == 1  # terminal: no retry
    assert _no_real_sleep == []


def test_exhausts_retries_on_persistent_5xx(monkeypatch, _no_real_sleep):
    calls = _seq_get(monkeypatch, [_Resp(500), _Resp(500), _Resp(500)])
    with pytest.raises(requests.HTTPError):
        http.fetch_html("http://x", retries=2)
    assert len(calls) == 3  # 1 initial + 2 retries


def test_success_first_try_has_zero_overhead(monkeypatch, _no_real_sleep):
    calls = _seq_get(monkeypatch, [_Resp(200, "<html>x</html>")])
    assert http.fetch_html("http://x") == "<html>x</html>"
    assert len(calls) == 1
    assert _no_real_sleep == []  # the 200 path never sleeps
