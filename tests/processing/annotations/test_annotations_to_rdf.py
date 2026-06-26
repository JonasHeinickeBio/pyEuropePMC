"""
Tests for annotations to RDF conversion.
"""

import pytest
from rdflib import Graph

from pyeuropepmc.processing.annotations_to_rdf import (
    annotations_to_entities,
    annotations_to_rdf,
    entity_annotation_to_model,
    relationship_annotation_to_model,
)


@pytest.fixture
def sample_entity_dict():
    """Sample entity annotation dictionary."""
    return {
        "id": "DOID:12365",
        "name": "malaria",
        "type": "Disease",
        "exact": "malaria",
        "section": "abstract",
        "provider": "Europe PMC",
        "confidence": 0.95,
    }


@pytest.fixture
def sample_relationship_dict():
    """Sample relationship annotation dictionary."""
    return {
        "subject": {"id": "GENE:7157", "name": "TP53", "type": "Gene"},
        "predicate": "associated_with",
        "object": {"id": "DOID:162", "name": "cancer", "type": "Disease"},
        "sentence": "TP53 is associated with cancer",
        "section": "body",
        "provider": "Europe PMC",
    }


@pytest.fixture
def sample_parsed_annotations():
    """Sample parsed annotations structure."""
    return {
        "entities": [
            {
                "id": "DOID:12365",
                "name": "malaria",
                "type": "Disease",
                "exact": "malaria",
                "section": "abstract",
                "provider": "Europe PMC",
            },
            {
                "id": "CHEBI:16236",
                "name": "ethanol",
                "type": "Chemical",
                "exact": "ethanol",
                "section": "body",
                "provider": "Europe PMC",
            },
        ],
        "relationships": [
            {
                "subject": {"id": "GENE:7157", "name": "TP53", "type": "Gene"},
                "predicate": "associated_with",
                "object": {"id": "DOID:162", "name": "cancer", "type": "Disease"},
                "sentence": "TP53 is associated with cancer",
                "section": "body",
            }
        ],
        "sentences": [],
        "metadata": {},
    }


class TestEntityAnnotationToModel:
    """Test entity_annotation_to_model function."""

    def test_convert_entity_dict(self, sample_entity_dict):
        """Test converting entity dictionary to model."""
        entity = entity_annotation_to_model(sample_entity_dict)

        assert entity.entity_id == "DOID:12365"
        assert entity.entity_name == "malaria"
        assert entity.entity_type == "Disease"
        assert entity.exact == "malaria"
        assert entity.section == "abstract"
        assert entity.provider == "Europe PMC"
        assert entity.confidence == 0.95

    def test_convert_entity_dict_minimal(self):
        """Test converting minimal entity dictionary."""
        minimal_dict = {"id": "TEST:123", "exact": "test"}
        entity = entity_annotation_to_model(minimal_dict)

        assert entity.entity_id == "TEST:123"
        assert entity.exact == "test"


class TestRelationshipAnnotationToModel:
    """Test relationship_annotation_to_model function."""

    def test_convert_relationship_dict(self, sample_relationship_dict):
        """Test converting relationship dictionary to model."""
        rel = relationship_annotation_to_model(sample_relationship_dict)

        assert rel.subject_id == "GENE:7157"
        assert rel.subject_name == "TP53"
        assert rel.subject_type == "Gene"
        assert rel.predicate == "associated_with"
        assert rel.object_id == "DOID:162"
        assert rel.object_name == "cancer"
        assert rel.object_type == "Disease"
        assert rel.exact == "TP53 is associated with cancer"


class TestAnnotationsToEntities:
    """Test annotations_to_entities function."""

    def test_convert_parsed_annotations(self, sample_parsed_annotations):
        """Test converting parsed annotations to entities."""
        entities = annotations_to_entities(sample_parsed_annotations)

        assert len(entities) == 3  # 2 entities + 1 relationship
        assert sum(1 for e in entities if hasattr(e, "entity_id")) == 2
        assert sum(1 for e in entities if hasattr(e, "subject_id")) == 1

    def test_convert_empty_annotations(self):
        """Test converting empty annotations."""
        empty = {"entities": [], "relationships": []}
        entities = annotations_to_entities(empty)

        assert len(entities) == 0


class TestAnnotationsToRDF:
    """Test annotations_to_rdf function."""

    def test_create_rdf_graph(self, sample_parsed_annotations):
        """Test creating RDF graph from annotations."""
        g = annotations_to_rdf(sample_parsed_annotations)

        assert isinstance(g, Graph)
        assert len(g) > 0  # Should have some triples

    def test_create_rdf_graph_with_custom_graph(self, sample_parsed_annotations):
        """Test adding annotations to existing graph."""
        existing_g = Graph()
        g = annotations_to_rdf(sample_parsed_annotations, graph=existing_g)

        assert g is existing_g
        assert len(g) > 0

    def test_create_rdf_graph_empty_annotations(self):
        """Test creating RDF graph from empty annotations."""
        empty = {"entities": [], "relationships": []}
        g = annotations_to_rdf(empty)

        assert isinstance(g, Graph)
        # Graph will have namespace bindings but no content triples

    def test_create_rdf_graph_custom_base_uri(self, sample_parsed_annotations):
        """Test creating RDF graph with custom base URI."""
        g = annotations_to_rdf(
            sample_parsed_annotations, base_uri="http://custom.org/annotations/"
        )

        assert isinstance(g, Graph)
        assert len(g) > 0


class TestRDFEdgeCases:
    """Edge case tests for annotations_to_rdf function."""

    def test_entity_with_http_id(self):
        """Entity ID starting with http:// triggers URIRef path (l.249) and OWL.sameAs (l.293-294)."""
        parsed = {
            "entities": [
                {
                    "annotation_id": "http://example.org/ann/1",
                    "id": "http://purl.obolibrary.org/obo/DOID_12365",
                    "name": "malaria",
                    "type": "Disease",
                    "exact": "malaria",
                    "section": "abstract",
                    "provider": "Europe PMC",
                }
            ],
            "relationships": [],
        }
        g = annotations_to_rdf(parsed)
        # Should have at least some triples
        assert len(g) > 0

    def test_entity_with_http_article_uri(self):
        """article_uri starting with http:// triggers OA.hasTarget with URIRef (l.300-304)."""
        parsed = {
            "entities": [
                {
                    "id": "DOID:12365",
                    "name": "malaria",
                    "type": "Disease",
                    "exact": "malaria",
                    "article_uri": "http://example.org/articles/PMC12345",
                }
            ],
            "relationships": [],
        }
        g = annotations_to_rdf(parsed)
        assert len(g) > 0

    def test_entity_with_prefix_postfix(self):
        """Entity with prefix/postfix triggers VOCAB.textPrefix/Postfix (l.325-327)."""
        parsed = {
            "entities": [
                {
                    "id": "DOID:12365",
                    "name": "malaria",
                    "type": "Disease",
                    "exact": "malaria",
                    "section": "abstract",
                    "prefix": "text before ",
                    "postfix": " text after",
                }
            ],
            "relationships": [],
        }
        g = annotations_to_rdf(parsed)
        assert len(g) > 0

    def test_entity_without_exact(self):
        """Entity missing exact triggers entity_name fallback (l.319)."""
        parsed = {
            "entities": [
                {
                    "id": "DOID:12365",
                    "name": "malaria",
                    "type": "Disease",
                    "section": "abstract",
                    # no "exact" key
                }
            ],
            "relationships": [],
        }
        g = annotations_to_rdf(parsed)
        assert len(g) > 0


class TestAnnotationsToEntitiesEdgeCases:
    """Edge case tests for annotations_to_entities."""

    def _get_ann_mod(self):
        """Get annotations_to_rdf module via sys.modules (avoids __init__ shadowing)."""
        import sys

        return sys.modules["pyeuropepmc.processing.annotations_to_rdf"]

    def test_entity_conversion_failure(self, monkeypatch):
        """Test exception handling in entity loop (l.149-153)."""
        mod = self._get_ann_mod()

        def failing_entity(d: dict):
            raise ValueError("bad entity")

        monkeypatch.setattr(mod, "entity_annotation_to_model", failing_entity)
        parsed = {
            "entities": [{"id": "BAD"}],
            "relationships": [],
        }
        entities = annotations_to_entities(parsed)
        assert len(entities) == 0  # entity failed but didn't crash

    def test_relationship_conversion_failure(self, monkeypatch):
        """Test exception handling in relationship loop (l.160-164)."""
        mod = self._get_ann_mod()

        def failing_rel(d: dict):
            raise ValueError("bad relation")

        monkeypatch.setattr(mod, "relationship_annotation_to_model", failing_rel)
        parsed = {
            "entities": [],
            "relationships": [{"subject": {}, "object": {}}],
        }
        entities = annotations_to_entities(parsed)
        assert len(entities) == 0  # relationship failed but didn't crash


class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow(self, sample_parsed_annotations):
        """Test complete workflow from parsed annotations to RDF."""
        # Convert to entities
        entities = annotations_to_entities(sample_parsed_annotations)
        assert len(entities) > 0

        # Convert to RDF
        g = annotations_to_rdf(sample_parsed_annotations)
        assert len(g) > 0

        # Serialize to Turtle (shouldn't raise)
        turtle = g.serialize(format="turtle")
        assert isinstance(turtle, str)
        assert len(turtle) > 0
