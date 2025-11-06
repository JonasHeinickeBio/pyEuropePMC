"""
Advanced Query Builder for Europe PMC searches.

This module provides a fluent API for building complex search queries with
type-safe field specifications, logical operators, and validation using the
CoLRev search-query package.

Supported Search Fields (from Europe PMC Web Service Reference 6.9.0):
-----------------------------------------------------------------------

Core Bibliographic:
    - title, abstract, author, journal, issn, volume, issue, page_info
    - pub_year, pub_type, doi, pmid, pmcid, ext_id

Date Fields:
    - e_pdate (electronic publication date)
    - first_pdate (first publication date)
    - p_pdate (print publication date)
    - embargo_date, creation_date, update_date

Author & Affiliation:
    - affiliation, investigator, authorid, authorid_type

Article Metadata:
    - language, grant_agency, grant_id, keyword, mesh
    - chemical, disease, gene_protein, goterm, organism

Manuscript Fields:
    - auth_man, auth_man_id, epmc_auth_man, nih_auth_man, embargoed_man

Full Text Availability:
    - has_abstract, has_pdf, has_full_text, has_reflist, has_tm
    - has_xrefs, has_suppl, has_labslinks, has_data, has_book
    - open_access, in_pmc, in_epmc

Database Cross-References:
    - has_uniprot, has_embl, has_pdb, has_intact, has_interpro
    - has_chebi, has_chembl, has_omim, has_arxpr, has_crd, has_doi

Database Citations:
    - uniprot_pubs, embl_pubs, pdb_pubs, intact_pubs, interpro_pubs
    - chebi_pubs, chembl_pubs, omim_pubs, arxpr_pubs, crd_links, labs_pubs

Accession & Citations:
    - accession_id, accession_type
    - citation_count, cites, cited, reffed_by

Collection Metadata:
    - source, license, subset

Books:
    - isbn, book_id, editor, publisher

Section-Level Search:
    - abbr, ack_fund, appendix, auth_con, case, comp_int, concl
    - discuss, fig, intro, methods, other, ref, results, suppl, table, body

Example usage:
    >>> from pyeuropepmc import QueryBuilder
    >>> # Use the generic field() method for field-specific searches
    >>> query = (QueryBuilder()
    ...     .field("author", "Smith J")
    ...     .and_()
    ...     .keyword("cancer", field="title")
    ...     .and_()
    ...     .date_range(start_year=2020, end_year=2023)
    ...     .and_()
    ...     .field("open_access", True)
    ...     .build())
    >>> client.search(query)
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Literal

try:
    from search_query import AndQuery, OrQuery, Query
    from search_query.parser import parse

    SEARCH_QUERY_AVAILABLE = True
except ImportError:
    SEARCH_QUERY_AVAILABLE = False
    # Provide fallback when search-query is not installed
    Query = Any
    AndQuery = Any
    OrQuery = Any

    def parse(*args: Any, **kwargs: Any) -> Any:
        """Fallback parse function when search-query is not available."""
        raise ImportError(
            "search-query package is required for query validation. "
            "Install it with: pip install search-query"
        )


from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import QueryBuilderError

# Initialize logger
logger = logging.getLogger(__name__)

__all__ = [
    "QueryBuilder",
    "QueryBuilderError",
    "get_available_fields",
    "validate_field_coverage",
    "get_field_info",
]

# Constants
MIN_VALID_YEAR = 1000  # Minimum valid publication year
SPECIAL_QUERY_CHARS = [" ", ":", "(", ")", "[", "]", "{", "}", "AND", "OR", "NOT"]


# Europe PMC searchable fields (from official API documentation)
# Last updated: 2025-11-05 from https://www.ebi.ac.uk/europepmc/webservices/rest/fields

# Field metadata: Maps lowercase field names to (API_NAME, description)
FIELD_METADATA: dict[str, tuple[str, str]] = {
    # Core bibliographic fields
    "title": ("TITLE", "Article or book title"),
    "abstract": ("ABSTRACT", "Article abstract text"),
    "author": ("AUTH", "Author name (full or abbreviated form)"),
    "auth": ("AUTH", "Author name (API abbreviated form)"),
    "journal": ("JOURNAL", "Journal name or abbreviation"),
    "issn": ("ISSN", "International Standard Serial Number"),
    "essn": ("ESSN", "Electronic ISSN"),
    "volume": ("VOLUME", "Journal volume number"),
    "issue": ("ISSUE", "Journal issue number"),
    "page_info": ("PAGE_INFO", "Page numbers or article number"),
    "pub_year": ("PUB_YEAR", "Publication year"),
    "pub_type": ("PUB_TYPE", "Publication type (e.g., journal article, review)"),
    "doi": ("DOI", "Digital Object Identifier"),
    "pmid": ("PMID", "PubMed identifier"),
    "pmcid": ("PMCID", "PubMed Central identifier"),
    "ext_id": ("EXT_ID", "External repository-level identifier"),
    # Date fields
    "e_pdate": ("E_PDATE", "Electronic publication date"),
    "first_pdate": ("FIRST_PDATE", "First publication date"),
    "first_idate": ("FIRST_IDATE", "First indexed date"),
    "first_idate_d": ("FIRST_IDATE_D", "First indexed date (day precision)"),
    "p_pdate": ("P_PDATE", "Print publication date"),
    "embargo_date": ("EMBARGO_DATE", "Embargo release date"),
    "creation_date": ("CREATION_DATE", "Record creation date"),
    "update_date": ("UPDATE_DATE", "Record last update date"),
    "index_date": ("INDEX_DATE", "Date record was indexed"),
    "ft_cdate": ("FT_CDATE", "Full text creation date"),
    "ft_cdate_d": ("FT_CDATE_D", "Full text creation date (day precision)"),
    # Author and affiliation
    "affiliation": ("AFF", "Author institutional affiliation"),
    "aff": ("AFF", "Author institutional affiliation (API abbreviated form)"),
    "investigator": ("INVESTIGATOR", "Principal investigator name"),
    "authorid": ("AUTHORID", "Author identifier (e.g., ORCID)"),
    "authorid_type": ("AUTHORID_TYPE", "Type of author identifier"),
    "auth_first": ("AUTH_FIRST", "First author name"),
    "auth_last": ("AUTH_LAST", "Last author name"),
    "auth_collective_list": ("AUTH_COLLECTIVE_LIST", "Collective author group names"),
    "author_roles": ("AUTHOR_ROLES", "Author contribution roles"),
    # Article metadata
    "language": ("LANG", "Publication language code"),
    "lang": ("LANG", "Publication language code (API abbreviated form)"),
    "grant_agency": ("GRANT_AGENCY", "Funding agency name"),
    "grant_agency_id": ("GRANT_AGENCY_ID", "Funding agency identifier"),
    "grant_id": ("GRANT_ID", "Grant or award number"),
    "funder_initiative": ("FUNDER_INITIATIVE", "Funding initiative or program name"),
    "keyword": ("KEYWORD", "Author-provided keywords"),
    "kw": ("KW", "Author-provided keywords (API abbreviated form)"),
    "mesh": ("MESH", "Medical Subject Heading terms"),
    "chemical": ("CHEM", "Chemical substance names"),
    "chem": ("CHEM", "Chemical substance names (API abbreviated form)"),
    "disease": ("DISEASE", "Disease or condition terms (text-mined)"),
    "disease_id": ("DISEASE_ID", "Disease identifier"),
    "gene_protein": ("GENE_PROTEIN", "Gene or protein names (text-mined)"),
    "goterm": ("GOTERM", "Gene Ontology term"),
    "goterm_id": ("GOTERM_ID", "Gene Ontology identifier"),
    "organism": ("ORGANISM", "Organism or species name"),
    "organism_id": ("ORGANISM_ID", "Organism taxonomy identifier"),
    "chebiterm": ("CHEBITERM", "Chemical Entities of Biological Interest term"),
    "chebiterm_id": ("CHEBITERM_ID", "ChEBI identifier"),
    "experimental_method": ("EXPERIMENTAL_METHOD", "Experimental method or technique"),
    "experimental_method_id": ("EXPERIMENTAL_METHOD_ID", "Experimental method identifier"),
    # Manuscript fields
    "auth_man": ("AUTH_MAN", "Author manuscript indicator"),
    "auth_man_id": ("AUTH_MAN_ID", "Author manuscript identifier"),
    "epmc_auth_man": ("EPMC_AUTH_MAN", "Europe PMC author manuscript"),
    "nih_auth_man": ("NIH_AUTH_MAN", "NIH author manuscript"),
    "embargoed_man": ("EMBARGOED_MAN", "Embargoed manuscript"),
    # Full text availability
    "has_abstract": ("HAS_ABSTRACT", "Has abstract (y/n)"),
    "has_pdf": ("HAS_PDF", "Has PDF available (y/n)"),
    "has_text": ("HAS_TEXT", "Has full text (y/n)"),
    "has_ft": ("HAS_FT", "Has full text (y/n)"),
    "has_fulltext": ("HAS_FULLTEXT", "Has full text available (y/n)"),
    "has_fulltextdata": ("HAS_FULLTEXTDATA", "Has full text data (y/n)"),
    "has_free_fulltext": ("HAS_FREE_FULLTEXT", "Has free full text access (y/n)"),
    "has_reflist": ("HAS_REFLIST", "Has reference list (y/n)"),
    "has_tm": ("HAS_TM", "Has text-mined annotations (y/n)"),
    "has_xrefs": ("HAS_XREFS", "Has cross-references (y/n)"),
    "has_suppl": ("HAS_SUPPL", "Has supplementary materials (y/n)"),
    "has_labslinks": ("HAS_LABSLINKS", "Has lab links (y/n)"),
    "has_data": ("HAS_DATA", "Has associated data (y/n)"),
    "has_book": ("HAS_BOOK", "Is a book or book chapter (y/n)"),
    "has_preprint": ("HAS_PREPRINT", "Has preprint version (y/n)"),
    "has_published_version": ("HAS_PUBLISHED_VERSION", "Has published version (y/n)"),
    "has_version_evaluations": ("HAS_VERSION_EVALUATIONS", "Has version evaluations (y/n)"),
    "open_access": ("OPEN_ACCESS", "Open access status (y/n)"),
    "in_pmc": ("IN_PMC", "Available in PubMed Central (y/n)"),
    "in_epmc": ("IN_EPMC", "Available in Europe PMC (y/n)"),
    # Database cross-references
    "has_uniprot": ("HAS_UNIPROT", "Has UniProt cross-references (y/n)"),
    "has_embl": ("HAS_EMBL", "Has EMBL/ENA cross-references (y/n)"),
    "has_pdb": ("HAS_PDB", "Has Protein Data Bank cross-references (y/n)"),
    "has_intact": ("HAS_INTACT", "Has IntAct molecular interaction data (y/n)"),
    "has_interpro": ("HAS_INTERPRO", "Has InterPro protein family cross-references (y/n)"),
    "has_chebi": ("HAS_CHEBI", "Has ChEBI chemical cross-references (y/n)"),
    "has_chembl": ("HAS_CHEMBL", "Has ChEMBL bioactivity cross-references (y/n)"),
    "has_omim": ("HAS_OMIM", "Has OMIM genetic disorder cross-references (y/n)"),
    "has_arxpr": ("HAS_ARXPR", "Has arXiv preprint cross-references (y/n)"),
    "has_crd": ("HAS_CRD", "Has clinical trial registry cross-references (y/n)"),
    "has_doi": ("HAS_DOI", "Has DOI identifier (y/n)"),
    "has_pride": ("HAS_PRIDE", "Has PRIDE proteomics cross-references (y/n)"),
    # Database citations
    "uniprot_pubs": ("UNIPROT_PUBS", "Cited by UniProt entries"),
    "embl_pubs": ("EMBL_PUBS", "Cited by EMBL/ENA entries"),
    "pdb_pubs": ("PDB_PUBS", "Cited by PDB structures"),
    "intact_pubs": ("INTACT_PUBS", "Cited by IntAct interactions"),
    "interpro_pubs": ("INTERPRO_PUBS", "Cited by InterPro entries"),
    "chebi_pubs": ("CHEBI_PUBS", "Cited by ChEBI entries"),
    "chembl_pubs": ("CHEMBL_PUBS", "Cited by ChEMBL entries"),
    "omim_pubs": ("OMIM_PUBS", "Cited by OMIM entries"),
    "arxpr_pubs": ("ARXPR_PUBS", "Cited by arXiv preprints"),
    "crd_links": ("CRD_LINKS", "Linked clinical trial records"),
    "labs_pubs": ("LABS_PUBS", "Laboratory publications"),
    "pride_pubs": ("PRIDE_PUBS", "Cited by PRIDE datasets"),
    # Accession types
    "accession_id": ("ACCESSION_ID", "Database accession number"),
    "accession_type": ("ACCESSION_TYPE", "Type of accession (e.g., arrayexpress, pdb)"),
    "ft_id": ("FT_ID", "Full text identifier"),
    "embl_ror_id": ("EMBL_ROR_ID", "EMBL Research Organization Registry ID"),
    "org_id": ("ORG_ID", "Organization identifier"),
    # Citation fields
    "citation_count": ("CITED", "Number of citations"),
    "cites": ("CITES", "Articles this paper cites"),
    "cited": ("CITED", "Citation count"),
    "reffed_by": ("REFFED_BY", "Articles that reference this paper"),
    # Collection metadata
    "source": ("SRC", "Data source code (MED, PMC, AGR, etc.)"),
    "src": ("SRC", "Data source code (API abbreviated form)"),
    "license": ("LICENSE", "Content license type"),
    "subset": ("SUBSET", "Content subset classification"),
    "resource_name": ("RESOURCE_NAME", "Resource or database name"),
    # Books
    "isbn": ("ISBN", "International Standard Book Number"),
    "book_id": ("BOOK_ID", "Book identifier"),
    "editor": ("ED", "Book editor name"),
    "ed": ("ED", "Book editor name (API abbreviated form)"),
    "publisher": ("PUBLISHER", "Publisher name"),
    "parent_title": ("PARENT_TITLE", "Parent book or series title"),
    "series_name": ("SERIES_NAME", "Book series name"),
    # Section-level search fields
    "abbr": ("ABBR", "Abbreviations in text"),
    "ack_fund": ("ACK_FUND", "Acknowledgments and funding section"),
    "appendix": ("APPENDIX", "Appendix section"),
    "auth_con": ("AUTH_CON", "Author contributions section"),
    "case": ("CASE", "Case study or case report section"),
    "comp_int": ("COMP_INT", "Competing interests section"),
    "concl": ("CONCL", "Conclusions section"),
    "discuss": ("DISCUSS", "Discussion section"),
    "fig": ("FIG", "Figure captions and content"),
    "intro": ("INTRO", "Introduction section"),
    "methods": ("METHODS", "Methods or materials section"),
    "other": ("OTHER", "Other uncategorized sections"),
    "ref": ("REF", "References section"),
    "results": ("RESULTS", "Results section"),
    "suppl": ("SUPPL", "Supplementary materials section"),
    "table": ("TABLE", "Table content"),
    "body": ("BODY", "Main article body text"),
    "back": ("BACK", "Back matter sections"),
    "back_noref": ("BACK_NOREF", "Back matter excluding references"),
    "data_availability": ("DATA_AVAILABILITY", "Data availability statement"),
    "title_abs": ("TITLE_ABS", "Combined title and abstract"),
    # Annotation fields
    "annotation_provider": ("ANNOTATION_PROVIDER", "Source of text-mining annotations"),
    "annotation_type": ("ANNOTATION_TYPE", "Type of annotation (e.g., Disease, Gene)"),
    # System fields (note: API returns these in lowercase)
    "shard": ("SHARD", "Database shard identifier (internal use)"),
    "qn1": ("QN1", "Query normalization field 1 (internal use)"),
    "qn2": ("QN2", "Query normalization field 2 (internal use)"),
    "_version_": ("_version_", "Document version (internal use)"),
    "text_hl": ("text_hl", "Highlighted text snippets (internal use)"),
    "text_synonyms": ("text_synonyms", "Text synonym expansion (internal use)"),
}

# Type hint for valid field names
FieldType = Literal[
    "title",
    "abstract",
    "author",
    "auth",
    "journal",
    "issn",
    "essn",
    "volume",
    "issue",
    "page_info",
    "pub_year",
    "pub_type",
    "doi",
    "pmid",
    "pmcid",
    "ext_id",
    "e_pdate",
    "first_pdate",
    "first_idate",
    "first_idate_d",
    "p_pdate",
    "embargo_date",
    "creation_date",
    "update_date",
    "index_date",
    "ft_cdate",
    "ft_cdate_d",
    "affiliation",
    "aff",
    "investigator",
    "authorid",
    "authorid_type",
    "auth_first",
    "auth_last",
    "auth_collective_list",
    "author_roles",
    "language",
    "lang",
    "grant_agency",
    "grant_agency_id",
    "grant_id",
    "funder_initiative",
    "keyword",
    "kw",
    "mesh",
    "chemical",
    "chem",
    "disease",
    "disease_id",
    "gene_protein",
    "goterm",
    "goterm_id",
    "organism",
    "organism_id",
    "chebiterm",
    "chebiterm_id",
    "experimental_method",
    "experimental_method_id",
    "auth_man",
    "auth_man_id",
    "epmc_auth_man",
    "nih_auth_man",
    "embargoed_man",
    "has_abstract",
    "has_pdf",
    "has_text",
    "has_ft",
    "has_fulltext",
    "has_fulltextdata",
    "has_free_fulltext",
    "has_reflist",
    "has_tm",
    "has_xrefs",
    "has_suppl",
    "has_labslinks",
    "has_data",
    "has_book",
    "has_preprint",
    "has_published_version",
    "has_version_evaluations",
    "open_access",
    "in_pmc",
    "in_epmc",
    "has_uniprot",
    "has_embl",
    "has_pdb",
    "has_intact",
    "has_interpro",
    "has_chebi",
    "has_chembl",
    "has_omim",
    "has_arxpr",
    "has_crd",
    "has_doi",
    "has_pride",
    "uniprot_pubs",
    "embl_pubs",
    "pdb_pubs",
    "intact_pubs",
    "interpro_pubs",
    "chebi_pubs",
    "chembl_pubs",
    "omim_pubs",
    "arxpr_pubs",
    "crd_links",
    "labs_pubs",
    "pride_pubs",
    "accession_id",
    "accession_type",
    "ft_id",
    "embl_ror_id",
    "org_id",
    "citation_count",
    "cites",
    "cited",
    "reffed_by",
    "source",
    "src",
    "license",
    "subset",
    "resource_name",
    "isbn",
    "book_id",
    "editor",
    "ed",
    "publisher",
    "parent_title",
    "series_name",
    "abbr",
    "ack_fund",
    "appendix",
    "auth_con",
    "case",
    "comp_int",
    "concl",
    "discuss",
    "fig",
    "intro",
    "methods",
    "other",
    "ref",
    "results",
    "suppl",
    "table",
    "body",
    "back",
    "back_noref",
    "data_availability",
    "title_abs",
    "annotation_provider",
    "annotation_type",
    "shard",
    "qn1",
    "qn2",
    "_version_",
    "text_hl",
    "text_synonyms",
]


class QueryBuilder:
    """
    A fluent API builder for constructing complex Europe PMC search queries.

    This class provides type-safe methods for building search queries with
    validation and optimization support through the CoLRev search-query package.

    Attributes
    ----------
    _parts : list[str]
        Query components that will be combined
    _last_operator : str | None
        Last logical operator used (for validation)
    _validate : bool
        Whether to validate queries before building

    Examples
    --------
    Simple query:
        >>> qb = QueryBuilder()
        >>> query = qb.keyword("cancer").build()
        >>> # Result: "cancer"

    Complex query with multiple conditions:
        >>> qb = QueryBuilder()
        >>> query = (qb
        ...     .field("author", "Smith J")
        ...     .and_()
        ...     .keyword("CRISPR", field="title")
        ...     .and_()
        ...     .date_range(2020, 2023)
        ...     .build())

    Using OR logic:
        >>> qb = QueryBuilder()
        >>> query = (qb
        ...     .keyword("cancer", field="title")
        ...     .or_()
        ...     .keyword("tumor", field="title")
        ...     .build())

    With MeSH terms and filters:
        >>> qb = QueryBuilder()
        >>> query = (qb
        ...     .field("mesh", "Neoplasms")
        ...     .and_()
        ...     .field("open_access", True)
        ...     .build())
    """

    def __init__(self, validate: bool = False) -> None:
        """
        Initialize a new QueryBuilder.

        Parameters
        ----------
        validate : bool, optional
            Whether to validate queries using search-query package (default: False).
            If search-query is not installed, validation is automatically disabled.
        """
        self._parts: list[str] = []
        self._last_operator: str | None = None
        self._validate = validate and SEARCH_QUERY_AVAILABLE

        if validate and not SEARCH_QUERY_AVAILABLE:
            import warnings

            warnings.warn(
                "search-query package not available. Query validation is disabled. "
                "Install it with: pip install search-query",
                stacklevel=2,
            )

    def keyword(self, term: str, field: FieldType | None = None) -> QueryBuilder:
        """
        Add a keyword search term.

        Parameters
        ----------
        term : str
            The search term to add
        field : FieldType, optional
            The field to search in (e.g., "title", "abstract")

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.keyword("cancer").build()
        >>> query = qb.keyword("CRISPR", field="title").build()
        """
        if not term or not term.strip():
            context = {"term": term}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        # Escape term if it contains special characters
        escaped_term = self._escape_term(term)

        if field:
            # Get the API field name (uppercase)
            api_field = self._get_api_field_name(field)
            self._parts.append(f"{api_field}:{escaped_term}")
        else:
            self._parts.append(escaped_term)

        self._last_operator = None
        return self

    def date_range(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> QueryBuilder:
        """
        Add a publication date range constraint.

        Parameters
        ----------
        start_year : int, optional
            Start year (inclusive)
        end_year : int, optional
            End year (inclusive)
        start_date : str, optional
            Start date in YYYY-MM-DD format (more precise than year)
        end_date : str, optional
            End date in YYYY-MM-DD format (more precise than year)

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.date_range(start_year=2020, end_year=2023).build()
        >>> query = qb.date_range(start_date="2020-01-01", end_date="2023-12-31").build()

        Raises
        ------
        QueryBuilderError
            If date format is invalid or date range is invalid
        """
        # Use dates if provided, otherwise fall back to years
        if start_date or end_date:
            self._add_date_range(start_date, end_date)
        elif start_year or end_year:
            self._add_year_range(start_year, end_year)

        self._last_operator = None
        return self

    def _add_date_range(self, start_date: str | None, end_date: str | None) -> None:
        """Add date range using date strings."""
        start = self._validate_date(start_date) if start_date else None
        end = self._validate_date(end_date) if end_date else None

        if start and end:
            self._parts.append(f"(PUB_YEAR:[{start} TO {end}])")
        elif start:
            self._parts.append(f"(PUB_YEAR:[{start} TO *])")
        elif end:
            self._parts.append(f"(PUB_YEAR:[* TO {end}])")

    def _add_year_range(self, start_year: int | None, end_year: int | None) -> None:
        """Add date range using year integers."""
        self._validate_year(start_year, "start_year")
        self._validate_year(end_year, "end_year")
        self._validate_year_order(start_year, end_year)

        range_query = self._build_year_range_query(start_year, end_year)
        self._parts.append(range_query)

    def _validate_year(self, year: int | None, field_name: str) -> None:
        """Validate a single year value."""
        if year is None:
            return

        current_year = datetime.now().year
        if year < MIN_VALID_YEAR or year > current_year + 1:
            context = {field_name: year}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)

    def _validate_year_order(self, start_year: int | None, end_year: int | None) -> None:
        """Validate that start year is not after end year."""
        if start_year and end_year and start_year > end_year:
            context = {"start_year": start_year, "end_year": end_year}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)

    def _build_year_range_query(self, start_year: int | None, end_year: int | None) -> str:
        """Build year range query string."""
        current_year = datetime.now().year
        if start_year and end_year:
            return f"(PUB_YEAR:[{start_year} TO {end_year}])"
        elif start_year:
            # Use current year instead of * for open-ended ranges
            return f"(PUB_YEAR:[{start_year} TO {current_year}])"
        elif end_year:
            return f"(PUB_YEAR:[{MIN_VALID_YEAR} TO {end_year}])"
        return ""

    def citation_count(
        self, min_count: int | None = None, max_count: int | None = None
    ) -> QueryBuilder:
        """
        Add a citation count filter.

        Parameters
        ----------
        min_count : int, optional
            Minimum citation count (inclusive)
        max_count : int, optional
            Maximum citation count (inclusive)

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.citation_count(min_count=10).build()
        >>> query = qb.citation_count(min_count=10, max_count=100).build()

        Raises
        ------
        QueryBuilderError
            If citation counts are invalid
        """
        self._validate_citation_count(min_count, "min_count")
        self._validate_citation_count(max_count, "max_count")
        self._validate_count_order(min_count, max_count)

        range_query = self._build_citation_range_query(min_count, max_count)
        self._parts.append(range_query)

        self._last_operator = None
        return self

    def _validate_citation_count(self, count: int | None, field_name: str) -> None:
        """Validate a single citation count value."""
        if count is not None and count < 0:
            context = {field_name: count}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)

    def _validate_count_order(self, min_count: int | None, max_count: int | None) -> None:
        """Validate that min count is not greater than max count."""
        if min_count is not None and max_count is not None and min_count > max_count:
            context = {"min_count": min_count, "max_count": max_count}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)

    def _build_citation_range_query(self, min_count: int | None, max_count: int | None) -> str:
        """Build citation count range query string."""
        if min_count is not None and max_count is not None:
            return f"(CITED:[{min_count} TO {max_count}])"
        elif min_count is not None:
            return f"(CITED:[{min_count} TO *])"
        elif max_count is not None:
            return f"(CITED:[* TO {max_count}])"
        return ""

    def pmcid(self, pmcid: str) -> QueryBuilder:
        """
        Search by PMC ID.

        Parameters
        ----------
        pmcid : str
            PMC ID (with or without "PMC" prefix)

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.pmcid("PMC1234567").build()
        >>> query = qb.pmcid("1234567").build()  # Also accepts without prefix
        """
        if not pmcid or not pmcid.strip():
            context = {"pmcid": pmcid}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        # Add PMC prefix if not present
        clean_id = pmcid.strip()
        if not clean_id.upper().startswith("PMC"):
            clean_id = f"PMC{clean_id}"

        self._parts.append(f"PMCID:{clean_id}")
        self._last_operator = None
        return self

    def source(self, source: str) -> QueryBuilder:
        """
        Search by data source.

        Parameters
        ----------
        source : str
            Data source code (e.g., "MED", "PMC", "AGR")

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.source("MED").build()
        """
        if not source or not source.strip():
            context = {"source": source}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        self._parts.append(f"SRC:{source.strip().upper()}")
        self._last_operator = None
        return self

    def accession_type(self, accession_type: str) -> QueryBuilder:
        """
        Search by accession type.

        Note: accession_type is lowercased automatically.

        Convenience wrapper for `field("accession_type", ...)`.

        Parameters
        ----------
        accession_type : str
            Accession type (e.g., "arrayexpress", "ensembl", "pdb")

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.accession_type("pdb").build()
        """
        if not accession_type or not accession_type.strip():
            context = {"accession_type": accession_type}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        # Special handling: accession_type needs lowercasing
        value = accession_type.strip().lower()
        self._parts.append(f"ACCESSION_TYPE:{value}")
        self._last_operator = None
        return self

    def cites(self, article_id: str, source: str = "med") -> QueryBuilder:
        """
        Search for publications that cite a specific article.

        Parameters
        ----------
        article_id : str
            Article ID to find citations for
        source : str, optional
            Data source (default: "med")

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.cites("8521067", "med").build()
        """
        if not article_id or not article_id.strip():
            context = {"article_id": article_id}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        self._parts.append(f"CITES:{article_id}_{source.lower()}")
        self._last_operator = None
        return self

    def and_(self) -> QueryBuilder:
        """
        Add an AND operator between query parts.

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.keyword("cancer").and_().keyword("treatment").build()

        Raises
        ------
        QueryBuilderError
            If AND is used incorrectly (e.g., at the beginning or consecutively)
        """
        if not self._parts:
            context = {"operator": "AND"}
            raise QueryBuilderError(ErrorCodes.QUERY003, context)

        if self._last_operator is not None:
            context = {"operator": "AND", "previous": self._last_operator}
            raise QueryBuilderError(ErrorCodes.QUERY003, context)

        self._parts.append("AND")
        self._last_operator = "AND"
        return self

    def or_(self) -> QueryBuilder:
        """
        Add an OR operator between query parts.

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.keyword("cancer").or_().keyword("tumor").build()

        Raises
        ------
        QueryBuilderError
            If OR is used incorrectly
        """
        if not self._parts:
            context = {"operator": "OR"}
            raise QueryBuilderError(ErrorCodes.QUERY003, context)

        if self._last_operator is not None:
            context = {"operator": "OR", "previous": self._last_operator}
            raise QueryBuilderError(ErrorCodes.QUERY003, context)

        self._parts.append("OR")
        self._last_operator = "OR"
        return self

    def not_(self) -> QueryBuilder:
        """
        Add a NOT operator before the next query part.

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.keyword("cancer").and_().not_().keyword("review").build()

        Raises
        ------
        QueryBuilderError
            If NOT is used incorrectly
        """
        if not self._parts:
            context = {"operator": "NOT"}
            raise QueryBuilderError(ErrorCodes.QUERY003, context)

        if self._last_operator is not None and self._last_operator != "AND":
            context = {"operator": "NOT", "previous": self._last_operator}
            raise QueryBuilderError(ErrorCodes.QUERY003, context)

        self._parts.append("NOT")
        self._last_operator = "NOT"
        return self

    def group(self, builder: QueryBuilder) -> QueryBuilder:
        """
        Add a grouped sub-query (wrapped in parentheses).

        Parameters
        ----------
        builder : QueryBuilder
            Another QueryBuilder instance to use as a sub-query

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb1 = QueryBuilder(validate=False)
        >>> sub = qb1.keyword("cancer").or_().keyword("tumor")
        >>> qb2 = QueryBuilder(validate=False)
        >>> query = qb2.group(sub).and_().author("Smith J").build()
        """
        if not builder._parts:
            context = {"error": "Empty sub-query"}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        sub_query = builder.build(validate=False)
        self._parts.append(f"({sub_query})")
        self._last_operator = None
        return self

    def raw(self, query_string: str) -> QueryBuilder:
        """
        Add a raw query string directly.

        Use this for complex queries or syntax not directly supported by the builder.

        Parameters
        ----------
        query_string : str
            Raw query string to add

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.raw("(cancer OR tumor) AND treatment").build()

        Warnings
        --------
        This bypasses type safety and may create invalid queries.
        """
        if not query_string or not query_string.strip():
            context = {"query_string": query_string}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        self._parts.append(query_string.strip())
        self._last_operator = None
        return self

    def build(self, validate: bool = True) -> str:
        """
        Build and return the final query string.

        Parameters
        ----------
        validate : bool, optional
            Whether to validate the query (default: True).
            Uses search-query package if available.

        Returns
        -------
        str
            The constructed query string

        Raises
        ------
        QueryBuilderError
            If the query is empty or ends with an operator
            If validation fails (when validate=True)

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.keyword("cancer").and_().author("Smith J").build()
        """
        self._validate_query_parts()
        query = " ".join(self._parts)

        if validate and self._validate and SEARCH_QUERY_AVAILABLE:
            query = self._validate_and_clean_query(query)

        return query

    def _validate_query_parts(self) -> None:
        """Validate that query has parts and doesn't end with an operator."""
        if not self._parts:
            context = {"error": "Empty query"}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        if self._last_operator is not None:
            context = {"operator": self._last_operator}
            raise QueryBuilderError(ErrorCodes.QUERY003, context)

    def _validate_and_clean_query(self, query: str) -> str:
        """Validate query syntax using search-query package and return cleaned version."""
        try:
            # Try to parse with search-query to validate syntax
            # Note: Europe PMC syntax may differ from PubMed, so we're lenient here
            parsed = parse(query, platform="pubmed")
            # If parse succeeds, the query is at least syntactically valid
            if parsed:
                # Get cleaned version if available
                cleaned: str = str(parsed.to_string())
                if cleaned:
                    return cleaned
        except Exception as e:
            # If validation fails, provide helpful error message
            context = {"query": query, "error": str(e)}
            raise QueryBuilderError(ErrorCodes.QUERY004, context) from e

        return query

    def _escape_term(self, term: str) -> str:
        """
        Escape special characters in search terms.

        Parameters
        ----------
        term : str
            The term to escape

        Returns
        -------
        str
            Escaped term (quoted if necessary)
        """
        term = term.strip()

        # If term contains spaces or special chars, wrap in quotes
        if any(char in term for char in SPECIAL_QUERY_CHARS):
            # Escape internal quotes
            term = term.replace('"', '\\"')
            return f'"{term}"'

        return term

    def _validate_date(self, date_str: str) -> str:
        """
        Validate and normalize a date string.

        Parameters
        ----------
        date_str : str
            Date string in YYYY-MM-DD format

        Returns
        -------
        str
            Validated date string

        Raises
        ------
        QueryBuilderError
            If date format is invalid
        """
        try:
            # Parse the date to validate format
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError as e:
            context = {"date": date_str, "error": str(e)}
            raise QueryBuilderError(ErrorCodes.QUERY002, context) from e

    def __repr__(self) -> str:
        """Return string representation of the query builder."""
        parts_str = " ".join(self._parts) if self._parts else "<empty>"
        return f"QueryBuilder(parts={parts_str!r})"

    def field(
        self, field_name: FieldType, value: str | int | bool, escape: bool = True
    ) -> QueryBuilder:
        """
        Generic field search method using FIELD_METADATA.

        This is a flexible method that can be used for any field defined in FIELD_METADATA.
        For convenience, specific methods like author(), journal(), etc. are also available.

        Parameters
        ----------
        field_name : FieldType
            The field to search (e.g., "author", "title", "disease")
        value : str, int, or bool
            The search value. For boolean fields, True='y', False='n'
        escape : bool, optional
            Whether to escape the value (default: True)

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.field("author", "Smith J").build()
        >>> query = qb.field("open_access", True).build()
        >>> query = qb.field("disease", "cancer").build()

        Raises
        ------
        QueryBuilderError
            If field_name is not valid or value is empty
        ValueError
            If field_name is not in FIELD_METADATA
        """
        self._validate_field_name(field_name)
        api_name = self._get_api_field_name(field_name)
        query_part = self._format_field_value(field_name, api_name, value, escape)

        self._parts.append(query_part)
        self._last_operator = None
        return self

    def _validate_field_name(self, field_name: FieldType) -> None:
        """Validate that field name is not empty."""
        if not field_name:
            context = {"action": "field_search", "field": field_name}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

    def _get_api_field_name(self, field_name: FieldType) -> str:
        """Get API field name from FIELD_METADATA."""
        field_lower = field_name.lower()
        if field_lower not in FIELD_METADATA:
            raise ValueError(f"Unknown field: {field_name}")

        api_name, _ = FIELD_METADATA[field_lower]
        return api_name

    def _format_field_value(
        self, field_name: FieldType, api_name: str, value: str | int | bool, escape: bool
    ) -> str:
        """Format field value into query part based on type."""
        if isinstance(value, bool):
            return self._format_boolean_field(api_name, value)
        elif isinstance(value, str | int):
            return self._format_string_or_int_field(field_name, api_name, value, escape)
        else:
            context = {
                "action": "field_search",
                "field": field_name,
                "value_type": type(value).__name__,
            }
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

    def _format_boolean_field(self, api_name: str, value: bool) -> str:
        """Format boolean field value (True='y', False='n')."""
        str_value = "y" if value else "n"
        return f"{api_name}:{str_value}"

    def _format_string_or_int_field(
        self, field_name: FieldType, api_name: str, value: str | int, escape: bool
    ) -> str:
        """Format string or integer field value."""
        if isinstance(value, str) and not value.strip():
            context = {
                "action": "field_search",
                "field": field_name,
                "value": value,
            }
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        str_value = str(value).strip()

        if escape and isinstance(value, str):
            str_value = self._escape_term(str_value)

        return f"{api_name}:{str_value}"


# Helper functions for field validation


def get_available_fields(api_url: str | None = None) -> list[str]:
    """
    Fetch the list of available search fields from Europe PMC API.

    Uses BaseAPIClient for robust HTTP requests with retries and proper error handling.

    Parameters
    ----------
    api_url : str, optional
        Custom API URL to fetch fields from.
        Default: https://www.ebi.ac.uk/europepmc/webservices/rest/fields?format=json

    Returns
    -------
    list[str]
        List of available field names (uppercase, as returned by API)

    Examples
    --------
    >>> fields = get_available_fields()
    >>> print(f"Available fields: {len(fields)}")
    >>> print("TITLE" in fields)

    Raises
    ------
    APIClientError
        If API request fails or returns invalid data
    """
    from pyeuropepmc.base import BaseAPIClient
    from pyeuropepmc.exceptions import APIClientError

    url = api_url or "https://www.ebi.ac.uk/europepmc/webservices/rest/fields?format=json"
    logger.debug("Fetching available fields from: %s", url)

    # Use BaseAPIClient for robust API requests
    client = BaseAPIClient()
    try:
        # Extract endpoint from full URL
        if url.startswith(client.BASE_URL):
            endpoint = url[len(client.BASE_URL) :]
            logger.debug("Using BaseAPIClient endpoint: %s", endpoint)
        else:
            # For custom URLs, we'll use requests directly but with similar error handling
            logger.debug("Using custom URL with requests library")
            import requests

            try:
                response = requests.get(url, timeout=client.DEFAULT_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                field_count = len(data.get("searchTermList", {}).get("searchTerms", []))
                logger.info("Successfully fetched %d fields from API", field_count)
                return _extract_field_names(data)
            except requests.exceptions.RequestException as e:
                logger.error("Failed to fetch fields from custom URL %s: %s", url, str(e))
                context = {"url": url, "error": str(e)}
                raise APIClientError(ErrorCodes.NET001, context) from e

        # Use BaseAPIClient's robust _get method
        try:
            response = client._get(endpoint, params={"format": "json"})
            data = response.json()
            field_count = len(data.get("searchTermList", {}).get("searchTerms", []))
            logger.info("Successfully fetched %d fields from API", field_count)
            return _extract_field_names(data)
        except Exception as e:
            logger.error("Failed to fetch fields from API: %s", str(e))
            raise
    finally:
        client.close()
        logger.debug("BaseAPIClient connection closed")


def _extract_field_names(data: dict[str, Any]) -> list[str]:
    """
    Extract field names from API response.

    Parameters
    ----------
    data : dict
        JSON response from Europe PMC fields API

    Returns
    -------
    list[str]
        Sorted list of field names

    Raises
    ------
    APIClientError
        If response structure is invalid
    """
    from pyeuropepmc.error_codes import ErrorCodes
    from pyeuropepmc.exceptions import APIClientError

    try:
        terms = data.get("searchTermList", {}).get("searchTerms", [])
        if not terms:
            logger.error(
                "No search terms found in API response. Available keys: %s", list(data.keys())
            )
            context: dict[str, Any] = {"data_keys": list(data.keys())}
            raise APIClientError(ErrorCodes.PARSE001, context)

        fields = [term["term"] for term in terms]
        logger.debug("Extracted %d field names from API response", len(fields))
        return sorted(fields)
    except (KeyError, ValueError, TypeError) as e:
        logger.error("Failed to extract field names from API response: %s", str(e))
        context_err: dict[str, Any] = {
            "error": str(e),
            "data_structure": str(type(data)),
        }
        raise APIClientError(ErrorCodes.PARSE001, context_err) from e


def get_field_info(field: str) -> tuple[str, str]:
    """
    Get API field name and description for a given field.

    Parameters
    ----------
    field : str
        Field name (can be lowercase alias or uppercase API name)

    Returns
    -------
    tuple[str, str]
        Tuple of (API_NAME, description)

    Raises
    ------
    ValueError
        If field is not found in FIELD_METADATA

    Examples
    --------
    >>> api_name, desc = get_field_info("author")
    >>> print(f"{api_name}: {desc}")
    AUTH: Author name (full or abbreviated form)
    """
    field_lower = field.lower()
    if field_lower in FIELD_METADATA:
        return FIELD_METADATA[field_lower]
    raise ValueError(f"Unknown field: {field}")


def _print_validation_report(
    result: dict[str, Any],
) -> None:
    """Log detailed validation report (helper for validate_field_coverage)."""
    _print_header(result)
    _print_missing_fields(result)
    _print_extra_fields(result)
    _print_status(result)


def _print_header(result: dict[str, Any]) -> None:
    """Log validation report header."""
    logger.info("=" * 70)
    logger.info("Europe PMC Field Coverage Validation")
    logger.info("=" * 70)
    logger.info("")
    logger.info("API Fields: %d", result["total_api_fields"])
    logger.info("Defined Fields: %d", result["total_defined_fields"])
    logger.info("Coverage: %.2f%%", result["coverage_percent"])
    logger.info("Up to date: %s", result["up_to_date"])


def _print_missing_fields(result: dict[str, Any]) -> None:
    """Log missing fields section."""
    if not result["missing_in_code"]:
        return

    logger.warning("⚠️  Missing in code (%d fields):", len(result["missing_in_code"]))
    for field in sorted(result["missing_in_code"]):
        logger.warning("  - %s", field)


def _print_extra_fields(result: dict[str, Any]) -> None:
    """Log extra fields section."""
    if not result["extra_in_code"]:
        return

    logger.info("")
    logger.info("📝 Extra in code (%d fields):", len(result["extra_in_code"]))
    logger.info("   (These may be deprecated or documented but not in API)")
    for field in sorted(result["extra_in_code"]):
        field_info = _find_field_info(field)
        logger.info("%s", field_info)


def _find_field_info(field: str) -> str:
    """Find and format field info from FIELD_METADATA."""
    for field_name, (api_name, description) in FIELD_METADATA.items():
        if api_name == field:
            return f"  - {field:20} ({field_name}) - {description}"
    return f"  - {field}"


def _print_status(result: dict[str, Any]) -> None:
    """Log final status message."""
    logger.info("")
    if result["up_to_date"]:
        logger.info("✅ All API fields are covered!")
    else:
        logger.error(
            "❌ %d field(s) need to be added to FIELD_METADATA", len(result["missing_in_code"])
        )
    logger.info("=" * 70)


def validate_field_coverage(verbose: bool = False) -> dict[str, Any]:
    """
    Check if QueryBuilder FIELD_METADATA covers all fields from the Europe PMC API.

    This function fetches the current fields from the API and compares them
    with the fields defined in the FIELD_METADATA dictionary. Uses BaseAPIClient
    for robust API requests with retries and proper error handling.

    Parameters
    ----------
    verbose : bool, optional
        If True, log detailed comparison (default: False)

    Returns
    -------
    dict[str, Any]
        Dictionary with validation results containing:
        - 'api_fields': List of fields from API
        - 'defined_fields': List of fields in FIELD_METADATA
        - 'missing_in_code': Fields in API but not in FIELD_METADATA
        - 'extra_in_code': Fields in FIELD_METADATA but not in API
        - 'coverage_percent': Percentage of API fields covered
        - 'up_to_date': True if all API fields are in FIELD_METADATA

    Examples
    --------
    >>> result = validate_field_coverage(verbose=True)
    >>> if not result['up_to_date']:
    ...     print(f"Missing fields: {result['missing_in_code']}")

    Raises
    ------
    APIClientError
        If API request fails or returns invalid data
    """
    logger.debug("Starting field coverage validation")

    try:
        # Get fields from API
        api_fields = set(get_available_fields())
        logger.debug("Retrieved %d fields from API", len(api_fields))

        # Get API field names from FIELD_METADATA (uppercase API names)
        # We need to extract the uppercase API names from the tuples
        defined_api_names = {api_name for api_name, _ in FIELD_METADATA.values()}
        logger.debug("Found %d fields defined in FIELD_METADATA", len(defined_api_names))

        # Compare
        missing_in_code = api_fields - defined_api_names
        extra_in_code = defined_api_names - api_fields

        if missing_in_code:
            logger.warning("Found %d fields missing in code", len(missing_in_code))
        if extra_in_code:
            logger.info("Found %d extra fields in code (may be deprecated)", len(extra_in_code))

        # Calculate coverage
        coverage = (
            (len(api_fields) - len(missing_in_code)) / len(api_fields) * 100 if api_fields else 0.0
        )

        result = {
            "api_fields": sorted(api_fields),
            "defined_fields": sorted(defined_api_names),
            "missing_in_code": sorted(missing_in_code),
            "extra_in_code": sorted(extra_in_code),
            "coverage_percent": round(coverage, 2),
            "up_to_date": len(missing_in_code) == 0,
            "total_api_fields": len(api_fields),
            "total_defined_fields": len(defined_api_names),
        }

        logger.info(
            "Field coverage validation complete: %.2f%% coverage, up_to_date=%s",
            coverage,
            result["up_to_date"],
        )

        if verbose:
            _print_validation_report(result)

        return result
    except Exception as e:
        logger.error("Field coverage validation failed: %s", str(e))
        raise
