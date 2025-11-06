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
        assert query == "TITLE:CRISPR"

    def test_quoted_keyword_with_spaces(self) -> None:
        """Test that keywords with spaces are properly quoted."""
        qb = QueryBuilder(validate=False)
        query = qb.keyword("gene editing", field="abstract").build()
        assert 'ABSTRACT:"gene editing"' in query

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


class TestFieldMethod:
    """Test field-specific query helper methods."""

    def test_field_author(self) -> None:
        """Test field() with author."""
        qb = QueryBuilder(validate=False)
        query = qb.field("author", "Smith J").build()
        assert 'AUTH:"Smith J"' in query or "AUTH:Smith J" in query

    def test_field_journal(self) -> None:
        """Test field() with journal."""
        qb = QueryBuilder(validate=False)
        query = qb.field("journal", "Nature").build()
        assert query == "JOURNAL:Nature"

    def test_field_mesh(self) -> None:
        """Test field() with mesh."""
        qb = QueryBuilder(validate=False)
        query = qb.field("mesh", "Neoplasms").build()
        assert query == "MESH:Neoplasms"

    def test_field_empty_author_raises_error(self) -> None:
        """Test that empty author raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.field("author", "")

    def test_field_empty_journal_raises_error(self) -> None:
        """Test that empty journal raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.field("journal", "")

    def test_field_empty_mesh_raises_error(self) -> None:
        """Test that empty MeSH term raises an error."""
        qb = QueryBuilder(validate=False)
        with pytest.raises(QueryBuilderError):
            qb.field("mesh", "")


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
        # Uses current year (2025) instead of * for open-ended ranges
        assert "PUB_YEAR:[2020 TO 2025]" in query

    def test_date_range_end_year_only(self) -> None:
        """Test date range with only end year."""
        qb = QueryBuilder(validate=False)
        query = qb.date_range(end_year=2023).build()
        # Uses MIN_VALID_YEAR (1000) instead of * for start
        assert "PUB_YEAR:[1000 TO 2023]" in query

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
        query = qb.field("open_access", True).build()
        assert query == "OPEN_ACCESS:y"

    def test_open_access_false(self) -> None:
        """Test open access filter set to false."""
        qb = QueryBuilder(validate=False)
        query = qb.field("open_access", False).build()
        assert query == "OPEN_ACCESS:n"

    def test_has_pdf(self) -> None:
        """Test has PDF filter."""
        qb = QueryBuilder(validate=False)
        query = qb.field("has_pdf", True).build()
        assert query == "HAS_PDF:y"

    def test_has_full_text(self) -> None:
        """Test has full text filter."""
        qb = QueryBuilder(validate=False)
        query = qb.field("has_text", True).build()
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
        query = qb.field("pmid", "12345678").build()
        assert query == "PMID:12345678"

    def test_pmid_int(self) -> None:
        """Test PMID search with integer."""
        qb = QueryBuilder(validate=False)
        query = qb.field("pmid", 12345678).build()
        assert query == "PMID:12345678"

    def test_doi_search(self) -> None:
        """Test DOI search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("doi", "10.1234/example.2023.001").build()
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
            qb.field("doi", "")


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
        query = qb.group(sub).and_().field("author", "Smith J").build()
        assert "(" in query
        assert ")" in query
        assert "cancer OR tumor" in query
        assert 'AUTH:"Smith J"' in query or "AUTH:Smith J" in query

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
            qb.field("author", "Smith J")
            .and_()
            .keyword("CRISPR", field="title")
            .and_()
            .date_range(start_year=2020, end_year=2023)
            .and_()
            .field("open_access", True)
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
            qb.field("journal", "Nature")
            .and_()
            .field("mesh", "Neoplasms")
            .or_()
            .field("mesh", "Carcinoma")
            .build()
        )
        assert "JOURNAL:Nature" in query
        assert "MESH:Neoplasms" in query
        assert "MESH:Carcinoma" in query
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
            .field("open_access", True)
            .and_()
            .citation_count(min_count=5)
            .build()
        )

        assert "TITLE:cancer" in query
        assert "2020" in query
        assert "OPEN_ACCESS:y" in query
        assert "CITED:[5 TO *]" in query

    def test_search_by_multiple_authors(self) -> None:
        """Test searching for papers by multiple authors."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.field("author", "Smith J")
            .or_()
            .field("author", "Doe Jane")
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
            qb.field("mesh", "Neoplasms")
            .and_()
            .field("mesh", "Drug Therapy")
            .and_()
            .field("has_text", True)
            .build()
        )

        assert "MESH:Neoplasms" in query
        assert 'MESH:"Drug Therapy"' in query or "MESH:Drug Therapy" in query
        assert "HAS_TEXT:y" in query

    def test_search_specific_journal_date_range(self) -> None:
        """Test searching specific journal within date range."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.field("journal", "Nature")
            .and_()
            .date_range(start_year=2018, end_year=2023)
            .and_()
            .keyword("machine learning")
            .build()
        )

        assert "JOURNAL:Nature" in query
        assert "2018" in query
        assert "2023" in query
        assert "machine learning" in query or '"machine learning"' in query


class TestExtendedFieldMethods:
    """Test extended field-specific methods from Europe PMC documentation."""

    def test_ext_id_search(self) -> None:
        """Test external ID search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("ext_id", "10826746").build()
        assert query == "EXT_ID:10826746"

    def test_issn_search(self) -> None:
        """Test ISSN search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("issn", "0028-0836").build()
        assert query == "ISSN:0028-0836"

    def test_affiliation_search(self) -> None:
        """Test author affiliation search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("affiliation", "university of cambridge").build()
        assert "university of cambridge" in query
        assert "AFF" in query

    def test_grant_agency_search(self) -> None:
        """Test grant agency search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("grant_agency", "wellcome").build()
        assert "GRANT_AGENCY:wellcome" in query

    def test_grant_id_search(self) -> None:
        """Test grant ID search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("grant_id", "100229").build()
        assert query == "GRANT_ID:100229"

    def test_pub_type_search(self) -> None:
        """Test publication type search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("pub_type", "review").build()
        assert query == "PUB_TYPE:review"

    def test_language_search(self) -> None:
        """Test language search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("language", "eng").build()
        assert query == "LANG:eng"

    def test_source_search(self) -> None:
        """Test data source search."""
        qb = QueryBuilder(validate=False)
        query = qb.source("MED").build()
        assert query == "SRC:MED"

    def test_isbn_search(self) -> None:
        """Test ISBN search for books."""
        qb = QueryBuilder(validate=False)
        query = qb.field("isbn", "9780815340720").build()
        assert query == "ISBN:9780815340720"

    def test_disease_search(self) -> None:
        """Test disease term search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("disease", "cancer").build()
        assert query == "DISEASE:cancer"

    def test_gene_protein_search(self) -> None:
        """Test gene/protein search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("gene_protein", "TP53").build()
        assert query == "GENE_PROTEIN:TP53"

    def test_organism_search(self) -> None:
        """Test organism search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("organism", "homo sapiens").build()
        assert "homo sapiens" in query
        assert "ORGANISM" in query

    def test_accession_id_search(self) -> None:
        """Test accession ID search."""
        qb = QueryBuilder(validate=False)
        query = qb.field("accession_id", "A12360").build()
        assert query == "ACCESSION_ID:A12360"

    def test_accession_type_search(self) -> None:
        """Test accession type search."""
        qb = QueryBuilder(validate=False)
        query = qb.accession_type("pdb").build()
        assert query == "ACCESSION_TYPE:pdb"

    def test_cites_search(self) -> None:
        """Test citation search."""
        qb = QueryBuilder(validate=False)
        query = qb.cites("8521067", "med").build()
        assert query == "CITES:8521067_med"

    def test_has_abstract_filter(self) -> None:
        """Test abstract presence filter."""
        qb = QueryBuilder(validate=False)
        query = qb.field("has_abstract", True).build()
        assert query == "HAS_ABSTRACT:y"

    def test_has_references_filter(self) -> None:
        """Test reference list presence filter."""
        qb = QueryBuilder(validate=False)
        query = qb.field("has_reflist", True).build()
        assert query == "HAS_REFLIST:y"

    def test_has_supplementary_filter(self) -> None:
        """Test supplementary data presence filter."""
        qb = QueryBuilder(validate=False)
        query = qb.field("has_suppl", True).build()
        assert query == "HAS_SUPPL:y"

    def test_in_pmc_filter(self) -> None:
        """Test PMC availability filter."""
        qb = QueryBuilder(validate=False)
        query = qb.field("in_pmc", True).build()
        assert query == "IN_PMC:y"

    def test_in_epmc_filter(self) -> None:
        """Test Europe PMC availability filter."""
        qb = QueryBuilder(validate=False)
        query = qb.field("in_epmc", True).build()
        assert query == "IN_EPMC:y"

    def test_complex_query_with_extended_fields(self) -> None:
        """Test complex query combining multiple extended fields."""
        qb = QueryBuilder(validate=False)
        query = (
            qb.field("disease", "cancer")
            .and_()
            .field("gene_protein", "TP53")
            .and_()
            .field("organism", "homo sapiens")
            .and_()
            .field("open_access", True)
            .and_()
            .field("has_pdf", True)
            .build()
        )
        assert "DISEASE:cancer" in query
        assert "GENE_PROTEIN:TP53" in query
        assert "ORGANISM" in query
        assert "OPEN_ACCESS:y" in query
        assert "HAS_PDF:y" in query
        assert query.count("AND") == 4

    def test_empty_field_raises_errors(self) -> None:
        """Test that empty values raise errors for new methods."""
        qb = QueryBuilder(validate=False)

        with pytest.raises(QueryBuilderError):
            qb.field("ext_id", "")

        with pytest.raises(QueryBuilderError):
            qb.field("issn", "")

        with pytest.raises(QueryBuilderError):
            qb.field("affiliation", "")

        with pytest.raises(QueryBuilderError):
            qb.field("grant_agency", "")

        with pytest.raises(QueryBuilderError):
            qb.field("disease", "")


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


# Field validation tests
class TestFieldValidation:
    """Test field validation helper functions."""

    def test_get_available_fields(self) -> None:
        """Test fetching available fields from API."""
        pytest.importorskip("requests")
        from pyeuropepmc.query_builder import get_available_fields

        fields = get_available_fields()
        assert isinstance(fields, list)
        assert len(fields) > 0
        # API returns most fields in uppercase (except internal fields)
        assert "ABSTRACT" in fields
        assert "TITLE" in fields
        assert "AUTH" in fields
        # Check internal fields are lowercase
        assert "_version_" in fields
        assert "text_hl" in fields
        assert all(isinstance(f, str) for f in fields)

    def test_get_available_fields_requires_requests(self) -> None:
        """Test that get_available_fields requires requests library."""
        # This test checks if ImportError is raised when requests is not available
        # We can't easily test this without uninstalling requests,
        # so we just verify the function exists
        from pyeuropepmc.query_builder import get_available_fields

        assert callable(get_available_fields)

    def test_validate_field_coverage(self) -> None:
        """Test field coverage validation."""
        pytest.importorskip("requests")
        from pyeuropepmc.query_builder import validate_field_coverage

        result = validate_field_coverage(verbose=False)

        # Check result structure
        assert isinstance(result, dict)
        assert "api_fields" in result
        assert "defined_fields" in result
        assert "missing_in_code" in result
        assert "extra_in_code" in result
        assert "coverage_percent" in result
        assert "up_to_date" in result
        assert "total_api_fields" in result
        assert "total_defined_fields" in result

        # Check types
        assert isinstance(result["api_fields"], list)
        assert isinstance(result["defined_fields"], list)
        assert isinstance(result["missing_in_code"], list)
        assert isinstance(result["extra_in_code"], list)
        assert isinstance(result["coverage_percent"], (int, float))
        assert isinstance(result["up_to_date"], bool)
        assert isinstance(result["total_api_fields"], int)
        assert isinstance(result["total_defined_fields"], int)

        # Check values are reasonable
        assert result["total_api_fields"] > 0
        assert result["total_defined_fields"] > 0
        assert 0 <= result["coverage_percent"] <= 100
        # We should have 100% coverage of API fields
        assert result["coverage_percent"] == 100.0
        assert result["up_to_date"] is True

    def test_validate_field_coverage_verbose(self) -> None:
        """Test field coverage validation with verbose output."""
        pytest.importorskip("requests")
        from pyeuropepmc.query_builder import validate_field_coverage

        # Should not raise and should print output
        result = validate_field_coverage(verbose=True)
        assert result["up_to_date"] is True

    def test_field_type_includes_common_fields(self) -> None:
        """Test that FieldType includes commonly used fields."""
        import typing

        from pyeuropepmc.query_builder import FieldType

        field_type_args = typing.get_args(FieldType)
        fields = set(field_type_args)

        # Check for common fields
        common_fields = [
            "title",
            "abstract",
            "author",
            "auth",  # abbreviated
            "journal",
            "pmid",
            "pmcid",
            "doi",
            "open_access",
            "has_pdf",
            "pub_year",
        ]

        for field in common_fields:
            assert field in fields, f"Common field '{field}' not in FieldType"

    def test_field_type_includes_aliases(self) -> None:
        """Test that FieldType includes both full and abbreviated field names."""
        import typing

        from pyeuropepmc.query_builder import FieldType

        field_type_args = typing.get_args(FieldType)
        fields = set(field_type_args)

        # Check for both versions of aliased fields
        aliases = [
            ("author", "auth"),
            ("affiliation", "aff"),
            ("language", "lang"),
            ("keyword", "kw"),
            ("chemical", "chem"),
            ("source", "src"),
            ("editor", "ed"),
        ]

        for full, abbr in aliases:
            assert (
                full in fields or abbr in fields
            ), f"Neither '{full}' nor '{abbr}' in FieldType"
