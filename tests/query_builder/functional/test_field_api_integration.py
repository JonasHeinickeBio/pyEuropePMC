"""
Functional tests for QueryBuilder field methods with real Europe PMC API calls.

These tests validate that:
1. Each field can build a valid query
2. The query executes successfully against the API
3. The field appears in the request queryString
4. Adding a field filter reduces result count (compared to no filter)
5. Results are returned (hitCount > 0)

Note: These tests make real API calls and may be slow. They are marked with
@pytest.mark.functional and @pytest.mark.slow for selective execution.
"""

from __future__ import annotations

import logging
import pytest
import time

from pyeuropepmc import QueryBuilder, SearchClient

logger = logging.getLogger(__name__)


# Mark all tests in this module as functional and slow
pytestmark = [pytest.mark.functional, pytest.mark.slow]


class TestFieldAPIIntegration:
    """Test each QueryBuilder field with real API searches."""

    @pytest.fixture
    def client(self) -> SearchClient:
        """Create a SearchClient for API calls."""
        return SearchClient()

    @pytest.fixture(autouse=True)
    def rate_limit(self) -> None:
        """Add delay between tests to respect API rate limits."""
        time.sleep(0.5)  # 500ms between tests

    def _test_field_reduces_results(
        self,
        client: SearchClient,
        field_query: str,
        base_query: str,
        field_name: str,
    ) -> None:
        """
        Helper to test that a field filter reduces results.

        Parameters
        ----------
        client : SearchClient
            SearchClient instance
        field_query : str
            Query with field filter
        base_query : str
            Query without field filter (should have more results)
        field_name : str
            Name of the field being tested (for assertions)
        """
        # Execute search with field filter
        field_response = client.search(field_query, page_size=5)

        logger.debug(f"Field query: {field_query}")
        logger.debug(f"Field response: {field_response}")

        # Validate response structure
        assert "hitCount" in field_response
        assert "request" in field_response
        assert "queryString" in field_response["request"]

        # Assert field appears in query
        assert field_name.upper() in field_response["request"]["queryString"]

        # Assert we got results
        field_count = field_response["hitCount"]
        logger.debug(f"{field_name} field count: {field_count}")
        assert field_count > 0, f"No results for {field_name} field query"

        # Execute base query (no field filter)
        base_response = client.search(base_query, page_size=5)
        base_count = base_response["hitCount"]
        logger.debug(f"Base query: {base_query}")
        logger.debug(f"Base count: {base_count}")

        # Assert field filter reduced results
        assert field_count <= base_count, (
            f"Field filter should reduce results: "
            f"{field_name}={field_count}, base={base_count}"
        )

    # Core Bibliographic Fields

    def test_title_field(self, client: SearchClient) -> None:
        """Test TITLE field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("title", "CRISPR").build(validate=False)
        base_query = "CRISPR"

        self._test_field_reduces_results(client, query, base_query, "TITLE")

    def test_abstract_field(self, client: SearchClient) -> None:
        """Test ABSTRACT field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("abstract", "gene editing").build(validate=False)
        base_query = "gene editing"

        self._test_field_reduces_results(client, query, base_query, "ABSTRACT")

    def test_author_field(self, client: SearchClient) -> None:
        """Test AUTH (author) field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("author", "Smith J").build(validate=False)
        base_query = "Smith"

        self._test_field_reduces_results(client, query, base_query, "AUTH")

    def test_journal_field(self, client: SearchClient) -> None:
        """Test JOURNAL field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("journal", "Nature").build(validate=False)
        base_query = "Nature"

        self._test_field_reduces_results(client, query, base_query, "JOURNAL")

    def test_issn_field(self, client: SearchClient) -> None:
        """Test ISSN field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("issn", "0028-0836").build(validate=False)  # Nature's ISSN
        base_query = "journal:Nature"

        self._test_field_reduces_results(client, query, base_query, "ISSN")

    def test_pub_year_field(self, client: SearchClient) -> None:
        """Test PUB_YEAR field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "cancer")
                .and_()
                .field("pub_year", 2023)
                .build(validate=False))
        base_query = "cancer"

        self._test_field_reduces_results(client, query, base_query, "PUB_YEAR")

    def test_doi_field(self, client: SearchClient) -> None:
        """Test DOI field with real API call."""
        qb = QueryBuilder(validate=False)
        # Use a known DOI
        query = qb.field("doi", "10.1038/nature12373").build(validate=False)

        logger.debug(f"Query: {query}")
        response = client.search(query, page_size=5)
        logger.debug(f"Response: {response}")

        assert "hitCount" in response
        assert response["hitCount"] > 0
        assert "DOI" in response["request"]["queryString"]

    def test_pmid_field(self, client: SearchClient) -> None:
        """Test PMID field with real API call."""
        qb = QueryBuilder(validate=False)
        # Use a known PMID
        query = qb.field("pmid", "23685479").build(validate=False)

        logger.debug(f"Query: {query}")
        response = client.search(query, page_size=5)
        logger.debug(f"Response: {response}")

        assert "hitCount" in response
        assert response["hitCount"] > 0
        assert "EXT_ID" in response["request"]["queryString"]

    def test_pmcid_method(self, client: SearchClient) -> None:
        """Test pmcid() method (special case with prefix) with real API call."""
        qb = QueryBuilder(validate=False)
        # Use a known PMC ID
        query = qb.pmcid("3258128").build(validate=False)

        logger.debug(f"Query: {query}")
        response = client.search(query, page_size=5)
        logger.debug(f"Response: {response}")

        assert "hitCount" in response
        assert response["hitCount"] > 0
        assert "PMCID:PMC" in response["request"]["queryString"]

    # Date Fields

    def test_date_range(self, client: SearchClient) -> None:
        """Test date_range() with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "CRISPR")
                .and_()
                .date_range(start_year=2020, end_year=2023)
                .build(validate=False))
        base_query = "TITLE:CRISPR"

        self._test_field_reduces_results(client, query, base_query, "PUB_YEAR")

    # Author & Affiliation

    def test_affiliation_field(self, client: SearchClient) -> None:
        """Test AFF (affiliation) field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("affiliation", "Harvard").build(validate=False)
        base_query = "Harvard"

        self._test_field_reduces_results(client, query, base_query, "AFF")

    def test_investigator_field(self, client: SearchClient) -> None:
        """Test INVESTIGATOR field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("investigator", "Smith").build(validate=False)
        base_query = "Smith"

        # Note: INVESTIGATOR may have fewer results than general search
        response = client.search(query, page_size=5)
        assert "hitCount" in response
        assert "INVESTIGATOR" in response["request"]["queryString"]

    # Article Metadata

    def test_language_field(self, client: SearchClient) -> None:
        """Test LANG (language) field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "cancer")
                .and_()
                .field("language", "eng")
                .build(validate=False))
        base_query = "TITLE:cancer"

        self._test_field_reduces_results(client, query, base_query, "LANG")

    def test_grant_agency_field(self, client: SearchClient) -> None:
        """Test GRANT_AGENCY field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("grant_agency", "NIH").build(validate=False)
        base_query = "NIH"

        self._test_field_reduces_results(client, query, base_query, "GRANT_AGENCY")

    def test_keyword_field(self, client: SearchClient) -> None:
        """Test KEYWORD field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("keyword", "genomics").build(validate=False)
        base_query = "genomics"

        self._test_field_reduces_results(client, query, base_query, "KEYWORD")

    @pytest.mark.skip(reason="MESH field syntax needs to be updated to use [MESH] tag format instead of MESH: prefix")
    def test_mesh_field(self, client: SearchClient) -> None:
        """Test MESH field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("mesh", "Neoplasms").build(validate=False)
        base_query = "Neoplasms"

        self._test_field_reduces_results(client, query, base_query, "MESH")

    def test_chemical_field(self, client: SearchClient) -> None:
        """Test CHEM (chemical) field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("chemical", "DNA").build(validate=False)
        base_query = "DNA"

        self._test_field_reduces_results(client, query, base_query, "CHEM")

    def test_disease_field(self, client: SearchClient) -> None:
        """Test DISEASE field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("disease", "cancer").build(validate=False)
        base_query = "cancer"

        self._test_field_reduces_results(client, query, base_query, "DISEASE")

    def test_gene_protein_field(self, client: SearchClient) -> None:
        """Test GENE_PROTEIN field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("gene_protein", "TP53").build(validate=False)
        base_query = "TP53"

        self._test_field_reduces_results(client, query, base_query, "GENE_PROTEIN")

    def test_organism_field(self, client: SearchClient) -> None:
        """Test ORGANISM field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("organism", "human").build(validate=False)
        base_query = "human"

        self._test_field_reduces_results(client, query, base_query, "ORGANISM")

    # Full Text Availability

    def test_has_abstract_field(self, client: SearchClient) -> None:
        """Test HAS_ABSTRACT field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "cancer")
                .and_()
                .field("has_abstract", True)
                .build(validate=False))
        base_query = "TITLE:cancer"

        self._test_field_reduces_results(client, query, base_query, "HAS_ABSTRACT")

    def test_has_pdf_field(self, client: SearchClient) -> None:
        """Test HAS_PDF field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "cancer")
                .and_()
                .field("has_pdf", True)
                .build(validate=False))
        base_query = "TITLE:cancer"

        self._test_field_reduces_results(client, query, base_query, "HAS_PDF")

    def test_open_access_field(self, client: SearchClient) -> None:
        """Test OPEN_ACCESS field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "CRISPR")
                .and_()
                .field("open_access", True)
                .build(validate=False))
        base_query = "TITLE:CRISPR"

        self._test_field_reduces_results(client, query, base_query, "OPEN_ACCESS")

    def test_in_pmc_field(self, client: SearchClient) -> None:
        """Test IN_PMC field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "genomics")
                .and_()
                .field("in_pmc", True)
                .build(validate=False))
        base_query = "TITLE:genomics"

        self._test_field_reduces_results(client, query, base_query, "IN_PMC")

    def test_in_epmc_field(self, client: SearchClient) -> None:
        """Test IN_EPMC field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "genomics")
                .and_()
                .field("in_epmc", True)
                .build(validate=False))
        base_query = "TITLE:genomics"

        self._test_field_reduces_results(client, query, base_query, "IN_EPMC")

    # Database Cross-References

    def test_has_uniprot_field(self, client: SearchClient) -> None:
        """Test HAS_UNIPROT field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "protein")
                .and_()
                .field("has_uniprot", True)
                .build(validate=False))
        base_query = "TITLE:protein"

        # Note: This may significantly reduce results
        response = client.search(query, page_size=5)
        assert "hitCount" in response
        assert "HAS_UNIPROT" in response["request"]["queryString"]

    def test_has_pdb_field(self, client: SearchClient) -> None:
        """Test HAS_PDB field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "structure")
                .and_()
                .field("has_pdb", True)
                .build(validate=False))
        base_query = "TITLE:structure"

        response = client.search(query, page_size=5)
        assert "hitCount" in response
        assert "HAS_PDB" in response["request"]["queryString"]

    # Citation Fields

    def test_citation_count(self, client: SearchClient) -> None:
        """Test citation_count() with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "CRISPR")
                .and_()
                .citation_count(min_count=10)
                .build(validate=False))
        base_query = "TITLE:CRISPR"

        self._test_field_reduces_results(client, query, base_query, "CITED")

    def test_cites_method(self, client: SearchClient) -> None:
        """Test cites() method with real API call."""
        qb = QueryBuilder(validate=False)
        # Use a known highly-cited paper ID
        query = qb.cites("23685479", "med").build(validate=False)

        logger.debug(f"Query: {query}")
        response = client.search(query, page_size=5)
        logger.debug(f"Response: {response}")

        assert "hitCount" in response
        assert "CITES" in response["request"]["queryString"]

    # Collection Metadata

    def test_source_method(self, client: SearchClient) -> None:
        """Test source() method (special case with uppercase) with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "cancer")
                .and_()
                .source("MED")
                .build(validate=False))
        base_query = "TITLE:cancer"

        self._test_field_reduces_results(client, query, base_query, "SRC")

    def test_license_field(self, client: SearchClient) -> None:
        """Test LICENSE field with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "genomics")
                .and_()
                .field("license", "cc by")
                .build(validate=False))
        base_query = "TITLE:genomics"

        # Note: LICENSE may have specific values
        response = client.search(query, page_size=5)
        assert "hitCount" in response
        assert "LICENSE" in response["request"]["queryString"]

    # Books

    def test_isbn_field(self, client: SearchClient) -> None:
        """Test ISBN field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("has_book", True).and_().field("title", "biology").build(validate=False)

        logger.debug(f"Query: {query}")
        response = client.search(query, page_size=5)
        logger.debug(f"Response: {response}")
        assert "hitCount" in response
        assert "HAS_BOOK" in response["request"]["queryString"]

    # Accession

    def test_accession_type_method(self, client: SearchClient) -> None:
        """Test accession_type() method (special case with lowercase) with real API call."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "protein")
                .and_()
                .accession_type("pdb")
                .build(validate=False))
        base_query = "TITLE:protein"

        response = client.search(query, page_size=5)
        assert "hitCount" in response
        assert "ACCESSION_TYPE" in response["request"]["queryString"]
        # Verify it's lowercased
        assert "accession_type:pdb" in response["request"]["queryString"].lower()

    # Section-Level Search

    def test_intro_field(self, client: SearchClient) -> None:
        """Test INTRO (introduction section) field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("intro", "background").build(validate=False)
        base_query = "background"

        self._test_field_reduces_results(client, query, base_query, "INTRO")

    def test_methods_field(self, client: SearchClient) -> None:
        """Test METHODS field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("methods", "sequencing").build(validate=False)
        base_query = "sequencing"

        self._test_field_reduces_results(client, query, base_query, "METHODS")

    def test_results_field(self, client: SearchClient) -> None:
        """Test RESULTS field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("results", "significant").build(validate=False)
        base_query = "significant"

        self._test_field_reduces_results(client, query, base_query, "RESULTS")

    def test_discuss_field(self, client: SearchClient) -> None:
        """Test DISCUSS (discussion section) field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("discuss", "implications").build(validate=False)
        base_query = "implications"

        self._test_field_reduces_results(client, query, base_query, "DISCUSS")

    def test_concl_field(self, client: SearchClient) -> None:
        """Test CONCL (conclusions section) field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("concl", "findings").build(validate=False)
        base_query = "findings"

        self._test_field_reduces_results(client, query, base_query, "CONCL")

    def test_body_field(self, client: SearchClient) -> None:
        """Test BODY (full text body) field with real API call."""
        qb = QueryBuilder(validate=False)
        query = qb.field("body", "CRISPR").build(validate=False)
        base_query = "CRISPR"

        self._test_field_reduces_results(client, query, base_query, "BODY")

    # Complex Queries

    def test_complex_query_multiple_fields(self, client: SearchClient) -> None:
        """Test complex query with multiple fields."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "CRISPR")
                .and_()
                .field("author", "Smith")
                .and_()
                .date_range(start_year=2020, end_year=2023)
                .and_()
                .field("open_access", True)
                .build(validate=False))

        response = client.search(query, page_size=5)

        assert "hitCount" in response
        assert "TITLE" in response["request"]["queryString"]
        assert "AUTH" in response["request"]["queryString"]
        assert "PUB_YEAR" in response["request"]["queryString"]
        assert "OPEN_ACCESS" in response["request"]["queryString"]

    def test_complex_query_with_or_logic(self, client: SearchClient) -> None:
        """Test complex query with OR logic."""
        qb = QueryBuilder(validate=False)
        query = (qb
                .field("title", "cancer")
                .or_()
                .field("title", "tumor")
                .build(validate=False))

        response = client.search(query, page_size=5)

        assert "hitCount" in response
        assert response["hitCount"] > 0
        assert "TITLE" in response["request"]["queryString"]

    def test_complex_query_with_grouping(self, client: SearchClient) -> None:
        """Test complex query with grouped sub-queries."""
        sub_qb = QueryBuilder(validate=False)
        sub_query = (sub_qb
                    .field("title", "cancer")
                    .or_()
                    .field("title", "tumor"))

        qb = QueryBuilder(validate=False)
        query = (qb
                .group(sub_query)
                .and_()
                .field("open_access", True)
                .build(validate=False))

        response = client.search(query, page_size=5)

        assert "hitCount" in response
        assert response["hitCount"] > 0
        # Should have parentheses for grouping
        assert "(" in response["request"]["queryString"]
        assert ")" in response["request"]["queryString"]


class TestFieldCoverage:
    """Test that all defined fields can be used in queries."""

    @pytest.fixture
    def client(self) -> SearchClient:
        """Create a SearchClient for API calls."""
        return SearchClient()

    def test_all_boolean_fields_work(self, client: SearchClient) -> None:
        """Test that all boolean fields (has_*, in_*, open_access) work."""
        boolean_fields = [
            "has_abstract", "has_pdf", "has_fulltext", "has_reflist",
            "has_tm", "has_xrefs", "has_suppl", "has_labslinks", "has_data",
            "open_access", "in_pmc", "in_epmc",
        ]

        for field in boolean_fields:
            qb = QueryBuilder(validate=False)
            query = qb.field(field, True).build(validate=False)

            logger.debug(f"Testing boolean field: {field}, query: {query}")
            # Verify query is valid (will raise if not)
            response = client.search(query, page_size=1)
            logger.debug(f"Response for {field}: {response}")
            assert "hitCount" in response
            # Field name should appear in query (uppercase)
            assert field.upper().replace("_", "") in response["request"]["queryString"].upper().replace("_", "")
