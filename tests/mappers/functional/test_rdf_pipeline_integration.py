"""Functional tests for RDF mapping integration with full pipeline."""

import tempfile
from pathlib import Path

import pytest
from rdflib import Graph

from pyeuropepmc.mappers import RDFMapper
from pyeuropepmc.models import PaperEntity, AuthorEntity, SectionEntity, ReferenceEntity


class TestRDFPipelineIntegration:
    """Integration tests for RDF mapping with full processing pipeline."""

    @pytest.fixture
    def mapper(self):
        """RDF mapper fixture."""
        return RDFMapper()

    @pytest.fixture
    def complex_paper_data(self):
        """Complex paper with all related entities."""
        # Create main paper
        paper = PaperEntity(
            pmcid="PMC1234567",
            doi="10.1371/journal.pcbi.1001234",
            title="Computational Analysis of Protein-Protein Interaction Networks",
            abstract="This study presents a comprehensive computational analysis...",
            keywords=["protein-protein interaction", "network analysis", "bioinformatics"],
            publication_year=2024,
            journal="PLOS Computational Biology",
            volume="20",
            issue="1",
            citation_count=25,
            is_oa=True,
        )

        # Create authors
        authors = [
            AuthorEntity(
                full_name="Dr. Alice Johnson",
                first_name="Alice",
                last_name="Johnson",
                orcid="0000-0001-2345-6789",
                email="alice.johnson@university.edu",
                affiliation_text="Department of Bioinformatics, University of Science",
            ),
            AuthorEntity(
                full_name="Dr. Bob Smith",
                first_name="Bob",
                last_name="Smith",
                orcid="0000-0002-3456-7890",
                email="bob.smith@research.org",
                affiliation_text="Center for Computational Biology",
            ),
        ]

        # Create sections
        sections = [
            SectionEntity(
                title="Introduction",
                content="Protein-protein interactions (PPIs) play crucial roles...",
                begin_index=0,
                end_index=500,
            ),
            SectionEntity(
                title="Methods",
                content="We collected PPI data from multiple databases...",
                begin_index=501,
                end_index=1200,
            ),
            SectionEntity(
                title="Results",
                content="Our analysis revealed several key findings...",
                begin_index=1201,
                end_index=1800,
            ),
        ]

        # Create references
        references = [
            ReferenceEntity(
                doi="10.1038/nature12345",
                title="Protein interaction databases",
                publication_year=2020,
            ),
            ReferenceEntity(
                doi="10.1093/bioinformatics/btaa123",
                title="Network analysis methods",
                publication_year=2021,
            ),
        ]

        return {
            "paper": paper,
            "authors": authors,
            "sections": sections,
            "references": references,
        }

    def test_full_pipeline_rdf_conversion(self, mapper, complex_paper_data):
        """Test complete RDF conversion with all entity relationships."""
        g = Graph()

        # Extract data
        paper = complex_paper_data["paper"]
        authors = complex_paper_data["authors"]
        sections = complex_paper_data["sections"]
        references = complex_paper_data["references"]

        # Convert all entities to RDF
        paper_uri = paper.to_rdf(g, mapper=mapper)

        author_uris = []
        for author in authors:
            uri = author.to_rdf(g, mapper=mapper)
            author_uris.append(uri)

        section_uris = []
        for section in sections:
            uri = section.to_rdf(g, mapper=mapper)
            section_uris.append(uri)

        reference_uris = []
        for ref in references:
            uri = ref.to_rdf(g, mapper=mapper)
            reference_uris.append(uri)

        # Add all relationships
        related_entities = {
            "authors": authors,
            "sections": sections,
            "references": references,
        }
        mapper.map_relationships(g, paper_uri, paper, related_entities)

        # Add author-paper relationships (inverse)
        for author, author_uri in zip(authors, author_uris):
            mapper.map_relationships(g, author_uri, author, {"papers": [paper]})

        # Add section-paper relationships (inverse)
        for section, section_uri in zip(sections, section_uris):
            mapper.map_relationships(g, section_uri, section, {"paper": [paper]})

        # Add reference-paper relationships (inverse)
        for ref, ref_uri in zip(references, reference_uris):
            mapper.map_relationships(g, ref_uri, ref, {"citing_paper": [paper]})

        # Verify comprehensive graph structure
        assert len(g) > 80  # Should have many triples

        # Verify paper has all expected relationships
        author_rels = list(g.triples((paper_uri, mapper._resolve_predicate("dcterms:creator"), None)))
        assert len(author_rels) == 2

        section_rels = list(g.triples((paper_uri, mapper._resolve_predicate("dcterms:hasPart"), None)))
        assert len(section_rels) == 3

        ref_rels = list(g.triples((paper_uri, mapper._resolve_predicate("cito:cites"), None)))
        assert len(ref_rels) == 2

        # Verify inverse relationships
        for author_uri in author_uris:
            paper_rels = list(g.triples((author_uri, mapper._resolve_predicate("foaf:made"), None)))
            assert len(paper_rels) == 1

        for section_uri in section_uris:
            paper_rels = list(g.triples((section_uri, mapper._resolve_predicate("dcterms:isPartOf"), None)))
            assert len(paper_rels) == 1

        for ref_uri in reference_uris:
            citing_rels = list(g.triples((ref_uri, mapper._resolve_predicate("cito:isCitedBy"), None)))
            assert len(citing_rels) == 1

    def test_batch_processing_with_files(self, mapper, complex_paper_data):
        """Test batch processing that saves to multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Prepare batch data
            entities_data = {
                "paper_1234567": {
                    "entity": complex_paper_data["paper"],
                    "related_entities": {
                        "authors": complex_paper_data["authors"],
                        "sections": complex_paper_data["sections"],
                        "references": complex_paper_data["references"],
                    }
                }
            }

            # Process batch
            results = mapper.convert_and_save_entities_to_rdf(
                entities_data,
                output_dir=tmpdir,
                prefix="batch_",
                extraction_info={
                    "timestamp": "2024-01-15T12:00:00Z",
                    "method": "functional_test",
                }
            )

            # Verify results
            assert "paper_1234567" in results
            graph = results["paper_1234567"]
            assert isinstance(graph, Graph)
            assert len(graph) > 30  # Substantial content

            # Check file was created
            files = list(Path(tmpdir).glob("*.ttl"))
            assert len(files) == 1
            assert files[0].name.startswith("batch_paper_")

            # Verify file content
            with open(files[0], 'r') as f:
                content = f.read()
                assert "@prefix" in content
                assert "Computational Analysis of Protein-Protein Interaction Networks" in content
                assert "prov:generatedAtTime" in content  # Provenance

    def test_rdf_validation_and_consistency(self, mapper, complex_paper_data):
        """Test RDF graph validation and internal consistency."""
        g = Graph()

        # Convert entities
        paper = complex_paper_data["paper"]
        authors = complex_paper_data["authors"]

        paper_uri = paper.to_rdf(g, mapper=mapper)
        author_uris = [author.to_rdf(g, mapper=mapper) for author in authors]

        # Add relationships
        mapper.map_relationships(g, paper_uri, paper, {"authors": authors})

        # Validate graph structure
        # 1. All subjects should have rdf:type
        subjects_with_types = set()
        for s, p, o in g.triples((None, mapper._resolve_predicate("rdf:type"), None)):
            subjects_with_types.add(s)

        # All our entities should have types
        assert paper_uri in subjects_with_types
        for uri in author_uris:
            assert uri in subjects_with_types

        # 2. Check for orphaned triples (subjects without types)
        all_subjects = set()
        for s, p, o in g:
            all_subjects.add(s)

        # Most subjects should have types (allowing for some blank nodes)
        typed_ratio = len(subjects_with_types) / len(all_subjects) if all_subjects else 0
        assert typed_ratio > 0.8  # At least 80% of subjects should be typed

        # 3. Validate URI consistency
        doi_uris = [str(o) for s, p, o in g.triples((None, mapper._resolve_predicate("owl:sameAs"), None))
                   if str(o).startswith("https://doi.org/")]
        assert len(doi_uris) > 0  # Should have DOI URIs

        # 4. Check for duplicate triples (shouldn't exist)
        triples_set = set()
        duplicates = []
        for triple in g:
            triple_tuple = (str(triple[0]), str(triple[1]), str(triple[2]))
            if triple_tuple in triples_set:
                duplicates.append(triple_tuple)
            triples_set.add(triple_tuple)

        assert len(duplicates) == 0, f"Found duplicate triples: {duplicates}"

    def test_memory_efficiency_large_batch(self, mapper):
        """Test memory efficiency with large batch processing."""
        # Create a batch of papers
        entities_data = {}
        for i in range(50):  # Large batch
            paper = PaperEntity(
                pmcid=f"PMC{i:07d}",
                doi=f"10.1234/batch.{2024:04d}.{i:03d}",
                title=f"Batch Paper {i}",
                keywords=[f"batch_keyword_{i}"],
                publication_year=2024,
            )
            entities_data[f"paper_{i}"] = {"entity": paper}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Process large batch
            results = mapper.convert_and_save_entities_to_rdf(
                entities_data,
                output_dir=tmpdir,
                prefix="large_batch_"
            )

            # Verify all papers were processed
            assert len(results) == 50

            # Check files were created
            ttl_files = list(Path(tmpdir).glob("*.ttl"))
            assert len(ttl_files) == 50

            # Verify total triples across all files
            total_triples = sum(len(graph) for graph in results.values())
            assert total_triples > 500  # Should have substantial content

            # Verify each graph has reasonable content
            for graph in results.values():
                assert len(graph) > 5  # Each paper should have multiple triples

    def test_format_conversion_consistency(self, mapper, complex_paper_data):
        """Test that different serialization formats contain equivalent information."""
        g = Graph()
        paper = complex_paper_data["paper"]
        paper.to_rdf(g, mapper=mapper)

        # Serialize to different formats
        turtle = mapper.serialize_graph(g, format="turtle")
        jsonld = mapper.serialize_graph(g, format="json-ld")
        xml = mapper.serialize_graph(g, format="xml")

        # All formats should contain key information
        title_present = "Computational Analysis of Protein-Protein Interaction Networks" in turtle
        assert title_present

        # JSON-LD should be parseable and contain title
        assert "Computational Analysis of Protein-Protein Interaction Networks" in jsonld

        # XML should contain title
        assert "Computational Analysis of Protein-Protein Interaction Networks" in xml

        # All should contain DOI
        doi_present = "10.1371/journal.pcbi.1001234" in turtle
        assert doi_present
        assert "10.1371/journal.pcbi.1001234" in jsonld
        assert "10.1371/journal.pcbi.1001234" in xml

    def test_incremental_graph_building(self, mapper, complex_paper_data):
        """Test building RDF graph incrementally."""
        paper = complex_paper_data["paper"]
        authors = complex_paper_data["authors"]
        sections = complex_paper_data["sections"]

        # Start with empty graph
        g = Graph()
        assert len(g) == 0

        # Add paper
        paper_uri = paper.to_rdf(g, mapper=mapper)
        paper_triples = len(g)
        assert paper_triples > 10

        # Add first author
        author1_uri = authors[0].to_rdf(g, mapper=mapper)
        after_author1 = len(g)
        assert after_author1 > paper_triples

        # Add relationship
        mapper.map_relationships(g, paper_uri, paper, {"authors": [authors[0]]})
        after_relationship = len(g)
        assert after_relationship > after_author1

        # Add section
        section_uri = sections[0].to_rdf(g, mapper=mapper)
        after_section = len(g)
        assert after_section > after_relationship

        # Add section relationship
        mapper.map_relationships(g, paper_uri, paper, {"sections": [sections[0]]})
        final_count = len(g)
        assert final_count > after_section

        # Verify final graph integrity
        assert (paper_uri, mapper._resolve_predicate("dcterms:creator"), author1_uri) in g
        assert (paper_uri, mapper._resolve_predicate("dcterms:hasPart"), section_uri) in g
