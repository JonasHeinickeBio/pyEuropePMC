"""
Adapter pattern for literature search clients.

This module provides adapter classes that wrap existing enrichment clients
to provide a consistent literature search interface.  The adapters follow
the same interface as :class:`BaseLiteratureClient` and return
:class:`~pyeuropepmc.models.literature.LiteratureResult` instances.

Adapters convert:
- Enrichment ``enrich(identifier)`` → Literature ``get_paper(identifier)``
- Search functionality             → Literature ``search(query)``
- Normalization of enrichment outputs → Literature normalized format
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

import requests

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.features.common.base import BaseHTTPClient
from pyeuropepmc.features.enrich.sources.openalex import OpenAlexClient
from pyeuropepmc.features.enrich.sources.semantic_scholar import SemanticScholarClient
from pyeuropepmc.features.literature.normalization import (
    normalize_affiliation,
    normalize_author_name,
    normalize_doi,
    normalize_journal_title,
    normalize_paper_title,
)
from pyeuropepmc.models.literature import Author, LiteratureResult

logger = logging.getLogger(__name__)

__all__ = [
    "EuropePMCLiteratureAdapter",
    "SemanticScholarLiteratureAdapter",
    "OpenAlexLiteratureAdapter",
]


class SemanticScholarLiteratureAdapter:
    """
    Adapter to convert SemanticScholarClient to literature search interface.

    Wraps the enrichment client's ``enrich()`` method to provide ``search()``
    and ``get_paper()`` methods compatible with
    :class:`~pyeuropepmc.features.search.base.BaseLiteratureClient`.

    Notes
    -----
    Semantic Scholar's search capabilities are limited compared to dedicated
    literature search APIs.  This adapter uses the enrichment client's ability
    to fetch papers by identifier, with search performed via the Semantic
    Scholar API directly.
    """

    #: Semantic Scholar paper-search endpoint (Graph API).
    SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(
        self,
        enrichment_client: SemanticScholarClient | None = None,
        api_key: str | None = None,
        rate_limit_delay: float = 1.2,
        timeout: int = 15,
    ) -> None:
        """
        Initialize the adapter.

        Parameters
        ----------
        enrichment_client : SemanticScholarClient, optional
            Existing enrichment client to wrap.  If ``None``, creates a new one.
        api_key : str, optional
            API key for higher rate limits. If not provided, uses environment variable.
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.2)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        """
        if enrichment_client is not None:
            self.enrichment_client = enrichment_client
        else:
            # Create a new SemanticScholarClient with the provided API key
            self.enrichment_client = SemanticScholarClient(
                api_key=api_key,
                rate_limit_delay=rate_limit_delay,
                timeout=timeout,
            )

        # Dedicated HTTP client for the *search* endpoint so the call goes
        # through a configured session (timeout, retries, rate-limit delay,
        # ``x-api-key`` header) instead of a bare ``requests.get``.
        self._http = BaseHTTPClient(
            base_url="https://api.semanticscholar.org/graph/v1",
            rate_limit_delay=self.enrichment_client.rate_limit_delay,
            timeout=self.enrichment_client.timeout,
        )
        if self.enrichment_client.api_key:
            self._http.session.headers.update({"x-api-key": self.enrichment_client.api_key})

    def _search_http(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Run a search request through the configured HTTP session.

        Parameters
        ----------
        params : dict
            Query-string parameters for the Semantic Scholar search endpoint.

        Returns
        -------
        dict
            Parsed JSON response.

        Raises
        ------
        requests.HTTPError
            If the API returns a non-2xx status.
        """
        response = self._http.session.get(
            self.SEARCH_URL,
            params=params,
            timeout=self._http.timeout,
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        """
        Get paper details by identifier using Semantic Scholar enrichment.

        Parameters
        ----------
        identifier : str
            Paper identifier (DOI, Semantic Scholar paper ID).
        **kwargs
            Additional parameters (unused).

        Returns
        -------
        LiteratureResult or None
            Paper details as a Pydantic model, or ``None`` if not found.
        """
        enriched = self.enrichment_client.enrich(identifier=identifier)
        if enriched is None:
            return None
        return self._normalize_to_literature_format(enriched)

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """
        Search papers using Semantic Scholar's paper search API.

        Parameters
        ----------
        query : str
            Search query string.
        limit : int, optional
            Maximum number of results (default: 25).
        sort : str, optional
            Sort order (e.g., ``'citationCount'``, ``'paperTitle'``).
        **kwargs
            Additional parameters.

        Returns
        -------
        list[LiteratureResult]
            List of search results as Pydantic models.
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }

        if sort:
            params["sort"] = sort

        try:
            data = self._search_http(params)
        except requests.RequestException:
            logger.exception("Semantic Scholar search failed for query=%r", query)
            return []

        papers = data.get("data", [])

        results: list[LiteratureResult] = []
        for paper in papers:
            normalized = self._normalize_to_literature_format(paper)
            if normalized:
                results.append(normalized)

        return results

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def _normalize_to_literature_format(
        self,
        data: dict[str, Any],
    ) -> LiteratureResult | None:
        """
        Normalize Semantic Scholar data to
        :class:`~pyeuropepmc.models.literature.LiteratureResult`.

        Parameters
        ----------
        data : dict
            Raw Semantic Scholar response.

        Returns
        -------
        LiteratureResult or None
            Normalized result.
        """
        # --- DOI ---
        doi = data.get("doi")
        if not doi and data.get("externalIds", {}).get("DOI"):
            doi = data["externalIds"]["DOI"]
        normalized_doi = normalize_doi(doi)

        # --- Authors ---
        authors_list: list[Author] = []
        for author in data.get("authors", []):
            name = None
            if author.get("lastName") or author.get("firstName"):
                parts = [author.get("lastName", ""), author.get("firstName", "")]
                name = ", ".join(p for p in parts if p)
            elif author.get("name"):
                name = author.get("name")

            if name:
                name = normalize_author_name(name)
            if not name:
                continue

            authors_list.append(
                Author(
                    name=name,
                    orcid=author.get("orcidId") or author.get("orcid"),
                )
            )

        # --- Year ---
        year = None
        if data.get("year"):
            year = int(data["year"])
        elif data.get("publicationDate"):
            with contextlib.suppress(TypeError, ValueError):
                year = int(data["publicationDate"][:4])

        # --- Journal ---
        journal = normalize_journal_title(data.get("venue"))

        # --- Title ---
        title = normalize_paper_title(data.get("title"))

        # --- Abstract ---
        abstract = data.get("abstract")
        if isinstance(abstract, str):
            abstract = abstract.strip()

        # --- Citation count ---
        citation_count = data.get("citationCount")
        if citation_count is not None:
            try:
                citation_count = int(citation_count)
            except (TypeError, ValueError):
                citation_count = None

        # --- External IDs ---
        ext_ids = data.get("externalIds", {}) or {}
        pmid = ext_ids.get("PubMed") or ext_ids.get("MED")
        pmcid = ext_ids.get("PubMedCentral")

        return LiteratureResult(
            doi=normalized_doi,
            pmid=str(pmid) if pmid else None,
            pmcid=str(pmcid) if pmcid else None,
            title=title,
            authors=authors_list or None,
            publication_year=year,
            journal=journal,
            abstract=abstract,
            citation_count=citation_count,
            source="semanticscholar",
            source_id=data.get("paperId", ""),
            semantic_scholar_data=data,
            # Extra fields
            influential_citation_count=data.get("influentialCitationCount"),
            fields_of_study=data.get("fieldsOfStudy"),
            s2_pdf_url=data.get("s2PdfUrl"),
            paper_id=data.get("paperId"),
        )


class OpenAlexLiteratureAdapter:
    """
    Adapter to convert OpenAlexClient to literature search interface.

    Wraps the enrichment client's ``enrich()`` method to provide ``search()``
    and ``get_paper()`` methods compatible with
    :class:`~pyeuropepmc.features.search.base.BaseLiteratureClient`.
    """

    #: OpenAlex works-search endpoint.
    SEARCH_URL = "https://api.openalex.org/works"

    def __init__(
        self,
        enrichment_client: OpenAlexClient | None = None,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize the adapter.

        Parameters
        ----------
        enrichment_client : OpenAlexClient, optional
            Existing enrichment client to wrap.  If ``None``, creates a new one.
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        """
        if enrichment_client is not None:
            self.enrichment_client = enrichment_client
        else:
            # Create a new OpenAlexClient with the provided parameters
            self.enrichment_client = OpenAlexClient(
                rate_limit_delay=rate_limit_delay,
                timeout=timeout,
                cache_config=cache_config,
            )

        # Dedicated HTTP client for the *search* endpoint so the call goes
        # through a configured session (timeout, retries, rate-limit delay,
        # polite-pool ``mailto``) instead of a bare ``requests.get``.
        self._http = BaseHTTPClient(
            base_url="https://api.openalex.org",
            rate_limit_delay=self.enrichment_client.rate_limit_delay,
            timeout=self.enrichment_client.timeout,
        )
        # Carry over the polite-pool User-Agent configured on the enrichment
        # client (it embeds ``mailto:`` when an email was supplied).
        ua = self.enrichment_client.session.headers.get("User-Agent")
        if ua:
            self._http.session.headers.update({"User-Agent": ua})
        self._mailto = getattr(self.enrichment_client, "email", None)

    def _search_http(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Run a search request through the configured HTTP session.

        Parameters
        ----------
        params : dict
            Query-string parameters for the OpenAlex works endpoint.

        Returns
        -------
        dict
            Parsed JSON response.

        Raises
        ------
        requests.HTTPError
            If the API returns a non-2xx status.
        """
        if self._mailto:
            params = {**params, "mailto": self._mailto}
        response = self._http.session.get(
            self.SEARCH_URL,
            params=params,
            timeout=self._http.timeout,
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        """
        Get paper details by identifier using OpenAlex enrichment.

        Parameters
        ----------
        identifier : str
            Paper identifier (DOI, OpenAlex paper ID).
        **kwargs
            Additional parameters (unused).

        Returns
        -------
        LiteratureResult or None
            Paper details as a Pydantic model, or ``None`` if not found.
        """
        enriched = self.enrichment_client.enrich(identifier=identifier)
        if enriched is None:
            return None
        return self._normalize_to_literature_format(enriched)

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """
        Search papers using OpenAlex's works search API.

        Parameters
        ----------
        query : str
            Search query string.
        limit : int, optional
            Maximum number of results (default: 25).
        sort : str, optional
            Sort order (e.g., ``'citation_count'``, ``'publication_date'``).
        **kwargs
            Additional parameters.

        Returns
        -------
        list[LiteratureResult]
            List of search results as Pydantic models.
        """
        params: dict[str, Any] = {
            "search": query,
            "per-page": limit,
        }

        if sort:
            sort_map = {
                "citation_count": "-cited_by_count",
                "date": "publication_date",
                "relevance": "relevance_score",
            }
            mapped = sort_map.get(sort)
            if mapped:
                params["sort"] = mapped

        try:
            data = self._search_http(params)
        except requests.RequestException:
            logger.exception("OpenAlex search failed for query=%r", query)
            return []

        papers = data.get("results", [])

        results: list[LiteratureResult] = []
        for paper in papers:
            normalized = self._normalize_to_literature_format(paper)
            if normalized:
                results.append(normalized)

        return results

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def _normalize_to_literature_format(  # noqa: C901
        self,
        data: dict[str, Any],
    ) -> LiteratureResult | None:
        """
        Normalize OpenAlex data to :class:`~pyeuropepmc.models.literature.LiteratureResult`.

        Parameters
        ----------
        data : dict
            Raw OpenAlex response.

        Returns
        -------
        LiteratureResult or None
            Normalized result.
        """
        # --- DOI ---
        doi = None
        if data.get("doi"):
            doi = data["doi"].replace("https://doi.org/", "")
        normalized_doi = normalize_doi(doi)

        # --- Authors ---
        authors_list: list[Author] = []
        for authorship in data.get("authorships", []):
            author_info = authorship.get("author", {}) or {}
            raw_name = author_info.get("display_name", "")

            if raw_name:
                name = normalize_author_name(raw_name)
            else:
                continue

            # Collect institutions
            institutions = [
                inst.get("display_name", "")
                for inst in authorship.get("institutions", [])
                if inst and inst.get("display_name")
            ]
            affiliation = ", ".join(institutions) if institutions else None
            if affiliation:
                affiliation = normalize_affiliation(affiliation)

            authors_list.append(
                Author(
                    name=name,
                    orcid=author_info.get("orcid"),
                    affiliation=affiliation,
                )
            )

        # --- Year ---
        year = None
        if data.get("publication_year"):
            with contextlib.suppress(TypeError, ValueError):
                year = int(data["publication_year"])

        # --- Journal ---
        journal = None
        primary_location = data.get("primary_location", {}) or {}
        source = primary_location.get("source", {}) or {}
        if source.get("display_name"):
            journal = normalize_journal_title(source["display_name"])
        if not journal:
            best_oa = data.get("best_oa_location", {}) or {}
            b_source = best_oa.get("source", {}) or {}
            if b_source.get("display_name"):
                journal = normalize_journal_title(b_source["display_name"])

        # --- Title ---
        title = normalize_paper_title(data.get("title"))

        # --- Abstract (inverted index → plain text) ---
        abstract = None
        inverted = data.get("abstract_inverted_index")
        if inverted and isinstance(inverted, dict):
            words = []
            for word, _ in sorted(inverted.items(), key=lambda x: x[1][0] if x[1] else 0):
                if word:
                    words.append(word)
            if words:
                abstract = " ".join(words)

        # --- Citation count ---
        citation_count = data.get("cited_by_count")
        if citation_count is not None:
            try:
                citation_count = int(citation_count)
            except (TypeError, ValueError):
                citation_count = None

        # --- External IDs ---
        ext_ids = data.get("ids", {}) or {}
        pmid = ext_ids.get("pmid")
        pmcid = ext_ids.get("pmcid")

        # --- Concepts / topics ---
        topics = [c.get("display_name", "") for c in data.get("concepts", []) if c]

        return LiteratureResult(
            doi=normalized_doi,
            pmid=str(pmid).replace("https://pubmed.ncbi.nlm.nih.gov/", "") if pmid else None,
            pmcid=str(pmcid).replace("https://www.ncbi.nlm.nih.gov/pmc/articles/", "")
            if pmcid
            else None,
            title=title,
            authors=authors_list or None,
            publication_year=year,
            journal=journal,
            abstract=abstract,
            citation_count=citation_count,
            source="openalex",
            source_id=data.get("id", "").replace("https://openalex.org/", ""),
            openalex_data=data,
            # Extra fields
            openalex_id=data.get("id"),
            type=data.get("type"),
            is_oa=data.get("open_access", {}).get("is_oa"),
            oa_status=data.get("open_access", {}).get("oa_status"),
            topics=topics,
        )


class EuropePMCLiteratureAdapter:
    """
    Adapter exposing the native Europe PMC :class:`SearchClient` through the
    literature-search interface used by
    :class:`~pyeuropepmc.features.search.unified_search.UnifiedSearch`.

    Europe PMC is the project's home API, so it belongs in the federated search
    alongside PubMed, arXiv, OpenAlex, etc.
    """

    def __init__(
        self,
        search_client: Any | None = None,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        **_ignored: Any,
    ) -> None:
        self.timeout = timeout
        if search_client is not None:
            self.search_client = search_client
        else:
            from pyeuropepmc.features.literature.search import SearchClient

            # SearchClient manages its own request timeout internally.
            self.search_client = SearchClient(rate_limit_delay=rate_limit_delay)

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """Search Europe PMC and normalize hits to :class:`LiteratureResult`."""
        params: dict[str, Any] = {"pageSize": min(limit, 1000)}
        if sort:
            params["sort"] = sort
        params.update(kwargs)

        try:
            records = self.search_client.search_and_parse(query, format="json", **params)
        except Exception:
            logger.exception("Europe PMC search failed for query=%r", query)
            return []

        results: list[LiteratureResult] = []
        for rec in records[:limit]:
            try:
                normalized = self._normalize_to_literature_format(rec)
            except Exception:
                logger.debug("Skipping unparseable Europe PMC record: %r", rec, exc_info=True)
                continue
            if normalized:
                results.append(normalized)
        return results

    def get_paper(self, identifier: str, **kwargs: Any) -> LiteratureResult | None:
        """Look up a single record by DOI / PMID / PMCID via a targeted query."""
        ident = identifier.strip()
        if ident.lower().startswith("10."):
            query = f'DOI:"{ident}"'
        elif ident.upper().startswith("PMC"):
            query = f"PMCID:{ident}"
        elif ident.isdigit():
            query = f"EXT_ID:{ident} AND SRC:MED"
        else:
            query = ident
        hits = self.search(query, limit=1)
        return hits[0] if hits else None

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.search_client.close()

    def _normalize_to_literature_format(self, data: dict[str, Any]) -> LiteratureResult | None:
        title = normalize_paper_title(data.get("title"))
        doi = normalize_doi(data.get("doi"))
        pmid = data.get("pmid") or (data.get("id") if data.get("source") == "MED" else None)
        pmcid = data.get("pmcid")

        authors_list: list[Author] = []
        author_string = data.get("authorString") or ""
        if author_string:
            for raw_name in author_string.split(","):
                name = normalize_author_name(raw_name.strip().rstrip("."))
                if name:
                    authors_list.append(Author(name=name))

        year = None
        if data.get("pubYear"):
            with contextlib.suppress(TypeError, ValueError):
                year = int(str(data["pubYear"])[:4])

        journal = data.get("journalTitle")
        if not journal:
            journal = (data.get("journalInfo", {}) or {}).get("journal", {}).get("title")
        journal = normalize_journal_title(journal)

        citation_count = data.get("citedByCount")
        if citation_count is not None:
            try:
                citation_count = int(citation_count)
            except (TypeError, ValueError):
                citation_count = None

        abstract = data.get("abstractText")
        if isinstance(abstract, str):
            abstract = abstract.strip()

        source_id = str(data.get("id") or pmid or doi or "")
        return LiteratureResult(
            doi=doi,
            pmid=str(pmid) if pmid else None,
            pmcid=str(pmcid) if pmcid else None,
            title=title,
            authors=authors_list or None,
            publication_year=year,
            journal=journal,
            abstract=abstract,
            citation_count=citation_count,
            source="europepmc",
            source_id=source_id,
            extra_metadata={
                "europepmc_source": data.get("source"),
                "is_open_access": data.get("isOpenAccess"),
            },
        )
