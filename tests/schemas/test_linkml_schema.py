"""
Unit tests for the LinkML schema.

These tests validate that the LinkML schema is correctly defined
and can generate various outputs (JSON Schema, SHACL, etc.).
"""

import pytest
from pathlib import Path

# Skip if linkml is not available
pytest.importorskip("linkml")
pytest.importorskip("linkml_runtime")


SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "pyeuropepmc_schema.yaml"


class TestLinkMLSchemaValidity:
    """Tests for LinkML schema validity."""

    def test_schema_file_exists(self) -> None:
        """Test that the schema file exists."""
        assert SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}"

    def test_schema_loads_successfully(self) -> None:
        """Test that the schema can be loaded by LinkML."""
        from linkml_runtime.loaders import yaml_loader
        from linkml_runtime.linkml_model import SchemaDefinition

        schema = yaml_loader.load(str(SCHEMA_PATH), target_class=SchemaDefinition)
        assert schema is not None
        assert schema.name == "pyeuropepmc"
        assert schema.id == "https://w3id.org/pyeuropepmc"

    def test_schema_view_loads(self) -> None:
        """Test that SchemaView can load the schema."""
        from linkml_runtime.utils.schemaview import SchemaView

        schema_view = SchemaView(str(SCHEMA_PATH))
        assert schema_view is not None

        # Verify basic schema properties
        assert schema_view.schema.name == "pyeuropepmc"
        assert schema_view.schema.version == "1.0.0"


class TestSchemaClasses:
    """Tests for LinkML schema class definitions."""

    @pytest.fixture
    def schema_view(self):
        """Fixture to provide a SchemaView instance."""
        from linkml_runtime.utils.schemaview import SchemaView

        return SchemaView(str(SCHEMA_PATH))

    def test_all_entity_classes_exist(self, schema_view) -> None:
        """Test that all expected entity classes are defined."""
        expected_classes = [
            "BaseEntity",
            "ScholarlyWorkEntity",
            "PaperEntity",
            "AuthorEntity",
            "SectionEntity",
            "TableEntity",
            "TableRowEntity",
            "ReferenceEntity",
            "InstitutionEntity",
            "JournalEntity",
            "GrantEntity",
            "FigureEntity",
        ]

        all_classes = schema_view.all_classes()
        for class_name in expected_classes:
            assert class_name in all_classes, f"Class {class_name} not found in schema"

    def test_paper_entity_has_expected_slots(self, schema_view) -> None:
        """Test that PaperEntity has expected slots."""
        paper_slots = schema_view.class_slots("PaperEntity")

        # Check for inherited slots from ScholarlyWorkEntity and BaseEntity
        expected_slots = [
            "title",
            "doi",
            "pmcid",
            "pmid",
            "abstract",
            "citation_count",
            "authors",
            "journal",
        ]

        for slot_name in expected_slots:
            assert slot_name in paper_slots, f"Slot {slot_name} not found in PaperEntity"

    def test_author_entity_has_expected_slots(self, schema_view) -> None:
        """Test that AuthorEntity has expected slots."""
        author_slots = schema_view.class_slots("AuthorEntity")

        expected_slots = [
            "full_name",
            "first_name",
            "last_name",
            "orcid",
            "email",
        ]

        for slot_name in expected_slots:
            assert slot_name in author_slots, f"Slot {slot_name} not found in AuthorEntity"

    def test_institution_entity_has_expected_slots(self, schema_view) -> None:
        """Test that InstitutionEntity has expected slots."""
        institution_slots = schema_view.class_slots("InstitutionEntity")

        expected_slots = [
            "display_name",
            "ror_id",
            "country",
            "city",
            "latitude",
            "longitude",
        ]

        for slot_name in expected_slots:
            assert slot_name in institution_slots, f"Slot {slot_name} not found in InstitutionEntity"


class TestSchemaPrefixes:
    """Tests for LinkML schema namespace prefixes."""

    @pytest.fixture
    def schema_view(self):
        """Fixture to provide a SchemaView instance."""
        from linkml_runtime.utils.schemaview import SchemaView

        return SchemaView(str(SCHEMA_PATH))

    def test_expected_prefixes_exist(self, schema_view) -> None:
        """Test that expected namespace prefixes are defined."""
        expected_prefixes = {
            "pyeuropepmc": "https://w3id.org/pyeuropepmc/vocab#",
            "dcterms": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
            "bibo": "http://purl.org/ontology/bibo/",
            "prov": "http://www.w3.org/ns/prov#",
            "cito": "http://purl.org/spar/cito/",
            "org": "http://www.w3.org/ns/org#",
        }

        schema_prefixes = schema_view.schema.prefixes

        for prefix, uri in expected_prefixes.items():
            assert prefix in schema_prefixes, f"Prefix {prefix} not found in schema"
            assert schema_prefixes[prefix].prefix_reference == uri, \
                f"Prefix {prefix} has unexpected URI: {schema_prefixes[prefix].prefix_reference}"


class TestSchemaEnums:
    """Tests for LinkML schema enum definitions."""

    @pytest.fixture
    def schema_view(self):
        """Fixture to provide a SchemaView instance."""
        from linkml_runtime.utils.schemaview import SchemaView

        return SchemaView(str(SCHEMA_PATH))

    def test_open_access_status_enum_exists(self, schema_view) -> None:
        """Test that OpenAccessStatus enum is defined."""
        enums = schema_view.all_enums()
        assert "OpenAccessStatus" in enums

        oa_enum = schema_view.get_enum("OpenAccessStatus")
        expected_values = ["open", "closed", "hybrid", "green", "gold", "bronze", "unknown"]

        for value in expected_values:
            assert value in oa_enum.permissible_values, f"Value {value} not found in OpenAccessStatus"

    def test_publication_type_enum_exists(self, schema_view) -> None:
        """Test that PublicationType enum is defined."""
        enums = schema_view.all_enums()
        assert "PublicationType" in enums

        pub_type_enum = schema_view.get_enum("PublicationType")
        expected_values = ["journal_article", "review", "preprint"]

        for value in expected_values:
            assert value in pub_type_enum.permissible_values, f"Value {value} not found in PublicationType"

    def test_institution_type_enum_exists(self, schema_view) -> None:
        """Test that InstitutionType enum is defined."""
        enums = schema_view.all_enums()
        assert "InstitutionType" in enums


class TestSchemaGenerators:
    """Tests for LinkML schema generator functionality."""

    def test_json_schema_generation(self) -> None:
        """Test that JSON Schema can be generated from the schema."""
        from linkml.generators.jsonschemagen import JsonSchemaGenerator

        generator = JsonSchemaGenerator(str(SCHEMA_PATH))
        json_schema = generator.serialize()

        assert json_schema is not None
        assert len(json_schema) > 0
        assert "$defs" in json_schema

    def test_shacl_generation(self) -> None:
        """Test that SHACL shapes can be generated from the schema."""
        from linkml.generators.shaclgen import ShaclGenerator

        generator = ShaclGenerator(str(SCHEMA_PATH))
        shacl = generator.serialize()

        assert shacl is not None
        assert len(shacl) > 0
        # SHACL output is in Turtle format
        assert "sh:property" in shacl or "@prefix sh:" in shacl

    def test_pydantic_generation(self) -> None:
        """Test that Pydantic models can be generated from the schema."""
        from linkml.generators.pydanticgen import PydanticGenerator

        generator = PydanticGenerator(str(SCHEMA_PATH))
        pydantic_code = generator.serialize()

        assert pydantic_code is not None
        assert len(pydantic_code) > 0
        assert "class" in pydantic_code
        assert "BaseModel" in pydantic_code


class TestSchemaInheritance:
    """Tests for LinkML schema class inheritance."""

    @pytest.fixture
    def schema_view(self):
        """Fixture to provide a SchemaView instance."""
        from linkml_runtime.utils.schemaview import SchemaView

        return SchemaView(str(SCHEMA_PATH))

    def test_paper_entity_inherits_from_scholarly_work(self, schema_view) -> None:
        """Test that PaperEntity inherits from ScholarlyWorkEntity."""
        paper_ancestors = schema_view.class_ancestors("PaperEntity")
        assert "ScholarlyWorkEntity" in paper_ancestors
        assert "BaseEntity" in paper_ancestors

    def test_reference_entity_inherits_from_scholarly_work(self, schema_view) -> None:
        """Test that ReferenceEntity inherits from ScholarlyWorkEntity."""
        ref_ancestors = schema_view.class_ancestors("ReferenceEntity")
        assert "ScholarlyWorkEntity" in ref_ancestors
        assert "BaseEntity" in ref_ancestors

    def test_author_entity_inherits_from_base_entity(self, schema_view) -> None:
        """Test that AuthorEntity inherits from BaseEntity."""
        author_ancestors = schema_view.class_ancestors("AuthorEntity")
        assert "BaseEntity" in author_ancestors

    def test_base_entity_is_abstract(self, schema_view) -> None:
        """Test that BaseEntity is marked as abstract."""
        base_entity = schema_view.get_class("BaseEntity")
        assert base_entity.abstract is True

    def test_scholarly_work_entity_is_abstract(self, schema_view) -> None:
        """Test that ScholarlyWorkEntity is marked as abstract."""
        scholarly_work = schema_view.get_class("ScholarlyWorkEntity")
        assert scholarly_work.abstract is True


class TestSchemaSlotConstraints:
    """Tests for LinkML schema slot constraints."""

    @pytest.fixture
    def schema_view(self):
        """Fixture to provide a SchemaView instance."""
        from linkml_runtime.utils.schemaview import SchemaView

        return SchemaView(str(SCHEMA_PATH))

    def test_confidence_has_range_constraints(self, schema_view) -> None:
        """Test that confidence slot has min/max value constraints."""
        confidence_slot = schema_view.get_slot("confidence")
        assert confidence_slot.minimum_value == 0.0
        assert confidence_slot.maximum_value == 1.0

    def test_citation_count_has_minimum_constraint(self, schema_view) -> None:
        """Test that citation_count slot has minimum value constraint."""
        citation_slot = schema_view.get_slot("citation_count")
        assert citation_slot.minimum_value == 0

    def test_orcid_has_pattern_constraint(self, schema_view) -> None:
        """Test that orcid slot has pattern constraint."""
        orcid_slot = schema_view.get_slot("orcid")
        assert orcid_slot.pattern is not None
        assert "\\d{4}" in orcid_slot.pattern  # ORCID pattern includes digit groups

    def test_pmcid_has_pattern_constraint(self, schema_view) -> None:
        """Test that pmcid slot has pattern constraint."""
        pmcid_slot = schema_view.get_slot("pmcid")
        assert pmcid_slot.pattern is not None
        assert "PMC" in pmcid_slot.pattern

    def test_latitude_has_range_constraints(self, schema_view) -> None:
        """Test that latitude slot has valid geographic range."""
        latitude_slot = schema_view.get_slot("latitude")
        assert latitude_slot.minimum_value == -90.0
        assert latitude_slot.maximum_value == 90.0

    def test_longitude_has_range_constraints(self, schema_view) -> None:
        """Test that longitude slot has valid geographic range."""
        longitude_slot = schema_view.get_slot("longitude")
        assert longitude_slot.minimum_value == -180.0
        assert longitude_slot.maximum_value == 180.0
