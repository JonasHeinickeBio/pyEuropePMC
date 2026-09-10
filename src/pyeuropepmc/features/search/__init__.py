"""Multi-source literature search clients.

This slice provides pluggable clients for searching literature
from multiple sources (PubMed, arXiv, ClinicalTrials.gov, CORE, DBLP,
DOAJ, HAL, Zenodo) with a unified interface and automatic deduplication.

Clients are imported lazily (PEP 562): ``from pyeuropepmc.features.search
import UnifiedSearch`` does not import every source client, and no source
client is loaded until it is actually selected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyeuropepmc._lazy import lazy_module

_LAZY = {
    "BaseLiteratureClient": "pyeuropepmc.features.search.base:BaseLiteratureClient",
    "UnifiedSearch": "pyeuropepmc.features.search.unified_search:UnifiedSearch",
    "SourceSpec": "pyeuropepmc.features.search.registry:SourceSpec",
    "register_source": "pyeuropepmc.features.search.registry:register_source",
    "available_sources": "pyeuropepmc.features.search.registry:available_sources",
    "source_capabilities": "pyeuropepmc.features.search.registry:source_capabilities",
    "load_source": "pyeuropepmc.features.search.registry:load_source",
    "translate_query": "pyeuropepmc.features.search.query_translation:translate_query",
    "ArxivClient": "pyeuropepmc.features.search.sources.arxiv:ArxivClient",
    "ClinicalTrialsClient": (
        "pyeuropepmc.features.search.sources.clinicaltrials:ClinicalTrialsClient"
    ),
    "COREClient": "pyeuropepmc.features.search.sources.core:COREClient",
    "DBLPClient": "pyeuropepmc.features.search.sources.dblp:DBLPClient",
    "DOAJClient": "pyeuropepmc.features.search.sources.doaj:DOAJClient",
    "HALClient": "pyeuropepmc.features.search.sources.hal:HALClient",
    "PubMedClient": "pyeuropepmc.features.search.sources.pubmed:PubMedClient",
    "ZenodoClient": "pyeuropepmc.features.search.sources.zenodo:ZenodoClient",
}

_lazy_getattr, __dir__, __all__ = lazy_module(__name__, _LAZY)


def __getattr__(name: str) -> Any:
    """Resolve a public attribute lazily (see :mod:`pyeuropepmc._lazy`)."""
    return _lazy_getattr(name)


if TYPE_CHECKING:
    from pyeuropepmc.features.search.base import BaseLiteratureClient as BaseLiteratureClient
    from pyeuropepmc.features.search.query_translation import translate_query as translate_query
    from pyeuropepmc.features.search.registry import (
        SourceSpec as SourceSpec,
        available_sources as available_sources,
        load_source as load_source,
        register_source as register_source,
        source_capabilities as source_capabilities,
    )
    from pyeuropepmc.features.search.sources.arxiv import ArxivClient as ArxivClient
    from pyeuropepmc.features.search.sources.clinicaltrials import (
        ClinicalTrialsClient as ClinicalTrialsClient,
    )
    from pyeuropepmc.features.search.sources.core import COREClient as COREClient
    from pyeuropepmc.features.search.sources.dblp import DBLPClient as DBLPClient
    from pyeuropepmc.features.search.sources.doaj import DOAJClient as DOAJClient
    from pyeuropepmc.features.search.sources.hal import HALClient as HALClient
    from pyeuropepmc.features.search.sources.pubmed import PubMedClient as PubMedClient
    from pyeuropepmc.features.search.sources.zenodo import ZenodoClient as ZenodoClient
    from pyeuropepmc.features.search.unified_search import UnifiedSearch as UnifiedSearch
