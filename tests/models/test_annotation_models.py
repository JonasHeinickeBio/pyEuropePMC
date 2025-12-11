"""
Tests for annotation entity models.
"""

import pytest
from rdflib import Graph

from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.models.annotation import (
    AnnotationEntity,
    EntityAnnotation,
    RelationshipAnnotation,
)


class TestAnnotationEntity:
    """Test AnnotationEntity model."""

    def test_create_annotation_entity(self):
        """Test creating an annotation entity."""
        annotation = AnnotationEntity(
            exact="malaria",
            section="abstract",
            provider="Europe PMC",
            annotation_type="entity",
        )
        assert annotation.exact == "malaria"
        assert annotation.section == "abstract"
        assert annotation.provider == "Europe PMC"

    def test_annotation_entity_validation(self):
        """Test validation of annotation entity."""
        annotation = AnnotationEntity(exact="test", section="abstract")
        annotation.validate()  # Should not raise

        invalid_annotation = AnnotationEntity(section="abstract")
        with pytest.raises(ValueError, match="must have 'exact' text"):
            invalid_annotation.validate()

    def test_annotation_entity_to_dict(self):
        """Test converting annotation entity to dictionary."""
        annotation = AnnotationEntity(
            exact="malaria", section="abstract", provider="Europe PMC"
        )
        data = annotation.to_dict()
        assert data["exact"] == "malaria"
        assert data["section"] == "abstract"


class TestEntityAnnotation:
    """Test EntityAnnotation model."""

    def test_create_entity_annotation(self):
        """Test creating an entity annotation."""
        entity = EntityAnnotation(
            exact="malaria",
            entity_id="DOID:12365",
            entity_name="malaria",
            entity_type="Disease",
            section="abstract",
            provider="Europe PMC",
            confidence=0.95,
        )
        assert entity.entity_id == "DOID:12365"
        assert entity.entity_name == "malaria"
        assert entity.entity_type == "Disease"
        assert entity.confidence == 0.95

    def test_entity_annotation_validation(self):
        """Test validation of entity annotation."""
        valid_entity = EntityAnnotation(
            exact="malaria", entity_id="DOID:12365", section="abstract"
        )
        valid_entity.validate()  # Should not raise

        invalid_entity = EntityAnnotation(exact="malaria", section="abstract")
        with pytest.raises(ValueError, match="must have entity_id or entity_name"):
            invalid_entity.validate()

    def test_entity_annotation_with_position(self):
        """Test entity annotation with position information."""
        entity = EntityAnnotation(
            exact="malaria",
            entity_id="DOID:12365",
            entity_name="malaria",
            section="abstract",
            position={"start": 100, "end": 107},
        )
        assert entity.position["start"] == 100
        assert entity.position["end"] == 107


class TestRelationshipAnnotation:
    """Test RelationshipAnnotation model."""

    def test_create_relationship_annotation(self):
        """Test creating a relationship annotation."""
        relationship = RelationshipAnnotation(
            exact="TP53 is associated with cancer",
            subject_id="GENE:7157",
            subject_name="TP53",
            subject_type="Gene",
            predicate="associated_with",
            object_id="DOID:162",
            object_name="cancer",
            object_type="Disease",
            section="body",
        )
        assert relationship.subject_id == "GENE:7157"
        assert relationship.predicate == "associated_with"
        assert relationship.object_id == "DOID:162"

    def test_relationship_annotation_validation(self):
        """Test validation of relationship annotation."""
        valid_rel = RelationshipAnnotation(
            exact="test",
            subject_id="GENE:7157",
            object_id="DOID:162",
            section="body",
        )
        valid_rel.validate()  # Should not raise

        # Missing subject
        invalid_rel = RelationshipAnnotation(
            exact="test", object_id="DOID:162", section="body"
        )
        with pytest.raises(ValueError, match="must have subject_id or subject_name"):
            invalid_rel.validate()

        # Missing object
        invalid_rel2 = RelationshipAnnotation(
            exact="test", subject_id="GENE:7157", section="body"
        )
        with pytest.raises(ValueError, match="must have object_id or object_name"):
            invalid_rel2.validate()


class TestAnnotationRDF:
    """Test RDF conversion for annotations."""

    def test_entity_annotation_to_rdf(self):
        """Test converting entity annotation to RDF."""
        entity = EntityAnnotation(
            exact="malaria",
            entity_id="DOID:12365",
            entity_name="malaria",
            entity_type="Disease",
            section="abstract",
            provider="Europe PMC",
        )

        g = Graph()
        mapper = RDFMapper()
        uri = entity.to_rdf(g, mapper=mapper)

        # Verify the graph contains triples
        assert len(g) > 0
        assert uri is not None

    def test_relationship_annotation_to_rdf(self):
        """Test converting relationship annotation to RDF."""
        relationship = RelationshipAnnotation(
            exact="TP53 is associated with cancer",
            subject_id="GENE:7157",
            subject_name="TP53",
            predicate="associated_with",
            object_id="DOID:162",
            object_name="cancer",
            section="body",
        )

        g = Graph()
        mapper = RDFMapper()
        uri = relationship.to_rdf(g, mapper=mapper)

        # Verify the graph contains triples
        assert len(g) > 0
        assert uri is not None
