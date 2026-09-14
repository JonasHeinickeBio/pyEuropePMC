"""Unit tests for pyeuropepmc.mcp.server infrastructure (hermetic).

These cover the FastMCP app wiring, the lazy-singleton cache, and the small
pure helpers — everything that isn't a specific tool's business logic (see
test_mcp_handlers.py for that).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
import logging
from unittest.mock import MagicMock

from mcp.server.fastmcp.exceptions import ToolError
import pytest

from pyeuropepmc.mcp import server as srv

ALL_CACHES = [
    srv._client_cache,
    srv._unified_cache,
    srv._citation_walker_cache,
    srv._clinical_trials_cache,
    srv._figure_extractor_cache,
    srv._llm_agent_cache,
    srv._bib_manager_cache,
    srv._bib_converter_cache,
    srv._bib_resolver_cache,
]


@pytest.fixture(autouse=True)
def _reset_singletons():
    for cache in ALL_CACHES:
        cache.reset()
    yield
    for cache in ALL_CACHES:
        cache.reset()


class TestLazy:
    """The generic thread-safe lazy singleton used for every cached client."""

    def test_get_calls_factory_once(self):
        factory = MagicMock(side_effect=lambda: object())
        lazy = srv._Lazy(factory)
        first = lazy.get()
        second = lazy.get()
        assert first is second
        factory.assert_called_once()

    def test_reset_forces_rebuild(self):
        factory = MagicMock(side_effect=lambda: object())
        lazy = srv._Lazy(factory)
        first = lazy.get()
        lazy.reset()
        second = lazy.get()
        assert first is not second
        assert factory.call_count == 2

    def test_set_bypasses_factory(self):
        factory = MagicMock(side_effect=AssertionError("factory should not run"))
        lazy = srv._Lazy(factory)
        sentinel = object()
        lazy.set(sentinel)
        assert lazy.get() is sentinel
        factory.assert_not_called()

    def test_failed_construction_is_retried(self):
        calls = {"n": 0}

        def factory():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return "ok"

        lazy = srv._Lazy(factory)
        with pytest.raises(RuntimeError):
            lazy.get()
        assert lazy.get() == "ok"
        assert calls["n"] == 2


class TestGetClient:
    def test_returns_search_client(self):
        client = srv._get_client()
        assert hasattr(client, "search_all")

    def test_has_caching_enabled(self):
        client = srv._get_client()
        assert client._cache is not None

    def test_cached_across_calls(self):
        assert srv._get_client() is srv._get_client()


class TestGetUnified:
    def test_unavailable_returns_none(self, monkeypatch):
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", False)
        assert srv._get_unified() is None

    def test_available_returns_cached_instance(self, monkeypatch):
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        sentinel = MagicMock()
        srv._unified_cache.set(sentinel)
        assert srv._get_unified() is sentinel


class TestRequireAvailable:
    def test_noop_when_available(self):
        srv._require_available(True, "Thing", "extra")  # must not raise

    def test_raises_with_install_hint(self):
        pattern = r"Thing not available.*pip install pyeuropepmc\[extra\]"
        with pytest.raises(ToolError, match=pattern):
            srv._require_available(False, "Thing", "extra")


class TestDedupReport:
    def test_extracts_expected_fields(self):
        report = MagicMock(total_input=10, total_output=6, duplicates_removed=4)
        assert srv._dedup_report(report) == {
            "total_input": 10,
            "total_output": 6,
            "duplicates_removed": 4,
        }


class TestToSerializable:
    def test_passthrough_scalar(self):
        assert srv._to_serializable(5) == 5
        assert srv._to_serializable("x") == "x"

    def test_dict_recurses(self):
        assert srv._to_serializable({"a": {"b": 1}}) == {"a": {"b": 1}}

    def test_list_and_tuple_recurse(self):
        assert srv._to_serializable([1, (2, 3)]) == [1, [2, 3]]

    def test_model_dump(self):
        obj = MagicMock()
        obj.model_dump.return_value = {"k": "v"}
        assert srv._to_serializable(obj) == {"k": "v"}

    def test_dict_method(self):
        class Legacy:
            def dict(self):
                return {"k": "v"}

        assert srv._to_serializable(Legacy()) == {"k": "v"}

    def test_to_dict_method(self):
        class Custom:
            def to_dict(self):
                return {"k": "v"}

        assert srv._to_serializable(Custom()) == {"k": "v"}

    def test_dataclass(self):
        @dataclass
        class Point:
            x: int
            y: int

        assert srv._to_serializable(Point(1, 2)) == {"x": 1, "y": 2}


class TestPaperSummaryFromRaw:
    def test_full_record(self):
        raw = {
            "pmid": "1",
            "pmcid": "PMC1",
            "doi": "10.1/x",
            "title": "T",
            "authorInfo": [{"author": "Smith J"}],
            "firstPublicationYear": "2020",
            "journalTitle": "J",
            "abstract": "A",
        }
        summary = srv._paper_summary_from_raw(raw)
        assert summary == {
            "pmid": "1",
            "pmcid": "PMC1",
            "doi": "10.1/x",
            "title": "T",
            "authors": [{"name": "Smith J"}],
            "publication_year": "2020",
            "journal": "J",
            "abstract": "A",
        }

    def test_missing_fields_default_empty(self):
        summary = srv._paper_summary_from_raw({"pmid": "1"})
        assert summary["pmid"] == "1"
        assert summary["authors"] == []
        assert summary["journal"] == ""


class TestFetchPaperSummary:
    def test_found(self):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        summary = asyncio.run(srv._fetch_paper_summary("1", client))
        assert summary["pmid"] == "1"
        assert summary["title"] == "T"
        client.search_all.assert_called_once_with("ext_id:1", pageSize=1)

    def test_not_found(self):
        client = MagicMock()
        client.search_all.return_value = []
        assert asyncio.run(srv._fetch_paper_summary("1", client)) is None


class TestServerVersion:
    def test_returns_installed_version(self):
        assert srv._server_version() != ""

    def test_falls_back_when_package_missing(self, monkeypatch):
        def _raise(_name):
            raise PackageNotFoundError

        monkeypatch.setattr(srv, "_pkg_version", _raise)
        assert srv._server_version() == "0.0.0+unknown"


class TestConfigureLogging:
    def test_sets_stderr_handler_and_level(self):
        root = logging.getLogger()
        previous_handlers = list(root.handlers)
        previous_level = root.level
        try:
            for h in previous_handlers:
                root.removeHandler(h)
            srv._configure_logging("DEBUG")
            assert root.level == logging.DEBUG
        finally:
            for h in list(root.handlers):
                root.removeHandler(h)
            for h in previous_handlers:
                root.addHandler(h)
            root.setLevel(previous_level)


class TestArgParser:
    def test_defaults_to_stdio(self, monkeypatch):
        monkeypatch.delenv("PYEUROPEPMC_MCP_TRANSPORT", raising=False)
        args = srv._build_arg_parser().parse_args([])
        assert args.transport == "stdio"
        assert args.host == "127.0.0.1"
        assert args.port == 8000
        assert args.log_level == "INFO"

    def test_env_vars_set_defaults(self, monkeypatch):
        monkeypatch.setenv("PYEUROPEPMC_MCP_TRANSPORT", "streamable-http")
        monkeypatch.setenv("PYEUROPEPMC_MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("PYEUROPEPMC_MCP_PORT", "9000")
        monkeypatch.setenv("PYEUROPEPMC_MCP_LOG_LEVEL", "WARNING")
        args = srv._build_arg_parser().parse_args([])
        assert args.transport == "streamable-http"
        assert args.host == "0.0.0.0"
        assert args.port == 9000
        assert args.log_level == "WARNING"

    def test_cli_flags_override_env(self, monkeypatch):
        monkeypatch.setenv("PYEUROPEPMC_MCP_TRANSPORT", "sse")
        args = srv._build_arg_parser().parse_args(["--transport", "stdio"])
        assert args.transport == "stdio"

    def test_rejects_unknown_transport(self):
        with pytest.raises(SystemExit):
            srv._build_arg_parser().parse_args(["--transport", "bogus"])


class TestToolAnnotationsHelper:
    def test_read_only_open_world_by_default(self):
        ann = srv._ro("Title")
        assert ann.title == "Title"
        assert ann.readOnlyHint is True
        assert ann.openWorldHint is True
        assert ann.idempotentHint is True

    def test_local_flag_flips_open_world(self):
        ann = srv._ro("Title", local=True)
        assert ann.openWorldHint is False

    def test_idempotent_override(self):
        ann = srv._ro("Title", idempotent=False)
        assert ann.idempotentHint is False


class TestToolRegistry:
    """FastMCP-level checks: every tool is discoverable with a valid schema."""

    EXPECTED_TOOLS = {
        "unified_search",
        "search_papers",
        "get_paper_details",
        "search_authors",
        "get_paper_citations",
        "citation_snowball",
        "clinical_trial_search",
        "fulltext_index_query",
        "paper_figures",
        "analyze_citations",
        "compare_citations",
        "summarize_citations",
        "paper_screening",
        "research_question_analysis",
        "preprint_analysis",
        "literature_review",
        "knowledge_graph",
        "bib_parse_string",
        "bib_validate",
        "bib_to_ris",
        "bib_to_csl",
        "ref_resolve_doi",
        "ref_resolve_pmid",
        "bib_merge",
    }

    def test_all_expected_tools_registered(self):
        tools = asyncio.run(srv.mcp.list_tools())
        names = {t.name for t in tools}
        assert names == self.EXPECTED_TOOLS

    def test_every_tool_has_description_and_schema(self):
        tools = asyncio.run(srv.mcp.list_tools())
        for tool in tools:
            assert tool.description
            assert tool.inputSchema["type"] == "object"

    def test_context_parameter_is_hidden_from_schema(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        assert "ctx" not in tools["unified_search"].inputSchema.get("properties", {})

    def test_unknown_tool_raises(self):
        with pytest.raises(ToolError, match="Unknown tool"):
            asyncio.run(srv.mcp.call_tool("totally_unknown", {}))

    def test_calling_tool_validates_input_types(self, monkeypatch):
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", True)
        args = {"identifier": "PMID:1", "strategy": "not-a-real-strategy"}
        with pytest.raises(Exception, match="strategy"):
            asyncio.run(srv.mcp.call_tool("citation_snowball", args))


class TestMainEntry:
    @pytest.fixture(autouse=True)
    def _no_real_logging_setup(self, monkeypatch):
        # _configure_logging mutates the root logger (see TestConfigureLogging,
        # which is careful to save/restore it); these tests are only about
        # argument-parsing/flag-plumbing to mcp.run, so skip that side effect.
        monkeypatch.setattr(srv, "_configure_logging", MagicMock())
        # srv.mcp is a module-level singleton reused for the whole test
        # session; restore its mutable settings so these tests don't leak
        # into whatever runs after them.
        previous_host, previous_port = srv.mcp.settings.host, srv.mcp.settings.port
        yield
        srv.mcp.settings.host, srv.mcp.settings.port = previous_host, previous_port

    def test_applies_flags_and_runs_requested_transport(self, monkeypatch):
        run = MagicMock()
        monkeypatch.setattr(srv.mcp, "run", run)

        srv._main_entry(["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9000"])

        assert srv.mcp.settings.host == "0.0.0.0"
        assert srv.mcp.settings.port == 9000
        run.assert_called_once_with(transport="streamable-http")

    def test_defaults_to_stdio(self, monkeypatch):
        run = MagicMock()
        monkeypatch.setattr(srv.mcp, "run", run)

        srv._main_entry([])

        run.assert_called_once_with(transport="stdio")
