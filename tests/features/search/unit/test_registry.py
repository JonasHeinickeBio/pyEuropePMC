"""Unit tests for the pluggable literature-source registry."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from pyeuropepmc._optional_imports import OptionalDependencyError
from pyeuropepmc.features.search import registry


def test_builtin_sources_registered():
    names = set(registry.available_sources())
    assert {"europepmc", "pubmed", "arxiv", "semantic_scholar", "openalex"} <= names


def test_get_source_spec_unknown_raises():
    with pytest.raises(KeyError, match="Unknown source"):
        registry.get_source_spec("does-not-exist")


def test_capabilities_lookup():
    caps = registry.source_capabilities("europepmc")
    assert "search" in caps and "fulltext" in caps


def test_resolve_returns_class_without_instantiating():
    cls = registry.get_source_spec("pubmed").resolve()
    assert cls.__name__ == "PubMedClient"


def test_available_sources_installed_only_filters_missing_extra(monkeypatch):
    spec = registry.get_source_spec("semantic_scholar")
    assert spec.extras == ("semanticscholar",)

    monkeypatch.setattr(registry, "is_package_available", lambda mod: mod != "semanticscholar")
    installed = registry.available_sources(installed_only=True)
    assert "semantic_scholar" not in installed
    assert "pubmed" in installed


def test_load_source_missing_extra_raises_helpful_error(monkeypatch):
    monkeypatch.setattr(registry, "is_package_available", lambda mod: mod != "semanticscholar")
    with pytest.raises(OptionalDependencyError) as exc:
        registry.load_source("semantic_scholar")
    assert "pip install pyeuropepmc[semanticscholar]" in str(exc.value)


def test_acceptable_kwargs_filters_to_signature():
    class _C:
        def __init__(self, rate_limit_delay: float = 1.0, timeout: int = 15) -> None:
            pass

    assert registry._acceptable_kwargs(_C) == {"rate_limit_delay", "timeout"}

    class _Var:
        def __init__(self, **kwargs: object) -> None:
            pass

    assert registry._acceptable_kwargs(_Var) is None


def test_load_source_tolerates_extra_kwargs():
    # ArxivClient.__init__ has no api_key / email params; load_source must drop them.
    client = registry.load_source(
        "arxiv", rate_limit_delay=2.0, timeout=9, api_key="unused", email="x@y.z"
    )
    assert client.rate_limit_delay == 2.0
    assert client.timeout == 9


def test_load_source_warns_when_a_declared_credential_is_dropped(caplog):
    """A credential the spec advertises must not vanish silently."""
    spec = registry.get_source_spec("arxiv")
    assert "api_key" not in spec.credential_kwargs  # arXiv declares no credentials

    registry.register_source(
        registry.SourceSpec("arxiv-with-key", spec.target, credential_kwargs=("api_key",)),
    )
    try:
        with caplog.at_level(logging.WARNING, logger=registry.logger.name):
            registry.load_source("arxiv-with-key", api_key="secret", timeout=9)
    finally:
        registry._REGISTRY.pop("arxiv-with-key", None)

    messages = [r.getMessage() for r in caplog.records]
    assert any("api_key" in m and "dropped" in m for m in messages), messages
    assert all("secret" not in m for m in messages), "the credential value must not be logged"


def test_load_source_does_not_warn_for_ordinary_extra_kwargs(caplog):
    with caplog.at_level(logging.WARNING, logger=registry.logger.name):
        registry.load_source("arxiv", timeout=9, not_a_credential=1)
    assert caplog.records == []


def test_openalex_adapter_accepts_the_email_credential():
    """``credential_kwargs=("email",)`` on the openalex spec must reach the client."""
    assert "email" in registry.get_source_spec("openalex").credential_kwargs

    client = registry.load_source("openalex", email="polite@example.org", timeout=9)

    assert client.enrichment_client.email == "polite@example.org"
    assert client._mailto == "polite@example.org"


class TestLoadEntryPointSources:
    """`load_entry_point_sources` is used by third-party plugins, not by this
    package itself, so nothing else in the suite exercises it."""

    def test_no_entry_points_is_a_noop(self, monkeypatch):
        monkeypatch.setattr("importlib.metadata.entry_points", lambda group: [])
        registry.load_entry_point_sources()  # must not raise

    def test_successful_entry_point_is_invoked(self, monkeypatch):
        callback = MagicMock()
        ep = MagicMock()
        ep.name = "fake-source"
        ep.load.return_value = callback
        monkeypatch.setattr("importlib.metadata.entry_points", lambda group: [ep])

        registry.load_entry_point_sources()

        callback.assert_called_once_with()

    def test_failing_entry_point_is_logged_not_raised(self, monkeypatch):
        ep = MagicMock()
        ep.name = "broken-source"
        ep.load.side_effect = RuntimeError("boom")
        monkeypatch.setattr("importlib.metadata.entry_points", lambda group: [ep])

        registry.load_entry_point_sources()  # must not raise

    def test_uses_the_requested_group(self, monkeypatch):
        entry_points = MagicMock(return_value=[])
        monkeypatch.setattr("importlib.metadata.entry_points", entry_points)

        registry.load_entry_point_sources(group="custom.group")

        entry_points.assert_called_once_with(group="custom.group")


def test_register_and_override(monkeypatch):
    spec = registry.SourceSpec("unit-test-src", "pkg.mod:Cls")
    registry.register_source(spec)
    try:
        assert "unit-test-src" in registry.available_sources()
        with pytest.raises(ValueError, match="already registered"):
            registry.register_source(spec)
        registry.register_source(
            registry.SourceSpec("unit-test-src", "pkg.other:Cls2"), replace=True
        )
        assert registry.get_source_spec("unit-test-src").target == "pkg.other:Cls2"
    finally:
        registry._REGISTRY.pop("unit-test-src", None)
