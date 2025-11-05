"""
Advanced Query Builder for Europe PMC searches.

This module provides a fluent API for building complex search queries with
type-safe field specifications, logical operators, and validation using the
CoLRev search-query package.

Example usage:
    >>> from pyeuropepmc import QueryBuilder
    >>> query = (QueryBuilder()
    ...     .author("Smith J")
    ...     .and_()
    ...     .keyword("cancer", field="title")
    ...     .and_()
    ...     .date_range(start_year=2020, end_year=2023)
    ...     .build())
    >>> client.search(query)
"""

from __future__ import annotations

from datetime import datetime
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

__all__ = ["QueryBuilder", "QueryBuilderError"]

# Constants
MIN_VALID_YEAR = 1000  # Minimum valid publication year
SPECIAL_QUERY_CHARS = [" ", ":", "(", ")", "[", "]", "{", "}", "AND", "OR", "NOT"]


# Europe PMC searchable fields
FieldType = Literal[
    "title",
    "abstract",
    "auth_man",  # author manuscript
    "author",
    "journal",
    "mesh",  # MeSH terms
    "grant_agency",
    "grant_id",
    "pub_type",
    "pub_year",
    "open_access",
    "has_pdf",
    "has_full_text",
    "citation_count",
    "pmcid",
    "pmid",
    "doi",
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
        ...     .author("Smith J")
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

    With MeSH terms:
        >>> qb = QueryBuilder()
        >>> query = (qb
        ...     .mesh_term("Neoplasms")
        ...     .and_()
        ...     .open_access(True)
        ...     .build())
    """

    def __init__(self, validate: bool = True) -> None:
        """
        Initialize a new QueryBuilder.

        Parameters
        ----------
        validate : bool, optional
            Whether to validate queries using search-query package (default: True).
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
            self._parts.append(f"{escaped_term}:{field.upper()}")
        else:
            self._parts.append(escaped_term)

        self._last_operator = None
        return self

    def author(self, author_name: str) -> QueryBuilder:
        """
        Add an author search constraint.

        Parameters
        ----------
        author_name : str
            Author name to search for (e.g., "Smith J", "Doe John")

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.author("Smith J").build()
        """
        if not author_name or not author_name.strip():
            context = {"author_name": author_name}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        escaped = self._escape_term(author_name)
        self._parts.append(f"{escaped}:AUTH")
        self._last_operator = None
        return self

    def journal(self, journal_name: str) -> QueryBuilder:
        """
        Add a journal name search constraint.

        Parameters
        ----------
        journal_name : str
            Journal name to search for

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.journal("Nature").build()
        """
        if not journal_name or not journal_name.strip():
            context = {"journal_name": journal_name}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        escaped = self._escape_term(journal_name)
        self._parts.append(f"{escaped}:JOURNAL")
        self._last_operator = None
        return self

    def mesh_term(self, mesh: str) -> QueryBuilder:
        """
        Add a MeSH (Medical Subject Heading) term search.

        Parameters
        ----------
        mesh : str
            MeSH term to search for

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.mesh_term("Neoplasms").build()
        """
        if not mesh or not mesh.strip():
            context = {"mesh_term": mesh}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        escaped = self._escape_term(mesh)
        self._parts.append(f"{escaped}:MESH")
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
        # Validate years
        current_year = datetime.now().year
        if start_year and (start_year < MIN_VALID_YEAR or start_year > current_year + 1):
            context = {"start_year": start_year}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)
        if end_year and (end_year < MIN_VALID_YEAR or end_year > current_year + 1):
            context = {"end_year": end_year}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)
        if start_year and end_year and start_year > end_year:
            context = {"start_year": start_year, "end_year": end_year}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)

        if start_year and end_year:
            self._parts.append(f"(PUB_YEAR:[{start_year} TO {end_year}])")
        elif start_year:
            self._parts.append(f"(PUB_YEAR:[{start_year} TO *])")
        elif end_year:
            self._parts.append(f"(PUB_YEAR:[* TO {end_year}])")

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
        if min_count is not None and min_count < 0:
            context = {"min_count": min_count}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)
        if max_count is not None and max_count < 0:
            context = {"max_count": max_count}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)
        if min_count is not None and max_count is not None and min_count > max_count:
            context = {"min_count": min_count, "max_count": max_count}
            raise QueryBuilderError(ErrorCodes.QUERY002, context)

        if min_count is not None and max_count is not None:
            self._parts.append(f"(CITED:[{min_count} TO {max_count}])")
        elif min_count is not None:
            self._parts.append(f"(CITED:[{min_count} TO *])")
        elif max_count is not None:
            self._parts.append(f"(CITED:[* TO {max_count}])")

        self._last_operator = None
        return self

    def open_access(self, is_open_access: bool = True) -> QueryBuilder:
        """
        Filter by open access status.

        Parameters
        ----------
        is_open_access : bool, optional
            True for open access only, False for non-open access (default: True)

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.open_access(True).build()
        """
        value = "y" if is_open_access else "n"
        self._parts.append(f"OPEN_ACCESS:{value}")
        self._last_operator = None
        return self

    def has_pdf(self, has_pdf: bool = True) -> QueryBuilder:
        """
        Filter by PDF availability.

        Parameters
        ----------
        has_pdf : bool, optional
            True for papers with PDF available (default: True)

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.has_pdf(True).build()
        """
        value = "y" if has_pdf else "n"
        self._parts.append(f"HAS_PDF:{value}")
        self._last_operator = None
        return self

    def has_full_text(self, has_text: bool = True) -> QueryBuilder:
        """
        Filter by full text availability.

        Parameters
        ----------
        has_text : bool, optional
            True for papers with full text available (default: True)

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.has_full_text(True).build()
        """
        value = "y" if has_text else "n"
        self._parts.append(f"HAS_TEXT:{value}")
        self._last_operator = None
        return self

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

    def pmid(self, pmid: str | int) -> QueryBuilder:
        """
        Search by PubMed ID.

        Parameters
        ----------
        pmid : str or int
            PubMed ID

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.pmid("12345678").build()
        >>> query = qb.pmid(12345678).build()
        """
        if not pmid:
            context = {"pmid": pmid}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        self._parts.append(f"PMID:{pmid}")
        self._last_operator = None
        return self

    def doi(self, doi: str) -> QueryBuilder:
        """
        Search by DOI.

        Parameters
        ----------
        doi : str
            Digital Object Identifier

        Returns
        -------
        QueryBuilder
            Self for method chaining

        Examples
        --------
        >>> qb = QueryBuilder()
        >>> query = qb.doi("10.1234/example.2023.001").build()
        """
        if not doi or not doi.strip():
            context = {"doi": doi}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        self._parts.append(f"DOI:{doi.strip()}")
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
        if not self._parts:
            context = {"error": "Empty query"}
            raise QueryBuilderError(ErrorCodes.QUERY001, context)

        if self._last_operator is not None:
            context = {"operator": self._last_operator}
            raise QueryBuilderError(ErrorCodes.QUERY003, context)

        query = " ".join(self._parts)

        # Validate if requested and available
        if validate and self._validate and SEARCH_QUERY_AVAILABLE:
            try:
                # Try to parse with search-query to validate syntax
                # Note: Europe PMC syntax may differ from PubMed, so we're lenient here
                parsed = parse(query, platform="pubmed")
                # If parse succeeds, the query is at least syntactically valid
                if parsed:
                    # Get cleaned version if available
                    cleaned = parsed.to_string()
                    if cleaned:
                        query = cleaned
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
