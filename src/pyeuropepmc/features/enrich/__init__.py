"""
External API enrichment for paper metadata.

This module provides integration with external academic APIs to enhance
paper metadata with additional information from CrossRef, Unpaywall,
Semantic Scholar, OpenAlex, and ORCID.
"""

from pyeuropepmc.features.enrich.base import BaseEnrichmentClient
from pyeuropepmc.features.enrich.config import EnrichmentConfig
from pyeuropepmc.features.enrich.sources.crossref import CrossRefClient
from pyeuropepmc.features.enrich.sources.datacite import DataCiteClient
from pyeuropepmc.features.enrich.enricher import PaperEnricher
from pyeuropepmc.features.enrich.sources.icite import ICiteClient
from pyeuropepmc.features.enrich.sources.openalex import OpenAlexClient
from pyeuropepmc.features.enrich.sources.orcid import OrcidClient
from pyeuropepmc.features.enrich.sources.ror import RorClient
from pyeuropepmc.features.enrich.sources.semantic_scholar import SemanticScholarClient
from pyeuropepmc.features.enrich.sources.unpaywall import UnpaywallClient

__all__ = [
    "BaseEnrichmentClient",
    "CrossRefClient",
    "DataCiteClient",
    "EnrichmentConfig",
    "ICiteClient",
    "OpenAlexClient",
    "OrcidClient",
    "PaperEnricher",
    "RorClient",
    "SemanticScholarClient",
    "UnpaywallClient",
]
