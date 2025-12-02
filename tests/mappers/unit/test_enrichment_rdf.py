"""Integration tests for RDF mapping with enrichment data."""

import pytest
from rdflib import Graph, Namespace

from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.models import AuthorEntity, InstitutionEntity, PaperEntity


class TestEnrichmentRDFMapping:
    """Tests for RDF mapping of enriched entities."""

    @pytest.fixture
    def mapper(self):
        """Create RDF mapper instance."""
        return RDFMapper()

    @pytest.fixture
    def enriched_paper(self):
        """Create a paper entity with enrichment data."""
        return PaperEntity(
            doi="10.1371/journal.pone.0308090",
            title="Test Article on Metabolic Syndrome",
            abstract="This is a test abstract about dietary patterns.",
            publication_date="2024-08-06",
            publication_year=2024,
            citation_count=3,
            influential_citation_count=0,
            is_oa=True,
            oa_status="gold",
            oa_url="https://doi.org/10.1371/journal.pone.0308090",
            fields_of_study=["Medicine", "Nutrition"],
            keywords=["metabolic syndrome", "dietary patterns"],
        )

    @pytest.fixture
    def enriched_author(self):
        """Create an author entity with enrichment data."""
        return AuthorEntity(
            full_name="John Doe",
            name="John Doe",
            first_name="John",
            last_name="Doe",
            orcid="0000-0001-2345-6789",
            openalex_id="https://openalex.org/A12345",
            position="first",
            email="john.doe@example.edu",
            sources=["crossref", "openalex"],
        )

    @pytest.fixture
    def enriched_institution(self):
        """Create an institution entity with enrichment data."""
        return InstitutionEntity(
            display_name="Example University",
            ror_id="https://ror.org/abc123",
            openalex_id="https://openalex.org/I123456",
            country="United States",
            country_code="US",
            city="Example City",
            latitude=40.7128,
            longitude=-74.0060,
            institution_type="education",
            grid_id="grid.1234.5",
            wikidata_id="Q12345",
            website="https://example.edu",
            established=1850,
            domains=["example.edu"],
        )

    def test_enriched_paper_to_rdf(self, mapper, enriched_paper):
        """Test converting enriched paper to RDF."""
        g = Graph()
        uri = enriched_paper.to_rdf(g, mapper=mapper)

        # Check basic paper properties
        assert (uri, mapper._resolve_predicate("dcterms:title"), None) in g
        assert (uri, mapper._resolve_predicate("dcterms:abstract"), None) in g

        # Check enrichment properties
        assert (uri, mapper._resolve_predicate("cito:citationCount"), None) in g
        assert (uri, mapper._resolve_predicate("ex:influentialCitationCount"), None) in g
        assert (uri, mapper._resolve_predicate("ex:isOpenAccess"), None) in g
        assert (uri, mapper._resolve_predicate("ex:openAccessStatus"), None) in g
        assert (uri, mapper._resolve_predicate("dcterms:date"), None) in g

        # Check multi-value fields
        assert (uri, mapper._resolve_predicate("dcterms:subject"), None) in g

        # Verify URI is DOI-based
        assert str(uri) == "https://doi.org/10.1371/journal.pone.0308090"

    def test_enriched_author_to_rdf(self, mapper, enriched_author):
        """Test converting enriched author to RDF."""
        g = Graph()
        uri = enriched_author.to_rdf(g, mapper=mapper)

        # Check basic author properties
        assert (uri, mapper._resolve_predicate("foaf:name"), None) in g
        assert (uri, mapper._resolve_predicate("foaf:givenName"), None) in g
        assert (uri, mapper._resolve_predicate("foaf:familyName"), None) in g

        # Check enrichment properties
        assert (uri, mapper._resolve_predicate("ex:orcid"), None) in g
        assert (uri, mapper._resolve_predicate("ex:openAlexId"), None) in g
        assert (uri, mapper._resolve_predicate("ex:authorPosition"), None) in g
        assert (uri, mapper._resolve_predicate("foaf:mbox"), None) in g

        # Check provenance
        assert (uri, mapper._resolve_predicate("prov:hadPrimarySource"), None) in g

        # Verify URI is name-based (prioritized over ORCID)
        assert str(uri) == "http://example.org/data/author/john-doe"

    def test_enriched_institution_to_rdf(self, mapper, enriched_institution):
        """Test converting enriched institution to RDF."""
        g = Graph()
        uri = enriched_institution.to_rdf(g, mapper=mapper)

        # Check basic institution properties
        assert (uri, mapper._resolve_predicate("skos:prefLabel"), None) in g
        assert (uri, mapper._resolve_predicate("ror:rorId"), None) in g
        assert (uri, mapper._resolve_predicate("ex:openAlexId"), None) in g

        # Check geographic properties
        assert (uri, mapper._resolve_predicate("ex:country"), None) in g
        assert (uri, mapper._resolve_predicate("ex:city"), None) in g
        assert (uri, mapper._resolve_predicate("geo:lat"), None) in g
        assert (uri, mapper._resolve_predicate("geo:long"), None) in g

        # Check external identifiers
        assert (uri, mapper._resolve_predicate("ex:gridId"), None) in g
        assert (uri, mapper._resolve_predicate("ex:wikidataId"), None) in g
        assert (uri, mapper._resolve_predicate("foaf:homepage"), None) in g

        # Check owl:sameAs links
        assert (uri, mapper._resolve_predicate("owl:sameAs"), None) in g

        # Verify URI is ROR-based
        assert str(uri) == "https://ror.org/abc123"

    def test_author_with_institutions_relationship(self, mapper, enriched_author, enriched_institution):
        """Test RDF mapping of author-institution relationship."""
        g = Graph()
        author_uri = enriched_author.to_rdf(g, mapper=mapper)

        # Map relationship to institution
        related = {"institutions": [enriched_institution]}
        mapper.map_relationships(g, author_uri, enriched_author, related)

        # Check relationship exists
        org_ns = Namespace("http://www.w3.org/ns/org#")
        assert (author_uri, org_ns["memberOf"], None) in g

    def test_paper_with_authors_relationship(self, mapper, enriched_paper, enriched_author):
        """Test RDF mapping of paper-author relationship."""
        g = Graph()
        paper_uri = enriched_paper.to_rdf(g, mapper=mapper)

        # Map relationship to authors
        related = {"authors": [enriched_author]}
        mapper.map_relationships(g, paper_uri, enriched_paper, related)

        # Check relationship exists
        dct_ns = Namespace("http://purl.org/dc/terms/")
        assert (paper_uri, dct_ns["creator"], None) in g

    def test_full_enriched_graph(self, mapper, enriched_paper, enriched_author, enriched_institution):
        """Test creating a complete enriched RDF graph with all entities."""
        g = Graph()

        # Add all entities
        paper_uri = enriched_paper.to_rdf(g, mapper=mapper)
        author_uri = enriched_author.to_rdf(g, mapper=mapper)
        inst_uri = enriched_institution.to_rdf(g, mapper=mapper)

        # Add relationships
        mapper.map_relationships(g, paper_uri, enriched_paper, {"authors": [enriched_author]})
        mapper.map_relationships(g, author_uri, enriched_author, {"institutions": [enriched_institution]})

        # Verify the graph has all entities
        assert (paper_uri, None, None) in g
        assert (author_uri, None, None) in g
        assert (inst_uri, None, None) in g

        # Verify graph size (should have many triples)
        assert len(g) > 30  # Expect at least 30 triples for this complete graph

    def test_rdf_serialization_turtle(self, mapper, enriched_paper):
        """Test serializing enriched RDF to Turtle format."""
        g = Graph()
        enriched_paper.to_rdf(g, mapper=mapper)

        ttl = mapper.serialize_graph(g, format="turtle")
        # Check for key predicates (actual URIs in serialization)
        assert "purl.org/ontology/bibo/AcademicArticle" in ttl or "AcademicArticle" in ttl
        assert "purl.org/dc/terms/" in ttl or "dcterms" in ttl
        assert "Test Article on Metabolic Syndrome" in ttl
