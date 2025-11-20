"""
Configuration classes for enrichment.

This module contains configuration classes used across the enrichment system.
"""

import os

from pyeuropepmc.cache.cache import CacheConfig


class EnrichmentConfig:
    """
    Configuration for paper enrichment.

    Attributes
    ----------
    enable_crossref : bool
        Enable CrossRef enrichment
    enable_datacite : bool
        Enable DataCite enrichment
    enable_unpaywall : bool
        Enable Unpaywall enrichment
    enable_semantic_scholar : bool
        Enable Semantic Scholar enrichment
    enable_openalex : bool
        Enable OpenAlex enrichment
    enable_ror : bool
        Enable ROR institutional enrichment
    unpaywall_email : str, optional
        Email for Unpaywall API (required if enable_unpaywall=True)
    crossref_email : str, optional
        Email for CrossRef polite pool (optional but recommended)
    datacite_email : str, optional
        Email for DataCite (optional)
    semantic_scholar_api_key : str, optional
        API key for Semantic Scholar (optional but recommended)
    openalex_email : str, optional
        Email for OpenAlex polite pool (optional but recommended)
    ror_email : str, optional
        Email for ROR API (optional)
    ror_client_id : str, optional
        Client ID for ROR API (optional, for higher rate limits)
    cache_config : CacheConfig, optional
        Cache configuration for API responses
    rate_limit_delay : float
        Delay between API requests in seconds
    """

    def __init__(
        self,
        enable_crossref: bool = True,
        enable_datacite: bool = False,
        enable_unpaywall: bool = False,
        enable_semantic_scholar: bool = True,
        enable_openalex: bool = True,
        enable_ror: bool = False,
        unpaywall_email: str | None = None,
        crossref_email: str | None = None,
        datacite_email: str | None = None,
        semantic_scholar_api_key: str | None = None,
        openalex_email: str | None = None,
        ror_email: str | None = None,
        ror_client_id: str | None = None,
        cache_config: CacheConfig | None = None,
        rate_limit_delay: float = 1.0,
    ) -> None:
        """
        Initialize enrichment configuration.

        Parameters
        ----------
        enable_crossref : bool, optional
            Enable CrossRef enrichment (default: True)
        enable_datacite : bool, optional
            Enable DataCite enrichment (default: False)
        enable_unpaywall : bool, optional
            Enable Unpaywall enrichment (default: False, requires email)
        enable_semantic_scholar : bool, optional
            Enable Semantic Scholar enrichment (default: True)
        enable_openalex : bool, optional
            Enable OpenAlex enrichment (default: True)
        enable_ror : bool, optional
            Enable ROR institutional enrichment (default: False)
        unpaywall_email : str, optional
            Email for Unpaywall API (required if enable_unpaywall=True)
        crossref_email : str, optional
            Email for CrossRef polite pool
        datacite_email : str, optional
            Email for DataCite
        semantic_scholar_api_key : str, optional
            API key for Semantic Scholar
        openalex_email : str, optional
            Email for OpenAlex polite pool
        ror_email : str, optional
            Email for ROR API
        ror_client_id : str, optional
            Client ID for ROR API (for higher rate limits)
        cache_config : CacheConfig, optional
            Cache configuration
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)

        Raises
        ------
        ValueError
            If Unpaywall is enabled but email is not provided
        """
        # Load from environment variables if not provided
        self.unpaywall_email = unpaywall_email or os.environ.get("UNPAYWALL_EMAIL")
        self.crossref_email = crossref_email or os.environ.get("CROSSREF_EMAIL")
        self.datacite_email = datacite_email or os.environ.get("DATACITE_EMAIL")
        self.semantic_scholar_api_key = semantic_scholar_api_key or os.environ.get(
            "SEMANTIC_SCHOLAR_API_KEY"
        )
        self.openalex_email = openalex_email or os.environ.get("OPENALEX_EMAIL")
        self.ror_email = ror_email or os.environ.get("ROR_EMAIL")
        self.ror_client_id = ror_client_id or os.environ.get("ROR_CLIENT_ID")

        self.enable_crossref = enable_crossref
        self.enable_datacite = enable_datacite
        self.enable_unpaywall = enable_unpaywall
        self.enable_semantic_scholar = enable_semantic_scholar
        self.enable_openalex = enable_openalex
        self.enable_ror = enable_ror
        self.cache_config = cache_config
        self.rate_limit_delay = rate_limit_delay

        # Validate configuration
        if enable_unpaywall and not self.unpaywall_email:
            raise ValueError("unpaywall_email is required when enable_unpaywall=True")
