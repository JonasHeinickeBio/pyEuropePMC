"""Unit tests for RDF utilities."""

from rdflib import Graph, URIRef

from pyeuropepmc.mappers.rdf_utils import (
    add_external_identifiers,
    generate_entity_uri,
    map_multi_value_fields,
    map_ontology_alignments,
    map_single_value_fields,
    normalize_name,
)
from pyeuropepmc.models import AuthorEntity, InstitutionEntity, PaperEntity, ReferenceEntity


class TestRDFUtils:
    """Tests for RDF utility functions."""

    def test_normalize_name(self):
        """Test name normalization for URIs."""
        # Test normal case
        normalized = normalize_name("John Doe")
        assert normalized == "john-doe"

        # Test with special characters
        normalized = normalize_name("José María O'Connor-Smith")
        assert normalized == "jos-mara-oconnorsmith"

        # Test empty/None
        assert normalize_name("") is None
        assert normalize_name("   ") is None

    def test_generate_entity_uri_paper_doi(self):
        """Test URI generation for paper with DOI."""
        paper = PaperEntity(doi="10.1234/test.2021.001", pmcid="PMC1234567")

        uri = generate_entity_uri(paper)
        assert str(uri) == "https://doi.org/10.1234/test.2021.001"

    def test_generate_entity_uri_paper_pmcid(self):
        """Test URI generation for paper with PMCID only."""
        paper = PaperEntity(pmcid="PMC1234567")

        uri = generate_entity_uri(paper)
        assert str(uri) == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/"

    def test_generate_entity_uri_author_orcid(self):
        """Test URI generation for author with ORCID."""
        author = AuthorEntity(full_name="John Doe", orcid="0000-0001-2345-6789")

        uri = generate_entity_uri(author)
        assert str(uri) == "http://example.org/data/author/john-doe"

    def test_generate_entity_uri_author_name(self):
        """Test URI generation for author with name only."""
        author = AuthorEntity(full_name="John Doe")

        uri = generate_entity_uri(author)
        assert "john-doe" in str(uri)

    def test_generate_entity_uri_institution_ror(self):
        """Test URI generation for institution with ROR."""
        institution = InstitutionEntity(display_name="Test University", ror_id="https://ror.org/123456")

        uri = generate_entity_uri(institution)
        assert str(uri) == "https://ror.org/123456"

    def test_generate_entity_uri_reference_doi(self):
        """Test URI generation for reference with DOI."""
        reference = ReferenceEntity(doi="10.1234/ref.2021.001")

        uri = generate_entity_uri(reference)
        assert str(uri) == "https://doi.org/10.1234/ref.2021.001"

    def test_generate_entity_uri_reference_pmid(self):
        """Test URI generation for reference with PMID."""
        reference = ReferenceEntity(pmid="12345678")

        uri = generate_entity_uri(reference)
        assert str(uri) == "https://pubmed.ncbi.nlm.nih.gov/12345678/"

    def test_map_single_value_fields(self):
        """Test mapping single-value fields."""
        g = Graph()
        subject = URIRef("http://example.org/test")

        # Mock resolve_predicate function
        def resolve_predicate(pred_str):
            return URIRef(f"http://example.org/{pred_str}")

        paper = PaperEntity(title="Test Title", doi="10.1234/test")
        fields_mapping = {"title": "title", "doi": "doi"}

        map_single_value_fields(g, subject, paper, fields_mapping, resolve_predicate)

        # Check triples were added
        assert len(g) == 2

    def test_map_multi_value_fields(self):
        """Test mapping multi-value fields."""
        g = Graph()
        subject = URIRef("http://example.org/test")

        # Mock resolve_predicate function
        def resolve_predicate(pred_str):
            return URIRef(f"http://example.org/{pred_str}")

        paper = PaperEntity(keywords=["key1", "key2"])
        multi_value_mapping = {"keywords": "keyword"}

        map_multi_value_fields(g, subject, paper, multi_value_mapping, resolve_predicate)

        # Check triples were added
        assert len(g) == 2

    def test_map_ontology_alignments_paper(self):
        """Test ontology alignments for paper."""
        g = Graph()
        subject = URIRef("http://example.org/test")

        # Mock resolve_predicate function
        def resolve_predicate(pred_str):
            if pred_str == "meshv:hasDescriptor":
                return URIRef("http://id.nlm.nih.gov/mesh/vocab#hasDescriptor")
            elif pred_str == "obo:RO_0000053":
                return URIRef("http://purl.obolibrary.org/obo/RO_0000053")
            return URIRef(f"http://example.org/{pred_str}")

        paper = PaperEntity(keywords=["COVID-19", "SARS-CoV-2"], doi="10.1234/test", pmcid="PMC123456")

        map_ontology_alignments(g, subject, paper, resolve_predicate)

        # Check triples were added (keywords + external identifiers)
        # Changed: now we have mesh_terms from keywords (2) + 3 external IDs (doi, pmcid, pubmed)
        assert len(g) >= 3  # 2 mesh descriptors + external identifiers

    def test_add_external_identifiers_paper(self):
        """Test adding external identifiers for paper."""
        g = Graph()
        subject = URIRef("http://example.org/test")

        # Mock resolve_predicate function
        def resolve_predicate(pred_str):
            if pred_str == "owl:sameAs":
                return URIRef("http://www.w3.org/2002/07/owl#sameAs")
            return URIRef(f"http://example.org/{pred_str}")

        paper = PaperEntity(doi="10.1234/test", pmcid="PMC123456")

        add_external_identifiers(g, subject, paper, resolve_predicate)

        # Check owl:sameAs triples were added
        # Changed: now includes PMID-based pubmed URI as well
        assert len(g) == 3  # DOI, PMCID, and PubMed URI

    def test_add_external_identifiers_author(self):
        """Test adding external identifiers for author."""
        g = Graph()
        subject = URIRef("http://example.org/test")

        # Mock resolve_predicate function
        def resolve_predicate(pred_str):
            if pred_str == "owl:sameAs":
                return URIRef("http://www.w3.org/2002/07/owl#sameAs")
            return URIRef(f"http://example.org/{pred_str}")

        author = AuthorEntity(orcid="0000-0001-2345-6789", openalex_id="https://openalex.org/A123456")

        add_external_identifiers(g, subject, author, resolve_predicate)

        # Check owl:sameAs triples were added
        assert len(g) == 2  # ORCID and OpenAlex

    def test_add_external_identifiers_institution(self):
        """Test adding external identifiers for institution."""
        g = Graph()
        subject = URIRef("http://example.org/test")

        # Mock resolve_predicate function
        def resolve_predicate(pred_str):
            if pred_str == "owl:sameAs":
                return URIRef("http://www.w3.org/2002/07/owl#sameAs")
            return URIRef(f"http://example.org/{pred_str}")

        institution = InstitutionEntity(
            ror_id="https://ror.org/123456",
            openalex_id="https://openalex.org/I123456",
            wikidata_id="Q123456"
        )

        add_external_identifiers(g, subject, institution, resolve_predicate)

        # Check owl:sameAs triples were added
        assert len(g) == 3  # ROR, OpenAlex, and Wikidata

    def test_add_external_identifiers_reference(self):
        """Test adding external identifiers for reference."""
        g = Graph()
        subject = URIRef("http://example.org/test")

        # Mock resolve_predicate function
        def resolve_predicate(pred_str):
            if pred_str == "owl:sameAs":
                return URIRef("http://www.w3.org/2002/07/owl#sameAs")
            return URIRef(f"http://example.org/{pred_str}")

        reference = ReferenceEntity(doi="10.1234/ref.2021.001", pmid="12345678")

        add_external_identifiers(g, subject, reference, resolve_predicate)

        # Check owl:sameAs triples were added
        assert len(g) == 2  # DOI and PMID
