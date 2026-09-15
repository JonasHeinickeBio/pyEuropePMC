"""Unit tests for SHACL validation shapes."""

from unittest.mock import MagicMock, patch

import pytest
from rdflib import Namespace

from pyeuropepmc.mappers.validation import add_shacl_validation_shapes


class TestAddShaclValidationShapes:
    """Tests for add_shacl_validation_shapes function."""

    @pytest.fixture
    def mock_config(self):
        """Mock RDF config utilities to return predictable namespaces."""
        with (
            patch("pyeuropepmc.mappers.validation.load_rdf_config") as mock_load,
            patch("pyeuropepmc.mappers.validation.get_namespace_from_config") as mock_get_ns,
        ):
            mock_config_dict = MagicMock()
            mock_load.return_value = mock_config_dict

            namespace_map = {
                "pyeuropepmc": Namespace("https://w3id.org/pyeuropepmc/vocab#"),
                "sh": Namespace("http://www.w3.org/ns/shacl#"),
                "fabio": Namespace("http://purl.org/spar/fabio/"),
                "ex": Namespace("http://example.org/data/"),
            }
            mock_get_ns.side_effect = lambda config, prefix: namespace_map[prefix]

            yield mock_load, mock_get_ns

    def test_normal_execution_adds_all_triples(self, mock_config):
        """Test that all 10 SHACL triples are added in normal execution."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        named_graph_uris = {"provenance": "http://example.org/prov"}

        add_shacl_validation_shapes(dataset, named_graph_uris)

        dataset.graph.assert_any_call("http://example.org/prov")
        assert dataset.graph.call_count == 10
        assert mock_graph.add.call_count == 10

    def test_adds_paper_shape_triples(self, mock_config):
        """Test paper shape triples: type, targetClass, and property refs."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_shacl_validation_shapes(dataset, {"provenance": "http://example.org/prov"})

        calls = mock_graph.add.call_args_list
        paper_shape_calls = [c for c in calls if "PaperShape" in str(c)]
        assert len(paper_shape_calls) == 4

    def test_adds_title_property_constraints(self, mock_config):
        """Test title property constraints: path, minCount, datatype."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_shacl_validation_shapes(dataset, {"provenance": "http://example.org/prov"})

        calls = mock_graph.add.call_args_list
        title_calls = [
            c for c in calls if "titleProperty" in str(c) and "PaperShape" not in str(c)
        ]
        assert len(title_calls) == 3

    def test_adds_doi_property_constraints(self, mock_config):
        """Test DOI property constraints: path, minCount, datatype."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_shacl_validation_shapes(dataset, {"provenance": "http://example.org/prov"})

        calls = mock_graph.add.call_args_list
        doi_calls = [c for c in calls if "doiProperty" in str(c) and "PaperShape" not in str(c)]
        assert len(doi_calls) == 3

    def test_empty_provenance_context(self, mock_config):
        """Test with empty provenance context string."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_shacl_validation_shapes(dataset, {"provenance": ""})

        dataset.graph.assert_any_call("")
        assert dataset.graph.call_count == 10
        assert mock_graph.add.call_count == 10

    def test_missing_provenance_key_raises_keyerror(self, mock_config):
        """Test that missing provenance key raises KeyError."""
        with pytest.raises(KeyError):
            add_shacl_validation_shapes(MagicMock(), {})
