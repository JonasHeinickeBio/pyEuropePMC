"""
Semantic Scholar API client for academic impact metrics.

Semantic Scholar provides citation counts, influential citations,
abstracts, and venue information.
"""

import logging
import os
import re
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient
from pyeuropepmc.enrichment.semanticscholar_pro import ProfessionalSemanticScholarClient

logger = logging.getLogger(__name__)

__all__ = ["SemanticScholarClient"]


class SemanticScholarClient(BaseEnrichmentClient):
    """
    Client for Semantic Scholar API enrichment.

    Semantic Scholar provides:
    - Citation counts
    - Influential citation counts
    - Abstract
    - Venue information
    - Author information
    - Fields of study
    - References and citations

    This client uses the danielnsilva/semanticscholar library for professional
    API handling with automatic retries, typed response objects, and async support.

    Examples
    --------
    >>> client = SemanticScholarClient()
    >>> metrics = client.enrich(doi="10.1371/journal.pone.0123456")
    >>> if metrics:
    ...     print(f"Citations: {metrics.get('citation_count')}")
    ...     print(f"Influential citations: {metrics.get('influential_citation_count')}")
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    RECOMMENDATIONS_BASE_URL = "https://api.semanticscholar.org/recommendations/v1"
    # Semantic Scholar recommendations endpoint currently allows up to 500 results per request.
    MAX_RECOMMENDATIONS = 500
    # IDs must start with an alphanumeric character and may include : . / _ -,
    # with a maximum length of 256 characters.
    _PAPER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:./_-]{0,255}$")

    # Use professional library internally for API calls
    _pro_client: ProfessionalSemanticScholarClient

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
        api_key: str | None = None,
    ) -> None:
        """
        Initialize Semantic Scholar client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        api_key : str, optional
            API key for higher rate limits (recommended but not required).
            If not provided, will load from SEMANTIC_SCHOLAR_API_KEY environment variable.
        """
        # Use provided API key or load from environment
        self.api_key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        api_key_missing = not bool(self.api_key)

        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
            api_key_missing=api_key_missing,
        )

        # Initialize professional Semantic Scholar client for API calls
        self._pro_client = ProfessionalSemanticScholarClient(
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            api_key=self.api_key,
            use_cache=True,
        )

        # Add API key to headers if available (Semantic Scholar uses Bearer auth)
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
            logger.info("Semantic Scholar API key configured")
        else:
            logger.warning(
                "No Semantic Scholar API key configured. Rate limits are lower (25k/month). "
                "Consider adding SEMANTIC_SCHOLAR_API_KEY to environment for higher limits (100k/month)."
            )

    def _normalize_recommendation_limit(self, limit: int | None) -> int:
        """Validate and normalize recommendation limit to API boundaries."""
        if limit is None:
            return self.MAX_RECOMMENDATIONS
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        return min(limit, self.MAX_RECOMMENDATIONS)

    def _validate_paper_id(self, paper_id: str) -> str:
        """Validate a Semantic Scholar paper identifier string."""
        normalized = paper_id.strip()
        if not normalized:
            raise ValueError("paper_id must be a non-empty string")
        if not self._PAPER_ID_PATTERN.match(normalized):
            raise ValueError(
                "paper_id contains invalid characters; allowed: letters, "
                "numbers, ':', '.', '/', '_', '-'"
            )
        return normalized

    def _validate_paper_ids(self, paper_ids: list[str], argument_name: str) -> list[str]:
        """
        Validate a list of paper identifiers and remove duplicates while preserving order.

        Notes
        -----
        Duplicate IDs are automatically de-duplicated in the returned list.
        """
        if not paper_ids:
            raise ValueError(f"{argument_name} must contain at least one paper ID")
        normalized_ids = [self._validate_paper_id(paper_id) for paper_id in paper_ids]
        return list(dict.fromkeys(normalized_ids))

    def _extract_recommendations(self, response: dict[str, Any] | None) -> list[dict[str, Any]]:
        """Extract recommendation payload from Semantic Scholar responses."""
        if not response:
            return []
        recommendations = response.get("recommendedPapers", [])
        if isinstance(recommendations, list):
            return [item for item in recommendations if isinstance(item, dict)]
        logger.warning("Unexpected recommendations response format")
        return []

    def get_recommendations_for_paper(
        self,
        paper_id: str,
        limit: int | None = None,
        fields: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get recommended papers for a single positive example paper.

        Parameters
        ----------
        paper_id : str
            Positive example paper ID.
        limit : int, optional
            Number of recommendations to return (capped at API maximum).
        fields : list[str], optional
            Additional paper fields to request from Semantic Scholar.
        use_cache : bool, optional
            Whether to use cache for idempotent requests.

        Returns
        -------
        list[dict]
            Recommended papers.
        """
        validated_paper_id = self._validate_paper_id(paper_id)

        try:
            # Use professional client for recommendations
            papers = self._pro_client.get_recommendations(
                paper_id=validated_paper_id,
                fields=fields,
                limit=self._normalize_recommendation_limit(limit),
            )
            return papers

        except Exception as e:
            logger.error(f"Failed to get recommendations for paper {validated_paper_id}: {e}")
            return []

    def get_recommendations_for_papers(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str] | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get recommended papers based on positive and optional negative example papers.

        Parameters
        ----------
        positive_paper_ids : list[str]
            Positive example paper IDs.
        negative_paper_ids : list[str], optional
            Negative example paper IDs.
        limit : int, optional
            Number of recommendations to return (capped at API maximum).
        fields : list[str], optional
            Additional paper fields to request from Semantic Scholar.
        use_cache : bool, optional
            Whether to use cache for idempotent requests.

        Returns
        -------
        list[dict]
            Recommended papers.
        """
        validated_positive = self._validate_paper_ids(positive_paper_ids, "positive_paper_ids")
        validated_negative: list[str] = []
        if negative_paper_ids:
            validated_negative = self._validate_paper_ids(negative_paper_ids, "negative_paper_ids")
            overlap = set(validated_positive).intersection(validated_negative)
            if overlap:
                raise ValueError(
                    "positive_paper_ids and negative_paper_ids must not contain the same paper IDs"
                )

        try:
            # Use professional client for recommendations from lists
            papers = self._pro_client.get_recommendations_from_lists(
                positive_paper_ids=validated_positive,
                negative_paper_ids=validated_negative or None,
                fields=fields,
                limit=self._normalize_recommendation_limit(limit),
            )
            return papers

        except Exception as e:
            logger.error(
                f"Failed to get recommendations for papers: positive={validated_positive}, negative={validated_negative or []}: {e}"
            )
            return []

    def enrich(
        self,
        identifier: str | None = None,
        use_cache: bool = True,
        semantic_scholar_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Enrich paper metadata using Semantic Scholar API.

        Parameters
        ----------
        identifier : str, optional
            Paper DOI
        use_cache : bool, optional
            Whether to use cached results (default: True)
        semantic_scholar_id : str, optional
            Semantic Scholar paper ID (alternative to identifier)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Enriched metadata with keys:
            - citation_count: Total citation count
            - influential_citation_count: Influential citation count
            - abstract: Paper abstract
            - venue: Publication venue
            - year: Publication year
            - authors: List of authors with enhanced information:
                - name: Author name
                - author_id: Semantic Scholar author ID
                - url: Link to author's Semantic Scholar profile
                - affiliations: Author affiliations (if available)
                - homepage: Author's homepage (if available)
            - fields_of_study: List of research fields
            - s2_paper_id: Semantic Scholar paper ID
            - external_ids: External identifiers (DOI, PubMed, etc.)
            - open_access_pdf_url: URL to open access PDF (if available)
            - publication_types: List of publication types
            - journal: Journal information
            - tldr: TL;DR summary (if available)

        Raises
        ------
        ValueError
            If neither identifier nor Semantic Scholar ID is provided
        """
        if not identifier and not semantic_scholar_id:
            raise ValueError("Either identifier or Semantic Scholar ID is required")

        # Use professional library for API calls
        paper_id = semantic_scholar_id or identifier
        if paper_id is None:
            raise ValueError("paper_id cannot be None")

        # Call professional client
        result = self._pro_client.get_paper(
            paper_id=paper_id,
            fields=[
                "title",
                "abstract",
                "venue",
                "year",
                "citationCount",
                "influentialCitationCount",
                "authors",
                "authors.affiliations",
                "fieldsOfStudy",
                "externalIds",
                "paperId",
                "corpusId",
                "referenceCount",
                "openAccessPdf",
                "publicationTypes",
                "publicationDate",
                "journal",
                "tldr",
                "s2FieldsOfStudy",
            ],
        )

        if result is None:
            logger.warning(f"No data found for: {paper_id}")
            return None

        try:
            logger.info(f"Successfully enriched metadata from Semantic Scholar: {paper_id}")
            return result

        except Exception as e:
            logger.error(f"Error processing Semantic Scholar data for {paper_id}: {e}")
            return None

    def enrich_batch(
        self, identifiers: list[str], use_cache: bool = True, **kwargs: Any
    ) -> dict[str, dict[str, Any]]:
        """
        Enrich multiple papers at once using the batch API.

        Parameters
        ----------
        identifiers : list[str]
            List of paper identifiers (DOIs, Semantic Scholar IDs, etc.)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict[str, dict | None]
            Dictionary mapping identifiers to enrichment results
        """
        if not identifiers:
            return {}

        # Limit batch size to API constraints (500 papers max)
        batch_size = 500
        results = {}

        for i in range(0, len(identifiers), batch_size):
            batch = identifiers[i : i + batch_size]

            # Use professional client for batch retrieval
            try:
                papers_result = self._pro_client.get_papers(
                    paper_ids=batch,
                    fields=[
                        "title",
                        "abstract",
                        "venue",
                        "year",
                        "citationCount",
                        "influentialCitationCount",
                        "authors",
                        "authors.affiliations",
                        "fieldsOfStudy",
                        "externalIds",
                        "paperId",
                        "corpusId",
                        "referenceCount",
                        "openAccessPdf",
                        "publicationTypes",
                        "publicationDate",
                        "journal",
                        "tldr",
                        "s2FieldsOfStudy",
                    ],
                )

                # Handle both return types: list (default) or tuple (return_not_found=True)
                if isinstance(papers_result, tuple):
                    papers_list, _ = papers_result
                else:
                    papers_list = papers_result

                for paper in papers_list:
                    if paper:
                        paper_id = paper.get("s2_paper_id")
                        doi = paper.get("external_ids", {}).get("DOI")
                        results[paper_id or doi] = paper

            except Exception as e:
                logger.warning(f"Batch request failed for batch starting at index {i}: {e}")

        return results

    def enrich_author(
        self, author_id: str, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich author information using Semantic Scholar API.

        Parameters
        ----------
        author_id : str
            Semantic Scholar author ID
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Author metadata with keys:
            - author_id: Semantic Scholar author ID
            - name: Author name
            - url: Author profile URL
            - affiliations: List of affiliations
            - homepage: Author homepage
            - paper_count: Total number of papers
            - citation_count: Total citation count
            - h_index: H-index
            - external_ids: External identifiers
        """
        try:
            result = self._pro_client.get_author(
                author_id=author_id,
                fields=[
                    "name",
                    "url",
                    "affiliations",
                    "homepage",
                    "paperCount",
                    "citationCount",
                    "hIndex",
                    "externalIds",
                ],
            )
            return result

        except Exception as e:
            logger.error(f"Error enriching author {author_id}: {e}")
            return None

    def search_papers(
        self,
        query: str,
        limit: int = 100,
        use_cache: bool = True,
        bulk: bool = False,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Search for papers using Semantic Scholar's relevance search.

        Parameters
        ----------
        query : str
            Search query
        limit : int, optional
            Maximum number of results (default: 100, max: 1000)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        bulk : bool, optional
            Use bulk retrieval (faster, no relevance ranking, up to 10M results)
        **kwargs
            Additional search parameters (year, venue, fieldsOfStudy, etc.)

        Returns
        -------
        list[dict]
            List of paper metadata dictionaries
        """
        params = {
            "query": query,
            "limit": min(limit, 1000),  # API limit
            "fields": (
                "title,abstract,venue,year,citationCount,"
                "influentialCitationCount,authors,fieldsOfStudy,"
                "externalIds,paperId"
            ),
        }

        # Add optional filters
        valid_keys = [
            "year",
            "venue",
            "fieldsOfStudy",
            "minCitationCount",
            "publicationDateOrYear",
        ]
        for key, value in kwargs.items():
            if key in valid_keys:
                params[key] = value

        try:
            results = self._pro_client.search_paper(
                query=query,
                year=kwargs.get("year"),
                venue=kwargs.get("venue"),
                fields_of_study=kwargs.get("fieldsOfStudy"),
                min_citation_count=kwargs.get("minCitationCount"),
                publication_date_or_year=kwargs.get("publicationDateOrYear"),
                limit=min(limit, 100),
                fields=[
                    "title",
                    "abstract",
                    "venue",
                    "year",
                    "citationCount",
                    "influentialCitationCount",
                    "authors",
                    "fieldsOfStudy",
                    "externalIds",
                    "paperId",
                ],
                bulk=bulk,
            )
            return results

        except Exception as e:
            logger.error(f"Error searching papers for query '{query}': {e}")
            return []
