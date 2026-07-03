"""
Unit tests for semantic enrichment functions.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from rdflib import DCTERMS, RDF, XSD, Graph, Literal, Namespace, URIRef

from pyeuropepmc.mappers import semantic_enrichment as se


def _config_with_prefixes(prefix_map):
    """Build a config dict with _@prefix structure for get_namespace_from_config."""
    return {"_@prefix": prefix_map}


@pytest.fixture
def mock_dataset():
    """Fixture for a mock RDF dataset with named graphs."""
    ds = MagicMock()
    ds.graph.return_value = Graph()
    return ds


@pytest.fixture
def named_graph_uris():
    """Fixture for named graph URIs."""
    return {
        "publications": URIRef("http://example.org/graph/publications"),
        "authors": URIRef("http://example.org/graph/authors"),
        "institutions": URIRef("http://example.org/graph/institutions"),
        "provenance": URIRef("http://example.org/graph/provenance"),
    }


@pytest.fixture
def mock_mapper():
    """Fixture for mock mapper."""
    mapper = MagicMock()
    mapper.generate_uri.side_effect = lambda entity_type, entity: URIRef(
        f"http://example.org/{entity_type}/{hash(str(entity))}"
    )
    return mapper


class TestProcessFunctions:
    """Tests for process_*_for_rdf functions."""

    def test_process_search_for_rdf_empty(self, mock_dataset, named_graph_uris, mock_mapper):
        """Test process_search_for_rdf with empty results."""
        with patch("pyeuropepmc.mappers.semantic_enrichment.process_search_results", return_value=[]):
            se.process_search_for_rdf([], mock_dataset, named_graph_uris, mock_mapper)
            assert len(mock_dataset.graph.return_value) == 0

    def test_process_search_for_rdf_with_entity(self, mock_dataset, named_graph_uris, mock_mapper):
        """Test process_search_for_rdf with entity."""
        mock_entity = MagicMock()
        mock_entity.to_rdf = MagicMock()
        mock_entity.authors = []

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.process_search_results",
            return_value=[{"entity": mock_entity, "related_entities": {}}],
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.add_paper_metadata",
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.add_author_metadata",
        ):
            se.process_search_for_rdf([{}], mock_dataset, named_graph_uris, mock_mapper)
            mock_entity.to_rdf.assert_called_once()

    def test_process_search_for_rdf_with_error(self, mock_dataset, named_graph_uris, mock_mapper):
        """Test process_search_for_rdf handles errors gracefully."""
        mock_entity = MagicMock()
        mock_entity.to_rdf.side_effect = ValueError("Conversion error")

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.process_search_results",
            return_value=[{"entity": mock_entity, "related_entities": {}}],
        ):
            se.process_search_for_rdf([{}], mock_dataset, named_graph_uris, mock_mapper)

    def test_process_search_for_rdf_with_authors(self, mock_dataset, named_graph_uris, mock_mapper):
        """Test process_search_for_rdf with author metadata."""
        mock_author = MagicMock()
        mock_entity = MagicMock()
        mock_entity.to_rdf = MagicMock()
        mock_entity.authors = [mock_author]

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.process_search_results",
            return_value=[{"entity": mock_entity, "related_entities": {}}],
        ):
            se.process_search_for_rdf([{}], mock_dataset, named_graph_uris, mock_mapper)
            mock_mapper.generate_uri.assert_any_call("author", mock_author)

    def test_process_xml_for_rdf(self, mock_dataset, named_graph_uris, mock_mapper):
        """Test process_xml_for_rdf."""
        mock_entity = MagicMock()
        mock_entity.to_rdf = MagicMock()

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.process_xml_data",
            return_value=[{"entity": mock_entity, "related_entities": {}}],
        ):
            se.process_xml_for_rdf({}, mock_dataset, named_graph_uris, mock_mapper)
            mock_entity.to_rdf.assert_called_once()

    def test_process_enrichment_for_rdf(self, mock_dataset, named_graph_uris, mock_mapper):
        """Test process_enrichment_for_rdf."""
        mock_entity = MagicMock()
        mock_entity.to_rdf = MagicMock()

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.process_enrichment_data",
            return_value=[{"entity": mock_entity, "related_entities": {}}],
        ):
            se.process_enrichment_for_rdf({}, mock_dataset, named_graph_uris, mock_mapper)
            mock_entity.to_rdf.assert_called_once()


class TestNetworkFunctions:
    """Tests for network building functions."""

    def test_build_citation_networks_empty(self, mock_dataset, named_graph_uris):
        """Test build_citation_networks with empty graph."""
        se.build_citation_networks(mock_dataset, named_graph_uris)
        assert len(mock_dataset.graph.return_value) == 0

    def test_build_citation_networks_with_citations(self, mock_dataset, named_graph_uris):
        """Test build_citation_networks with citations."""
        g = mock_dataset.graph.return_value
        EX = Namespace("http://example.org/ex/")
        CITO = Namespace("http://example.org/cito/")
        pub1 = URIRef("http://example.org/paper/1")
        pub2 = URIRef("http://example.org/paper/2")

        g.add((pub1, EX.citedByCount, Literal(5)))
        g.add((pub2, EX.cites, pub1))

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.load_rdf_config",
            return_value=_config_with_prefixes({"ex": str(EX), "cito": str(CITO)}),
        ):
            se.build_citation_networks(mock_dataset, named_graph_uris)

        assert len(g) >= 3

    def test_build_collaboration_networks_empty(self, mock_dataset, named_graph_uris):
        """Test build_collaboration_networks with empty graph."""
        se.build_collaboration_networks(mock_dataset, named_graph_uris)
        assert len(mock_dataset.graph.return_value) == 0

    def test_build_collaboration_networks_with_authors(self, mock_dataset, named_graph_uris):
        """Test build_collaboration_networks with authors."""
        g = mock_dataset.graph.return_value
        EX = Namespace("http://example.org/ex/")
        VIVO = Namespace("http://example.org/vivo/")
        pub1 = URIRef("http://example.org/paper/1")
        author1 = URIRef("http://example.org/author/john-doe")
        author2 = URIRef("http://example.org/author/jane-doe")

        g.add((pub1, DCTERMS.creator, author1))
        g.add((pub1, DCTERMS.creator, author2))

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.load_rdf_config",
            return_value=_config_with_prefixes({"ex": str(EX), "vivo": str(VIVO)}),
        ):
            se.build_collaboration_networks(mock_dataset, named_graph_uris)

        assert len(g) >= 2

    def test_build_institutional_hierarchies_empty(self, mock_dataset, named_graph_uris):
        """Test build_institutional_hierarchies with empty graph."""
        se.build_institutional_hierarchies(mock_dataset, named_graph_uris)
        assert len(mock_dataset.graph.return_value) == 0

    def test_build_institutional_hierarchies_with_affiliations(
        self, mock_dataset, named_graph_uris
    ):
        """Test build_institutional_hierarchies with affiliations."""
        g = mock_dataset.graph.return_value
        EX = Namespace("http://example.org/ex/")
        EUROPEPMC = Namespace("http://example.org/europepmc/")
        ORG = Namespace("http://example.org/org/")
        author1 = URIRef("http://example.org/author/1")
        author2 = URIRef("http://example.org/author/2")

        g.add((author1, EX.affiliation, Literal("University A")))
        g.add((author2, EX.affiliation, Literal("University A")))

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.load_rdf_config",
            return_value=_config_with_prefixes({
                "ex": str(EX),
                "europepmc": str(EUROPEPMC),
                "org": str(ORG),
            }),
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.calculate_institution_quality_score",
            return_value=0.85,
        ):
            se.build_institutional_hierarchies(mock_dataset, named_graph_uris)

        assert len(g) > 2


class TestMetadataFunctions:
    """Tests for metadata functions."""

    def test_add_quality_metrics(self, mock_dataset, named_graph_uris):
        """Test add_quality_metrics."""
        g = mock_dataset.graph.return_value
        PYEUROPEPMC = Namespace("http://example.org/pyeuropepmc/")

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.load_rdf_config",
            return_value=_config_with_prefixes({"pyeuropepmc": str(PYEUROPEPMC)}),
        ):
            se.add_quality_metrics(mock_dataset, named_graph_uris)

        assert len(g) >= 3

    def test_add_provenance_and_metadata_default(self, mock_dataset, named_graph_uris):
        """Test add_provenance_and_metadata with no extraction info."""
        g = mock_dataset.graph.return_value
        PYEUROPEPMC = Namespace("http://example.org/pyeuropepmc/")
        EX = Namespace("http://example.org/ex/")

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.load_rdf_config",
            return_value=_config_with_prefixes({
                "pyeuropepmc": str(PYEUROPEPMC),
                "ex": str(EX),
            }),
        ):
            se.add_provenance_and_metadata(mock_dataset, named_graph_uris)

        assert len(g) >= 7

    def test_add_paper_metadata(self, mock_dataset, named_graph_uris):
        """Test add_paper_metadata."""
        g = mock_dataset.graph.return_value
        paper_uri = URIRef("http://example.org/paper/1")
        mock_entity = MagicMock()
        mock_entity.cited_by_count = 10

        EX = Namespace("http://example.org/ex/")
        EUROPEPMC = Namespace("http://example.org/europepmc/")

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.load_rdf_config",
            return_value=_config_with_prefixes({
                "ex": str(EX),
                "europepmc": str(EUROPEPMC),
            }),
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.calculate_paper_quality_score",
            return_value=0.9,
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.get_confidence_level",
            return_value="high",
        ):
            se.add_paper_metadata(mock_entity, mock_dataset, paper_uri, named_graph_uris["publications"])

        assert len(g) == 5

    def test_add_paper_metadata_no_citations(self, mock_dataset, named_graph_uris):
        """Test add_paper_metadata without citations."""
        g = mock_dataset.graph.return_value
        paper_uri = URIRef("http://example.org/paper/1")
        mock_entity = MagicMock()
        mock_entity.cited_by_count = 0

        EX = Namespace("http://example.org/ex/")
        EUROPEPMC = Namespace("http://example.org/europepmc/")

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.load_rdf_config",
            return_value=_config_with_prefixes({
                "ex": str(EX),
                "europepmc": str(EUROPEPMC),
            }),
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.calculate_paper_quality_score",
            return_value=0.5,
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.get_confidence_level",
            return_value="medium",
        ):
            se.add_paper_metadata(mock_entity, mock_dataset, paper_uri, named_graph_uris["publications"])

        # citedByCount only added if truthy, 0 is falsy
        assert len(g) == 4

    def test_add_author_metadata(self, mock_dataset, named_graph_uris):
        """Test add_author_metadata."""
        g = mock_dataset.graph.return_value
        author_uri = URIRef("http://example.org/author/1")
        mock_author = MagicMock()

        EX = Namespace("http://example.org/ex/")
        EUROPEPMC = Namespace("http://example.org/europepmc/")

        with patch(
            "pyeuropepmc.mappers.semantic_enrichment.load_rdf_config",
            return_value=_config_with_prefixes({
                "ex": str(EX),
                "europepmc": str(EUROPEPMC),
            }),
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.calculate_author_quality_score",
            return_value=0.75,
        ), patch(
            "pyeuropepmc.mappers.semantic_enrichment.get_confidence_level",
            return_value="high",
        ):
            se.add_author_metadata(mock_author, mock_dataset, author_uri, named_graph_uris["authors"])

        assert len(g) == 4
