"""
Unit tests for AnnotationParser.
"""

import pytest

from pyeuropepmc.processing.annotation_parser import (
    AnnotationParser,
    parse_annotations,
    extract_entities,
    extract_sentences,
    extract_relationships,
)


@pytest.fixture
def sample_entity_annotation():
    """Sample entity annotation in JSON-LD format."""
    return {
        "type": "entity",
        "exact": "malaria",
        "prefix": "The ",
        "postfix": " parasite",
        "section": "abstract",
        "position": {"start": 100, "end": 107},
        "tags": [
            {
                "uri": "DOID:12365",
                "name": "malaria",
                "type": "Disease",
                "confidence": 0.95,
            }
        ],
        "provider": {"name": "Europe PMC"},
    }


@pytest.fixture
def sample_sentence_annotation():
    """Sample sentence annotation in JSON-LD format."""
    return {
        "type": "sentence",
        "exact": "Malaria is a significant public health challenge.",
        "section": "abstract",
        "position": {"start": 0, "end": 50},
        "target": "PMC1234567",
        "provider": {"name": "Europe PMC"},
    }


@pytest.fixture
def sample_relationship_annotation():
    """Sample relationship annotation in JSON-LD format."""
    return {
        "type": "relationship",
        "relation": "associated_with",
        "exact": "TP53 is associated with cancer development.",
        "section": "body",
        "tags": [
            {
                "uri": "GENE:7157",
                "name": "TP53",
                "type": "Gene",
            },
            {
                "uri": "DOID:162",
                "name": "cancer",
                "type": "Disease",
            },
        ],
        "provider": {"name": "Europe PMC"},
    }


@pytest.fixture
def sample_annotations_response():
    """Sample complete annotations response."""
    return {
        "annotations": [
            {
                "type": "entity",
                "exact": "malaria",
                "tags": [
                    {
                        "uri": "DOID:12365",
                        "name": "malaria",
                        "type": "Disease",
                    }
                ],
                "section": "abstract",
                "provider": {"name": "Europe PMC"},
            },
            {
                "type": "sentence",
                "exact": "Malaria is a disease.",
                "section": "abstract",
                "target": "PMC1234567",
                "provider": {"name": "Europe PMC"},
            },
        ],
        "totalCount": 2,
        "page": 1,
        "pageSize": 25,
    }


class TestAnnotationParserParse:
    """Test AnnotationParser.parse_annotations method."""

    def test_parse_valid_response(self, sample_annotations_response):
        """Test parsing a valid annotation response."""
        result = AnnotationParser.parse_annotations(sample_annotations_response)

        assert isinstance(result, dict)
        assert "entities" in result
        assert "sentences" in result
        assert "relationships" in result
        assert "metadata" in result
        assert "raw" in result

    def test_parse_empty_response(self):
        """Test parsing an empty response."""
        result = AnnotationParser.parse_annotations({})

        assert result["entities"] == []
        assert result["sentences"] == []
        assert result["relationships"] == []

    def test_parse_invalid_response(self):
        """Test parsing an invalid response."""
        result = AnnotationParser.parse_annotations("invalid")

        assert result["entities"] == []
        assert result["sentences"] == []
        assert result["relationships"] == []

    def test_parse_metadata_extraction(self, sample_annotations_response):
        """Test metadata extraction from response."""
        result = AnnotationParser.parse_annotations(sample_annotations_response)

        metadata = result["metadata"]
        assert metadata["total_count"] == 2
        assert metadata["page"] == 1
        assert metadata["page_size"] == 25


class TestExtractEntities:
    """Test AnnotationParser.extract_entities method."""

    def test_extract_entity_success(self, sample_entity_annotation):
        """Test extracting a valid entity annotation."""
        entities = AnnotationParser.extract_entities([sample_entity_annotation])

        assert len(entities) == 1
        entity = entities[0]
        assert entity["id"] == "DOID:12365"
        assert entity["name"] == "malaria"
        assert entity["type"] == "Disease"
        assert entity["exact"] == "malaria"
        assert entity["section"] == "abstract"
        assert entity["provider"] == "Europe PMC"
        assert entity["confidence"] == 0.95

    def test_extract_entity_with_position(self, sample_entity_annotation):
        """Test extracting entity with position information."""
        entities = AnnotationParser.extract_entities([sample_entity_annotation])

        assert len(entities) == 1
        assert "position" in entities[0]
        assert entities[0]["position"]["start"] == 100
        assert entities[0]["position"]["end"] == 107

    def test_extract_entities_empty_list(self):
        """Test extracting from empty list."""
        entities = AnnotationParser.extract_entities([])
        assert entities == []

    def test_extract_entities_no_tags(self):
        """Test extracting from annotation without tags."""
        annotation = {
            "type": "entity",
            "exact": "test",
            "tags": [],
        }
        entities = AnnotationParser.extract_entities([annotation])
        assert entities == []

    def test_extract_entities_invalid_annotation(self):
        """Test extracting from invalid annotation."""
        entities = AnnotationParser.extract_entities(["invalid"])
        assert entities == []


class TestExtractSentences:
    """Test AnnotationParser.extract_sentences method."""

    def test_extract_sentence_success(self, sample_sentence_annotation):
        """Test extracting a valid sentence annotation."""
        sentences = AnnotationParser.extract_sentences([sample_sentence_annotation])

        assert len(sentences) == 1
        sentence = sentences[0]
        assert sentence["text"] == "Malaria is a significant public health challenge."
        assert sentence["section"] == "abstract"
        assert sentence["provider"] == "Europe PMC"

    def test_extract_sentence_with_position(self, sample_sentence_annotation):
        """Test extracting sentence with position information."""
        sentences = AnnotationParser.extract_sentences([sample_sentence_annotation])

        assert len(sentences) == 1
        assert "position" in sentences[0]

    def test_extract_sentences_empty_list(self):
        """Test extracting from empty list."""
        sentences = AnnotationParser.extract_sentences([])
        assert sentences == []

    def test_extract_sentences_no_target(self):
        """Test extracting from annotation without target."""
        annotation = {
            "type": "entity",
            "exact": "test",
        }
        sentences = AnnotationParser.extract_sentences([annotation])
        assert sentences == []


class TestExtractRelationships:
    """Test AnnotationParser.extract_relationships method."""

    def test_extract_relationship_success(self, sample_relationship_annotation):
        """Test extracting a valid relationship annotation."""
        relationships = AnnotationParser.extract_relationships(
            [sample_relationship_annotation]
        )

        assert len(relationships) == 1
        rel = relationships[0]
        assert rel["subject"]["id"] == "GENE:7157"
        assert rel["subject"]["name"] == "TP53"
        assert rel["subject"]["type"] == "Gene"
        assert rel["predicate"] == "associated_with"
        assert rel["object"]["id"] == "DOID:162"
        assert rel["object"]["name"] == "cancer"
        assert rel["object"]["type"] == "Disease"

    def test_extract_relationships_empty_list(self):
        """Test extracting from empty list."""
        relationships = AnnotationParser.extract_relationships([])
        assert relationships == []

    def test_extract_relationships_insufficient_tags(self):
        """Test extracting from annotation with insufficient tags."""
        annotation = {
            "type": "relationship",
            "tags": [{"uri": "GENE:7157"}],  # Only one tag
        }
        relationships = AnnotationParser.extract_relationships([annotation])
        assert relationships == []

    def test_extract_relationships_no_relation_type(self):
        """Test extracting relationship without explicit relation type."""
        annotation = {
            "type": "relationship",
            "exact": "TP53 and cancer",
            "tags": [
                {"uri": "GENE:7157", "name": "TP53", "type": "Gene"},
                {"uri": "DOID:162", "name": "cancer", "type": "Disease"},
            ],
        }
        relationships = AnnotationParser.extract_relationships([annotation])

        assert len(relationships) == 1
        # Should default to "related_to" if no explicit predicate
        assert relationships[0]["predicate"] == "related_to"


class TestHelperFunctions:
    """Test helper extraction functions."""

    def test_extract_entity_type_from_uri(self):
        """Test extracting entity type from URI."""
        tag = {"uri": "CHEBI:16236"}
        entity_type = AnnotationParser._extract_entity_type(tag)
        assert entity_type == "CHEBI"

    def test_extract_entity_type_from_type_field(self):
        """Test extracting entity type from type field."""
        tag = {"type": "Disease", "uri": "DOID:12365"}
        entity_type = AnnotationParser._extract_entity_type(tag)
        assert entity_type == "Disease"

    def test_extract_provider_from_dict(self):
        """Test extracting provider from dictionary."""
        annotation = {"provider": {"name": "Europe PMC"}}
        provider = AnnotationParser._extract_provider(annotation)
        assert provider == "Europe PMC"

    def test_extract_provider_from_string(self):
        """Test extracting provider from string."""
        annotation = {"provider": "Europe PMC"}
        provider = AnnotationParser._extract_provider(annotation)
        assert provider == "Europe PMC"

    def test_extract_provider_fallback(self):
        """Test fallback provider extraction."""
        annotation = {}
        provider = AnnotationParser._extract_provider(annotation)
        assert provider == "Unknown"

    def test_extract_metadata(self):
        """Test metadata extraction."""
        response = {
            "totalCount": 100,
            "page": 2,
            "pageSize": 50,
            "version": "1.0",
            "source": "Europe PMC",
        }
        metadata = AnnotationParser._extract_metadata(response)

        assert metadata["total_count"] == 100
        assert metadata["page"] == 2
        assert metadata["page_size"] == 50
        assert metadata["version"] == "1.0"
        assert metadata["source"] == "Europe PMC"


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_parse_annotations_function(self, sample_annotations_response):
        """Test parse_annotations convenience function."""
        result = parse_annotations(sample_annotations_response)
        assert isinstance(result, dict)
        assert "entities" in result

    def test_extract_entities_function(self, sample_entity_annotation):
        """Test extract_entities convenience function."""
        entities = extract_entities([sample_entity_annotation])
        assert len(entities) == 1

    def test_extract_sentences_function(self, sample_sentence_annotation):
        """Test extract_sentences convenience function."""
        sentences = extract_sentences([sample_sentence_annotation])
        assert len(sentences) == 1

    def test_extract_relationships_function(self, sample_relationship_annotation):
        """Test extract_relationships convenience function."""
        relationships = extract_relationships([sample_relationship_annotation])
        assert len(relationships) == 1


class TestEntityExtractionContext:
    """Test entity extraction with context from target (JSON-LD format)."""

    def test_extract_entity_with_target_context(self):
        """Test extracting entity with target context (JSON-LD format)."""
        annotation = {
            "id": "http://europepmc.org/article/MED/9050854#phenebank-4336f204e03abb0fee2d9017eb5802e1",
            "type": "Cell",
            "creator": "PheneBank",
            "body": "http://browser.ihtsdotools.org/?perspective=full&conceptId1=4421005",
            "target": {
                "source": "http://europepmc.org/article/MED/9050854",
                "isPartOf": "Abstract",
                "selector": {
                    "type": "TextQuoteSelector",
                    "exact": "cell",
                    "prefix": "which an inactivated ",
                    "suffix": " can inactivate adjacent",
                },
            },
            "exact": "cell",
            "annotation_id": "http://europepmc.org/article/MED/9050854#phenebank-4336f204e03abb0fee2d9017eb5802e1",
        }
        entities = AnnotationParser.extract_entities([annotation])

        assert len(entities) == 1
        entity = entities[0]

        # Test entity type from IRI domain
        assert entity["type"] == "SNOMED_CT"

        # Test name from exact text
        assert entity["name"] == "cell"

        # Test prefix/postfix from selector
        assert entity["prefix"] == "which an inactivated "
        assert entity["postfix"] == " can inactivate adjacent"

        # Test section from target
        assert entity["section"] == "Abstract"

        # Test provider from creator
        assert entity["provider"] == "PheneBank"

        # Test article_id from target source
        assert entity["article_id"] == "http://europepmc.org/article/MED/9050854"

    def test_extract_entity_type_from_identifiers_org(self):
        """Test extracting type from identifiers.org IRI."""
        tag = {"uri": "http://identifiers.org/taxonomy/9606"}
        entity_type = AnnotationParser._extract_entity_type(tag)
        assert entity_type == "Taxonomy"

    def test_extract_entity_type_from_chebi(self):
        """Test extracting CHEBI type from IRI."""
        tag = {"uri": "http://identifiers.org/chebi:123"}
        entity_type = AnnotationParser._extract_entity_type(tag)
        assert entity_type == "CHEBI"

    def test_extract_entity_type_from_doid(self):
        """Test extracting DOID (Disease) type from IRI."""
        tag = {"uri": "http://identifiers.org/doid:123"}
        entity_type = AnnotationParser._extract_entity_type(tag)
        assert entity_type == "Disease"

    def test_extract_provider_from_creator(self):
        """Test extracting provider from creator field (JSON-LD format)."""
        annotation = {"creator": "Europe PMC"}
        provider = AnnotationParser._extract_provider(annotation)
        assert provider == "Europe PMC"

    def test_extract_provider_from_creator_dict(self):
        """Test extracting provider from creator dict."""
        annotation = {"creator": {"name": "Europe PMC"}}
        provider = AnnotationParser._extract_provider(annotation)
        assert provider == "Europe PMC"

    def test_extract_provider_creator_fallback(self):
        """Test provider extraction with creator as fallback."""
        annotation = {"creator": "Europe PMC"}
        provider = AnnotationParser._extract_provider(annotation)
        assert provider == "Europe PMC"

    def test_extract_provider_priority(self):
        """Test provider extraction priority: provider > creator > annotator."""
        # Provider takes priority
        annotation = {
            "provider": "PriorityProvider",
            "creator": "CreatorProvider",
        }
        provider = AnnotationParser._extract_provider(annotation)
        assert provider == "PriorityProvider"
