"""Unit tests for the service-status and cache tools (hermetic: no request is sent).

``requests.get`` is replaced by a fake whose responses are chosen per URL, so the three
states the issue asks for (healthy, one 503, everything timing out) are exercised without
touching Europe PMC.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
import threading
from unittest.mock import MagicMock

from mcp.server.fastmcp.exceptions import ToolError  # noqa: F401 - kept for symmetry
import pytest

from pyeuropepmc.mcp import _fulltext as ft, _status as st, server as srv

WORKFLOW = Path(__file__).parents[3] / ".github" / "workflows" / "europepmc-health.yml"


def _run(coro):
    return asyncio.run(coro)


class FakeResponse:
    """A response whose body must never be read, and that records being closed."""

    def __init__(self, code: int) -> None:
        self.status_code = code
        self.closed = False

    def close(self) -> None:
        self.closed = True

    @property
    def content(self):
        raise AssertionError("the probe must not read the body")

    @property
    def text(self):
        raise AssertionError("the probe must not read the body")


def make_get(plan, calls=None):
    """``plan`` maps a URL fragment to a status code or an exception instance."""

    def get(url, **kwargs):
        if calls is not None:
            calls.append((url, kwargs))
        for fragment, outcome in plan.items():
            if fragment in url:
                if isinstance(outcome, Exception):
                    raise outcome
                return FakeResponse(outcome)
        return FakeResponse(200)

    return get


@pytest.fixture(autouse=True)
def _reset_state():
    for cache in (
        srv._status_cache,
        srv._client_cache,
        srv._article_client_cache,
        srv._annotations_client_cache,
        srv._fulltext_xml_cache,
    ):
        cache.reset()
    yield
    for cache in (
        srv._status_cache,
        srv._client_cache,
        srv._article_client_cache,
        srv._annotations_client_cache,
        srv._fulltext_xml_cache,
    ):
        cache.reset()


class TestEndpointList:
    def test_it_matches_the_health_workflow(self):
        """One list, two places: a change to one without the other must fail here."""
        text = WORKFLOW.read_text()
        block = text[
            text.index("ENDPOINTS=(") : text.index("\n          )", text.index("ENDPOINTS=("))
        ]
        found = re.findall(r'"([^|"]+)\|([^"]+)"', block)
        assert found, "could not read the endpoint list from the workflow"
        in_workflow = [(label, url.replace("$BASE", st.BASE)) for label, url in found]
        in_code = [(label, url) for _key, label, url in st.ENDPOINTS]
        assert in_code == in_workflow

    def test_keys_are_unique_and_named(self):
        keys = [key for key, _label, _url in st.ENDPOINTS]
        assert keys == ["search", "fulltext", "citations", "annotations"]
        assert len(set(keys)) == len(keys)


class TestProbeOne:
    @pytest.mark.parametrize(
        ("code", "verdict"),
        [
            (200, "ok"),
            (204, "ok"),
            (301, "unexpected"),
            (404, "unexpected"),
            (429, "unexpected"),
            (500, "error"),
            (503, "error"),
            (599, "error"),
        ],
    )
    def test_verdicts(self, code, verdict):
        assert st.verdict_for(code) == verdict

    def test_a_request_is_streamed_never_read_and_closed(self):
        calls = []
        responses = []

        def get(url, **kwargs):
            calls.append(kwargs)
            response = FakeResponse(200)
            responses.append(response)
            return response

        result = st.probe_one("https://x/y", get, timeout=3.0)

        assert result.verdict == "ok"
        assert result.http == 200
        assert calls[0]["stream"] is True
        assert calls[0]["timeout"] == 3.0
        assert "pyEuropePMC" in calls[0]["headers"]["User-Agent"]
        assert responses[0].closed is True

    def test_a_failure_to_answer_reports_the_exception_class_only(self):
        secret = "https://internal.example/token=abc123"

        def get(url, **kwargs):
            raise TimeoutError(secret)

        result = st.probe_one("https://x/y", get, timeout=1.0)

        assert (result.verdict, result.http, result.error) == ("unreachable", None, "TimeoutError")
        assert secret not in json.dumps(result.to_dict())

    def test_the_response_is_closed_even_when_reading_the_code_fails(self):
        response = FakeResponse(200)
        response.status_code = "not a number"  # type: ignore[assignment]
        with pytest.raises(ValueError):
            st.probe_one("https://x/y", lambda url, **kw: response, timeout=1.0)
        assert response.closed is True


def _results(**verdicts):
    return {
        key: st.EndpointResult(v, 200 if v == "ok" else (503 if v == "error" else None), 5)
        for key, v in verdicts.items()
    }


class TestOverall:
    @pytest.mark.parametrize(
        ("verdicts", "expected"),
        [
            (dict(a="ok", b="ok", c="ok", d="ok"), "ok"),
            (dict(a="ok", b="error", c="ok", d="ok"), "degraded"),  # one 503
            (dict(a="ok", b="unreachable", c="ok", d="ok"), "degraded"),
            (dict(a="unreachable", b="unreachable", c="unreachable", d="unreachable"), "down"),
            (dict(a="error", b="error", c="error", d="error"), "down"),
            (dict(a="error", b="unreachable"), "down"),
            (dict(a="ok", b="unexpected"), "unknown"),  # a 4xx is not an outage
            (dict(a="unexpected", b="unexpected"), "unknown"),
            (dict(a="error", b="unexpected"), "down"),
            (dict(a="ok", b="error", c="unexpected"), "degraded"),
        ],
    )
    def test_states(self, verdicts, expected):
        assert st.overall(_results(**verdicts)) == expected


class TestProbe:
    def test_the_endpoints_are_probed_at_the_same_time(self):
        barrier = threading.Barrier(len(st.ENDPOINTS), timeout=5)

        def get(url, **kwargs):
            barrier.wait()  # only passes when every endpoint is in flight at once
            return FakeResponse(200)

        results = st.probe(get)

        assert {r.verdict for r in results.values()} == {"ok"}
        assert list(results) == ["search", "fulltext", "citations", "annotations"]


class TestStatusCache:
    def test_fresh_then_expired(self):
        now = [100.0]
        cache = st.StatusCache(ttl=30, clock=lambda: now[0])
        assert cache.get() is None
        cache.set({"status": "ok"})
        now[0] = 129.0
        value, age = cache.get()
        assert value == {"status": "ok"}
        assert age == pytest.approx(29.0)
        now[0] = 130.0
        assert cache.get() is None

    def test_reset(self):
        cache = st.StatusCache()
        cache.set({"status": "ok"})
        cache.reset()
        assert cache.get() is None


class TestEpmcStatusTool:
    def test_healthy(self, monkeypatch):
        monkeypatch.setattr(srv.requests, "get", make_get({}))
        out = _run(srv.epmc_status())
        assert out["status"] == "ok"
        assert out["cached"] is False
        assert out["age_seconds"] == 0
        assert set(out["endpoints"]) == {"search", "fulltext", "citations", "annotations"}
        assert all(e["verdict"] == "ok" and e["http"] == 200 for e in out["endpoints"].values())
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", out["checked_at"])

    def test_degraded_when_one_endpoint_answers_503(self, monkeypatch):
        monkeypatch.setattr(srv.requests, "get", make_get({"fullTextXML": 503}))
        out = _run(srv.epmc_status())
        assert out["status"] == "degraded"
        assert out["endpoints"]["fulltext"] == {
            "verdict": "error",
            "http": 503,
            "ms": out["endpoints"]["fulltext"]["ms"],
        }
        assert out["endpoints"]["search"]["verdict"] == "ok"

    def test_down_when_everything_times_out(self, monkeypatch):
        monkeypatch.setattr(srv.requests, "get", make_get({"ebi.ac.uk": TimeoutError("slow")}))
        out = _run(srv.epmc_status())
        assert out["status"] == "down"
        assert {e["error"] for e in out["endpoints"].values()} == {"TimeoutError"}
        assert all(e["http"] is None for e in out["endpoints"].values())

    def test_a_4xx_only_is_unknown_not_an_outage(self, monkeypatch):
        monkeypatch.setattr(srv.requests, "get", make_get({"ebi.ac.uk": 403}))
        assert _run(srv.epmc_status())["status"] == "unknown"

    def test_the_answer_is_kept_so_asking_again_does_not_probe_again(self, monkeypatch):
        calls = []
        monkeypatch.setattr(srv.requests, "get", make_get({}, calls))

        first = _run(srv.epmc_status())
        second = _run(srv.epmc_status())
        third = _run(srv.epmc_status())

        assert len(calls) == 4  # one probe of four endpoints, not three
        assert (first["cached"], second["cached"], third["cached"]) == (False, True, True)
        assert second["checked_at"] == first["checked_at"]

    def test_it_probes_again_once_the_answer_has_expired(self, monkeypatch):
        calls = []
        monkeypatch.setattr(srv.requests, "get", make_get({}, calls))
        now = [0.0]
        monkeypatch.setattr(srv._status_cache, "_clock", lambda: now[0])

        _run(srv.epmc_status())
        now[0] = 29.0
        assert _run(srv.epmc_status())["cached"] is True
        now[0] = 31.0
        again = _run(srv.epmc_status())

        assert again["cached"] is False
        assert len(calls) == 8

    def test_callers_arriving_together_share_one_probe(self, monkeypatch):
        calls = []
        release = threading.Event()

        def get(url, **kwargs):
            calls.append(url)
            release.wait(5)
            return FakeResponse(200)

        monkeypatch.setattr(srv.requests, "get", get)

        async def together():
            tasks = [asyncio.create_task(srv.epmc_status()) for _ in range(5)]
            await asyncio.sleep(0.3)
            release.set()
            return await asyncio.gather(*tasks)

        results = _run(together())

        assert len(calls) == 4
        assert sum(not r["cached"] for r in results) == 1

    def test_no_url_or_body_is_returned(self, monkeypatch):
        monkeypatch.setattr(
            srv.requests, "get", make_get({"search": TimeoutError("https://secret")})
        )
        dumped = json.dumps(_run(srv.epmc_status()))
        assert "ebi.ac.uk" not in dumped
        assert "secret" not in dumped

    def test_the_tool_reads_from_the_network_and_is_read_only(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        ann = tools["epmc_status"].annotations
        assert ann.readOnlyHint is True
        assert ann.openWorldHint is True


class TestXmlCacheStats:
    def test_counts_hits_and_misses_without_keys(self):
        cache = ft.XmlCache(maxsize=2)
        assert cache.get("PMC1") is None
        cache.set("PMC1", "<a/>")
        assert cache.get("PMC1") == "<a/>"
        cache.set("PMC2", "<b/>")
        cache.set("PMC3", "<c/>")  # evicts PMC1

        stats = cache.stats()

        assert stats == {"entries": 2, "max_entries": 2, "hits": 1, "misses": 1, "hit_rate": 0.5}
        assert "PMC" not in json.dumps(stats)

    def test_hit_rate_is_none_before_any_lookup(self):
        assert ft.XmlCache().stats()["hit_rate"] is None

    def test_clear_keeps_the_counters_and_reset_does_not(self):
        cache = ft.XmlCache()
        cache.set("PMC1", "x")
        cache.get("PMC1")
        assert cache.clear() == 1
        assert cache.stats()["hits"] == 1
        assert cache.clear() == 0
        cache.reset()
        assert cache.stats()["hits"] == 0


def _client_with_stats(extra=None):
    client = MagicMock()
    client.get_cache_stats.return_value = {
        "overall": {"hits": 3, "misses": 1, "hit_rate": 0.75},
        "layers": {"l1": {"entry_count": 7, "maxsize": 10000, "size_bytes": 2048}},
        # things that must never reach the output
        "keys": ["search:malaria dengue"],
        "cache_dir": "/home/someone/.cache/pyeuropepmc",
        **(extra or {}),
    }
    client.clear_cache.return_value = True
    return client


class TestCacheStatusTool:
    def test_nothing_created_yet(self):
        out = _run(srv.cache_status())
        assert out["search"] == {"created": False, "entries": 0}
        assert out["article"] == {"created": False, "entries": 0}
        assert out["annotations"] == {"created": False, "entries": 0}
        assert out["xml"]["entries"] == 0
        assert out["service_status"] == {"cached": False}

    def test_asking_does_not_create_a_client(self):
        _run(srv.cache_status())
        assert srv._client_cache.peek() is None

    def test_shape_and_no_sensitive_content(self):
        srv._client_cache.set(_client_with_stats())
        out = _run(srv.cache_status())
        assert out["search"] == {
            "created": True,
            "entries": 7,
            "max_entries": 10000,
            "size_bytes": 2048,
            "hits": 3,
            "misses": 1,
            "hit_rate": 0.75,
        }
        dumped = json.dumps(out)
        assert "malaria" not in dumped  # a cache key can hold query text
        assert "/home/" not in dumped  # and a cache path says where the server runs

    def test_a_broken_cache_does_not_break_the_report(self):
        client = MagicMock()
        client.get_cache_stats.side_effect = RuntimeError("boom")
        srv._article_client_cache.set(client)
        out = _run(srv.cache_status())
        assert out["article"] == {"created": True, "error": "statistics unavailable"}
        assert out["search"]["created"] is False

    def test_the_xml_cache_and_the_status_cache_are_reported(self, monkeypatch):
        srv._fulltext_xml_cache.set("PMC1", "<a/>")
        srv._fulltext_xml_cache.get("PMC1")
        srv._status_cache.set({"status": "ok"})
        out = _run(srv.cache_status())
        assert out["xml"]["entries"] == 1
        assert out["xml"]["hits"] == 1
        assert out["service_status"] == {"cached": True}

    def test_the_tool_is_local_and_read_only(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        assert tools["cache_status"].annotations.readOnlyHint is True
        assert tools["cache_status"].annotations.openWorldHint is False


class TestClearCacheTool:
    def test_it_is_not_read_only_and_says_so(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        ann = tools["clear_cache"].annotations
        assert ann.readOnlyHint is False
        assert ann.destructiveHint is False
        assert ann.idempotentHint is True
        assert ann.openWorldHint is False

    def test_the_scopes_are_a_closed_set(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        schema = tools["clear_cache"].inputSchema["properties"]["scope"]
        assert schema["enum"] == ["search", "article", "annotations", "xml", "all"]

    @pytest.mark.parametrize(
        ("scope", "lazy"),
        [
            ("search", "_client_cache"),
            ("article", "_article_client_cache"),
            ("annotations", "_annotations_client_cache"),
        ],
    )
    def test_one_client_cache_only(self, scope, lazy):
        clients = {
            "_client_cache": _client_with_stats(),
            "_article_client_cache": _client_with_stats(),
            "_annotations_client_cache": _client_with_stats(),
        }
        for name, client in clients.items():
            getattr(srv, name).set(client)
        srv._fulltext_xml_cache.set("PMC1", "<a/>")

        out = _run(srv.clear_cache(scope))

        assert list(out["results"]) == [scope]
        assert out["results"][scope] == {"cleared": True, "entries_dropped": 7}
        for name, client in clients.items():
            assert client.clear_cache.call_count == (1 if name == lazy else 0)
        assert srv._fulltext_xml_cache.stats()["entries"] == 1  # untouched

    def test_xml_only(self):
        client = _client_with_stats()
        srv._client_cache.set(client)
        srv._fulltext_xml_cache.set("PMC1", "<a/>")
        srv._fulltext_xml_cache.set("PMC2", "<b/>")

        out = _run(srv.clear_cache("xml"))

        assert out["results"] == {"xml": {"cleared": True, "entries_dropped": 2}}
        assert srv._fulltext_xml_cache.stats()["entries"] == 0
        client.clear_cache.assert_not_called()

    def test_all_clears_each_of_the_four(self):
        clients = [_client_with_stats() for _ in range(3)]
        srv._client_cache.set(clients[0])
        srv._article_client_cache.set(clients[1])
        srv._annotations_client_cache.set(clients[2])
        srv._fulltext_xml_cache.set("PMC1", "<a/>")

        out = _run(srv.clear_cache("all"))

        assert list(out["results"]) == ["search", "article", "annotations", "xml"]
        assert all(r["cleared"] for r in out["results"].values())
        assert all(c.clear_cache.call_count == 1 for c in clients)

    def test_a_cache_that_was_never_used_is_not_created_to_be_cleared(self):
        out = _run(srv.clear_cache("search"))
        assert out["results"]["search"] == {
            "cleared": False,
            "entries_dropped": 0,
            "reason": "nothing cached yet",
        }
        assert srv._client_cache.peek() is None

    def test_a_client_that_fails_to_clear_reports_it(self):
        client = _client_with_stats()
        client.clear_cache.return_value = False
        srv._client_cache.set(client)
        out = _run(srv.clear_cache("search"))
        assert out["results"]["search"] == {"cleared": False, "entries_dropped": 0}

    def test_clearing_twice_is_harmless(self):
        srv._fulltext_xml_cache.set("PMC1", "<a/>")
        _run(srv.clear_cache("xml"))
        again = _run(srv.clear_cache("xml"))
        assert again["results"]["xml"] == {"cleared": True, "entries_dropped": 0}
