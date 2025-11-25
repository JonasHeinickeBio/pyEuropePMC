"""Functional tests for RDF mapping end-to-end workflows."""

import tempfile
from pathlib import Path

import pytest
from rdflib import Graph, URIRef

from pyeuropepmc.mappers import RDFMapper
from pyeuropepmc.models import AuthorEntity, InstitutionEntity, PaperEntity


class TestRDFMappingEndToEnd:
    """End-to-end functional tests for RDF mapping."""

    @pytest.fixture
    def mapper(self):
        """RDF mapper fixture."""
        return RDFMapper()

    @pytest.fixture
    def sample_paper(self):
        """Sample paper entity with all fields populated."""
        return PaperEntity(
            pmcid="PMC1234567",
            doi="10.1371/journal.pone.0308090",
            title="Test Article on Metabolic Syndrome",
            abstract="This is a comprehensive study of metabolic syndrome...",
            keywords=["metabolic syndrome", "cardiovascular disease", "diabetes"],
            publication_year=2024,
            publication_date="2024-01-15",
            journal="PLOS ONE",
            volume="19",
            issue="1",
            pages="1-20",
            first_page="1",
            last_page="20",
            citation_count=45,
            influential_citation_count=12,
            is_oa=True,
            oa_status="gold",
            oa_url="https://doi.org/10.1371/journal.pone.0308090",
            publisher="Public Library of Science",
            issn="1932-6203",
            publication_type="Journal Article",
            semantic_scholar_corpus_id="12345678",
            openalex_id="https://openalex.org/W1234567890",
            reference_count=35,
            cited_by_count=67,
        )

    @pytest.fixture
    def sample_author(self):
        """Sample author entity."""
        return AuthorEntity(
            full_name="Dr. Jane Smith",
            first_name="Jane",
            last_name="Smith",
            orcid="0000-0002-1234-5678",
            openalex_id="https://openalex.org/A123456789",
            email="jane.smith@university.edu",
            affiliation_text="Department of Medicine, University of Example",
        )

    @pytest.fixture
    def sample_institution(self):
        """Sample institution entity."""
        return InstitutionEntity(
            display_name="University of Example",
            ror_id="https://ror.org/123456789",
            openalex_id="https://openalex.org/I123456789",
            country="United States",
            country_code="US",
            city="Example City",
            latitude=40.7128,
            longitude=-74.0060,
            institution_type="education",
            website="https://www.example.edu",
            wikidata_id="Q123456",
        )

    def test_complete_paper_rdf_conversion(self, mapper, sample_paper):
        """Test complete RDF conversion of a paper entity."""
        g = Graph()

        # Convert to RDF
        uri = sample_paper.to_rdf(g, mapper=mapper)

        # Verify URI generation
        assert str(uri) == "https://doi.org/10.1371/journal.pone.0308090"

        # Verify basic triples
        assert (uri, mapper._resolve_predicate("dcterms:title"), None) in g
        assert (uri, mapper._resolve_predicate("dcterms:abstract"), None) in g
        assert (uri, mapper._resolve_predicate("bibo:doi"), None) in g

        # Verify keywords (multi-value field)
        keyword_count = 0
        for triple in g.triples((uri, mapper._resolve_predicate("dcterms:subject"), None)):
            keyword_count += 1
        assert keyword_count == 3  # 3 keywords

        # Verify external identifiers (owl:sameAs)
        sameas_count = 0
        for triple in g.triples((uri, mapper._resolve_predicate("owl:sameAs"), None)):
            sameas_count += 1
        assert sameas_count >= 2  # DOI and PMCID at minimum

        # Verify graph has substantial content
        assert len(g) > 20  # Should have many triples

    def test_paper_with_relationships_rdf(self, mapper, sample_paper, sample_author, sample_institution):
        """Test RDF conversion with relationships between entities."""
        g = Graph()

        # Convert entities
        paper_uri = sample_paper.to_rdf(g, mapper=mapper)
        author_uri = sample_author.to_rdf(g, mapper=mapper)
        inst_uri = sample_institution.to_rdf(g, mapper=mapper)

        # Add relationships
        related_entities = {"authors": [sample_author]}
        mapper.map_relationships(g, paper_uri, sample_paper, related_entities)

        related_entities = {"institutions": [sample_institution]}
        mapper.map_relationships(g, author_uri, sample_author, related_entities)

        # Verify relationships exist
        assert (paper_uri, mapper._resolve_predicate("dcterms:creator"), author_uri) in g
        assert (author_uri, mapper._resolve_predicate("org:memberOf"), inst_uri) in g

        # Verify all entities are in graph
        assert len(list(g.triples((paper_uri, None, None)))) > 0
        assert len(list(g.triples((author_uri, None, None)))) > 0
        assert len(list(g.triples((inst_uri, None, None)))) > 0

    def test_rdf_file_save_and_load(self, mapper, sample_paper):
        """Test saving RDF to file and loading it back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_paper.ttl"

            # Create and save RDF
            g = Graph()
            sample_paper.to_rdf(g, mapper=mapper)
            mapper.serialize_graph(g, format="turtle", destination=str(filepath))

            # Verify file was created
            assert filepath.exists()
            assert filepath.stat().st_size > 0

            # Load RDF back
            loaded_g = Graph()
            loaded_g.parse(str(filepath), format="turtle")

            # Verify content is the same
            assert len(g) == len(loaded_g)

            # Verify key triples are preserved
            paper_uri = URIRef("https://doi.org/10.1371/journal.pone.0308090")
            assert (paper_uri, mapper._resolve_predicate("dcterms:title"), None) in loaded_g

    def test_batch_entity_conversion(self, mapper, sample_paper, sample_author):
        """Test batch conversion of multiple entities."""
        entities_data = {
            "paper1": {
                "entity": sample_paper,
                "related_entities": {"authors": [sample_author]}
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            results = mapper.convert_and_save_entities_to_rdf(
                entities_data,
                output_dir=tmpdir,
                prefix="test_"
            )

            # Verify results
            assert "paper1" in results
            assert isinstance(results["paper1"], Graph)
            assert len(results["paper1"]) > 0

            # Verify file was created
            expected_file = Path(tmpdir) / "test_paper_paper1.ttl"
            assert expected_file.exists()

    def test_multiple_formats_serialization(self, mapper, sample_paper):
        """Test serialization to multiple RDF formats."""
        g = Graph()
        sample_paper.to_rdf(g, mapper=mapper)

        # Test Turtle format
        ttl = mapper.serialize_graph(g, format="turtle")
        assert "@prefix" in ttl
        assert "dcterms:title" in ttl
        assert "Test Article on Metabolic Syndrome" in ttl

        # Test JSON-LD format
        jsonld = mapper.serialize_graph(g, format="json-ld")
        assert '"@type"' in jsonld or '"type"' in jsonld
        assert "Test Article on Metabolic Syndrome" in jsonld

        # Test RDF/XML format
        xml = mapper.serialize_graph(g, format="xml")
        assert "<rdf:RDF" in xml or "<?xml" in xml
        assert "Test Article on Metabolic Syndrome" in xml

    def test_provenance_tracking(self, mapper, sample_paper):
        """Test that provenance information is correctly added."""
        g = Graph()

        extraction_info = {
            "timestamp": "2024-01-15T10:30:00Z",
            "method": "xml_parser",
            "quality": {
                "validation_passed": True,
                "completeness_score": 0.95
            }
        }

        uri = sample_paper.to_rdf(g, mapper=mapper, extraction_info=extraction_info)

        # Verify provenance triples
        assert (uri, mapper._resolve_predicate("prov:generatedAtTime"), None) in g
        assert (uri, mapper._resolve_predicate("prov:wasGeneratedBy"), None) in g
        assert (uri, mapper._resolve_predicate("ex:validationStatus"), None) in g
        assert (uri, mapper._resolve_predicate("ex:completenessScore"), None) in g

    def test_ontology_alignments_complete(self, mapper, sample_paper, sample_author, sample_institution):
        """Test complete ontology alignments across all entity types."""
        g = Graph()

        # Convert all entities
        paper_uri = sample_paper.to_rdf(g, mapper=mapper)
        author_uri = sample_author.to_rdf(g, mapper=mapper)
        inst_uri = sample_institution.to_rdf(g, mapper=mapper)

        # Check paper ontology alignments (MeSH terms for keywords)
        mesh_triples = list(g.triples((paper_uri, mapper._resolve_predicate("mesh:hasSubject"), None)))
        assert len(mesh_triples) == 3  # 3 keywords

        # Check external identifiers for all entities
        paper_sameas = list(g.triples((paper_uri, mapper._resolve_predicate("owl:sameAs"), None)))
        assert len(paper_sameas) >= 2  # DOI + PMCID + OpenAlex

        author_sameas = list(g.triples((author_uri, mapper._resolve_predicate("owl:sameAs"), None)))
        assert len(author_sameas) >= 1  # ORCID + OpenAlex

        inst_sameas = list(g.triples((inst_uri, mapper._resolve_predicate("owl:sameAs"), None)))
        assert len(inst_sameas) >= 2  # ROR + OpenAlex + Wikidata

    def test_large_graph_performance(self, mapper):
        """Test performance with larger graphs (basic performance check)."""
        g = Graph()

        # Create multiple entities
        papers = []
        for i in range(10):
            paper = PaperEntity(
                pmcid=f"PMC{i:07d}",
                doi=f"10.1234/test.{2024+i:04d}.001",
                title=f"Test Paper {i}",
                keywords=[f"keyword{i}", f"topic{i}"],
                publication_year=2024 + i
            )
            papers.append(paper)

        # Convert all to RDF
        for paper in papers:
            paper.to_rdf(g, mapper=mapper)

        # Verify we have a substantial graph
        assert len(g) > 100  # Should have many triples

        # Verify all papers are represented
        paper_uris = set()
        for s, p, o in g.triples((None, mapper._resolve_predicate("dcterms:title"), None)):
            if "Test Paper" in str(o):
                paper_uris.add(s)
        assert len(paper_uris) == 10

    def test_error_handling_invalid_entities(self, mapper):
        """Test error handling with invalid entities."""
        g = Graph()

        # Create invalid paper (missing required fields)
        invalid_paper = PaperEntity()  # No PMCID, DOI, or title

        # Should raise validation error
        with pytest.raises(ValueError, match="PaperEntity must have at least one"):
            invalid_paper.validate()

        # But if we skip validation, RDF conversion should still work with fallback URI
        uri = invalid_paper.to_rdf(g, mapper=mapper)
        assert uri is not None
        assert len(g) > 0  # Should still create some triples
