"""The outage-to-skip rule in tests/conftest.py: which failures count as a third-party outage."""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "_suite_conftest", Path(__file__).parent / "conftest.py"
)
assert _spec is not None and _spec.loader is not None
_suite = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_suite)


@pytest.mark.parametrize(
    "text",
    [
        "[HTTP503] Service temporarily unavailable",
        "[HTTP502] Bad gateway",
        "[HTTP504] Gateway timeout",
        "[NET001] Network connection failed",
        "HTTPSConnectionPool: Read timed out. (read timeout=3)",
    ],
)
def test_outage_text_is_recognised(text):
    assert _suite._is_upstream_outage(RuntimeError(text))


@pytest.mark.parametrize(
    "text",
    [
        "assert 0 > 0",
        "[HTTP404] Not found",
        "[PARSE003] No XML content has been parsed",
        "KeyError: 'resultList'",
    ],
)
def test_other_failures_still_fail(text):
    assert not _suite._is_upstream_outage(RuntimeError(text))


def test_failed_assertion_is_never_an_outage():
    assert not _suite._is_upstream_outage(
        AssertionError("HTTP503 response was handled incorrectly")
    )


def test_live_service_markers_are_covered():
    assert {"functional", "network", "integration"} <= _suite._OUTAGE_CATEGORIES
    assert "unit" not in _suite._OUTAGE_CATEGORIES
