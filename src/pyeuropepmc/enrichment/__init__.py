"""
External API enrichment for paper metadata.

This module provides integration with external academic APIs to enhance
paper metadata with additional information from CrossRef, Unpaywall,
Semantic Scholar, and OpenAlex.
"""

from pyeuropepmc.enrichment.base import BaseEnrichmentClient
from pyeuropepmc.enrichment.crossref import CrossRefClient
from pyeuropepmc.enrichment.enricher import EnrichmentConfig, PaperEnricher
from pyeuropepmc.enrichment.openalex import OpenAlexClient
from pyeuropepmc.enrichment.semantic_scholar import SemanticScholarClient
from pyeuropepmc.enrichment.unpaywall import UnpaywallClient

__all__ = [
    "BaseEnrichmentClient",
    "CrossRefClient",
    "UnpaywallClient",
    "SemanticScholarClient",
    "OpenAlexClient",
    "PaperEnricher",
    "EnrichmentConfig",
]
