"""
External API enrichment for paper metadata.

This module provides integration with external academic APIs to enhance
paper metadata with additional information from CrossRef, Unpaywall,
Semantic Scholar, OpenAlex, and ORCID.

Clients are imported lazily (PEP 562).  Sources backed by an optional
third-party library (e.g. Semantic Scholar via the ``semanticscholar``
package, ``pip install pyeuropepmc[enrichment]``) do not import that library
until the client is instantiated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyeuropepmc._lazy import lazy_module

_LAZY = {
    "BaseEnrichmentClient": "pyeuropepmc.features.enrich.base:BaseEnrichmentClient",
    "EnrichmentConfig": "pyeuropepmc.features.enrich.config:EnrichmentConfig",
    "PaperEnricher": "pyeuropepmc.features.enrich.enricher:PaperEnricher",
    "CrossRefClient": "pyeuropepmc.features.enrich.sources.crossref:CrossRefClient",
    "DataCiteClient": "pyeuropepmc.features.enrich.sources.datacite:DataCiteClient",
    "ICiteClient": "pyeuropepmc.features.enrich.sources.icite:ICiteClient",
    "OpenAlexClient": "pyeuropepmc.features.enrich.sources.openalex:OpenAlexClient",
    "OrcidClient": "pyeuropepmc.features.enrich.sources.orcid:OrcidClient",
    "RorClient": "pyeuropepmc.features.enrich.sources.ror:RorClient",
    "SemanticScholarClient": (
        "pyeuropepmc.features.enrich.sources.semantic_scholar:SemanticScholarClient"
    ),
    "UnpaywallClient": "pyeuropepmc.features.enrich.sources.unpaywall:UnpaywallClient",
}

_lazy_getattr, __dir__, __all__ = lazy_module(__name__, _LAZY)


def __getattr__(name: str) -> Any:
    """Resolve a public attribute lazily (see :mod:`pyeuropepmc._lazy`)."""
    return _lazy_getattr(name)


if TYPE_CHECKING:
    from pyeuropepmc.features.enrich.base import BaseEnrichmentClient as BaseEnrichmentClient
    from pyeuropepmc.features.enrich.config import EnrichmentConfig as EnrichmentConfig
    from pyeuropepmc.features.enrich.enricher import PaperEnricher as PaperEnricher
    from pyeuropepmc.features.enrich.sources.crossref import CrossRefClient as CrossRefClient
    from pyeuropepmc.features.enrich.sources.datacite import DataCiteClient as DataCiteClient
    from pyeuropepmc.features.enrich.sources.icite import ICiteClient as ICiteClient
    from pyeuropepmc.features.enrich.sources.openalex import OpenAlexClient as OpenAlexClient
    from pyeuropepmc.features.enrich.sources.orcid import OrcidClient as OrcidClient
    from pyeuropepmc.features.enrich.sources.ror import RorClient as RorClient
    from pyeuropepmc.features.enrich.sources.semantic_scholar import (
        SemanticScholarClient as SemanticScholarClient,
    )
    from pyeuropepmc.features.enrich.sources.unpaywall import UnpaywallClient as UnpaywallClient
