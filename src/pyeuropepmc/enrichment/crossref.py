"""
CrossRef API client for enriching paper metadata.

CrossRef provides comprehensive bibliographic metadata, citations,
and licensing information for academic papers.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["CrossRefClient"]


class CrossRefClient(BaseEnrichmentClient):
    """
    Client for CrossRef API enrichment.

    CrossRef provides metadata including:
    - Title, authors, abstract
    - Journal information
    - Publication dates
    - Citation counts
    - License information
    - References and citations
    - Funding information

    Examples
    --------
    >>> client = CrossRefClient()
    >>> metadata = client.enrich(doi="10.1371/journal.pone.0123456")
    >>> if metadata:
    ...     print(metadata.get("title"))
    ...     print(metadata.get("citation_count"))
    """

    BASE_URL = "https://api.crossref.org/works"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
        email: str | None = None,
    ) -> None:
        """
        Initialize CrossRef client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        email : str, optional
            Email for polite pool (gets faster response times)
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        self.email = email

        # Add email to headers for polite pool if provided
        if email:
            self.session.headers.update({"mailto": email})
            logger.info(f"CrossRef polite pool enabled with email: {email}")

    def enrich(
        self, identifier: str | None = None, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich paper metadata using CrossRef API.

        Parameters
        ----------
        identifier : str
            Paper DOI (required)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Enriched metadata with keys:
            - title: Paper title
            - authors: List of author names
            - abstract: Paper abstract
            - journal: Journal name
            - publication_date: Publication date
            - citation_count: Citation count
            - references_count: Number of references
            - license: License information
            - funder: Funding information
            - is_referenced_by_count: Times cited

        Raises
        ------
        ValueError
            If identifier is not provided
        """
        if not identifier:
            raise ValueError("Identifier is required for CrossRef enrichment")

        logger.debug(f"Enriching metadata for identifier: {identifier}")

        # Make request to CrossRef API
        response = self._make_request(endpoint=identifier, use_cache=use_cache)
        if response is None:
            logger.warning(f"No data found for identifier: {identifier}")
            return None

        # Extract metadata from response
        try:
            message = response.get("message", {})
            if not message:
                logger.warning(f"Empty response from CrossRef for identifier: {identifier}")
                return None

            # Parse and normalize metadata
            enriched = self._parse_crossref_response(message)
            logger.info(f"Successfully enriched metadata for identifier: {identifier}")
            return enriched

        except Exception as e:
            logger.error(f"Error parsing CrossRef response for {identifier}: {e}")
            return None

    def _parse_crossref_response(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Parse CrossRef API response into normalized metadata.

        Parameters
        ----------
        message : dict
            CrossRef API message object

        Returns
        -------
        dict
            Normalized metadata
        """
        # Extract basic metadata
        title = self._extract_title(message)
        authors = self._extract_authors(message)
        abstract = message.get("abstract")
        journal = self._extract_journal(message)
        publication_date = self._extract_publication_date(message)
        citation_count = message.get("is-referenced-by-count", 0)
        references_count = message.get("references-count", 0)
        license_info = self._extract_license(message)
        funders = self._extract_funders(message)

        # Extract bibliographic information
        biblio = {
            "type": message.get("type"),
            "issn": message.get("ISSN"),
            "volume": message.get("volume"),
            "issue": message.get("issue"),
            "page": message.get("page"),
            "publisher": message.get("publisher"),
        }
        # Remove None values from biblio
        biblio = {k: v for k, v in biblio.items() if v is not None}

        return {
            "source": "crossref",
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "journal": journal,
            "publication_date": publication_date,
            "citation_count": citation_count,
            "references_count": references_count,
            "license": license_info,
            "funders": funders if funders else None,
            **biblio,
        }

    def _extract_title(self, message: dict[str, Any]) -> str | None:
        """Extract title from CrossRef message."""
        title_list = message.get("title", [])
        return title_list[0] if title_list else None

    def _extract_authors(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract detailed author information from CrossRef message."""
        authors = []
        for author in message.get("author", []):
            if not isinstance(author, dict):
                continue

            # Extract name components
            given = author.get("given", "")
            family = author.get("family", "")
            name = author.get("name", "")

            # Build full name if not provided
            if not name and (given or family):
                name = f"{given} {family}".strip()

            # Extract ORCID
            orcid = author.get("ORCID")
            if orcid and not orcid.startswith("https://orcid.org/"):
                orcid = f"https://orcid.org/{orcid}"

            # Extract affiliations
            affiliations = []
            author_affiliations = author.get("affiliation", [])
            if isinstance(author_affiliations, list):
                for aff in author_affiliations:
                    if isinstance(aff, dict) and aff.get("name"):
                        affiliations.append(aff["name"])

            # Extract sequence information
            sequence = author.get("sequence")

            author_data = {
                "name": name,
                "given": given,
                "family": family,
                "orcid": orcid,
                "affiliation": affiliations,
                "sequence": sequence,
                "ORCID": orcid,  # Keep original key for compatibility
            }

            # Remove None values
            author_data = {k: v for k, v in author_data.items() if v is not None}
            authors.append(author_data)

        return authors

    def _extract_journal(self, message: dict[str, Any]) -> str | None:
        """Extract journal/container title."""
        container_title = message.get("container-title", [])
        return container_title[0] if container_title else None

    def _extract_publication_date(self, message: dict[str, Any]) -> str | None:
        """Extract publication date."""
        pub_date_parts = message.get("published", {}).get("date-parts", [[]])
        pub_date = None
        if pub_date_parts and pub_date_parts[0]:
            date_parts = pub_date_parts[0]
            if len(date_parts) >= 3:
                pub_date = f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
            elif len(date_parts) >= 2:
                pub_date = f"{date_parts[0]}-{date_parts[1]:02d}"
            elif len(date_parts) >= 1:
                pub_date = str(date_parts[0])
        return pub_date

    def _extract_license(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Extract license information."""
        licenses = message.get("license", [])
        if licenses:
            return {
                "url": licenses[0].get("URL"),
                "start": licenses[0].get("start", {}).get("date-time"),
                "delay_in_days": licenses[0].get("delay-in-days"),
            }
        return None

    def _extract_funders(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract funder information."""
        funders = []
        for funder in message.get("funder", []):
            funders.append(
                {
                    "name": funder.get("name"),
                    "doi": funder.get("DOI"),
                    "award": funder.get("award", []),
                }
            )
        return funders
