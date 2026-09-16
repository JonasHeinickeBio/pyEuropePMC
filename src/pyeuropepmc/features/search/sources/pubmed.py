"""
PubMed API client for literature search.

PubMed provides access to biomedical literature citations from MEDLINE,
life science journals, and online books.  This client provides search
functionality, paper details extraction, batch retrieval, and citation
lookup via NCBI's E-utilities API.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

import requests

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.core.xml_parsing import parse_xml
from pyeuropepmc.features.literature.normalization import (
    normalize_affiliation,
    normalize_author_list,
    normalize_doi,
    normalize_journal_title,
    normalize_paper_title,
)
from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import Author, LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["PubMedClient"]

# ---------------------------------------------------------------------------
# XML namespace for EFetch results
# ---------------------------------------------------------------------------
_NS = {"ns": "http://www.ncbi.nlm.nih.gov/PubMed"}


def _element_text(element: ET.Element | None) -> str:
    """All the text of ``element``, inline markup included, whitespace collapsed.

    ``element.text`` stops at the first child element, and EFetch keeps
    inline HTML-style markup - <i>, <b>, <sup>, <sub> - in titles, abstracts
    and affiliations.
    """
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


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

        try:
            response = self.session.post(
                f"{self.BASE_URL}/ecitmatch.cgi",
                params=params,
                data=data,
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

        # EFetch returns XML, not JSON — ask the base client for the raw text.
        response = self._make_request("efetch.fcgi", params=params, response_format="xml")
        if not response:
            return None

        return self._parse_efetch_xml(response, identifier)

    def _parse_efetch_xml(  # noqa: C901
        self,
        xml_text: str,
        pmid: str,
    ) -> LiteratureResult | None:
        """Parse EFetch XML response into a :class:`LiteratureResult`."""
        try:
            root: ET.Element = parse_xml(xml_text, what="The EFetch response")
        except ParsingError as exc:
            logger.warning("EFetch XML for PMID=%s could not be parsed, no result: %s", pmid, exc)
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
        # Like an abstract section, a title keeps inline markup: "Structure
        # of the <i>Escherichia coli</i> LolCDE complex" read as "Structure of
        # the" through .text.
        title = normalize_paper_title(_element_text(title_elem) or None)

        # --- Authors ---
        authors_list: list[Author] = []
        author_list_elem = medline.find(".//AuthorList")
        if author_list_elem is not None:
            for author_elem in author_list_elem.findall("Author"):
                author = self._efetch_author(author_elem)
                if author is not None:
                    authors_list.append(author)

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
        # NB: ``or``-chaining Element.find() results is unsafe — an Element
        # with no children (e.g. a leaf <Year>2022</Year>) is falsy, so `or`
        # would skip straight past a real match to the next candidate. Pick
        # the first *found* (non-None) element explicitly instead.
        pub_date = next(
            (
                el
                for el in (
                    medline.find(".//Journal/JournalIssue/PubDate/Year"),
                    medline.find(".//Article/ArticleDate/Year"),
                    medline.find(".//DateCreated/Year"),
                )
                if el is not None
            ),
            None,
        )
        if pub_date is not None and pub_date.text:
            with contextlib.suppress(ValueError):
                year = int(pub_date.text)

        # --- Abstract ---
        abstract_text = None
        abstract_elem = medline.find(".//Abstract/AbstractText")
        if abstract_elem is not None:
            # Collect all AbstractText elements
            parts: list[str] = []
            for at in medline.findall(".//Abstract/AbstractText"):
                label = at.get("Label", "")
                # itertext, not .text: a section is cut off at its first
                # inline element, and PubMed keeps <i>, <b>, <sup> and <sub>
                # in abstracts. PMID 28424752's BACKGROUND section stopped at
                # "commercial", before <i>bath salts</i>.
                text = _element_text(at)
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

        # --- DOI and PMCID ---
        # The record's own identifiers are in <PubmedData><ArticleIdList>, a
        # sibling of <MedlineCitation>, so the DOI search - which ran inside
        # <MedlineCitation> - found nothing: 5 of 5 measured records came back
        # without a DOI. The PMCID search ran over the whole <PubmedArticle>,
        # which also holds an <ArticleIdList> for every cited reference, so a
        # record with no PMCID of its own took a reference's: PMID 33093664
        # reported "1738058".
        own_ids = self._efetch_own_article_ids(article)

        doi = next(
            (
                d
                for eid in own_ids
                if eid.get("IdType") == "doi" and (d := normalize_doi(eid.text))
            ),
            None,
        )
        if doi is None and art_elem is not None:
            doi = next(
                (
                    d
                    for eloc in art_elem.findall("ELocationID")
                    if eloc.get("EIdType") == "doi"
                    and eloc.get("ValidYN", "Y") == "Y"
                    and (d := normalize_doi(eloc.text))
                ),
                None,
            )

        pmcid = next(
            (
                eid.text.strip()
                for eid in own_ids
                if eid.get("IdType") == "pmc" and eid.text and eid.text.strip()
            ),
            None,
        )

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
            source_id=str(pmid) if pmid else (doi or ""),
            pubmed_data={
                "efetch_xml": True,
                "mesh_terms": mesh_terms,
                "publication_types": pub_types,
                "keywords": keywords,
                "grants": grants,
            },
        )

    @staticmethod
    def _efetch_own_article_ids(article: ET.Element) -> list[ET.Element]:
        """The <ArticleId> elements that identify this record.

        Only <PubmedData><ArticleIdList> - not the <ArticleIdList> of each
        <Reference> in <ReferenceList>, which describe the works it cites.
        """
        return article.findall("./PubmedData/ArticleIdList/ArticleId")

    @staticmethod
    def _efetch_author(author_elem: ET.Element) -> Author | None:
        """One EFetch <Author>, with its ORCID and affiliations.

        Both were dropped. An author with several <AffiliationInfo> elements
        gets them joined with "; ", since each affiliation is a full address
        that contains commas of its own.
        """
        last = _element_text(author_elem.find("LastName"))
        if not last:
            return None
        fore = _element_text(author_elem.find("ForeName"))
        name = f"{last}, {fore}" if fore else last

        affiliations = [
            affiliation
            for elem in author_elem.findall("AffiliationInfo/Affiliation")
            if (affiliation := normalize_affiliation(_element_text(elem)))
        ]
        affiliation = "; ".join(affiliations) or None

        orcid = next(
            (
                value
                for identifier in author_elem.findall("Identifier")
                if identifier.get("Source") == "ORCID" and (value := _element_text(identifier))
            ),
            None,
        )
        try:
            return Author(name=name, orcid=orcid, affiliation=affiliation)
        except ValueError:
            # A malformed ORCID must not cost the author: keep the name and
            # the affiliation.
            logger.debug("Ignoring invalid ORCID %r for %s", orcid, name)
            return Author(name=name, affiliation=affiliation)

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
        # ESummary returns the PMID under "uid" and identifiers under
        # "articleids" (e.g. [{'idtype': 'doi', 'value': '10.xxx/yyy'}]).
        pmid = raw_result.get("pmid") or raw_result.get("uid")
        doi = raw_result.get("doi")
        if not doi:
            for item in raw_result.get("articleids") or []:
                if isinstance(item, dict) and item.get("idtype") == "doi":
                    doi = item.get("value")
                    break
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
            source_id=str(pmid) if pmid else (doi or ""),
            pubmed_data=raw_result,
        )
