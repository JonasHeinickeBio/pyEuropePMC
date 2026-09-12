"""Hermetic defaults for the enrichment unit tests.

``PaperEnricher`` now resolves an identifier to a ``{doi, pmid, pmcid}`` bundle
via one Europe PMC query, and enables Europe PMC + iCite sources by default.
Unit tests must not touch the network, so this autouse fixture stubs the
Europe PMC id-resolution lookup and the two extra network sources. Tests that
want real behaviour can re-patch these objects themselves.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _hermetic_enricher(monkeypatch: pytest.MonkeyPatch) -> None:
    # _resolve_ids() -> SearchClient().search_and_parse(...)
    fake_search = MagicMock()
    fake_search.return_value.__enter__.return_value.search_and_parse.return_value = []
    monkeypatch.setattr(
        "pyeuropepmc.features.enrich.enricher.SearchClient", fake_search, raising=False
    )

    # Europe PMC / iCite enrichment clients: no-op unless a test overrides.
    monkeypatch.setattr(
        "pyeuropepmc.features.enrich.sources.europepmc.EuropePMCEnrichmentClient.enrich",
        lambda self, *a, **k: None,
        raising=False,
    )
    monkeypatch.setattr(
        "pyeuropepmc.features.enrich.sources.icite.ICiteClient.enrich",
        lambda self, *a, **k: None,
        raising=False,
    )
