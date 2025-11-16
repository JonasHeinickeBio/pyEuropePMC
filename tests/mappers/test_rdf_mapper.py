"""Unit tests for RDF mapper."""

import os
import tempfile

import pytest
from rdflib import Graph, Namespace

from pyeuropepmc.mappers import RDFMapper
from pyeuropepmc.models import PaperEntity

DCT = Namespace("http://purl.org/dc/terms/")


class TestRDFMapper:
    """Tests for RDFMapper."""

    def test_mapper_initialization(self):
        """Test mapper initialization."""
        mapper = RDFMapper()
        assert mapper.config is not None
        assert mapper.namespaces is not None

    def test_load_config(self):
        """Test configuration loading."""
        mapper = RDFMapper()
        assert "_@prefix" in mapper.config
        assert "PaperEntity" in mapper.config
        assert "AuthorEntity" in mapper.config

    def test_build_namespaces(self):
        """Test namespace building."""
        mapper = RDFMapper()
        assert "dct" in mapper.namespaces
        assert "bibo" in mapper.namespaces
        assert "foaf" in mapper.namespaces

    def test_resolve_predicate_with_prefix(self):
        """Test predicate resolution with prefix."""
        mapper = RDFMapper()
        predicate = mapper._resolve_predicate("dct:title")
        assert "title" in str(predicate)
        assert "purl.org/dc/terms" in str(predicate)

    def test_resolve_predicate_without_prefix(self):
        """Test predicate resolution without prefix."""
        mapper = RDFMapper()
        predicate = mapper._resolve_predicate("http://example.org/test")
        # Use startswith to properly validate URL structure
        assert str(predicate).startswith("http://example.org/")

    def test_add_types(self):
        """Test adding RDF types."""
        mapper = RDFMapper()
        g = Graph()
        from rdflib import URIRef
        from rdflib.namespace import RDF

        subject = URIRef("http://example.org/test")
        mapper.add_types(g, subject, ["bibo:AcademicArticle"])

        # Check type was added
        types = list(g.objects(subject, RDF.type))
        assert len(types) == 1
        assert "bibo" in str(types[0])

    def test_map_fields(self):
        """Test mapping entity fields."""
        mapper = RDFMapper()
        g = Graph()
        from rdflib import URIRef

        paper = PaperEntity(title="Test Article", doi="10.1234/test")
        subject = URIRef("http://example.org/paper1")

        mapper.map_fields(g, subject, paper)

        # Check that fields were mapped
        title_values = list(g.objects(subject, DCT.title))
        assert len(title_values) == 1
        assert str(title_values[0]) == "Test Article"

    def test_map_multi_value_fields(self):
        """Test mapping multi-value fields."""
        mapper = RDFMapper()
        g = Graph()
        from rdflib import URIRef

        paper = PaperEntity(
            title="Test Article",
            keywords=["keyword1", "keyword2", "keyword3"],
        )
        subject = URIRef("http://example.org/paper1")

        mapper.map_fields(g, subject, paper)

        # Check that keywords were mapped
        keyword_values = list(g.objects(subject, DCT.subject))
        assert len(keyword_values) == 3

    def test_serialize_graph_to_string(self):
        """Test serializing graph to string."""
        mapper = RDFMapper()
        g = Graph()
        from rdflib import URIRef

        paper = PaperEntity(title="Test Article")
        subject = URIRef("http://example.org/paper1")
        mapper.map_fields(g, subject, paper)

        ttl = mapper.serialize_graph(g, format="turtle")
        assert len(ttl) > 0
        assert "Test Article" in ttl

    def test_serialize_graph_to_file(self):
        """Test serializing graph to file."""
        mapper = RDFMapper()
        g = Graph()
        from rdflib import URIRef

        paper = PaperEntity(title="Test Article")
        subject = URIRef("http://example.org/paper1")
        mapper.map_fields(g, subject, paper)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".ttl") as tmp:
            tmp_path = tmp.name

        try:
            result = mapper.serialize_graph(g, format="turtle", destination=tmp_path)
            assert result == ""
            assert os.path.exists(tmp_path)

            # Read and check content
            with open(tmp_path) as f:
                content = f.read()
                assert len(content) > 0
                assert "Test Article" in content
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_invalid_config_path(self):
        """Test handling of invalid config path."""
        with pytest.raises(FileNotFoundError):
            RDFMapper(config_path="/nonexistent/path.yml")
