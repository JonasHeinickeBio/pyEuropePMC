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

import logging
from typing import Any

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

    def __init__(
        self,
        enrichment_client: SemanticScholarClient | None = None,
    ) -> None:
        """
        Initialize the adapter.

        Parameters
        ----------
        enrichment_client : SemanticScholarClient, optional
            Existing enrichment client to wrap.  If ``None``, creates a new one.
        """
        self.enrichment_client = enrichment_client or SemanticScholarClient()

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
        import requests

        search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }

        if sort:
            params["sort"] = sort

        headers = {"Accept": "application/json"}
        if self.enrichment_client.api_key:
            headers["x-api-key"] = self.enrichment_client.api_key

        response = requests.get(search_url, params=params, headers=headers)

        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.exception("Semantic Scholar search failed for query=%r", query)
            return []

        data = response.json()
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
        Normalize Semantic Scholar data to :class:`~pyeuropepmc.models.literature.LiteratureResult`.

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
            try:
                year = int(data["publicationDate"][:4])
            except (TypeError, ValueError):
                pass

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

    def __init__(
        self,
        enrichment_client: OpenAlexClient | None = None,
    ) -> None:
        """
        Initialize the adapter.

        Parameters
        ----------
        enrichment_client : OpenAlexClient, optional
            Existing enrichment client to wrap.  If ``None``, creates a new one.
        """
        self.enrichment_client = enrichment_client or OpenAlexClient()

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
        import requests

        search_url = "https://api.openalex.org/works"
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
            response = requests.get(search_url, params=params)
            response.raise_for_status()
        except requests.HTTPError:
            logger.exception("OpenAlex search failed for query=%r", query)
            return []

        data = response.json()
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

    def _normalize_to_literature_format(
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
            try:
                year = int(data["publication_year"])
            except (TypeError, ValueError):
                pass

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
            for word, positions in sorted(inverted.items(), key=lambda x: x[1][0] if x[1] else 0):
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
