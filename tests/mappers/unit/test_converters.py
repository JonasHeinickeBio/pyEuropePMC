"""Unit tests for RDF converters."""

import pytest
from unittest.mock import Mock, patch
from rdflib import Graph

from pyeuropepmc.cache.cache import CacheDataType
from pyeuropepmc.mappers.converters import (
    RDFConversionError,
    _convert_to_rdf,
    convert_search_to_rdf,
    convert_xml_to_rdf,
    convert_enrichment_to_rdf,
    convert_pipeline_to_rdf,
    convert_incremental_to_rdf,
)
from pyeuropepmc.mappers.validators import (
    validate_search_results,
    validate_xml_data,
    validate_enrichment_data,
)
from pyeuropepmc.mappers.processors import (
    process_search_results,
    process_xml_data,
    process_enrichment_data,
)
from pyeuropepmc.models import PaperEntity, AuthorEntity, JournalEntity


class TestConvertersValidation:
    """Tests for validation functions."""

    def test_validate_search_results_valid(self):
        """Test validation of valid search results."""
        valid_data = [{"doi": "10.1234/test", "title": "Test"}]
        validate_search_results(valid_data)  # Should not raise

    def test_validate_search_results_empty(self):
        """Test validation of empty search results."""
        with pytest.raises(RDFConversionError, match="Search results cannot be empty"):
            validate_search_results([])

    def test_validate_search_results_invalid_type(self):
        """Test validation of invalid search results type."""
        with pytest.raises(RDFConversionError, match="Search results must be a list or dict"):
            validate_search_results("invalid")

    def test_validate_xml_data_valid(self):
        """Test validation of valid XML data."""
        valid_data = {"paper": {"title": "Test"}}
        validate_xml_data(valid_data)  # Should not raise

    def test_validate_xml_data_empty(self):
        """Test validation of empty XML data."""
        with pytest.raises(RDFConversionError, match="XML data cannot be empty"):
            validate_xml_data({})

    def test_validate_enrichment_data_valid(self):
        """Test validation of valid enrichment data."""
        valid_data = {"paper": {"title": "Test"}}
        validate_enrichment_data(valid_data)  # Should not raise

    def test_validate_enrichment_data_empty(self):
        """Test validation of empty enrichment data."""
        with pytest.raises(RDFConversionError, match="Enrichment data cannot be empty"):
            validate_enrichment_data({})


class TestConvertersProcessing:
    """Tests for data processing functions."""

    def test_process_search_results_single_dict(self):
        """Test processing single search result dict."""
        search_data = {
            "doi": "10.1234/test",
            "title": "Test Paper",
            "journalTitle": "Test Journal",
            "pubYear": 2024,
        }

        entities_data = process_search_results(search_data)

        assert len(entities_data) == 1
        entity_data = entities_data[0]
        assert isinstance(entity_data["entity"], PaperEntity)
        assert entity_data["entity"].doi == "10.1234/test"
        assert entity_data["entity"].title == "Test Paper"
        assert isinstance(entity_data["entity"].journal, JournalEntity)
        assert entity_data["entity"].journal.title == "Test Journal"
        assert entity_data["entity"].publication_year == 2024

    def test_process_search_results_list(self):
        """Test processing list of search results."""
        search_data = [
            {"doi": "10.1234/test1", "title": "Paper 1"},
            {"doi": "10.1234/test2", "title": "Paper 2"},
        ]

        entities_data = process_search_results(search_data)

        assert len(entities_data) == 2
        assert all(isinstance(ed["entity"], PaperEntity) for ed in entities_data)
        assert entities_data[0]["entity"].doi == "10.1234/test1"
        assert entities_data[1]["entity"].doi == "10.1234/test2"

    def test_process_search_results_with_missing_fields(self):
        """Test processing search results with missing optional fields."""
        search_data = {"title": "Test Paper"}  # Missing DOI, journal, etc.

        entities_data = process_search_results(search_data)

        assert len(entities_data) == 1
        entity = entities_data[0]["entity"]
        assert entity.title == "Test Paper"
        assert entity.doi is None
        assert entity.journal is None

    def test_process_xml_data(self):
        """Test processing XML data."""
        xml_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": "Test Journal",
                "publication_year": 2024,
            },
            "authors": [{"full_name": "John Doe"}],
            "sections": [{"title": "Introduction"}],
        }

        entities_data = process_xml_data(xml_data, include_content=True)

        assert len(entities_data) == 1
        entity_data = entities_data[0]
        assert isinstance(entity_data["entity"], PaperEntity)
        assert entity_data["entity"].doi == "10.1234/test"

        # Check related entities
        related = entity_data["related_entities"]
        assert "authors" in related
        assert "sections" in related
        assert "tables" in related

    def test_process_xml_data_exclude_content(self):
        """Test processing XML data excluding content entities."""
        xml_data = {
            "paper": {"title": "Test Paper"},
            "sections": [{"title": "Introduction"}],
            "tables": [{"caption": "Table 1"}],
        }

        entities_data = process_xml_data(xml_data, include_content=False)

        assert len(entities_data) == 1
        related = entities_data[0]["related_entities"]
        assert len(related["sections"]) == 0  # Should be excluded
        assert len(related["tables"]) == 0  # Should be excluded

    def test_process_enrichment_data_paper_level(self):
        """Test processing enrichment data at paper level."""
        enrichment_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": "Test Journal",
            },
            "authors": [{"full_name": "John Doe"}],
        }

        entities_data = process_enrichment_data(enrichment_data)

        assert len(entities_data) == 1
        entity_data = entities_data[0]
        assert isinstance(entity_data["entity"], PaperEntity)
        assert entity_data["entity"].doi == "10.1234/test"

    def test_process_enrichment_data_author_level(self):
        """Test processing enrichment data at author level."""
        enrichment_data = {
            "authors": [
                {"full_name": "John Doe", "orcid": "0000-0001-2345-6789"},
                {"full_name": "Jane Smith", "orcid": "0000-0002-3456-7890"},
            ]
        }

        entities_data = process_enrichment_data(enrichment_data)

        assert len(entities_data) == 2
        assert all(isinstance(ed["entity"], AuthorEntity) for ed in entities_data)  # AuthorEntity objects


class TestConvertersGeneric:
    """Tests for the generic _convert_to_rdf function."""

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_graph")
    def test_convert_to_rdf_success(self, mock_setup_graph, mock_get_mapper):
        """Test successful conversion with generic function."""
        # Setup mocks
        mock_mapper = Mock()
        mock_graph = Mock()
        mock_get_mapper.return_value = mock_mapper
        mock_setup_graph.return_value = mock_graph

        # Mock entity with to_rdf method
        mock_entity = Mock()
        mock_entity.to_rdf.return_value = None

        # Test data
        data = {"test": "data"}
        validator = Mock()
        processor = Mock(return_value=[{"entity": mock_entity, "related_entities": {}}])

        result = _convert_to_rdf(
            data=data,
            validator=validator,
            processor=processor,
            cache_key_prefix="test",
            cache_data_type=CacheDataType.SEARCH,
        )

        # Verify calls
        validator.assert_called_once_with(data)
        processor.assert_called_once_with(data)
        mock_get_mapper.assert_called_once()
        mock_setup_graph.assert_called_once()
        mock_entity.to_rdf.assert_called_once()
        assert result == mock_graph

    def test_convert_to_rdf_validation_error(self):
        """Test conversion with validation error."""
        validator = Mock(side_effect=RDFConversionError("Validation failed"))

        with pytest.raises(RDFConversionError, match="Validation failed"):
            _convert_to_rdf(
                data={},
                validator=validator,
                processor=Mock(),
                cache_key_prefix="test",
                cache_data_type=CacheDataType.SEARCH,
            )

    def test_convert_to_rdf_processing_error(self):
        """Test conversion with processing error."""
        validator = Mock()
        processor = Mock(side_effect=Exception("Processing failed"))

        with pytest.raises(RDFConversionError, match="Failed to convert data to RDF"):
            _convert_to_rdf(
                data={"test": "data"},
                validator=validator,
                processor=processor,
                cache_key_prefix="test",
                cache_data_type=CacheDataType.SEARCH,
            )

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_graph")
    def test_convert_to_rdf_with_caching(self, mock_setup_graph, mock_get_mapper):
        """Test conversion with cache backend."""
        # Setup mocks
        mock_mapper = Mock()
        mock_graph = Mock()
        mock_cache = Mock()
        mock_get_mapper.return_value = mock_mapper
        mock_setup_graph.return_value = mock_graph

        mock_entity = Mock()
        mock_entity.to_rdf.return_value = None

        result = _convert_to_rdf(
            data={"test": "data"},
            validator=Mock(),
            processor=Mock(return_value=[{"entity": mock_entity, "related_entities": {}}]),
            cache_key_prefix="test",
            cache_data_type=CacheDataType.SEARCH,
            cache_backend=mock_cache,
        )

        # Verify caching was called
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][0].startswith("test_")  # cache key
        assert call_args[0][1] == mock_graph  # graph
        assert call_args[1]["data_type"] == CacheDataType.SEARCH  # data type in kwargs


class TestConvertersIndividual:
    """Tests for individual converter functions."""

    def test_convert_search_to_rdf_success(self):
        """Test successful search results conversion."""
        search_data = [{"doi": "10.1234/test", "title": "Test Paper"}]

        graph = convert_search_to_rdf(search_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0  # Should have triples

    def test_convert_search_to_rdf_empty_data(self):
        """Test search conversion with empty data."""
        with pytest.raises(RDFConversionError, match="Search results cannot be empty"):
            convert_search_to_rdf([])

    def test_convert_xml_to_rdf_success(self):
        """Test successful XML data conversion."""
        xml_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": "Test Journal",
            }
        }

        graph = convert_xml_to_rdf(xml_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_xml_to_rdf_empty_data(self):
        """Test XML conversion with empty data."""
        with pytest.raises(RDFConversionError, match="XML data cannot be empty"):
            convert_xml_to_rdf({})

    def test_convert_enrichment_to_rdf_success(self):
        """Test successful enrichment data conversion."""
        enrichment_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": "Test Journal",
            }
        }

        graph = convert_enrichment_to_rdf(enrichment_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_enrichment_to_rdf_empty_data(self):
        """Test enrichment conversion with empty data."""
        with pytest.raises(RDFConversionError, match="Enrichment data cannot be empty"):
            convert_enrichment_to_rdf({})

    def test_convert_pipeline_to_rdf_combined(self):
        """Test pipeline conversion with multiple data sources."""
        search_data = [{"doi": "10.1234/test", "title": "Test Paper"}]
        xml_data = {"paper": {"doi": "10.1234/test", "title": "Test Paper"}}
        enrichment_data = {"paper": {"doi": "10.1234/test", "title": "Test Paper"}}

        graph = convert_pipeline_to_rdf(
            search_results=search_data,
            xml_data=xml_data,
            enrichment_data=enrichment_data,
        )

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_pipeline_to_rdf_partial(self):
        """Test pipeline conversion with partial data."""
        search_data = [{"doi": "10.1234/test", "title": "Test Paper"}]

        graph = convert_pipeline_to_rdf(search_results=search_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_incremental_to_rdf_success(self):
        """Test successful incremental conversion."""
        base_graph = Graph()
        enrichment_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": "Test Journal",
            }
        }

        result_graph = convert_incremental_to_rdf(base_graph, enrichment_data)

        assert isinstance(result_graph, Graph)
        assert len(result_graph) > 0

    def test_convert_incremental_to_rdf_empty_enrichment(self):
        """Test incremental conversion with empty enrichment data."""
        base_graph = Graph()

        with pytest.raises(RDFConversionError, match="Enrichment data cannot be empty"):
            convert_incremental_to_rdf(base_graph, {})


class TestConvertersCaching:
    """Tests for caching behavior in converters."""

    @patch("pyeuropepmc.mappers.converters._convert_to_rdf")
    def test_convert_search_to_rdf_with_cache(self, mock_convert):
        """Test search conversion passes cache backend correctly."""
        mock_cache = Mock()
        mock_graph = Mock()
        mock_convert.return_value = mock_graph

        search_data = [{"doi": "10.1234/test", "title": "Test Paper"}]

        result = convert_search_to_rdf(search_data, cache_backend=mock_cache)

        mock_convert.assert_called_once()
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["cache_backend"] == mock_cache
        assert call_kwargs["cache_key_prefix"] == "search_rdf"
        assert call_kwargs["cache_data_type"] == CacheDataType.SEARCH
        assert result == mock_graph

    @patch("pyeuropepmc.mappers.converters._convert_to_rdf")
    def test_convert_xml_to_rdf_with_cache(self, mock_convert):
        """Test XML conversion passes cache backend correctly."""
        mock_cache = Mock()
        mock_graph = Mock()
        mock_convert.return_value = mock_graph

        xml_data = {"paper": {"title": "Test"}}

        result = convert_xml_to_rdf(xml_data, cache_backend=mock_cache)

        mock_convert.assert_called_once()
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["cache_backend"] == mock_cache
        assert call_kwargs["cache_key_prefix"] == "xml_rdf"
        assert call_kwargs["cache_data_type"] == CacheDataType.FULLTEXT

    @patch("pyeuropepmc.mappers.converters._convert_to_rdf")
    def test_convert_enrichment_to_rdf_with_cache(self, mock_convert):
        """Test enrichment conversion passes cache backend correctly."""
        mock_cache = Mock()
        mock_graph = Mock()
        mock_convert.return_value = mock_graph

        enrichment_data = {"paper": {"title": "Test"}}

        result = convert_enrichment_to_rdf(enrichment_data, cache_backend=mock_cache)

        mock_convert.assert_called_once()
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["cache_backend"] == mock_cache
        assert call_kwargs["cache_key_prefix"] == "enrichment_rdf"
        assert call_kwargs["cache_data_type"] == CacheDataType.RECORD


class TestConvertersNamespaces:
    """Tests for namespace handling in converters."""

    def test_convert_search_to_rdf_with_namespaces(self):
        """Test search conversion with custom namespaces."""
        search_data = [{"doi": "10.1234/test", "title": "Test Paper"}]
        custom_namespaces = {"custom": "http://example.org/custom#"}


        graph = convert_search_to_rdf(search_data, namespaces=custom_namespaces)

        assert isinstance(graph, Graph)
        # Check that custom namespace was bound
        namespace_uris = [str(ns[1]) for ns in graph.namespaces()]
        assert "http://example.org/custom#" in namespace_uris

    def test_convert_xml_to_rdf_with_namespaces(self):
        """Test XML conversion with custom namespaces."""
        xml_data = {"paper": {"title": "Test"}}
        custom_namespaces = {"custom": "http://example.org/custom#"}


        graph = convert_xml_to_rdf(xml_data, namespaces=custom_namespaces)

        assert isinstance(graph, Graph)
        namespace_uris = [str(ns[1]) for ns in graph.namespaces()]
        assert "http://example.org/custom#" in namespace_uris

    def test_convert_pipeline_to_rdf_with_namespaces(self):
        """Test pipeline conversion with custom namespaces."""
        search_data = [{"title": "Test"}]
        custom_namespaces = {"custom": "http://example.org/custom#"}


        graph = convert_pipeline_to_rdf(search_results=search_data, namespaces=custom_namespaces)

        assert isinstance(graph, Graph)
        namespace_uris = [str(ns[1]) for ns in graph.namespaces()]
        assert "http://example.org/custom#" in namespace_uris


class TestConvertersConfig:
    """Tests for configuration handling in converters."""

    @patch("pyeuropepmc.mappers.converters._convert_to_rdf")
    def test_convert_search_to_rdf_with_config(self, mock_convert):
        """Test search conversion passes config path correctly."""
        mock_graph = Mock()
        mock_convert.return_value = mock_graph

        search_data = [{"title": "Test"}]
        config_path = "/path/to/config.yml"

        result = convert_search_to_rdf(search_data, config_path=config_path)

        mock_convert.assert_called_once()
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["config_path"] == config_path

    @patch("pyeuropepmc.mappers.converters._convert_to_rdf")
    def test_convert_xml_to_rdf_with_config(self, mock_convert):
        """Test XML conversion passes config path correctly."""
        mock_graph = Mock()
        mock_convert.return_value = mock_graph

        xml_data = {"paper": {"title": "Test"}}
        config_path = "/path/to/config.yml"

        result = convert_xml_to_rdf(xml_data, config_path=config_path)

        mock_convert.assert_called_once()
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["config_path"] == config_path
