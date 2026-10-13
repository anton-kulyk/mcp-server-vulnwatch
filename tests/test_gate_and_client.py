"""Offline unit tests: auth gate, confused-deputy gate, request building,
and error semantics. None of these touch the network."""
import httpx
import pytest

from vulnwatch_mcp import server


def test_no_token_raises_without_network(monkeypatch):
    """With no VULNWATCH_API_TOKEN, read tools fail closed and never hit the network."""
    monkeypatch.delenv("VULNWATCH_API_TOKEN", raising=False)

    class ExplodingClient:
        def __init__(self, *a, **k):
            raise AssertionError("network must not be used when no token is configured")

    monkeypatch.setattr(server.httpx, "Client", ExplodingClient)
    with pytest.raises(RuntimeError, match="VULNWATCH_API_TOKEN is not set"):
        server.vw_get_stats()


def test_submit_scan_disabled_by_default(monkeypatch):
    """submit_scan is a side-effecting action and must be gated off by default."""
    monkeypatch.delenv("VULNWATCH_MCP_ALLOW_SCAN", raising=False)
    with pytest.raises(RuntimeError, match="disabled"):
        server.vw_submit_scan("https://example.com")


class FakeHttp:
    """Stand-in for httpx.Client created by VulnWatchClient.__init__.

    Keeps the headers the client was constructed with (that's where the
    Authorization token lives) and records every request + returns a canned
    response, so no bytes ever leave the process."""

    def __init__(self, headers, status, payload):
        self.headers = headers or {}
        self.status = status
        self.payload = payload
        self.calls = []

    def request(self, method, url, **kw):
        self.calls.append({"method": method, "url": url, "kw": kw})
        return httpx.Response(self.status, json=self.payload)

    def assert_auth(self, expected):
        assert self.headers.get("Authorization") == expected


def _patch_client(monkeypatch, status=200, payload=None):
    holder = {"fake": None}

    def factory(*a, **kw):
        holder["fake"] = FakeHttp(kw.get("headers"), status, payload or {})
        return holder["fake"]

    monkeypatch.setattr(server.httpx, "Client", factory)
    return holder


def test_get_stats_sends_bearer_and_path(monkeypatch):
    monkeypatch.setenv("VULNWATCH_API_TOKEN", "tok_abc")
    holder = _patch_client(monkeypatch, 200, {"completed": 1})
    assert server.vw_get_stats() == {"completed": 1}
    fake = holder["fake"]
    fake.assert_auth("Bearer tok_abc")
    assert fake.calls[0]["url"].endswith("/scan/action/stats")


def test_scan_history_status_filter(monkeypatch):
    monkeypatch.setenv("VULNWATCH_API_TOKEN", "tok")
    holder = _patch_client(monkeypatch, 200, {"items": []})
    server.vw_scan_history(status="failed", per_page=5, page=2)
    assert holder["fake"].calls[0]["kw"]["params"] == {"per_page": 5, "page": 2, "status": "failed"}


def test_report_uses_check_uuid_path(monkeypatch):
    monkeypatch.setenv("VULNWATCH_API_TOKEN", "tok")
    holder = _patch_client(monkeypatch, 200, {"findings": []})
    server.vw_scan_report("abc-123")
    assert holder["fake"].calls[0]["url"].endswith("/scan/action/abc-123/report")


def test_http_401_surfaces_status_and_body(monkeypatch):
    """Non-2xx must raise RuntimeError with the HTTP status and the API message,
    rather than silently returning junk."""
    monkeypatch.setenv("VULNWATCH_API_TOKEN", "tok")
    _patch_client(monkeypatch, 401, {"message": "Unauthenticated."})
    with pytest.raises(RuntimeError) as ei:
        server.vw_get_stats()
    assert "401" in str(ei.value)
    assert "Unauthenticated" in str(ei.value)