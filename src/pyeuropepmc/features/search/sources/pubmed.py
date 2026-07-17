"""
PubMed API client for literature search.

PubMed provides access to biomedical literature citations from MEDLINE,
life science journals, and online books.  This client provides search
functionality, paper details extraction, batch retrieval, and citation
lookup via NCBI's E-utilities API.
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.features.literature.normalization import (
    normalize_author_list,
    normalize_doi,
    normalize_journal_title,
    normalize_paper_title,
)
from pyeuropepmc.models.literature import Author, LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["PubMedClient"]

# ---------------------------------------------------------------------------
# XML namespace for EFetch results
# ---------------------------------------------------------------------------
_NS = {"ns": "http://www.ncbi.nlm.nih.gov/PubMed"}


class PubMedClient(BaseLiteratureClient):
    """
    Client for PubMed API literature search.

    PubMed provides:
    - Biomedical literature citations from MEDLINE
    - Life science journal articles
    - Author information
    - Publication details
    - Citation counts  (via linked PMC)

    The client supports two retrieval methods:

    * **ESummary** (JSON, default) — lightweight, sufficient for most searches.
    * **EFetch**  (XML) — full records including MeSH terms, grants, chemical
      lists, publication types, and keyword lists.

    Examples
    --------
    >>> client = PubMedClient()
    >>> results = client.search("CRISPR cancer therapy", limit=10)
    >>> for paper in results:
    ...     print(f"{paper.title} ({paper.publication_year})")
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        rate_limit_delay: float = 0.35,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
        email: str | None = None,
        tool_name: str = "pyeuropepmc",
    ) -> None:
        """
        Initialize PubMed client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 0.35).
            NCBI recommends at least 0.33 s delay for E-utilities.
        timeout : int, optional
            Request timeout in seconds (default: 15).
        cache_config : CacheConfig, optional
            Cache configuration.
        email : str, optional
            Email address for NCBI account (improves rate limits).
        tool_name : str, optional
            Tool name for User-Agent (default: ``"pyeuropepmc"``).
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        self.email = email
        self.tool_name = tool_name

        # Set user agent
        user_agent = (
            f"{tool_name}/1.0 (https://github.com/JonasHeinickeBio/pyEuropePMC; mailto:{email})"
            if email
            else f"{tool_name}/1.0"
        )
        self.session.headers.update({"User-Agent": user_agent})

        if email:
            logger.info("PubMed email registered: %s", email)

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
        """
        Search PubMed using ESearch + ESummary.

        Parameters
        ----------
        query : str
            Search query string.
        limit : int, optional
            Maximum number of results (default: 25).
        sort : str, optional
            Sort order  (e.g., ``'relevance'``, ``'date'``, ``'citation'``).
        **kwargs
            Additional parameters:

            - ``pub_date`` — publication date range (e.g. ``"2020/2023"``)
            - ``journal``  — filter by journal title
            - ``author``   — filter by author name

        Returns
        -------
        list[LiteratureResult]
            List of search results as Pydantic models.
        """
        esearch_params: dict[str, Any] = {
            "retmode": "json",
            "retmax": limit,
            "db": "pubmed",
            "term": query,
        }

        if sort:
            esearch_params["sort"] = sort

        if "pub_date" in kwargs:
            esearch_params["datetype"] = "pdat"
            esearch_params["reldate"] = kwargs["pub_date"]

        response = self._make_request("esearch.fcgi", params=esearch_params)
        if response is None:
            return []

        id_list = response.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # Fetch details
        return self.get_papers_batch(id_list[:limit])

    # ------------------------------------------------------------------
    # Get single paper
    # ------------------------------------------------------------------

    def get_paper(
        self,
        identifier: str,
        use_efetch: bool = False,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        """
        Get paper details by PubMed ID.

        Parameters
        ----------
        identifier : str
            PubMed ID (PMID).
        use_efetch : bool, optional
            If ``True``, use EFetch (XML, richer metadata).  Otherwise use
            ESummary (JSON, lighter weight).  Default ``False``.
        **kwargs
            Additional parameters (unused).

        Returns
        -------
        LiteratureResult or None
            Paper details as a Pydantic model, or ``None`` if not found.
        """
        if use_efetch:
            return self._get_paper_efetch(identifier)

        esummary_params = {
            "retmode": "json",
            "db": "pubmed",
            "id": identifier,
        }

        response = self._make_request("esummary.fcgi", params=esummary_params)
        if response is None:
            return None

        papers = response.get("result", {})
        paper = papers.get(identifier, {})
        if not paper:
            return None

        return self._normalize_result(paper)

    # ------------------------------------------------------------------
    # Batch retrieval
    # ------------------------------------------------------------------

    def get_papers_batch(
        self,
        identifiers: list[str],
        use_efetch: bool = False,
    ) -> list[LiteratureResult]:
        """
        Retrieve multiple papers by PMID in a single request (ESummary)
        or individual requests (EFetch).

        Parameters
        ----------
        identifiers : list[str]
            List of PubMed IDs.
        use_efetch : bool, optional
            Whether to use EFetch for each paper (default ``False``).

        Returns
        -------
        list[LiteratureResult]
            List of normalized paper results (failed lookups are omitted).
        """
        if not identifiers:
            return []

        if use_efetch:
            results: list[LiteratureResult] = []
            for pmid in identifiers:
                paper = self._get_paper_efetch(pmid)
                if paper:
                    results.append(paper)
            return results

        # ESummary supports multiple IDs in a single request
        ids_str = ",".join(identifiers)
        params = {
            "retmode": "json",
            "db": "pubmed",
            "id": ids_str,
        }

        response = self._make_request("esummary.fcgi", params=params)
        if response is None:
            return []

        papers_data = response.get("result", {})
        results = []
        for pmid in identifiers:
            raw = papers_data.get(pmid, {})
            if raw:
                normalized = self._normalize_result(raw)
                if normalized:
                    results.append(normalized)

        return results

    # ------------------------------------------------------------------
    # Citation lookup
    # ------------------------------------------------------------------

    def pmid_for_citation(
        self,
        author: str | None = None,
        year: str | int | None = None,
        journal: str | None = None,
        volume: str | None = None,
        first_page: str | None = None,
        title: str | None = None,
    ) -> str | None:
        """
        Resolve a citation to a PubMed ID using ECitMatch.

        At least **3 of the 6** parameters should be provided for reliable
        matching.  This is modelled after Metapub's ``pmids_for_citation``.

        Parameters
        ----------
        author : str, optional
            First author surname (e.g. ``"Smith"``).
        year : str or int, optional
            Publication year.
        journal : str, optional
            Journal abbreviation (NLM style).
        volume : str, optional
            Journal volume.
        first_page : str, optional
            First page number.
        title : str, optional
            First word or phrase of the article title.

        Returns
        -------
        str or None
            PMID if found, else ``None``.
        """
        # Build the citation string for ECitMatch
        parts = [
            author or "",
            str(year) if year else "",
            journal or "",
            volume or "",
            first_page or "",
            title or "",
        ]

        params = {
            "db": "pubmed",
            "retmode": "xml",
            "rettype": "ulist",
        }
        # ECitMatch expects the citation in POST data
        cit_string = "|".join(parts)
        data = {"cit": cit_string}

        import requests

        try:
            response = requests.post(
                f"{self.BASE_URL}/ecitmatch.cgi",
                params=params,
                data=data,
                headers={"User-Agent": self.session.headers.get("User-Agent", "")},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("ECitMatch failed for citation")
            return None

        text = response.text.strip()
        if not text or "NOT_FOUND" in text:
            return None

        # Response format:  <journal>|...|PMID
        for line in text.splitlines():
            if "|" in line:
                parts_line = line.split("|")
                potential_pmid = parts_line[-1].strip()
                if potential_pmid.isdigit():
                    return potential_pmid

        return None

    # ------------------------------------------------------------------
    # EFetch (XML) — rich metadata
    # ------------------------------------------------------------------

    def _get_paper_efetch(self, identifier: str) -> LiteratureResult | None:
        """Fetch a paper using EFetch for rich XML metadata."""
        params = {
            "db": "pubmed",
            "id": identifier,
            "retmode": "xml",
            "rettype": "full",
        }

        response = self._make_request("efetch.fcgi", params=params)
        if response is None:
            return None

        # EFetch returns XML wrapped in JSON as a string in the "xml" key
        xml_text = None
        if isinstance(response, dict):
            xml_text = response.get("xml")
        if not xml_text:
            return None

        return self._parse_efetch_xml(xml_text, identifier)

    def _parse_efetch_xml(
        self,
        xml_text: str,
        pmid: str,
    ) -> LiteratureResult | None:
        """Parse EFetch XML response into a :class:`LiteratureResult`."""
        try:
            from xml.etree import ElementTree as ET
        except ImportError:
            logger.warning("EFetch requires xml.etree.ElementTree — falling back to ESummary")
            return self.get_paper(pmid, use_efetch=False)

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.exception("Failed to parse EFetch XML for PMID=%s", pmid)
            return None

        # Find the PubmedArticle
        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        medline = article.find(".//MedlineCitation")
        if medline is None:
            return None

        # --- Article title ---
        art_elem = medline.find(".//Article")
        title_elem = art_elem.find("ArticleTitle") if art_elem is not None else None
        title = title_elem.text if title_elem is not None else None
        title = normalize_paper_title(title)

        # --- Authors ---
        authors_list: list[Author] = []
        author_list_elem = medline.find(".//AuthorList")
        if author_list_elem is not None:
            for author_elem in author_list_elem.findall("Author"):
                last = author_elem.find("LastName")
                fore = author_elem.find("ForeName")
                if last is not None:
                    name = f"{last.text}, {fore.text}" if fore is not None else last.text
                    authors_list.append(Author(name=name or ""))

        # --- Journal ---
        journal_elem = medline.find(".//Journal/Title")
        journal_abbrev_elem = medline.find(".//Journal/ISOAbbreviation")
        journal = None
        if journal_elem is not None and journal_elem.text:
            journal = normalize_journal_title(journal_elem.text)
        if not journal and journal_abbrev_elem is not None:
            journal = normalize_journal_title(journal_abbrev_elem.text)

        # --- Year ---
        year = None
        pub_date = (
            medline.find(".//Journal/JournalIssue/PubDate/Year")
            or medline.find(".//Article/ArticleDate/Year")
            or medline.find(".//DateCreated/Year")
        )
        if pub_date is not None and pub_date.text:
            try:
                year = int(pub_date.text)
            except ValueError:
                pass

        # --- Abstract ---
        abstract_text = None
        abstract_elem = medline.find(".//Abstract/AbstractText")
        if abstract_elem is not None:
            # Collect all AbstractText elements
            parts: list[str] = []
            for at in medline.findall(".//Abstract/AbstractText"):
                label = at.get("Label", "")
                text = (at.text or "").strip()
                if label and text:
                    parts.append(f"{label}: {text}")
                elif text:
                    parts.append(text)
            abstract_text = " ".join(parts) if parts else (abstract_elem.text or "")

        # --- MeSH terms ---
        mesh_terms: list[str] = []
        for mesh in medline.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
            if mesh.text:
                mesh_terms.append(mesh.text)

        # --- Publication types ---
        pub_types: list[str] = []
        for pt in medline.findall(".//PublicationTypeList/PublicationType"):
            if pt.text:
                pub_types.append(pt.text)

        # --- Keywords ---
        keywords: list[str] = []
        for kw in medline.findall(".//KeywordList/Keyword"):
            if kw.text:
                keywords.append(kw.text)

        # --- DOI ---
        doi = None
        for eid in medline.findall(".//ArticleIdList/ArticleId"):
            if eid.get("IdType") == "doi" and eid.text:
                doi = normalize_doi(eid.text)
                break

        # --- PMCID ---
        pmcid = None
        for eid in article.findall(".//ArticleIdList/ArticleId"):
            if eid.get("IdType") == "pmc" and eid.text:
                pmcid = eid.text
                break

        # --- Grant info ---
        grants: list[dict[str, str]] = []
        for grant in medline.findall(".//GrantList/Grant"):
            grant_id = grant.find("GrantID")
            acronym = grant.find("Acronym")
            agency = grant.find("Agency")
            grant_rec: dict[str, str] = {}
            if grant_id is not None and grant_id.text:
                grant_rec["id"] = grant_id.text
            if acronym is not None and acronym.text:
                grant_rec["acronym"] = acronym.text
            if agency is not None and agency.text:
                grant_rec["agency"] = agency.text
            if grant_rec:
                grants.append(grant_rec)

        return LiteratureResult(
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            title=title,
            authors=authors_list or None,
            publication_year=year,
            journal=journal,
            abstract=abstract_text.strip() if abstract_text else None,
            citation_count=None,  # EFetch doesn't return citation counts
            source="pubmed",
            source_id=pmid,
            pubmed_data={
                "efetch_xml": True,
                "mesh_terms": mesh_terms,
                "publication_types": pub_types,
                "keywords": keywords,
                "grants": grants,
            },
        )

    # ------------------------------------------------------------------
    # Normalisation  (ESummary → LiteratureResult)
    # ------------------------------------------------------------------

    def _normalize_result(self, raw_result: dict[str, Any]) -> LiteratureResult:
        """
        Normalize PubMed ESummary response to :class:`LiteratureResult`.

        Parameters
        ----------
        raw_result : dict
            Raw PubMed API response.

        Returns
        -------
        LiteratureResult
            Normalized result as a Pydantic model.
        """
        pmid = raw_result.get("pmid")
        doi = raw_result.get("doi")
        title = raw_result.get("title")
        raw_authors = raw_result.get("authors", [])
        publication_year = raw_result.get("pubdate", "")
        journal = raw_result.get("source")
        abstract = raw_result.get("abstract")
        citation_count = raw_result.get("citationcount", 0)

        # Normalize publication year
        year = None
        if publication_year:
            import re

            match = re.search(r"(\d{4})", str(publication_year))
            if match:
                year = int(match.group(1))

        # Normalize author list
        normalized_authors = normalize_author_list(raw_authors)

        author_objects: list[Author] = []
        for author_dict in normalized_authors or []:
            author_objects.append(
                Author(
                    name=author_dict.get("name", ""),
                    orcid=author_dict.get("orcid"),
                    affiliation=author_dict.get("affiliation"),
                )
            )

        return LiteratureResult(
            doi=normalize_doi(doi),
            pmid=str(pmid) if pmid else None,
            pmcid=None,  # ESummary doesn't provide PMCID
            title=normalize_paper_title(title),
            authors=author_objects if author_objects else None,
            publication_year=year,
            journal=normalize_journal_title(journal),
            abstract=abstract.strip() if isinstance(abstract, str) else abstract,
            citation_count=int(citation_count) if citation_count else None,
            source="pubmed",
            source_id=str(pmid) if pmid else None,
            pubmed_data=raw_result,
        )
