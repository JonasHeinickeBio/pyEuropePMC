"""Multi-source literature search clients.

This slice provides pluggable clients for searching literature
from multiple sources (PubMed, arXiv, ClinicalTrials.gov, CORE, DBLP,
DOAJ, HAL, Zenodo) with a unified interface and automatic deduplication.
"""

from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.features.search.unified_search import UnifiedSearch
from pyeuropepmc.features.search.sources.arxiv import ArxivClient
from pyeuropepmc.features.search.sources.clinicaltrials import ClinicalTrialsClient
from pyeuropepmc.features.search.sources.core import COREClient
from pyeuropepmc.features.search.sources.dblp import DBLPClient
from pyeuropepmc.features.search.sources.doaj import DOAJClient
from pyeuropepmc.features.search.sources.hal import HALClient
from pyeuropepmc.features.search.sources.pubmed import PubMedClient
from pyeuropepmc.features.search.sources.zenodo import ZenodoClient

__all__ = [
    "ArxivClient",
    "BaseLiteratureClient",
    "ClinicalTrialsClient",
    "COREClient",
    "DBLPClient",
    "DOAJClient",
    "HALClient",
    "PubMedClient",
    "UnifiedSearch",
    "ZenodoClient",
]
