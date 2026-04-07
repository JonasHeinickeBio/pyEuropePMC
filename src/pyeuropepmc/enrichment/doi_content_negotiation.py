"""
DOI Content Negotiation API client for resolving DOIs to metadata.

This client implements DOI content negotiation (RFC 7240) to resolve DOIs
to structured metadata from the appropriate registration agency.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["DoiContentNegotiationClient"]


class DoiContentNegotiationClient(BaseEnrichmentClient):
    """
    Client for DOI Content Negotiation API.

    DOI Content Negotiation allows requesting metadata in different formats
    by setting the Accept header. This client primarily requests JSON metadata
    and routes to the appropriate registration agency (CrossRef, DataCite, etc.).

    Supports content negotiation for:
    - CrossRef DOIs (10.1002/, 10.1038/, 10.1371/, etc.)
    - DataCite DOIs (10.5061/, 10.5281/, etc.)
    - Other DOI registration agencies

    Examples
    --------
    >>> client = DoiContentNegotiationClient()
    >>> metadata = client.enrich(doi="10.1038/s41392-025-02280-1")
    >>> if metadata:
    ...     print(f"Title: {metadata.get('title')}")
    ...     print(f"Agency: {metadata.get('agency')}")
    ...     print(f"Publisher: {metadata.get('publisher')}")
    """

    BASE_URL = "https://doi.org"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 30,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize DOI Content Negotiation client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 30)
        cache_config : CacheConfig, optional
            Cache configuration
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )

    def enrich(
        self, identifier: str | None = None, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Resolve DOI to metadata using content negotiation.

        Parameters
        ----------
        identifier : str
            DOI (required, with or without doi: prefix)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            DOI metadata with keys:
            - doi: Normalized DOI
            - agency: Registration agency (crossref, datacite, etc.)
            - type: Resource type
            - title: Resource title
            - authors: List of authors
            - publisher: Publisher name
            - publication_date: Publication date
            - url: Canonical URL
            - identifiers: Other identifiers
            - funding: Funding information
            - license: License information
            - source: Source identifier ("doi_content_negotiation")

        Raises
        ------
        ValueError
            If identifier is not provided or invalid DOI format
        """
        if not identifier:
            raise ValueError("DOI is required for DOI Content Negotiation enrichment")

        # Normalize DOI
        doi = self._normalize_doi(identifier)
        if not doi:
            raise ValueError(f"Invalid DOI format: {identifier}")

        logger.debug(f"Resolving DOI via content negotiation: {doi}")

        # Try CrossRef first (most common agency)
        metadata = self._get_crossref_metadata(doi, use_cache)
        if metadata:
            metadata["agency"] = "crossref"
            metadata["source"] = "doi_content_negotiation"
            logger.info(f"Successfully resolved DOI: {doi} via CrossRef content negotiation")
            return metadata

        # Try DataCite
        metadata = self._get_datacite_metadata(doi, use_cache)
        if metadata:
            metadata["agency"] = "datacite"
            metadata["source"] = "doi_content_negotiation"
            logger.info(f"Successfully resolved DOI: {doi} via DataCite content negotiation")
            return metadata

        # Try generic content negotiation
        metadata = self._get_generic_metadata(doi, use_cache)
        if metadata:
            metadata["agency"] = "unknown"
            metadata["source"] = "doi_content_negotiation"
            logger.info(f"Successfully resolved DOI: {doi} via generic content negotiation")
            return metadata

        # Fallback: try to get agency information and then request metadata
        agency_info = self._get_doi_agency(doi, use_cache)
        if agency_info:
            agency = agency_info.get("agency", "").lower()
            if agency == "crossref":
                metadata = self._get_crossref_metadata(doi, use_cache)
            elif agency == "datacite":
                metadata = self._get_datacite_metadata(doi, use_cache)
            else:
                metadata = self._get_generic_metadata(doi, use_cache)

            if metadata:
                metadata["agency"] = agency
                metadata["source"] = "doi_content_negotiation"
                logger.info(f"Successfully resolved DOI: {doi} via {agency} (with agency lookup)")
                return metadata

        logger.warning(f"Failed to resolve metadata for DOI: {doi}")
        return None

    def _normalize_doi(self, doi: str) -> str | None:
        """
        Normalize DOI to standard format.

        Parameters
        ----------
        doi : str
            DOI with or without doi: prefix

        Returns
        -------
        str or None
            Normalized DOI or None if invalid
        """

        # Remove doi: prefix if present
        doi = doi.replace("doi:", "").strip()

        # Basic DOI validation (should start with 10. and contain /)
        if not doi.startswith("10.") or "/" not in doi:
            return None

        return doi

    def _get_doi_agency(self, doi: str, use_cache: bool = True) -> dict[str, Any] | None:
        """
        Get DOI registration agency information.

        Parameters
        ----------
        doi : str
            Normalized DOI
        use_cache : bool, optional
            Whether to use cache

        Returns
        -------
        dict or None
            Agency information
        """
        try:
            response = self._make_request(
                endpoint=doi,
                headers={"Accept": "application/vnd.doi.service+json"},
                use_cache=use_cache,
            )
            if response and isinstance(response, dict):
                return response
            else:
                logger.warning(f"Invalid agency response for DOI {doi}: {response}")
                return None
        except Exception as e:
            logger.warning(f"Failed to get agency info for DOI {doi}: {e}")
            return None

    def _get_crossref_metadata(self, doi: str, use_cache: bool = True) -> dict[str, Any] | None:
        """
        Get metadata from CrossRef via content negotiation.

        Parameters
        ----------
        doi : str
            DOI
        use_cache : bool, optional
            Whether to use cache

        Returns
        -------
        dict or None
            Normalized CrossRef metadata
        """
        try:
            response = self._make_request(
                endpoint=doi,
                headers={"Accept": "application/vnd.crossref.unixsd+json"},
                use_cache=use_cache,
            )

            if not response or not isinstance(response, dict):
                logger.warning(f"Invalid CrossRef response for DOI {doi}: {type(response)}")
                return None

            # CrossRef returns data in 'message' field
            message = response.get("message", {})
            if not message:
                logger.warning(f"Empty message in CrossRef response for DOI {doi}")
                return None

            return self._normalize_crossref_response(message)

        except Exception as e:
            logger.warning(f"Failed to get CrossRef metadata for DOI {doi}: {e}")
            return None

    def _get_datacite_metadata(self, doi: str, use_cache: bool = True) -> dict[str, Any] | None:
        """
        Get metadata from DataCite via content negotiation.

        Parameters
        ----------
        doi : str
            DOI
        use_cache : bool, optional
            Whether to use cache

        Returns
        -------
        dict or None
            Normalized DataCite metadata
        """
        try:
            response = self._make_request(
                endpoint=doi,
                headers={"Accept": "application/vnd.datacite.datacite+json"},
                use_cache=use_cache,
            )

            if not response:
                return None

            # DataCite returns data in 'data' field
            data = response.get("data", {})
            # Always try to normalize, even if data is empty
            return self._normalize_datacite_response(data)

        except Exception as e:
            logger.warning(f"Failed to get DataCite metadata for DOI {doi}: {e}")
            return None

    def _get_generic_metadata(self, doi: str, use_cache: bool = True) -> dict[str, Any] | None:
        """
        Get generic metadata via content negotiation.

        Parameters
        ----------
        doi : str
            DOI
        use_cache : bool, optional
            Whether to use cache

        Returns
        -------
        dict or None
            Basic metadata
        """
        try:
            # Try to get any available metadata format
            response = self._make_request(
                endpoint=doi, headers={"Accept": "application/json"}, use_cache=use_cache
            )

            if response:
                return {
                    "doi": doi,
                    "url": response.get("URL"),
                    "type": response.get("type"),
                    "title": response.get("title"),
                }

        except Exception as e:
            logger.warning(f"Failed to get generic metadata for DOI {doi}: {e}")

        return None

    def _normalize_crossref_response(self, message: dict[str, Any]) -> dict[str, Any]:
        """Normalize CrossRef response to standard format."""
        # Extract title
        title = message.get("title", [])
        title = title[0] if title else None

        # Extract authors
        authors = []
        for author in message.get("author", []):
            authors.append(
                {
                    "given": author.get("given"),
                    "family": author.get("family"),
                    "name": author.get("name"),
                    "orcid": author.get("ORCID"),
                    "affiliation": author.get("affiliation", []),
                }
            )

        # Extract publication date
        published = message.get("published", {}).get("date-parts", [])
        pub_date = None
        if published and published[0]:
            parts = published[0]
            if len(parts) >= 3:
                pub_date = {"year": parts[0], "month": parts[1], "day": parts[2]}
            elif len(parts) >= 2:
                pub_date = {"year": parts[0], "month": parts[1]}
            elif len(parts) >= 1:
                pub_date = {"year": parts[0]}

        # Extract funding
        funders = []
        for funder in message.get("funder", []):
            funders.append(
                {
                    "name": funder.get("name"),
                    "doi": funder.get("DOI"),
                    "award": funder.get("award", []),
                }
            )

        # Extract abstract
        abstract = message.get("abstract")

        return {
            "doi": message.get("DOI"),
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "publisher": message.get("publisher"),
            "publication_date": pub_date,
            "type": message.get("type"),
            "url": message.get("URL"),
            "journal": message.get("container-title", []),
            "volume": message.get("volume"),
            "issue": message.get("issue"),
            "page": message.get("page"),
            "issn": message.get("ISSN", []),
            "funding": funders if funders else None,
            "license": message.get("license", []),
            "citation_count": message.get("is-referenced-by-count"),
            "references_count": message.get("references-count"),
        }

    def _normalize_datacite_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize DataCite response to standard format."""
        attributes = data.get("attributes", {})

        # Extract title
        titles = attributes.get("titles", [])
        title = titles[0].get("title") if titles else None

        # Extract authors
        authors = []
        for creator in attributes.get("creators", []):
            authors.append(
                {
                    "name": creator.get("name"),
                    "given": creator.get("givenName"),
                    "family": creator.get("familyName"),
                    "orcid": creator.get("nameIdentifiers", []),
                    "affiliation": creator.get("affiliation", []),
                }
            )

        # Extract publication date
        pub_date = attributes.get("publicationYear")

        # Extract funding
        funding = attributes.get("fundingReferences", [])

        # Extract abstract (DataCite often stores abstracts in descriptions)
        descriptions = attributes.get("descriptions", [])
        abstract = None
        if descriptions:
            for desc in descriptions:
                if desc.get("descriptionType") == "Abstract":
                    abstract = desc.get("description")
                    break
            # If no explicit abstract, use the first description
            if not abstract and descriptions:
                abstract = descriptions[0].get("description")

        # Extract journal/container
        container = attributes.get("container", {})
        journal = container.get("title") if container else None

        # Extract citation count
        citation_count = attributes.get("citationCount")

        return {
            "doi": data.get("id"),
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "publisher": attributes.get("publisher"),
            "publication_date": {"year": pub_date} if pub_date else None,
            "type": attributes.get("types", {}).get("resourceTypeGeneral"),
            "url": attributes.get("url"),
            "journal": journal,
            "citation_count": citation_count,
            "funding": funding if funding else None,
            "license": attributes.get("rightsList", []),
        }
