"""
External API enrichment for paper metadata.

This module provides integration with external academic APIs to enhance
paper metadata with additional information from CrossRef, Unpaywall,
Semantic Scholar, and OpenAlex.
"""

from pyeuropepmc.enrichment.base import BaseEnrichmentClient
from pyeuropepmc.enrichment.config import EnrichmentConfig
from pyeuropepmc.enrichment.crossref import CrossRefClient
from pyeuropepmc.enrichment.datacite import DataCiteClient
from pyeuropepmc.enrichment.enricher import PaperEnricher
from pyeuropepmc.enrichment.openalex import OpenAlexClient
from pyeuropepmc.enrichment.ror import RorClient
from pyeuropepmc.enrichment.semantic_scholar import SemanticScholarClient
from pyeuropepmc.enrichment.unpaywall import UnpaywallClient

__all__ = [
    "BaseEnrichmentClient",
    "CrossRefClient",
    "DataCiteClient",
    "UnpaywallClient",
    "SemanticScholarClient",
    "OpenAlexClient",
    "RorClient",
    "PaperEnricher",
    "EnrichmentConfig",
]
