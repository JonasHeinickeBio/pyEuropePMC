"""
arXiv API client for literature search.

arXiv provides open access to preprints in physics, mathematics,
computer science, quantitative biology, quantitative finance, and statistics.
This client uses the arXiv API v1 which returns Atom XML results.

The API is free and requires no API key.

References
----------
- arXiv API: https://info.arxiv.org/help/api/
- arXiv API v1: http://export.arxiv.org/api/query
"""

from __future__ import annotations

import logging
import re
from typing import Any
from xml.etree import ElementTree  # nosec B405

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.core.xml_parsing import parse_xml
from pyeuropepmc.features.literature.normalization import (
    normalize_author_list,
    normalize_doi,
    normalize_journal_title,
    normalize_paper_title,
)
from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["ArxivClient"]

# ---------------------------------------------------------------------------
# Atom XML namespace
# ---------------------------------------------------------------------------
_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"
_OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"

_ARXIV_ID_PATTERN = re.compile(
    r"(?:arxiv:|http://arxiv.org/abs/|https://arxiv.org/abs/)(\d+\.\d+|\w+/\d+)"
)

# An arXiv API error is returned as a normal Atom feed holding a single entry
# whose <id> points at the error namespace; without this check the error text
# comes back as a search result titled "Error".
_ARXIV_ERROR_MARKER = "arxiv.org/api/errors"


class ArxivClient(BaseLiteratureClient):
    """
    Client for arXiv API literature search.

    arXiv provides:
    - Open access preprints in physics, math, CS, biology, economics
    - Author information
    - Publication dates
    - Abstract text
    - DOI links (when available)

    The API is free and does not require an API key.

    Examples
    --------
    >>> client = ArxivClient()
    >>> results = client.search("quantum machine learning", limit=10)
    >>> for paper in results:
    ...     print(f"{paper.title} ({paper.source_id})")
    """

    BASE_URL = "http://export.arxiv.org/api"

    def __init__(
        self,
        rate_limit_delay: float = 3.0,
        timeout: int = 30,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize arXiv client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 3.0).
            arXiv asks to not make more than 1 request per 3 seconds.
        timeout : int, optional
            Request timeout in seconds (default: 30).
        cache_config : CacheConfig, optional
            Cache configuration for API responses.
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """
        Search arXiv preprints.

        Parameters
        ----------
        query : str
            Search query string (arXiv search query syntax).
        limit : int, optional
            Maximum number of results (default: 25, max: 2000 per request).
        sort : str, optional
            Sort order: ``"relevance"`` (default), ``"date"``, or ``"title"``.
        **kwargs
            ``categories``: one arXiv subject category or a list/comma-separated
            string of them (e.g. ``"cs.AI"`` or ``["cs.AI", "cs.LG"]``).  The
            categories are OR-ed together and AND-ed onto *query*.
            ``id_list``: comma-separated arXiv IDs for a targeted lookup.

        Returns
        -------
        list[LiteratureResult]
            List of search results as Pydantic models.
        """
        params: dict[str, Any] = {
            "search_query": self._apply_categories(query, kwargs.get("categories")),
            "max_results": min(limit, 2000),
        }
        if sort:
            sort_map = {"relevance": "relevance", "date": "submittedDate", "title": "title"}
            params["sortBy"] = sort_map.get(sort, "relevance")

        # Support passing an explicit id_list for targeted lookups
        id_list = kwargs.get("id_list")
        if id_list:
            params["id_list"] = id_list

        # arXiv API returns Atom XML (not JSON) — ask the base client for the
        # raw response text.
        raw = self._make_request("query", params=params, use_cache=True, response_format="xml")
        if raw is None:
            return []

        return self._parse_feed(raw)

    @staticmethod
    def _apply_categories(query: str, categories: Any) -> str:
        """Restrict *query* to arXiv subject categories with ``cat:`` clauses."""
        if not categories:
            return query
        if isinstance(categories, str):
            cats = [c.strip() for c in categories.split(",") if c.strip()]
        else:
            cats = [str(c).strip() for c in categories if str(c).strip()]
        if not cats:
            return query

        clause = " OR ".join(f"cat:{c}" for c in cats)
        if not query or not query.strip():
            return f"({clause})"
        return f"({query}) AND ({clause})"

    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        """
        Get paper details by arXiv ID.

        Parameters
        ----------
        identifier : str
            arXiv ID (e.g. ``"2301.12345"`` or full URL).
        **kwargs
            Additional parameters (not used for arXiv single-paper lookup).

        Returns
        -------
        LiteratureResult or None
            Paper details as Pydantic model, or None if not found.
        """
        # Normalize arXiv ID. Handle both standard forms
        # (arxiv:1706.03762, https://arxiv.org/abs/1706.03762) and
        # DOI-embedded forms (10.48550/arXiv.1706.03762).
        match = _ARXIV_ID_PATTERN.search(identifier)
        if match:
            arxiv_id = match.group(1)
        else:
            doi_match = re.search(r"arXiv\.(\d+\.\d+|\w+/\d+)", identifier, re.IGNORECASE)
            arxiv_id = doi_match.group(1) if doi_match else identifier

        # arXiv single paper lookup via id_list parameter
        raw = self._make_request(
            "query",
            params={"id_list": arxiv_id, "max_results": 1},
            use_cache=True,
            response_format="xml",
        )

        # Fallback: if the identifier looks like a DOI, arXiv does not index
        # by id_list, so search for it instead.
        if raw is None and (identifier.lower().startswith("10.") or "/" in identifier):
            raw = self._make_request(
                "query",
                params={
                    "search_query": f'all:"{identifier}"',
                    "max_results": 1,
                },
                use_cache=True,
                response_format="xml",
            )
        if raw is None:
            return None

        results = self._parse_feed(raw)
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_result(self, raw_result: dict[str, Any]) -> LiteratureResult:
        """
        Normalize API response to standard format.

        Parameters
        ----------
        raw_result : dict
            Raw API response data (from XML parsing).

        Returns
        -------
        LiteratureResult
            Normalized result as Pydantic model.
        """
        title = normalize_paper_title(raw_result.get("title", ""))
        source_id = raw_result.get("id", "")
        doi = normalize_doi(raw_result.get("doi", ""))

        authors_raw = raw_result.get("authors", [])
        authors = None
        if authors_raw:
            # normalize_author_list expects plain dicts, not Author objects
            author_list = [a for a in authors_raw if isinstance(a, dict) and a.get("name")]
            if author_list:
                authors = normalize_author_list(author_list)

        year = raw_result.get("year")
        try:
            pub_year = int(year) if year else None
        except (TypeError, ValueError):
            logger.debug("arXiv entry %r has an unparseable date %r", source_id, year)
            pub_year = None

        journal = raw_result.get("journal")
        if journal:
            journal = normalize_journal_title(journal)

        return LiteratureResult(
            doi=doi or None,
            pmid=None,
            pmcid=None,
            title=title or None,
            authors=authors,
            publication_year=pub_year,
            journal=journal or None,
            abstract=raw_result.get("abstract"),
            citation_count=raw_result.get("citation_count"),
            source="arxiv",
            source_id=source_id,
        )

    # ------------------------------------------------------------------
    # XML parsing
    # ------------------------------------------------------------------

    def _parse_feed(self, xml_data: str | dict[str, Any]) -> list[LiteratureResult]:
        """
        Parse arXiv Atom XML feed into LiteratureResult list.

        Parameters
        ----------
        xml_data : str or dict
            Atom XML string or dict (from cache/error path).

        Returns
        -------
        list[LiteratureResult]
            Parsed results.
        """
        # With ``response_format="xml"`` the base client returns the raw XML
        # string; a dict can still turn up from a cache/error path.
        if isinstance(xml_data, dict):
            logger.warning("arXiv API returned JSON/empty dict instead of XML — no results")
            return []

        if not xml_data or not isinstance(xml_data, str):
            return []

        try:
            root: ElementTree.Element = parse_xml(xml_data, what="The arXiv feed")
        except ParsingError as exc:
            logger.warning("arXiv feed could not be parsed, no results: %s", exc)
            return []

        # Check for total results > 0. A malformed or missing count is not a
        # reason to throw away the entries the feed does carry.
        total = root.find(f"{{{_OPENSEARCH_NS}}}totalResults")
        if total is not None:
            try:
                if int((total.text or "0").strip()) == 0:
                    return []
            except ValueError:
                logger.debug("arXiv returned a non-numeric totalResults: %r", total.text)

        results: list[LiteratureResult] = []
        for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
            if self._is_error_entry(entry):
                continue
            parsed = self._parse_entry(entry)
            if parsed:
                results.append(parsed)

        return results

    @staticmethod
    def _is_error_entry(entry: ElementTree.Element) -> bool:
        """True for the placeholder entry arXiv returns to report a bad request."""
        id_tag = entry.find(f"{{{_ATOM_NS}}}id")
        if id_tag is None or not id_tag.text:
            return False
        if _ARXIV_ERROR_MARKER not in id_tag.text:
            return False
        summary = entry.find(f"{{{_ATOM_NS}}}summary")
        logger.warning(
            "arXiv API error: %s",
            (summary.text or "").strip() if summary is not None else id_tag.text.strip(),
        )
        return True

    def _parse_entry(self, entry: ElementTree.Element) -> LiteratureResult | None:
        """Parse a single Atom entry into a LiteratureResult."""
        raw: dict[str, Any] = {}

        # arXiv ID (from <id> tag: http://arxiv.org/abs/2301.12345)
        id_tag = entry.find(f"{{{_ATOM_NS}}}id")
        if id_tag is not None and id_tag.text:
            raw["id"] = id_tag.text.strip()
            match = _ARXIV_ID_PATTERN.search(raw["id"])
            if match:
                raw["id"] = match.group(1)

        # Title
        title_tag = entry.find(f"{{{_ATOM_NS}}}title")
        if title_tag is not None and title_tag.text:
            raw["title"] = title_tag.text.strip().replace("\n", " ").strip()

        # Summary (abstract)
        summary_tag = entry.find(f"{{{_ATOM_NS}}}summary")
        if summary_tag is not None and summary_tag.text:
            raw["abstract"] = summary_tag.text.strip()

        # Published date
        published_tag = entry.find(f"{{{_ATOM_NS}}}published")
        if published_tag is not None and published_tag.text:
            raw["year"] = published_tag.text[:4]

        # Updated date (fallback for year)
        if "year" not in raw:
            updated_tag = entry.find(f"{{{_ATOM_NS}}}updated")
            if updated_tag is not None and updated_tag.text:
                raw["year"] = updated_tag.text[:4]

        # Authors
        authors: list[dict[str, str]] = []
        for author_elem in entry.findall(f"{{{_ATOM_NS}}}author"):
            name_elem = author_elem.find(f"{{{_ATOM_NS}}}name")
            if name_elem is not None and name_elem.text:
                authors.append({"name": name_elem.text.strip()})
        if authors:
            raw["authors"] = authors

        # DOI (in arXiv namespace)
        doi_tag = entry.find(f"{{{_ARXIV_NS}}}doi")
        if doi_tag is not None and doi_tag.text:
            raw["doi"] = doi_tag.text.strip()

        # Journal reference
        jref_tag = entry.find(f"{{{_ARXIV_NS}}}journal_ref")
        if jref_tag is not None and jref_tag.text:
            raw["journal"] = jref_tag.text.strip()

        # Categories (as tags / topics)
        # categories: list[str] = []
        # for cat in entry.findall(f"{{{_ATOM_NS}}}category"):
        #     term = cat.get("term")
        #     if term:
        #         categories.append(term)
        # if categories:
        #     raw["categories"] = categories

        if not raw.get("id") and not raw.get("title"):
            return None

        return self._normalize_result(raw)
