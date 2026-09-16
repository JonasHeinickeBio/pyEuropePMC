"""RML subject ids, and agreement between rdf_map.yml, the models and rml_mappings.ttl.

These run without the ``rdfizer`` package: the id helpers are plain functions,
and the mapping generator is a script.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from pyeuropepmc.mappers.rml_rdfizer import _assign_missing_ids, _content_digest
import pyeuropepmc.models as models

ROOT = Path(__file__).resolve().parents[3]
RDF_MAP = ROOT / "conf" / "rdf_map.yml"
RML_MAPPINGS = ROOT / "conf" / "rml_mappings.ttl"


def _load_sync_script():
    spec = importlib.util.spec_from_file_location(
        "sync_rdf_mappings", ROOT / "examples" / "scripts" / "sync_rdf_mappings.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAssignMissingIds:
    def test_every_record_gets_an_id(self):
        """Authors, sections and references used to get none, so they produced no triples."""
        records = [{"full_name": "Jane Doe"}, {"full_name": "John Roe"}]
        _assign_missing_ids(records, "author")
        assert all(r["id"].startswith("author-") for r in records)
        assert records[0]["id"] != records[1]["id"]

    def test_digest_id_is_stable_across_processes(self):
        """hash() is salted per process; the digest must not be."""
        record = {"title": "Introduction", "content": "Some text."}
        expected = f"section-{_content_digest(record)}"
        code = (
            "from pyeuropepmc.mappers.rml_rdfizer import _assign_missing_ids\n"
            "r = [{'title': 'Introduction', 'content': 'Some text.'}]\n"
            "_assign_missing_ids(r, 'section'); print(r[0]['id'])\n"
        )
        ids = {
            subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            ).stdout.strip()
            for seed in ("1", "2", "3")
        }
        assert ids == {expected}

    def test_golden_digest(self):
        assert _content_digest({"a": 1, "b": ["x"]}) == "8387fd01c31f4ba4"

    def test_identical_records_get_distinct_ids(self):
        records = [{"cells": ["1", "2"]}, {"cells": ["1", "2"]}, {"cells": ["1", "2"]}]
        _assign_missing_ids(records, "tablerow")
        base = records[0]["id"]
        assert [r["id"] for r in records] == [base, f"{base}-2", f"{base}-3"]

    def test_volatile_fields_do_not_change_the_id(self):
        a = [{"title": "T", "last_updated": "2026-01-01T00:00:00Z"}]
        b = [{"title": "T", "last_updated": "2026-09-16T10:00:00Z"}]
        _assign_missing_ids(a, "paper")
        _assign_missing_ids(b, "paper")
        assert a[0]["id"] == b[0]["id"]

    @pytest.mark.parametrize(
        ("record", "expected"),
        [
            ({"doi": "10.1/x", "pmid": "1"}, "10.1/x"),
            ({"pmcid": "PMC1", "pmid": "1"}, "PMC1"),
            ({"pmid": "123"}, "pmid:123"),
            ({"full_name": "Jane", "orcid": "0000-0002-1825-0097"}, "0000-0002-1825-0097"),
            (
                {"display_name": "Uni", "ror_id": "https://ror.org/03yrm5c26"},
                "https://ror.org/03yrm5c26",
            ),
        ],
    )
    def test_identifiers_are_used_when_present(self, record, expected):
        records = [dict(record)]
        _assign_missing_ids(records, "reference")
        assert records[0]["id"] == expected

    def test_existing_id_is_kept(self):
        records = [{"id": "keep-me", "title": "T"}]
        _assign_missing_ids(records, "section")
        assert records[0]["id"] == "keep-me"


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load(RDF_MAP.read_text(encoding="utf-8"))


class TestRdfMapYaml:
    def test_rdf_type_matches_the_model_default_types(self, config):
        """RDFMapper types entities from `types`; the generated RML from the YAML."""
        mismatches = {}
        for name, entry in config.items():
            cls = getattr(models, name, None)
            if name.startswith("_") or cls is None or name == "ScholarlyWorkEntity":
                continue
            if entry.get("rdf:type") != cls().types:
                mismatches[name] = (entry.get("rdf:type"), cls().types)
        assert mismatches == {}

    def test_reference_entity_type(self, config):
        assert config["ReferenceEntity"]["rdf:type"] == ["bibo:Document"]

    def test_figure_relationships_are_not_the_grant_ones(self, config):
        assert config["FigureEntity"]["relationships"] == {
            "paper": {"predicate": "dcterms:isPartOf", "inverse": "dcterms:hasPart"}
        }


class TestSyncRdfMappingsScript:
    def test_string_predicates_are_accepted(self):
        """The annotation classes map fields to bare predicate strings."""
        script = _load_sync_script()
        lines = script.generate_fields_mapping(
            {
                "exact": "oa:hasBody",
                "entity_id": {"predicate": "oa:hasBody", "datatype": "xsd:anyURI"},
            }
        )
        text = "\n".join(lines)
        assert 'rr:objectMap [ rml:reference "exact" ]' in text
        assert 'rr:objectMap [ rml:reference "entity_id" ; rr:datatype xsd:anyURI ]' in text

    def test_committed_rml_file_is_up_to_date(self, tmp_path, capsys):
        """conf/rml_mappings.ttl is generated; regenerate it after editing rdf_map.yml."""
        script = _load_sync_script()
        generated = tmp_path / "rml_mappings.ttl"
        script.sync_mappings(RDF_MAP, generated)
        assert generated.read_text(encoding="utf-8") == RML_MAPPINGS.read_text(encoding="utf-8")

    def test_generated_rml_is_valid_turtle_with_figure_and_reference_maps(self):
        from rdflib import Graph, URIRef

        g = Graph().parse(RML_MAPPINGS, format="turtle")
        classes = {str(o) for o in g.objects(predicate=URIRef("http://www.w3.org/ns/r2rml#class"))}
        assert "http://purl.org/ontology/bibo/Image" in classes
        assert "http://purl.org/ontology/bibo/Document" in classes
        assert "http://purl.org/ontology/bibo/Article" not in classes

    def test_makefile_target_points_at_the_script(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        assert "examples/scripts/sync_rdf_mappings.py" in makefile
        assert (ROOT / "examples" / "scripts" / "sync_rdf_mappings.py").exists()
