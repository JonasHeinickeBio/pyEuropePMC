"""
Unit tests for the QueryBuilder class.

Tests cover:
- Basic query construction with keywords
- Field-specific helpers (author, journal, date range, MeSH terms, etc.)
- Logical operators (AND, OR, NOT)
- Query validation and error handling
- Edge cases and validation
"""

import pytest

from pyeuropepmc.exceptions import QueryBuilderError
from pyeuropepmc.query_builder import QueryBuilder


class TestQueryBuilderBasics:
    """Test basic query builder functionality."""

    def test_simple_keyword_query(self) -> None:
        """Test building a simple keyword query."""
        qb = QueryBuilder(validate=False)
        query = qb.keyword("cancer").build()
        assert query == "cancer"

    def test_keyword_with_field(self) -> None:
        """Test keyword search with specific field."""
        qb = QueryBuilder(validate=False)
        query = qb.keyword("CRISPR", field="title").build()
        assert query == "CRISPR:TITLE"

    def test_quoted_keyword_with_spaces(self) -> None:
        """Test that keywords with spaces are properly quoted."""
        qb = QueryBuilder(validate=False)
        query = qb.keyword("gene editing", field="abstract").build()
        assert '"gene editing":ABSTRACT' in query

    def test_empty_query_raises_error(self) -> None:
        """Test that building an empty query raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.build()

    def test_empty_keyword_raises_error(self) -> None:
        """Test that empty keyword raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.keyword("")

    def test_repr(self) -> None:
        """Test string representation of QueryBuilder."""
        qb = QueryBuilder(validate=False)
        qb.keyword("cancer")
        repr_str = repr(qb)
        assert "QueryBuilder" in repr_str
        assert "cancer" in repr_str


class TestFieldSpecificHelpers:
    """Test field-specific query helper methods."""

    def test_author_search(self) -> None:
        """Test author search helper."""
        qb = QueryBuilder(validate=False)
        query = qb.author("Smith J").build()
        assert "Smith J:AUTH" in query or '"Smith J":AUTH' in query

    def test_journal_search(self) -> None:
        """Test journal search helper."""
        qb = QueryBuilder(validate=False)
        query = qb.journal("Nature").build()
        assert query == "Nature:JOURNAL"

    def test_mesh_term_search(self) -> None:
        """Test MeSH term search helper."""
        qb = QueryBuilder(validate=False)
        query = qb.mesh_term("Neoplasms").build()
        assert query == "Neoplasms:MESH"

    def test_empty_author_raises_error(self) -> None:
        """Test that empty author raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.author("")

    def test_empty_journal_raises_error(self) -> None:
        """Test that empty journal raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.journal("")

    def test_empty_mesh_raises_error(self) -> None:
        """Test that empty MeSH term raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.mesh_term("")


class TestDateRangeFilters:
    """Test date range filtering functionality."""

    def test_date_range_with_years(self) -> None:
        """Test date range with start and end years."""
        qb = QueryBuilder(validate=False)
        query = qb.date_range(start_year=2020, end_year=2023).build()
        assert "PUB_YEAR:[2020 TO 2023]" in query

    def test_date_range_start_year_only(self) -> None:
        """Test date range with only start year."""
        qb = QueryBuilder(validate=False)
        query = qb.date_range(start_year=2020).build()
        assert "PUB_YEAR:[2020 TO *]" in query

    def test_date_range_end_year_only(self) -> None:
        """Test date range with only end year."""
        qb = QueryBuilder(validate=False)
        query = qb.date_range(end_year=2023).build()
        assert "PUB_YEAR:[* TO 2023]" in query

    def test_date_range_with_dates(self) -> None:
        """Test date range with specific dates."""
        qb = QueryBuilder(validate=False)
        query = qb.date_range(start_date="2020-01-01", end_date="2023-12-31").build()
        assert "PUB_YEAR:[2020-01-01 TO 2023-12-31]" in query

    def test_invalid_start_year_raises_error(self) -> None:
        """Test that invalid start year raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.date_range(start_year=999)

    def test_invalid_end_year_raises_error(self) -> None:
        """Test that invalid end year raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.date_range(end_year=3000)

    def test_reversed_year_range_raises_error(self) -> None:
        """Test that reversed year range raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.date_range(start_year=2023, end_year=2020)

    def test_invalid_date_format_raises_error(self) -> None:
        """Test that invalid date format raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.date_range(start_date="2020/01/01")


class TestCitationCountFilters:
    """Test citation count filtering functionality."""

    def test_citation_count_min_only(self) -> None:
        """Test citation count with minimum only."""
        qb = QueryBuilder(validate=False)
        query = qb.citation_count(min_count=10).build()
        assert "CITED:[10 TO *]" in query

    def test_citation_count_max_only(self) -> None:
        """Test citation count with maximum only."""
        qb = QueryBuilder(validate=False)
        query = qb.citation_count(max_count=100).build()
        assert "CITED:[* TO 100]" in query

    def test_citation_count_range(self) -> None:
        """Test citation count with both min and max."""
        qb = QueryBuilder(validate=False)
        query = qb.citation_count(min_count=10, max_count=100).build()
        assert "CITED:[10 TO 100]" in query

    def test_negative_citation_count_raises_error(self) -> None:
        """Test that negative citation count raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.citation_count(min_count=-1)

    def test_reversed_citation_range_raises_error(self) -> None:
        """Test that reversed citation range raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.citation_count(min_count=100, max_count=10)


class TestBooleanFilters:
    """Test boolean filter helpers."""

    def test_open_access_true(self) -> None:
        """Test open access filter set to true."""
        qb = QueryBuilder(validate=False)
        query = qb.open_access(True).build()
        assert query == "OPEN_ACCESS:y"

    def test_open_access_false(self) -> None:
        """Test open access filter set to false."""
        qb = QueryBuilder(validate=False)
        query = qb.open_access(False).build()
        assert query == "OPEN_ACCESS:n"

    def test_has_pdf(self) -> None:
        """Test has PDF filter."""
        qb = QueryBuilder(validate=False)
        query = qb.has_pdf(True).build()
        assert query == "HAS_PDF:y"

    def test_has_full_text(self) -> None:
        """Test has full text filter."""
        qb = QueryBuilder(validate=False)
        query = qb.has_full_text(True).build()
        assert query == "HAS_TEXT:y"


class TestIdentifierSearch:
    """Test identifier-based search methods."""

    def test_pmcid_with_prefix(self) -> None:
        """Test PMCID search with PMC prefix."""
        qb = QueryBuilder(validate=False)
        query = qb.pmcid("PMC1234567").build()
        assert query == "PMCID:PMC1234567"

    def test_pmcid_without_prefix(self) -> None:
        """Test PMCID search without PMC prefix (should add it)."""
        qb = QueryBuilder(validate=False)
        query = qb.pmcid("1234567").build()
        assert query == "PMCID:PMC1234567"

    def test_pmid_string(self) -> None:
        """Test PMID search with string."""
        qb = QueryBuilder(validate=False)
        query = qb.pmid("12345678").build()
        assert query == "PMID:12345678"

    def test_pmid_int(self) -> None:
        """Test PMID search with integer."""
        qb = QueryBuilder(validate=False)
        query = qb.pmid(12345678).build()
        assert query == "PMID:12345678"

    def test_doi_search(self) -> None:
        """Test DOI search."""
        qb = QueryBuilder(validate=False)
        query = qb.doi("10.1234/example.2023.001").build()
        assert query == "DOI:10.1234/example.2023.001"

    def test_empty_pmcid_raises_error(self) -> None:
        """Test that empty PMCID raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.pmcid("")

    def test_empty_doi_raises_error(self) -> None:
        """Test that empty DOI raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.doi("")


class TestLogicalOperators:
    """Test logical operator functionality."""

    def test_and_operator(self) -> None:
        """Test AND operator between terms."""
        qb = QueryBuilder(validate=False)
        query = qb.keyword("cancer").and_().keyword("treatment").build()
        assert query == "cancer AND treatment"

    def test_or_operator(self) -> None:
        """Test OR operator between terms."""
        qb = QueryBuilder(validate=False)
        query = qb.keyword("cancer").or_().keyword("tumor").build()
        assert query == "cancer OR tumor"

    def test_not_operator(self) -> None:
        """Test NOT operator."""
        qb = QueryBuilder(validate=False)
        query = qb.keyword("cancer").and_().not_().keyword("review").build()
        assert query == "cancer AND NOT review"

    def test_complex_boolean_query(self) -> None:
        """Test complex query with multiple operators."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.keyword("cancer")
            .or_()
            .keyword("tumor")
            .and_()
            .keyword("treatment")
            .build()
        )
        assert "cancer OR tumor AND treatment" in query

    def test_and_at_start_raises_error(self) -> None:
        """Test that AND at start raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.and_()

    def test_or_at_start_raises_error(self) -> None:
        """Test that OR at start raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.or_()

    def test_not_at_start_raises_error(self) -> None:
        """Test that NOT at start raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.not_()

    def test_consecutive_operators_raise_error(self) -> None:
        """Test that consecutive operators raise an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.keyword("cancer").and_().and_()

    def test_query_ending_with_operator_raises_error(self) -> None:
        """Test that query ending with operator raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.keyword("cancer").and_().build()


class TestGrouping:
    """Test query grouping functionality."""

    def test_group_sub_query(self) -> None:
        """Test grouping a sub-query."""
        sub = QueryBuilder(validate=False).keyword("cancer").or_().keyword("tumor")
        qb = QueryBuilder(validate=False)
        query = qb.group(sub).and_().author("Smith J").build()
        assert "(" in query
        assert ")" in query
        assert "cancer OR tumor" in query
        assert "Smith J:AUTH" in query or '"Smith J":AUTH' in query

    def test_empty_sub_query_raises_error(self) -> None:
        """Test that empty sub-query raises an error."""
        sub = QueryBuilder(validate=False)
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.group(sub)


class TestRawQueries:
    """Test raw query string functionality."""

    def test_raw_query_string(self) -> None:
        """Test adding raw query string."""
        qb = QueryBuilder(validate=False)
        query = qb.raw("(cancer OR tumor) AND treatment").build()
        assert query == "(cancer OR tumor) AND treatment"

    def test_empty_raw_query_raises_error(self) -> None:
        """Test that empty raw query raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.raw("")


class TestMethodChaining:
    """Test method chaining fluent API."""

    def test_complex_chained_query(self) -> None:
        """Test building a complex query with method chaining."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.author("Smith J")
            .and_()
            .keyword("CRISPR", field="title")
            .and_()
            .date_range(start_year=2020, end_year=2023)
            .and_()
            .open_access(True)
            .build()
        )

        # Check that all parts are present
        assert "Smith J" in query or '"Smith J"' in query
        assert "AUTH" in query
        assert "CRISPR" in query
        assert "TITLE" in query
        assert "2020" in query
        assert "2023" in query
        assert "OPEN_ACCESS:y" in query
        assert "AND" in query

    def test_chaining_returns_self(self) -> None:
        """Test that methods return self for chaining."""
        qb = QueryBuilder(validate=False)
        result = qb.keyword("cancer")
        assert result is qb

    def test_mixed_field_and_operator_chaining(self) -> None:
        """Test mixing field helpers and operators."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.journal("Nature")
            .and_()
            .mesh_term("Neoplasms")
            .or_()
            .mesh_term("Carcinoma")
            .build()
        )
        assert "Nature:JOURNAL" in query
        assert "Neoplasms:MESH" in query
        assert "Carcinoma:MESH" in query
        assert "AND" in query
        assert "OR" in query


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_search_recent_cancer_papers(self) -> None:
        """Test building query for recent cancer research papers."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.keyword("cancer", field="title")
            .and_()
            .date_range(start_year=2020)
            .and_()
            .open_access(True)
            .and_()
            .citation_count(min_count=5)
            .build()
        )

        assert "cancer:TITLE" in query
        assert "2020" in query
        assert "OPEN_ACCESS:y" in query
        assert "CITED:[5 TO *]" in query

    def test_search_by_multiple_authors(self) -> None:
        """Test searching for papers by multiple authors."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.author("Smith J")
            .or_()
            .author("Doe Jane")
            .and_()
            .keyword("genetics")
            .build()
        )

        assert "Smith J" in query or '"Smith J"' in query
        assert "Doe Jane" in query or '"Doe Jane"' in query
        assert "genetics" in query

    def test_search_mesh_terms_with_filters(self) -> None:
        """Test searching MeSH terms with additional filters."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.mesh_term("Neoplasms")
            .and_()
            .mesh_term("Drug Therapy")
            .and_()
            .has_full_text(True)
            .build()
        )

        assert "Neoplasms:MESH" in query
        assert "Drug Therapy:MESH" in query or '"Drug Therapy":MESH' in query
        assert "HAS_TEXT:y" in query

    def test_search_specific_journal_date_range(self) -> None:
        """Test searching specific journal within date range."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.journal("Nature")
            .and_()
            .date_range(start_year=2018, end_year=2023)
            .and_()
            .keyword("machine learning")
            .build()
        )

        assert "Nature:JOURNAL" in query
        assert "2018" in query
        assert "2023" in query
        assert "machine learning" in query or '"machine learning"' in query


# Integration test with search-query package (if available)
class TestValidation:
    """Test query validation functionality."""

    def test_validation_disabled_by_default_if_no_package(self) -> None:
        """Test that validation can be disabled even if package is available."""
        # This test will work whether or not search-query is installed
        qb = QueryBuilder(validate=True)
        # Should not raise even if search-query is not available
        query = qb.keyword("cancer").build(validate=False)
        assert query == "cancer"

    def test_validation_can_be_disabled(self) -> None:
        """Test that validation can be explicitly disabled."""
        qb = QueryBuilder(validate=False)
        query = qb.keyword("cancer").build(validate=False)
        assert query == "cancer"
