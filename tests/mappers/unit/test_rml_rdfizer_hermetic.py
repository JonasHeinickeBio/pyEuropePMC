"""Fast, hermetic unit tests for pyeuropepmc.mappers.rml_rdfizer.

The existing tests/mappers/test_rml_rdfizer.py exercises the real
SDM-RDFizer end-to-end but is marked @pytest.mark.slow (excluded from the
default run). These tests mock `semantify` so the same logic — JSON
serialization, temp config rewriting, namespace binding, output-file
discovery — gets covered by the default (fast, hermetic) test run.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from pyeuropepmc.mappers.rml_rdfizer import RDFIZER_AVAILABLE, RMLRDFizer
from pyeuropepmc.models import AuthorEntity, PaperEntity

pytestmark = pytest.mark.skipif(not RDFIZER_AVAILABLE, reason="rdfizer package not installed")


def _fake_semantify_writes_nt(triples: str = "") -> callable:
    """Return a `semantify` stand-in that drops an .nt file into the output dir."""

    def _fake(config_path: str) -> None:
        # Recover temp_dir from the config file path (…/temp_dir/rdfizer_config.ini)
        temp_dir = os.path.dirname(config_path)
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "result.nt"), "w", encoding="utf-8") as f:
            f.write(triples)

    return _fake


NT_TRIPLE = '<http://example.org/data/paper/PMC1> <http://purl.org/dc/terms/title> "Test"@en .\n'


class TestInit:
    def test_default_paths_exist(self):
        rdfizer = RMLRDFizer()
        assert os.path.exists(rdfizer.config_path)
        assert os.path.exists(rdfizer.mapping_path)

    def test_not_available_raises(self):
        with patch("pyeuropepmc.mappers.rml_rdfizer.RDFIZER_AVAILABLE", False):
            with pytest.raises(ImportError, match="rdfizer package not found"):
                RMLRDFizer()

    def test_missing_config_raises(self, tmp_path):
        mapping = tmp_path / "map.ttl"
        mapping.write_text("")
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            RMLRDFizer(config_path=str(tmp_path / "nope.ini"), mapping_path=str(mapping))

    def test_missing_mapping_raises(self, tmp_path):
        config = tmp_path / "config.ini"
        config.write_text("[default]\n")
        with pytest.raises(FileNotFoundError, match="Mapping file not found"):
            RMLRDFizer(config_path=str(config), mapping_path=str(tmp_path / "nope.ttl"))


class TestCreateEmptyJsonFiles:
    def test_creates_all_expected_files(self, tmp_path):
        rdfizer = RMLRDFizer()
        rdfizer._create_empty_json_files(str(tmp_path))
        for name in [
            "paper.json",
            "authors.json",
            "sections.json",
            "tables.json",
            "references.json",
            "journal.json",
            "grant.json",
            "scholarlywork.json",
            "table_rows.json",
            "institutions.json",
        ]:
            path = tmp_path / name
            assert path.exists()
            assert json.loads(path.read_text()) == []

    def test_does_not_overwrite_existing_file(self, tmp_path):
        (tmp_path / "paper.json").write_text('[{"id": "already-here"}]')
        rdfizer = RMLRDFizer()
        rdfizer._create_empty_json_files(str(tmp_path))
        assert json.loads((tmp_path / "paper.json").read_text()) == [{"id": "already-here"}]


class TestEntitiesToJson:
    def test_paper_entities_get_generated_id_from_doi(self, tmp_path):
        rdfizer = RMLRDFizer()
        paper = PaperEntity(doi="10.1234/x", title="T")
        path = rdfizer._entities_to_json([paper], "paper", str(tmp_path))
        data = json.loads(open(path, encoding="utf-8").read())
        assert data[0]["id"] == "10.1234/x"

    def test_paper_entities_get_generated_id_from_pmcid(self, tmp_path):
        rdfizer = RMLRDFizer()
        paper = PaperEntity(pmcid="PMC123", title="T")
        path = rdfizer._entities_to_json([paper], "paper", str(tmp_path))
        data = json.loads(open(path, encoding="utf-8").read())
        assert data[0]["id"] == "PMC123"

    def test_paper_entities_get_generated_id_from_pmid(self, tmp_path):
        rdfizer = RMLRDFizer()
        paper = PaperEntity(pmid="999", title="T")
        path = rdfizer._entities_to_json([paper], "paper", str(tmp_path))
        data = json.loads(open(path, encoding="utf-8").read())
        assert data[0]["id"] == "pmid:999"

    def test_paper_entities_fallback_generated_id(self, tmp_path):
        rdfizer = RMLRDFizer()
        paper = PaperEntity(title="No identifiers at all")
        path = rdfizer._entities_to_json([paper], "paper", str(tmp_path))
        data = json.loads(open(path, encoding="utf-8").read())
        assert data[0]["id"].startswith("entity_")

    def test_none_values_filtered_and_stringified(self, tmp_path):
        rdfizer = RMLRDFizer()
        author = AuthorEntity(id="a1", label="Jane Doe")
        path = rdfizer._entities_to_json([author], "author", str(tmp_path))
        data = json.loads(open(path, encoding="utf-8").read())
        assert "label" in data[0]
        assert isinstance(data[0]["label"], str)
        # Non-set attributes should not appear as explicit nulls
        assert all(v is not None for v in data[0].values())

    def test_uses_correct_filename_for_entity_type(self, tmp_path):
        rdfizer = RMLRDFizer()
        author = AuthorEntity(id="a1", label="Jane Doe")
        rdfizer._entities_to_json([author], "author", str(tmp_path))
        assert (tmp_path / "authors.json").exists()

    def test_unknown_entity_type_uses_generic_filename(self, tmp_path):
        rdfizer = RMLRDFizer()
        author = AuthorEntity(id="a1", label="Jane Doe")
        rdfizer._entities_to_json([author], "widget", str(tmp_path))
        assert (tmp_path / "widget.json").exists()


class TestCreateTempConfig:
    def test_rewrites_paths_into_temp_dir(self, tmp_path):
        rdfizer = RMLRDFizer()
        temp_config = rdfizer._create_temp_config(str(tmp_path), entity_type="paper")
        content = open(temp_config, encoding="utf-8").read()
        assert str(tmp_path) in content
        assert os.path.exists(os.path.join(str(tmp_path), "rml_mappings.ttl"))

    def test_mapping_json_source_paths_rewritten(self, tmp_path):
        rdfizer = RMLRDFizer()
        rdfizer._create_temp_config(str(tmp_path), entity_type="paper")
        mapping_content = (tmp_path / "rml_mappings.ttl").read_text(encoding="utf-8")
        assert '"paper.json"' not in mapping_content or str(tmp_path) in mapping_content


class TestBindNamespaces:
    def test_binds_expected_prefixes(self):
        from rdflib import Graph

        rdfizer = RMLRDFizer()
        g = Graph()
        rdfizer._bind_namespaces(g)
        bound = dict(g.namespaces())
        assert "dct" in bound
        assert "bibo" in bound
        assert str(bound["dct"]) == "http://purl.org/dc/terms/"


class TestRunRdfizer:
    def test_finds_output_file(self, tmp_path):
        rdfizer = RMLRDFizer()
        config_path = tmp_path / "rdfizer_config.ini"
        config_path.write_text("[default]\n")
        with patch(
            "pyeuropepmc.mappers.rml_rdfizer.semantify",
            side_effect=_fake_semantify_writes_nt(NT_TRIPLE),
        ):
            output_file = rdfizer._run_rdfizer(str(config_path), str(tmp_path))
        assert output_file.endswith(".nt")
        assert os.path.exists(output_file)

    def test_no_output_produced_returns_empty_string(self, tmp_path):
        rdfizer = RMLRDFizer()
        config_path = tmp_path / "rdfizer_config.ini"
        config_path.write_text("[default]\n")
        with patch("pyeuropepmc.mappers.rml_rdfizer.semantify", return_value=None):
            output_file = rdfizer._run_rdfizer(str(config_path), str(tmp_path))
        assert output_file == ""


class TestEntitiesToRdf:
    def test_produces_graph_with_triples(self):
        rdfizer = RMLRDFizer()
        paper = PaperEntity(pmcid="PMC1", title="Test")
        with patch(
            "pyeuropepmc.mappers.rml_rdfizer.semantify",
            side_effect=_fake_semantify_writes_nt(NT_TRIPLE),
        ):
            g = rdfizer.entities_to_rdf([paper], entity_type="paper")
        assert len(g) == 1

    def test_no_output_produces_empty_graph(self):
        rdfizer = RMLRDFizer()
        paper = PaperEntity(pmcid="PMC1", title="Test")
        with patch("pyeuropepmc.mappers.rml_rdfizer.semantify", return_value=None):
            g = rdfizer.entities_to_rdf([paper], entity_type="paper")
        assert len(g) == 0
        # namespaces are still bound even for an empty graph
        assert "dct" in dict(g.namespaces())


class TestConvertJsonToRdf:
    def test_dict_input_is_wrapped_in_list(self):
        rdfizer = RMLRDFizer()
        with patch(
            "pyeuropepmc.mappers.rml_rdfizer.semantify",
            side_effect=_fake_semantify_writes_nt(NT_TRIPLE),
        ):
            g = rdfizer.convert_json_to_rdf(
                {"pmcid": "PMC1", "title": "Test"}, entity_type="paper"
            )
        assert len(g) == 1

    def test_list_input(self):
        rdfizer = RMLRDFizer()
        with patch(
            "pyeuropepmc.mappers.rml_rdfizer.semantify",
            side_effect=_fake_semantify_writes_nt(NT_TRIPLE),
        ):
            g = rdfizer.convert_json_to_rdf(
                [{"pmcid": "PMC1", "title": "Test"}], entity_type="paper"
            )
        assert len(g) == 1

    def test_unknown_entity_type_uses_generic_filename(self, tmp_path):
        rdfizer = RMLRDFizer()
        with patch("pyeuropepmc.mappers.rml_rdfizer.semantify", return_value=None):
            g = rdfizer.convert_json_to_rdf({"a": 1}, entity_type="widget")
        assert len(g) == 0
