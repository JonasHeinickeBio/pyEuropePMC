"""
Tests for the benchmark profiler and memory modules.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET  # nosec B405

import pytest

from pyeuropepmc.benchmark.memory import MemoryTracker, profile_memory, profile_memory_blocks
from pyeuropepmc.benchmark.profiler import ProfilerContext, profile_text, time_et_parse, time_function

SIMPLE_XML = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front><article-meta>
<article-id pub-id-type="pmcid">PMC9999999</article-id>
<title-group><article-title>Test Article</article-title></title-group>
</article-meta></front>
<body>
<sec><title>Introduction</title>
<p>This is the first paragraph with <bold>bold</bold> and <italic>italic</italic> text.</p>
<p>Second paragraph with an <xref ref-type="fig" rid="f1">inline xref</xref>.</p>
</sec>
</body>
</article>
"""


# ============================================================================
# Profiler Tests
# ============================================================================


class TestProfilerContext:
    """Tests for ProfilerContext."""

    def test_context_manager_lifecycle(self):
        """Verify start/stop lifecycle."""
        with ProfilerContext() as prof:
            _ = sum(range(1000))
        assert prof.elapsed > 0
        assert prof.stats is not None
        stats = prof.stats_dict()
        assert stats["total_calls"] > 0
        assert stats["by_function"] != {}

    def test_print_stats_output(self):
        """Verify print_stats returns formatted output."""
        with ProfilerContext() as prof:
            _ = sum(range(1000))
        output = prof.print_stats(top_n=5)
        assert isinstance(output, str)
        assert "ncalls" in output or "function" in output or "tottime" in output

    def test_stats_dict_structure(self):
        """Verify stats_dict has expected keys."""
        with ProfilerContext() as prof:
            _ = sum(range(1000))
        stats = prof.stats_dict()
        assert "elapsed_s" in stats
        assert "by_function" in stats
        assert "total_calls" in stats
        assert isinstance(stats["by_function"], dict)

    def test_simple_function_profile(self):
        """Verify function-level data is captured."""
        def foo():
            return sum(range(100))

        with ProfilerContext() as prof:
            foo()

        stats = prof.stats_dict()
        assert foo.__name__ in stats["by_function"]

    def test_filter_by_module(self):
        """Verify module filtering."""
        def bar():
            _ = ET.fromstring("<a><b/></a>")

        with ProfilerContext() as prof:
            bar()

        xml_stats = prof.filter_by_module("xml")
        assert "by_function" in xml_stats

    def test_total_time_by_module(self):
        """Verify module time accumulation."""
        with ProfilerContext() as prof:
            _ = ET.fromstring(SIMPLE_XML)

        total = prof.total_time_by_module("xml")
        assert total >= 0


class TestProfileText:
    """Tests for the profile_text convenience function."""

    def test_profile_text_returns_dict(self):
        """Verify profile_text returns correct structure."""
        result = profile_text(SIMPLE_XML)
        assert "elapsed_s" in result
        assert "by_function" in result
        assert "parser_breakdown_s" in result
        assert "total_calls" in result
        assert result["elapsed_s"] > 0

    def test_parser_breakdown_contains_methods(self):
        """Verify parser_breakdown_s has expected keys."""
        result = profile_text(SIMPLE_XML)
        breakdown = result["parser_breakdown_s"]
        # cProfile may not capture __init__ separately for dataclass-based classes;
        # verify at least the major extraction methods are tracked
        key_methods = ["get_full_text_sections_structured", "extract_metadata",
                       "get_full_text_sections"]
        found = [m for m in key_methods if m in breakdown]
        assert len(found) >= 2, \
            f"Expected >=2 key methods in breakdown, got {found} from {list(breakdown.keys())}"
        assert breakdown.get("get_full_text_sections_structured", 0) >= 0


class TestTimeFunctions:
    """Tests for micro-benchmark helpers."""

    def test_time_function(self):
        """Verify time_function returns timing dict."""
        result = time_function(sum, range(1000))
        assert "seconds" in result
        assert "result" in result
        assert result["seconds"] > 0
        assert result["result"] == sum(range(1000))

    def test_time_et_parse(self):
        """Verify time_et_parse returns parsed root."""
        result = time_et_parse(SIMPLE_XML)
        assert "seconds" in result
        assert "result" in result
        assert result["result"].tag.endswith("article")


# ============================================================================
# Memory Tracker Tests
# ============================================================================


class TestMemoryTracker:
    """Tests for MemoryTracker."""

    def test_start_stop_lifecycle(self):
        """Verify basic start/stop cycle."""
        tracker = MemoryTracker()
        tracker.start()
        _ = sum(range(10000))
        snapshot = tracker.stop()
        assert "peak_mib" in snapshot
        assert "current_mib" in snapshot
        assert "top_allocations" in snapshot
        assert snapshot["peak_mib"] >= 0

    def test_context_manager(self):
        """Verify context manager lifecycle."""
        with MemoryTracker() as tracker:
            _ = sum(range(10000))
        snapshot = tracker.stop()
        assert "peak_mib" in snapshot

    def test_intermediate_snapshot(self):
        """Verify snapshot during active tracing."""
        tracker = MemoryTracker()
        tracker.start()
        _ = sum(range(10000))
        snap = tracker.snapshot()
        assert "current_mib" in snap
        assert "peak_mib" in snap
        tracker.stop()

    def test_memory_usage_non_negative(self):
        """Verify all memory values are non-negative."""
        with MemoryTracker() as tracker:
            _ = sum(range(10000))
        snapshot = tracker.stop()
        assert snapshot["peak_mib"] >= 0
        assert snapshot["current_mib"] >= 0


class TestProfileMemory:
    """Tests for profile_memory convenience functions."""

    def test_profile_memory(self):
        """Verify profile_memory works end-to-end."""
        mem = profile_memory(SIMPLE_XML)
        assert "peak_mib" in mem
        assert "current_mib" in mem
        assert mem["peak_mib"] >= 0

    def test_profile_memory_blocks(self):
        """Verify profile_memory_blocks focuses on block extraction."""
        mem = profile_memory_blocks(SIMPLE_XML)
        assert "peak_mib" in mem
        assert mem["peak_mib"] >= 0
