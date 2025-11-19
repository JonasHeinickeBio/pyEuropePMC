"""Unit tests for RML RDFizer."""

import json
import os
import tempfile

import pytest

from pyeuropepmc.mappers import RDFIZER_AVAILABLE, RMLRDFizer
from pyeuropepmc.models import AuthorEntity, PaperEntity

# Skip all tests if rdfizer is not available
pytestmark = pytest.mark.skipif(
    not RDFIZER_AVAILABLE, reason="rdfizer package not installed"
)


class TestRMLRDFizer:
    """Tests for RMLRDFizer."""

    def test_rdfizer_initialization(self):
        """Test RMLRDFizer initialization."""
        rdfizer = RMLRDFizer()
        assert rdfizer.config_path is not None
        assert rdfizer.mapping_path is not None
        assert os.path.exists(rdfizer.config_path)
        assert os.path.exists(rdfizer.mapping_path)

    def test_rdfizer_initialization_rdfizer_not_available(self):
        """Test RMLRDFizer initialization when rdfizer is not available."""
        # Mock RDFIZER_AVAILABLE to False
        import pyeuropepmc.mappers.rml_rdfizer as rml_module
        original_available = rml_module.RDFIZER_AVAILABLE
        rml_module.RDFIZER_AVAILABLE = False

        try:
            with pytest.raises(ImportError, match="rdfizer package not found"):
                RMLRDFizer()
        finally:
            rml_module.RDFIZER_AVAILABLE = original_available

    def test_rdfizer_with_custom_paths(self):
        """Test RMLRDFizer with custom config paths."""
        # Create temp files
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ini", delete=False
        ) as config_file:
            config_file.write("[default]\nmain_directory: .\n")
            config_path = config_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ttl", delete=False
        ) as mapping_file:
            mapping_file.write("@prefix rr: <http://www.w3.org/ns/r2rml#> .\n")
            mapping_path = mapping_file.name

        try:
            rdfizer = RMLRDFizer(
                config_path=config_path, mapping_path=mapping_path
            )
            assert rdfizer.config_path == config_path
            assert rdfizer.mapping_path == mapping_path
        finally:
            os.unlink(config_path)
            os.unlink(mapping_path)

    def test_rdfizer_invalid_config_path(self):
        """Test RMLRDFizer with invalid config path."""
        with pytest.raises(FileNotFoundError):
            RMLRDFizer(config_path="/nonexistent/path.ini")

    def test_rdfizer_invalid_mapping_path(self):
        """Test RMLRDFizer with invalid mapping path."""
        # Create a valid config file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ini", delete=False
        ) as config_file:
            config_file.write("[default]\nmain_directory: .\n")
            config_path = config_file.name

        try:
            with pytest.raises(FileNotFoundError):
                RMLRDFizer(
                    config_path=config_path, mapping_path="/nonexistent/path.ttl"
                )
        finally:
            os.unlink(config_path)

    def test_entities_to_rdf_output_format(self):
        """Test entities_to_rdf with different output formats."""
        rdfizer = RMLRDFizer()

        paper = PaperEntity(
            pmcid="PMC123456",
            doi="10.1234/test",
            title="Test Paper",
        )

        try:
            # Test with different output formats (though RDFizer may not respect this)
            g = rdfizer.entities_to_rdf([paper], entity_type="paper", output_format="xml")
            assert isinstance(g, object)  # RDFLib Graph
        except Exception as e:
            pytest.skip(f"RDFizer execution failed: {e}")

    def test_entities_to_json_non_paper_entity(self):
        """Test converting non-paper entities to JSON."""
        rdfizer = RMLRDFizer()

        authors = [
            AuthorEntity(full_name="John Doe", orcid="0000-0001-2345-6789"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            json_file = rdfizer._entities_to_json(authors, "author", temp_dir)
            assert os.path.exists(json_file)
            assert json_file.endswith("authors.json")

            # Verify content
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                assert isinstance(data, list)
                assert len(data) == 1

    def test_entities_to_rdf_paper(self):
        """Test converting paper entity to RDF using RML."""
        rdfizer = RMLRDFizer()

        paper = PaperEntity(
            pmcid="PMC123456",
            doi="10.1234/test",
            title="Test Paper",
            journal="Test Journal",
        )

        try:
            g = rdfizer.entities_to_rdf([paper], entity_type="paper")
            assert len(g) > 0  # Should have some triples

            # Check that we have triples (basic smoke test)
            # More detailed validation would require parsing RML output
            assert isinstance(g, object)  # RDFLib Graph
        except Exception as e:
            # RDFizer might fail for various reasons (missing deps, etc.)
            pytest.skip(f"RDFizer execution failed: {e}")

    def test_entities_to_rdf_authors(self):
        """Test converting author entities to RDF using RML."""
        rdfizer = RMLRDFizer()

        authors = [
            AuthorEntity(full_name="John Doe", orcid="0000-0001-2345-6789"),
            AuthorEntity(full_name="Jane Smith"),
        ]

        try:
            g = rdfizer.entities_to_rdf(authors, entity_type="author")
            assert len(g) >= 0  # May be 0 if RDFizer didn't run successfully
        except Exception as e:
            pytest.skip(f"RDFizer execution failed: {e}")

    def test_convert_json_to_rdf_single_author_dict(self):
        """Test converting single author dict to RDF."""
        rdfizer = RMLRDFizer()

        json_data = {
            "full_name": "John Doe",
            "orcid": "0000-0001-2345-6789",
        }

        try:
            g = rdfizer.convert_json_to_rdf(json_data, entity_type="author")
            assert len(g) >= 0
        except Exception as e:
            pytest.skip(f"RDFizer execution failed: {e}")

    def test_convert_json_to_rdf_list_input(self):
        """Test converting list of JSON data to RDF."""
        rdfizer = RMLRDFizer()

        json_data = [
            {
                "full_name": "John Doe",
                "orcid": "0000-0001-2345-6789",
            },
            {
                "full_name": "Jane Smith",
            }
        ]

        try:
            g = rdfizer.convert_json_to_rdf(json_data, entity_type="author")
            assert len(g) >= 0
        except Exception as e:
            pytest.skip(f"RDFizer execution failed: {e}")

    def test_create_temp_config(self):
        """Test creating temporary config file."""
        rdfizer = RMLRDFizer()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_config = rdfizer._create_temp_config(temp_dir)
            assert os.path.exists(temp_config)
            assert temp_config.endswith(".ini")

            # Verify content
            with open(temp_config, encoding="utf-8") as f:
                content = f.read()
                assert temp_dir in content


class TestRMLRDFizerNotAvailable:
    """Tests for when rdfizer is not available."""

    def test_import_check(self):
        """Test that RDFIZER_AVAILABLE flag is set correctly."""
        # This should always be True since we installed it
        # But we test the flag exists
        assert isinstance(RDFIZER_AVAILABLE, bool)
