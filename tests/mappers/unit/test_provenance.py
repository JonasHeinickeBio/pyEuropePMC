"""Unit tests for provenance utilities."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from rdflib import Namespace, URIRef

from pyeuropepmc.mappers.provenance import (
    add_author_metadata,
    add_paper_metadata,
    add_provenance_and_metadata,
    add_quality_metrics,
)


class TestAddProvenanceAndMetadata:
    """Tests for add_provenance_and_metadata function."""

    @pytest.fixture
    def mock_config(self):
        """Mock config utilities to return predictable namespaces."""
        with (
            patch("pyeuropepmc.mappers.provenance.load_rdf_config") as mock_load,
            patch("pyeuropepmc.mappers.provenance.get_namespace_from_config") as mock_get_ns,
        ):
            mock_config_dict = MagicMock()
            mock_load.return_value = mock_config_dict

            namespace_map = {
                "pyeuropepmc": Namespace("https://w3id.org/pyeuropepmc/vocab#"),
                "ex": Namespace("http://example.org/data/"),
            }
            mock_get_ns.side_effect = lambda config, prefix: namespace_map[prefix]

            yield mock_load, mock_get_ns

    def test_adds_provenance_entities(self, mock_config):
        """Test that PROV-O entities and SoftwareAgent are added."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_provenance_and_metadata(dataset, {"provenance": "http://example.org/prov"})

        dataset.graph.assert_any_call("http://example.org/prov")
        assert dataset.graph.call_count == 7
        assert mock_graph.add.call_count == 7

    def test_adds_prov_type_triples(self, mock_config):
        """Test that prov:Entity and prov:SoftwareAgent type triples are added."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_provenance_and_metadata(dataset, {"provenance": "http://example.org/prov"})

        calls = mock_graph.add.call_args_list
        prov_type_calls = [
            c for c in calls if "prov#Entity" in str(c) or "prov#SoftwareAgent" in str(c)
        ]
        assert len(prov_type_calls) == 2

    def test_accepts_optional_extraction_info(self, mock_config):
        """Test that extraction_info parameter is accepted (currently unused)."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        extraction_info = {"source": "europepmc", "timestamp": "2024-01-01"}
        add_provenance_and_metadata(
            dataset, {"provenance": "http://example.org/prov"}, extraction_info
        )

        assert mock_graph.add.call_count == 7

    def test_empty_provenance_context(self, mock_config):
        """Test with empty provenance context string."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_provenance_and_metadata(dataset, {"provenance": ""})

        dataset.graph.assert_any_call("")
        assert dataset.graph.call_count == 7
        assert mock_graph.add.call_count == 7

    def test_no_extraction_info_defaults_to_none(self, mock_config):
        """Test that extraction_info defaults to None."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_provenance_and_metadata(dataset, {"provenance": "http://example.org/prov"})

        assert mock_graph.add.call_count == 7


class TestAddPaperMetadata:
    """Tests for add_paper_metadata function."""

    @pytest.fixture
    def mock_config(self):
        """Mock config and quality functions for paper metadata."""
        with (
            patch("pyeuropepmc.mappers.provenance.load_rdf_config") as mock_load,
            patch("pyeuropepmc.mappers.provenance.get_namespace_from_config") as mock_get_ns,
            patch(
                "pyeuropepmc.mappers.provenance.calculate_paper_quality_score"
            ) as mock_calc_score,
            patch("pyeuropepmc.mappers.provenance.get_confidence_level") as mock_conf_level,
        ):
            mock_config_dict = MagicMock()
            mock_load.return_value = mock_config_dict

            namespace_map = {
                "ex": Namespace("http://example.org/data/"),
                "europepmc": Namespace("https://europepmc.org/"),
            }
            mock_get_ns.side_effect = lambda config, prefix: namespace_map[prefix]

            mock_calc_score.return_value = 0.85
            mock_conf_level.return_value = "high"

            yield {
                "calc_paper_score": mock_calc_score,
                "conf_level": mock_conf_level,
            }

    def test_adds_metadata_without_cited_by_count(self, mock_config):
        """Test 4 triples added when entity has no cited_by_count."""
        paper_entity = SimpleNamespace(doi="10.1234/test")
        publications_graph = MagicMock()
        paper_uri = URIRef("http://example.org/paper/1")

        add_paper_metadata(paper_entity, publications_graph, paper_uri)

        assert publications_graph.add.call_count == 4

    def test_adds_metadata_with_cited_by_count(self, mock_config):
        """Test 5 triples added when entity has cited_by_count."""
        paper_entity = SimpleNamespace(doi="10.1234/test", cited_by_count=42)
        publications_graph = MagicMock()
        paper_uri = URIRef("http://example.org/paper/1")

        add_paper_metadata(paper_entity, publications_graph, paper_uri)

        assert publications_graph.add.call_count == 5

    def test_adds_mandatory_triples(self, mock_config):
        """Test dataSource, qualityScore, confidenceLevel, lastUpdated added."""
        paper_entity = SimpleNamespace(doi="10.1234/test")
        publications_graph = MagicMock()
        paper_uri = URIRef("http://example.org/paper/1")

        add_paper_metadata(paper_entity, publications_graph, paper_uri)

        calls = [str(c) for c in publications_graph.add.call_args_list]
        assert any("dataSource" in c for c in calls)
        assert any("qualityScore" in c for c in calls)
        assert any("confidenceLevel" in c for c in calls)
        assert any("lastUpdated" in c for c in calls)

    def test_adds_cited_by_count_when_present_and_truthy(self, mock_config):
        """Test citedByCount triple added when value is truthy."""
        paper_entity = SimpleNamespace(doi="10.1234/test", cited_by_count=10)
        publications_graph = MagicMock()
        paper_uri = URIRef("http://example.org/paper/1")

        add_paper_metadata(paper_entity, publications_graph, paper_uri)

        calls = [str(c) for c in publications_graph.add.call_args_list]
        cited_by_calls = [c for c in calls if "citedByCount" in c]
        assert len(cited_by_calls) == 1

    def test_skips_cited_by_count_when_zero(self, mock_config):
        """Test citedByCount skipped when value is 0 (falsy)."""
        paper_entity = SimpleNamespace(doi="10.1234/test", cited_by_count=0)
        publications_graph = MagicMock()
        paper_uri = URIRef("http://example.org/paper/1")

        add_paper_metadata(paper_entity, publications_graph, paper_uri)

        assert publications_graph.add.call_count == 4

    def test_calls_quality_functions(self, mock_config):
        """Test calculate_paper_quality_score and get_confidence_level called."""
        paper_entity = SimpleNamespace(doi="10.1234/test")
        publications_graph = MagicMock()
        paper_uri = URIRef("http://example.org/paper/1")

        add_paper_metadata(paper_entity, publications_graph, paper_uri)

        mock_config["calc_paper_score"].assert_called_once_with(paper_entity)
        mock_config["conf_level"].assert_called_once_with(0.85)


class TestAddAuthorMetadata:
    """Tests for add_author_metadata function."""

    @pytest.fixture
    def mock_config(self):
        """Mock config and quality functions for author metadata."""
        with (
            patch("pyeuropepmc.mappers.provenance.load_rdf_config") as mock_load,
            patch("pyeuropepmc.mappers.provenance.get_namespace_from_config") as mock_get_ns,
            patch(
                "pyeuropepmc.mappers.provenance.calculate_author_quality_score"
            ) as mock_calc_score,
            patch("pyeuropepmc.mappers.provenance.get_confidence_level") as mock_conf_level,
        ):
            mock_config_dict = MagicMock()
            mock_load.return_value = mock_config_dict

            namespace_map = {
                "ex": Namespace("http://example.org/data/"),
                "europepmc": Namespace("https://europepmc.org/"),
            }
            mock_get_ns.side_effect = lambda config, prefix: namespace_map[prefix]

            mock_calc_score.return_value = 0.75
            mock_conf_level.return_value = "medium"

            yield {
                "calc_author_score": mock_calc_score,
                "conf_level": mock_conf_level,
            }

    def test_adds_author_metadata_triples(self, mock_config):
        """Test that all 4 author metadata triples are added."""
        author_entity = SimpleNamespace(orcid="0000-0001-2345-6789")
        authors_graph = MagicMock()
        author_uri = URIRef("http://example.org/author/1")

        add_author_metadata(author_entity, authors_graph, author_uri)

        assert authors_graph.add.call_count == 4

    def test_adds_mandatory_author_triples(self, mock_config):
        """Test dataSource, qualityScore, confidenceLevel, lastUpdated added."""
        author_entity = SimpleNamespace(orcid="0000-0001-2345-6789")
        authors_graph = MagicMock()
        author_uri = URIRef("http://example.org/author/1")

        add_author_metadata(author_entity, authors_graph, author_uri)

        calls = [str(c) for c in authors_graph.add.call_args_list]
        assert any("dataSource" in c for c in calls)
        assert any("qualityScore" in c for c in calls)
        assert any("confidenceLevel" in c for c in calls)
        assert any("lastUpdated" in c for c in calls)

    def test_calls_author_quality_functions(self, mock_config):
        """Test calculate_author_quality_score and get_confidence_level called."""
        author_entity = SimpleNamespace(orcid="0000-0001-2345-6789")
        authors_graph = MagicMock()
        author_uri = URIRef("http://example.org/author/1")

        add_author_metadata(author_entity, authors_graph, author_uri)

        mock_config["calc_author_score"].assert_called_once_with(author_entity)
        mock_config["conf_level"].assert_called_once_with(0.75)


class TestAddQualityMetrics:
    """Tests for add_quality_metrics function."""

    @pytest.fixture
    def mock_config(self):
        """Mock config utilities to return pyeuropepmc namespace."""
        with (
            patch("pyeuropepmc.mappers.provenance.load_rdf_config") as mock_load,
            patch("pyeuropepmc.mappers.provenance.get_namespace_from_config") as mock_get_ns,
        ):
            mock_config_dict = MagicMock()
            mock_load.return_value = mock_config_dict

            namespace_map = {
                "pyeuropepmc": Namespace("https://w3id.org/pyeuropepmc/vocab#"),
            }
            mock_get_ns.side_effect = lambda config, prefix: namespace_map[prefix]

            yield mock_load, mock_get_ns

    def test_adds_quality_assessment_triples(self, mock_config):
        """Test that 3 quality assessment triples are added."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_quality_metrics(dataset, {"provenance": "http://example.org/prov"})

        dataset.graph.assert_any_call("http://example.org/prov")
        assert dataset.graph.call_count == 3
        assert mock_graph.add.call_count == 3

    def test_adds_prov_activity_type(self, mock_config):
        """Test that prov:Activity type triple is added."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_quality_metrics(dataset, {"provenance": "http://example.org/prov"})

        calls = [str(c) for c in mock_graph.add.call_args_list]
        assert any("prov#Activity" in c for c in calls)

    def test_adds_started_at_time(self, mock_config):
        """Test that prov:startedAtTime triple is added."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_quality_metrics(dataset, {"provenance": "http://example.org/prov"})

        calls = [str(c) for c in mock_graph.add.call_args_list]
        assert any("startedAtTime" in c for c in calls)

    def test_adds_description(self, mock_config):
        """Test that dcterms:description triple is added."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_quality_metrics(dataset, {"provenance": "http://example.org/prov"})

        calls = [str(c) for c in mock_graph.add.call_args_list]
        assert any("description" in c for c in calls)

    def test_empty_provenance_context(self, mock_config):
        """Test with empty provenance context string."""
        dataset = MagicMock()
        mock_graph = MagicMock()
        dataset.graph.return_value = mock_graph

        add_quality_metrics(dataset, {"provenance": ""})

        dataset.graph.assert_any_call("")
        assert dataset.graph.call_count == 3
        assert mock_graph.add.call_count == 3
