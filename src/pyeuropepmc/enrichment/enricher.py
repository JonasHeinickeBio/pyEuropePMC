"""
Paper enrichment orchestrator for combining multiple external APIs.

This module provides a high-level interface for enriching paper metadata
using multiple external APIs (CrossRef, Unpaywall, Semantic Scholar, OpenAlex).
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.crossref import CrossRefClient
from pyeuropepmc.enrichment.openalex import OpenAlexClient
from pyeuropepmc.enrichment.semantic_scholar import SemanticScholarClient
from pyeuropepmc.enrichment.unpaywall import UnpaywallClient

logger = logging.getLogger(__name__)

__all__ = ["PaperEnricher", "EnrichmentConfig"]


class EnrichmentConfig:
    """
    Configuration for paper enrichment.

    Attributes
    ----------
    enable_crossref : bool
        Enable CrossRef enrichment
    enable_unpaywall : bool
        Enable Unpaywall enrichment
    enable_semantic_scholar : bool
        Enable Semantic Scholar enrichment
    enable_openalex : bool
        Enable OpenAlex enrichment
    unpaywall_email : str, optional
        Email for Unpaywall API (required if enable_unpaywall=True)
    crossref_email : str, optional
        Email for CrossRef polite pool (optional but recommended)
    semantic_scholar_api_key : str, optional
        API key for Semantic Scholar (optional but recommended)
    openalex_email : str, optional
        Email for OpenAlex polite pool (optional but recommended)
    cache_config : CacheConfig, optional
        Cache configuration for API responses
    rate_limit_delay : float
        Delay between API requests in seconds
    """

    def __init__(
        self,
        enable_crossref: bool = True,
        enable_unpaywall: bool = False,
        enable_semantic_scholar: bool = True,
        enable_openalex: bool = True,
        unpaywall_email: str | None = None,
        crossref_email: str | None = None,
        semantic_scholar_api_key: str | None = None,
        openalex_email: str | None = None,
        cache_config: CacheConfig | None = None,
        rate_limit_delay: float = 1.0,
    ) -> None:
        """
        Initialize enrichment configuration.

        Parameters
        ----------
        enable_crossref : bool, optional
            Enable CrossRef enrichment (default: True)
        enable_unpaywall : bool, optional
            Enable Unpaywall enrichment (default: False, requires email)
        enable_semantic_scholar : bool, optional
            Enable Semantic Scholar enrichment (default: True)
        enable_openalex : bool, optional
            Enable OpenAlex enrichment (default: True)
        unpaywall_email : str, optional
            Email for Unpaywall API (required if enable_unpaywall=True)
        crossref_email : str, optional
            Email for CrossRef polite pool
        semantic_scholar_api_key : str, optional
            API key for Semantic Scholar
        openalex_email : str, optional
            Email for OpenAlex polite pool
        cache_config : CacheConfig, optional
            Cache configuration
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)

        Raises
        ------
        ValueError
            If Unpaywall is enabled but email is not provided
        """
        self.enable_crossref = enable_crossref
        self.enable_unpaywall = enable_unpaywall
        self.enable_semantic_scholar = enable_semantic_scholar
        self.enable_openalex = enable_openalex
        self.unpaywall_email = unpaywall_email
        self.crossref_email = crossref_email
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self.openalex_email = openalex_email
        self.cache_config = cache_config
        self.rate_limit_delay = rate_limit_delay

        # Validate configuration
        if enable_unpaywall and not unpaywall_email:
            raise ValueError("unpaywall_email is required when enable_unpaywall=True")


class PaperEnricher:
    """
    High-level orchestrator for enriching paper metadata.

    This class coordinates multiple external APIs to provide comprehensive
    metadata enrichment while handling errors gracefully and respecting
    rate limits.

    Examples
    --------
    >>> from pyeuropepmc.enrichment import PaperEnricher, EnrichmentConfig
    >>> config = EnrichmentConfig(
    ...     enable_crossref=True,
    ...     enable_semantic_scholar=True,
    ...     crossref_email="your@email.com"
    ... )
    >>> enricher = PaperEnricher(config)
    >>> enriched = enricher.enrich_paper(doi="10.1371/journal.pone.0123456")
    >>> print(f"Sources: {enriched.get('sources')}")
    >>> print(f"Citations: {enriched.get('citation_count')}")
    """

    def __init__(self, config: EnrichmentConfig) -> None:
        """
        Initialize paper enricher.

        Parameters
        ----------
        config : EnrichmentConfig
            Configuration for enrichment
        """
        self.config = config
        self.clients: dict[str, Any] = {}

        # Initialize enabled clients
        if config.enable_crossref:
            self.clients["crossref"] = CrossRefClient(
                rate_limit_delay=config.rate_limit_delay,
                cache_config=config.cache_config,
                email=config.crossref_email,
            )
            logger.info("CrossRef client initialized")

        if config.enable_unpaywall:
            if config.unpaywall_email:  # Type guard
                self.clients["unpaywall"] = UnpaywallClient(
                    email=config.unpaywall_email,
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                )
                logger.info("Unpaywall client initialized")
            else:
                logger.warning("Unpaywall enabled but email not provided, skipping initialization")

        if config.enable_semantic_scholar:
            self.clients["semantic_scholar"] = SemanticScholarClient(
                rate_limit_delay=config.rate_limit_delay,
                cache_config=config.cache_config,
                api_key=config.semantic_scholar_api_key,
            )
            logger.info("Semantic Scholar client initialized")

        if config.enable_openalex:
            self.clients["openalex"] = OpenAlexClient(
                rate_limit_delay=config.rate_limit_delay,
                cache_config=config.cache_config,
                email=config.openalex_email,
            )
            logger.info("OpenAlex client initialized")

        logger.info(f"PaperEnricher initialized with {len(self.clients)} clients")

    def __enter__(self) -> "PaperEnricher":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and clean up resources."""
        self.close()

    def close(self) -> None:
        """Close all API clients."""
        for name, client in self.clients.items():
            try:
                client.close()
                logger.debug(f"Closed {name} client")
            except Exception as e:
                logger.warning(f"Error closing {name} client: {e}")

    def enrich_paper(self, doi: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Enrich paper metadata using all configured APIs.

        Parameters
        ----------
        doi : str, optional
            Paper DOI
        **kwargs
            Additional parameters for specific APIs

        Returns
        -------
        dict
            Merged enriched metadata from all sources with keys:
            - sources: List of sources that provided data
            - crossref: CrossRef metadata (if available)
            - unpaywall: Unpaywall OA info (if available)
            - semantic_scholar: Semantic Scholar metrics (if available)
            - openalex: OpenAlex metadata (if available)
            - merged: Merged/aggregated metadata from all sources

        Raises
        ------
        ValueError
            If DOI is not provided and required by enabled clients
        """
        if not doi:
            raise ValueError("DOI is required for enrichment")

        results: dict[str, Any] = {
            "doi": doi,
            "sources": [],
            "crossref": None,
            "unpaywall": None,
            "semantic_scholar": None,
            "openalex": None,
        }

        # Enrich from each source
        for source_name, client in self.clients.items():
            try:
                logger.debug(f"Enriching from {source_name}")
                data = client.enrich(doi=doi, **kwargs)
                if data:
                    results[source_name] = data
                    results["sources"].append(source_name)
                    logger.info(f"Successfully enriched from {source_name}")
                else:
                    logger.warning(f"No data from {source_name}")
            except Exception as e:
                logger.error(f"Error enriching from {source_name}: {e}", exc_info=True)
                # Continue with other sources

        # Merge results
        if results["sources"]:
            results["merged"] = self._merge_results(results)
            logger.info(f"Enrichment complete with {len(results['sources'])} sources")
        else:
            logger.warning(f"No enrichment data found for DOI: {doi}")
            results["merged"] = {}

        return results

    def _merge_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """
        Merge results from multiple sources into a single metadata dict.

        Parameters
        ----------
        results : dict
            Results from all sources

        Returns
        -------
        dict
            Merged metadata
        """
        merged: dict[str, Any] = {}

        # Priority order for fields (prefer more reliable sources)
        # CrossRef is authoritative for bibliographic data
        # Semantic Scholar is good for metrics
        # OpenAlex provides comprehensive coverage
        # Unpaywall is best for OA status

        # Title (prefer CrossRef, then OpenAlex, then Semantic Scholar)
        for source in ["crossref", "openalex", "semantic_scholar"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict) and source_data.get("title"):
                merged["title"] = source_data["title"]
                break

        # Authors (prefer CrossRef, then OpenAlex)
        for source in ["crossref", "openalex"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict) and source_data.get("authors"):
                merged["authors"] = source_data["authors"]
                break

        # Abstract (prefer CrossRef, then Semantic Scholar)
        for source in ["crossref", "semantic_scholar"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict) and source_data.get("abstract"):
                merged["abstract"] = source_data["abstract"]
                break

        # Journal/venue (prefer CrossRef, then OpenAlex)
        for source in ["crossref", "openalex"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict):
                journal = source_data.get("journal") or source_data.get("venue", {})
                if journal:
                    merged["journal"] = journal
                    break

        # Publication date/year (prefer CrossRef)
        crossref_data = results.get("crossref")
        openalex_data = results.get("openalex")
        if crossref_data and isinstance(crossref_data, dict) and crossref_data.get("publication_date"):
            merged["publication_date"] = crossref_data["publication_date"]
        elif openalex_data and isinstance(openalex_data, dict):
            if openalex_data.get("publication_date"):
                merged["publication_date"] = openalex_data["publication_date"]
            elif openalex_data.get("publication_year"):
                merged["publication_year"] = openalex_data["publication_year"]

        # Citation count (aggregate from all sources)
        citation_counts = []
        for source in ["crossref", "semantic_scholar", "openalex"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict):
                count = source_data.get("citation_count")
                if count is not None:
                    citation_counts.append({"source": source, "count": count})

        if citation_counts:
            merged["citation_counts"] = citation_counts
            # Use the maximum as the primary citation count
            merged["citation_count"] = max(c["count"] for c in citation_counts)

        # Open access information (from Unpaywall or OpenAlex)
        unpaywall_data = results.get("unpaywall")
        if unpaywall_data and isinstance(unpaywall_data, dict):
            merged["is_oa"] = unpaywall_data.get("is_oa", False)
            merged["oa_status"] = unpaywall_data.get("oa_status")
            best_oa = unpaywall_data.get("best_oa_location")
            if best_oa and isinstance(best_oa, dict):
                merged["oa_url"] = best_oa.get("url")
        elif openalex_data and isinstance(openalex_data, dict):
            merged["is_oa"] = openalex_data.get("is_oa", False)
            merged["oa_status"] = openalex_data.get("oa_status")
            merged["oa_url"] = openalex_data.get("oa_url")

        # Additional metrics from Semantic Scholar
        semantic_data = results.get("semantic_scholar")
        if semantic_data and isinstance(semantic_data, dict):
            merged["influential_citation_count"] = semantic_data.get(
                "influential_citation_count"
            )
            merged["fields_of_study"] = semantic_data.get("fields_of_study")

        # Topics from OpenAlex
        if openalex_data and isinstance(openalex_data, dict):
            merged["topics"] = openalex_data.get("topics")

        # License information (from CrossRef)
        if crossref_data and isinstance(crossref_data, dict) and crossref_data.get("license"):
            merged["license"] = crossref_data["license"]

        # Funders (from CrossRef)
        if crossref_data and isinstance(crossref_data, dict) and crossref_data.get("funders"):
            merged["funders"] = crossref_data["funders"]

        return merged
