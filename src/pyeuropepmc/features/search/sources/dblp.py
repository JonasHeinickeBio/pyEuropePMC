"""
DBLP computer science bibliography literature client.

DBLP (dblp.org) is a comprehensive computer science bibliography with
over 7 million publications. This client provides search via the DBLP
REST API (free, no API key required, returns XML/JSON).

API docs: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Any

from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["DBLPClient"]

_XML_AUTHOR_RE = re.compile(r"<author>(.*?)</author>")
_XML_TITLE_RE = re.compile(r"<title>(.*?)</title>")
_XML_YEAR_RE = re.compile(r"<year>(.*?)</year>")
_XML_JOURNAL_RE = re.compile(r"<(journal|booktitle)>(.*?)</\1>")
_XML_DOI_RE = re.compile(r"<doi>(.*?)</doi>")


class DBLPClient(BaseLiteratureClient):
    """
    Client for the DBLP bibliography search API.

    Searches publications in computer science and related fields.

    Examples
    --------
    >>> client = DBLPClient()
    >>> results = client.search("graph neural networks", limit=10)
    >>> for r in results:
    ...     print(r.title, r.publication_year)
    """

    BASE_URL = "https://dblp.org/search/publ/api"

    def __init__(
        self,
        rate_limit_delay: float = 3.0,
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            **kwargs,
        )

    # Override _make_request since DBLP returns XML
    def _make_request(
        self,
        endpoint: str = "",
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any] | None:
        if params is None:
            params = {}
        params.setdefault("format", "json")
        params.setdefault("h", 100)
        # Delegate to parent but DBLP uses the base URL directly as the endpoint
        return super()._make_request("", params=params, headers=headers, use_cache=use_cache)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "h": min(limit, 100),
        }
        # DBLP doesn't have a server-side sort for this endpoint

        data = self._make_request(params=params)
        if not data:
            return []

        # Parse DBLP JSON response
        result = data.get("result", {})
        hits = result.get("hits", {})
        hit_list = hits.get("hit", []) if isinstance(hits, dict) else []
        if not hit_list:
            return []

        results: list[LiteratureResult] = []
        for item in hit_list[:limit]:
            info = item.get("info", {})
            nr = self._normalize_result(info)
            if nr is not None:
                results.append(nr)
        return results

    # ------------------------------------------------------------------
    # Get single paper
    # ------------------------------------------------------------------

    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        # DBLP doesn't have a general-purpose get-by-ID endpoint.
        # We try to match by DOI or DBLP key.
        # For DBLP key lookup: https://dblp.org/search/publ/api?q=...
        # A proper lookup would use the key directly but this API is limited.
        if identifier.startswith("10."):
            return (
                self.search(f"doi:{identifier}", limit=1)[:1][0]
                if self.search(f"doi:{identifier}", limit=1)
                else None
            )
        return (
            self.search(identifier, limit=1)[:1][0] if self.search(identifier, limit=1) else None
        )

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def _normalize_result(self, raw: dict[str, Any]) -> LiteratureResult:
        # DBLP returns structured JSON per record
        doi: str | None = raw.get("doi", "") or raw.get("doi", "")
        doi = doi or raw.get("accession", "") if "doi" in raw.get("accession", "") else doi

        title: str | None = raw.get("title", "")
        # Remove HTML in titles
        if title:
            title = (
                title.replace("<sub>", "")
                .replace("</sub>", "")
                .replace("<sup>", "")
                .replace("</sup>", "")
                .replace("<i>", "")
                .replace("</i>", "")
            )

        # Authors
        authors_raw = raw.get("authors", {})
        author_list = authors_raw.get("author", []) if isinstance(authors_raw, dict) else []
        if isinstance(author_list, dict):
            author_list = [author_list]
        authors = []
        for a in author_list:
            if isinstance(a, str):
                authors.append({"name": a})
            elif isinstance(a, dict):
                authors.append({"name": a.get("text", a.get("@text", a.get("__text", "")))})
        if not authors:
            authors = None

        # Year
        year: int | None = None
        y = raw.get("year", "") or raw.get("year", "")
        if y:
            with contextlib.suppress(ValueError, IndexError):
                year = int(str(y)[:4])

        # Venue (journal or proceedings)
        venue: str | None = (
            raw.get("journal", "") or raw.get("booktitle", "") or raw.get("venue", "")
        )

        # Abstract may not be available from DBLP
        abstract: str | None = raw.get("abstract", "")

        # Source
        source = "dblp"
        dblp_key: str = (
            raw.get("key", "")
            or raw.get("url", "").replace("https://dblp.org/rec/", "").rstrip(".xml")
            if "url" in raw
            else raw.get("@id", "")
        )

        # Extra metadata
        extra = {
            "dblp_key": dblp_key,
            "dblp_url": f"https://dblp.org/rec/{dblp_key}" if dblp_key else None,
            "type": raw.get("type", ""),
            "pages": raw.get("pages", ""),
            "publisher": raw.get("publisher", ""),
            "ee": raw.get("ee", ""),
        }

        return LiteratureResult(
            doi=doi,
            title=title,
            authors=authors,
            publication_year=year,
            journal=venue,
            abstract=abstract,
            citation_count=0,
            source=source,
            source_id=dblp_key or doi or title or "",
            extra_metadata=extra,
            pmid=None,
            pmcid=None,
        )
