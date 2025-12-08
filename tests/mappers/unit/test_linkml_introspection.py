"""
Tests for LinkML schema introspection module.

These tests verify that the LinkML schema can be loaded and introspected
to extract mappings for RDF conversion.
"""

import pytest

from pyeuropepmc.mappers.linkml_introspection import (
    LINKML_AVAILABLE,
    LinkMLSchemaIntrospector,
    get_class_mapping,
    get_schema_view,
    get_slot_mapping,
)


# Skip all tests if LinkML is not available
pytestmark = pytest.mark.skipif(
    not LINKML_AVAILABLE, reason="LinkML runtime not available"
)


class TestLinkMLSchemaIntrospector:
    """Tests for the LinkMLSchemaIntrospector class."""

    @pytest.fixture
    def introspector(self) -> LinkMLSchemaIntrospector:
        """Get a schema introspector instance."""
        return LinkMLSchemaIntrospector()

    def test_is_available(self, introspector: LinkMLSchemaIntrospector) -> None:
        """Test that LinkML introspection is available."""
        assert introspector.is_available is True

    def test_get_all_classes(self, introspector: LinkMLSchemaIntrospector) -> None:
        """Test getting all class names from schema."""
        classes = introspector.get_all_classes()
        assert len(classes) > 0
        assert "PaperEntity" in classes
        assert "AuthorEntity" in classes
        assert "InstitutionEntity" in classes

    def test_get_class_mapping_paper(
        self, introspector: LinkMLSchemaIntrospector
    ) -> None:
        """Test getting mapping for PaperEntity."""
        mapping = introspector.get_class_mapping("PaperEntity")

        assert mapping is not None
        assert "class_uri" in mapping
        assert "fields" in mapping
        assert "relationships" in mapping

        # Check specific fields exist
        assert "title" in mapping["fields"] or "title" in introspector.get_all_slots_for_class("PaperEntity")
        assert "doi" in mapping["fields"] or "doi" in introspector.get_all_slots_for_class("PaperEntity")

    def test_get_class_mapping_author(
        self, introspector: LinkMLSchemaIntrospector
    ) -> None:
        """Test getting mapping for AuthorEntity."""
        mapping = introspector.get_class_mapping("AuthorEntity")

        assert mapping is not None
        assert "class_uri" in mapping
        assert "fields" in mapping

    def test_get_class_mapping_nonexistent(
        self, introspector: LinkMLSchemaIntrospector
    ) -> None:
        """Test getting mapping for non-existent class returns empty dict."""
        mapping = introspector.get_class_mapping("NonExistentEntity")
        assert mapping == {}

    def test_get_slot_mapping(self, introspector: LinkMLSchemaIntrospector) -> None:
        """Test getting mapping for a specific slot."""
        mapping = introspector.get_slot_mapping("title")

        assert mapping is not None
        assert "predicate" in mapping
        assert "range" in mapping

    def test_get_namespaces(self, introspector: LinkMLSchemaIntrospector) -> None:
        """Test getting namespace prefixes from schema."""
        namespaces = introspector.get_namespaces()

        assert len(namespaces) > 0
        assert "dcterms" in namespaces
        assert "foaf" in namespaces
        assert "bibo" in namespaces

    def test_build_namespaces(self, introspector: LinkMLSchemaIntrospector) -> None:
        """Test building Namespace objects from prefixes."""
        namespaces = introspector.build_namespaces()

        assert len(namespaces) > 0
        # Check that values are Namespace objects
        for ns in namespaces.values():
            assert hasattr(ns, "__getitem__")  # Namespace objects support indexing

    def test_get_namespace(self, introspector: LinkMLSchemaIntrospector) -> None:
        """Test getting a specific namespace."""
        ns = introspector.get_namespace("dcterms")
        assert ns is not None

    def test_resolve_predicate(self, introspector: LinkMLSchemaIntrospector) -> None:
        """Test resolving a CURIE to full URI."""
        uri = introspector.resolve_predicate("dcterms:title")
        assert uri is not None
        assert "title" in uri

    def test_get_entity_types(self, introspector: LinkMLSchemaIntrospector) -> None:
        """Test getting RDF types for a class."""
        types = introspector.get_entity_types("PaperEntity")
        assert len(types) > 0

    def test_get_inheritance_chain(
        self, introspector: LinkMLSchemaIntrospector
    ) -> None:
        """Test getting the inheritance chain for a class."""
        chain = introspector.get_inheritance_chain("PaperEntity")

        assert "PaperEntity" in chain
        assert "ScholarlyWorkEntity" in chain
        assert "BaseEntity" in chain

    def test_get_all_slots_for_class(
        self, introspector: LinkMLSchemaIntrospector
    ) -> None:
        """Test getting all slots including inherited ones."""
        slots = introspector.get_all_slots_for_class("PaperEntity")

        assert len(slots) > 0
        # Should include inherited slots from ScholarlyWorkEntity
        assert "title" in slots or "doi" in slots


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_schema_view(self) -> None:
        """Test that schema view can be obtained."""
        schema_view = get_schema_view()
        assert schema_view is not None

    def test_get_slot_mapping_convenience(self) -> None:
        """Test convenience function for slot mapping."""
        mapping = get_slot_mapping("title")
        assert mapping is not None
        assert "predicate" in mapping

    def test_get_class_mapping_convenience(self) -> None:
        """Test convenience function for class mapping."""
        mapping = get_class_mapping("AuthorEntity")
        assert mapping is not None
        assert "class_uri" in mapping


class TestSchemaValidation:
    """Tests for entity validation against schema."""

    @pytest.fixture
    def introspector(self) -> LinkMLSchemaIntrospector:
        """Get a schema introspector instance."""
        return LinkMLSchemaIntrospector()

    def test_validate_entity_no_errors(
        self, introspector: LinkMLSchemaIntrospector
    ) -> None:
        """Test validation of a valid entity returns no errors."""
        # Create a mock entity with required fields
        class MockAuthor:
            full_name = "John Doe"

        errors = introspector.validate_entity(MockAuthor(), "AuthorEntity")
        # Should have no required field errors since full_name is provided
        required_errors = [e for e in errors if "required" in e.lower()]
        assert len(required_errors) == 0

    def test_validate_entity_pattern_error(
        self, introspector: LinkMLSchemaIntrospector
    ) -> None:
        """Test validation catches pattern mismatches."""
        class MockAuthor:
            full_name = "John Doe"
            orcid = "invalid-orcid"  # Should match ORCID pattern

        errors = introspector.validate_entity(MockAuthor(), "AuthorEntity")
        # Should report pattern mismatch for orcid
        pattern_errors = [e for e in errors if "pattern" in e.lower()]
        assert len(pattern_errors) > 0
