"""Coverage for RDFMapper's convert_and_save_*/save_* orchestration methods
and the metadata/content entity filters — the file-writing / dispatch layer
around to_rdf(), independent of the field-mapping internals.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.utils.dependencies import is_dependency_available

pytestmark = pytest.mark.skipif(
    not is_dependency_available("rdflib"), reason="skipped due to missing rdflib"
)

from pyeuropepmc.mappers import RDFMapper


def _fake_entity(class_name: str, triples: int = 1):
    entity = MagicMock()
    entity.__class__.__name__ = class_name

    def to_rdf(g, mapper, related_entities, extraction_info):
        for _ in range(triples):
            g.add(
                (
                    __import__("rdflib").URIRef("http://x/s"),
                    __import__("rdflib").URIRef("http://x/p"),
                    __import__("rdflib").URIRef("http://x/o"),
                )
            )

    entity.to_rdf.side_effect = to_rdf
    return entity


@pytest.fixture
def mapper():
    return RDFMapper()


class TestConvertAndSaveEntitiesToRdf:
    def test_success_writes_file(self, mapper, tmp_path):
        entity = _fake_entity("PaperEntity")
        with patch.object(mapper, "serialize_graph") as mock_serialize:
            graphs = mapper.convert_and_save_entities_to_rdf(
                {"10.1/x": {"entity": entity}}, output_dir=str(tmp_path)
            )
        assert "10.1/x" in graphs
        mock_serialize.assert_called_once()
        entity.to_rdf.assert_called_once()

    def test_identifier_sanitized_in_default_filename(self, mapper, tmp_path):
        entity = _fake_entity("PaperEntity")
        with patch.object(mapper, "serialize_graph") as mock_serialize:
            mapper.convert_and_save_entities_to_rdf(
                {"10.1/x.y": {"entity": entity}}, output_dir=str(tmp_path)
            )
        _, kwargs = mock_serialize.call_args
        assert "10_1_x_y" in kwargs["destination"]

    def test_custom_filename_template(self, mapper, tmp_path):
        entity = _fake_entity("PaperEntity")
        with patch.object(mapper, "serialize_graph") as mock_serialize:
            mapper.convert_and_save_entities_to_rdf(
                {"1": {"entity": entity}},
                output_dir=str(tmp_path),
                filename_template="{prefix}custom_{identifier}.ttl",
                prefix="pre_",
            )
        _, kwargs = mock_serialize.call_args
        assert kwargs["destination"].endswith("pre_custom_1.ttl")

    def test_include_content_false_filters_related_entities(self, mapper, tmp_path):
        entity = _fake_entity("PaperEntity")
        author = MagicMock()
        author.__class__.__name__ = "AuthorEntity"
        section = MagicMock()
        section.__class__.__name__ = "SectionEntity"

        with patch.object(mapper, "serialize_graph"):
            mapper.convert_and_save_entities_to_rdf(
                {
                    "1": {
                        "entity": entity,
                        "related_entities": {"authors": [author], "sections": [section]},
                    }
                },
                output_dir=str(tmp_path),
                include_content=False,
            )
        _, kwargs = entity.to_rdf.call_args
        assert "authors" in kwargs["related_entities"]
        assert "sections" not in kwargs["related_entities"]

    def test_entity_to_rdf_exception_is_caught(self, mapper, tmp_path):
        entity = _fake_entity("PaperEntity")
        entity.to_rdf.side_effect = RuntimeError("boom")
        graphs = mapper.convert_and_save_entities_to_rdf(
            {"1": {"entity": entity}}, output_dir=str(tmp_path)
        )
        assert graphs == {}

    def test_serialize_exception_does_not_abort_whole_batch(self, mapper, tmp_path):
        entity1 = _fake_entity("PaperEntity")
        entity2 = _fake_entity("PaperEntity")
        with patch.object(
            mapper, "serialize_graph", side_effect=[RuntimeError("disk full"), None]
        ):
            graphs = mapper.convert_and_save_entities_to_rdf(
                {"1": {"entity": entity1}, "2": {"entity": entity2}}, output_dir=str(tmp_path)
            )
        # Both graphs are still returned even though the first save failed
        assert set(graphs) == {"1", "2"}

    def test_extraction_info_defaults_when_not_provided(self, mapper, tmp_path):
        entity = _fake_entity("PaperEntity")
        with patch.object(mapper, "serialize_graph"):
            mapper.convert_and_save_entities_to_rdf(
                {"1": {"entity": entity}}, output_dir=str(tmp_path)
            )
        _, kwargs = entity.to_rdf.call_args
        assert "timestamp" in kwargs["extraction_info"]


class TestConvertAndSavePapersToRdf:
    def test_tuple_format_converted(self, mapper, tmp_path):
        paper = _fake_entity("PaperEntity")
        with patch.object(mapper, "serialize_graph"):
            graphs = mapper.convert_and_save_papers_to_rdf(
                {"10.1/x": (paper, ["author"], ["section"], ["table"], ["figure"], ["ref"])},
                output_dir=str(tmp_path),
            )
        assert "10.1/x" in graphs
        _, kwargs = paper.to_rdf.call_args
        assert kwargs["related_entities"]["authors"] == ["author"]
        assert kwargs["related_entities"]["sections"] == ["section"]
        assert "figures" not in kwargs["related_entities"]  # dropped, matches source behavior

    def test_uses_default_include_content_when_none(self, mapper, tmp_path):
        paper = _fake_entity("PaperEntity")
        mapper.default_include_content = False
        author = MagicMock()
        author.__class__.__name__ = "AuthorEntity"
        with patch.object(mapper, "serialize_graph"):
            mapper.convert_and_save_papers_to_rdf(
                {"1": (paper, [author], [], [], [], [])}, output_dir=str(tmp_path)
            )
        _, kwargs = paper.to_rdf.call_args
        assert "authors" in kwargs["related_entities"]


class TestFilterMetadataEntities:
    def test_keeps_only_metadata_types(self, mapper):
        author = MagicMock()
        author.__class__.__name__ = "AuthorEntity"
        section = MagicMock()
        section.__class__.__name__ = "SectionEntity"
        result = mapper._filter_metadata_entities({"authors": [author], "sections": [section]})
        assert list(result) == ["authors"]

    def test_empty_lists_and_all_filtered_out_dropped(self, mapper):
        section = MagicMock()
        section.__class__.__name__ = "SectionEntity"
        result = mapper._filter_metadata_entities({"sections": [section], "empty": []})
        assert result == {}


class TestFilterContentEntitiesFromRelated:
    def test_keeps_only_content_relationships(self, mapper):
        result = mapper._filter_content_entities_from_related(
            {"sections": ["s"], "authors": ["a"], "tables": ["t"]}
        )
        assert set(result) == {"sections", "tables"}

    def test_empty_relationship_dropped(self, mapper):
        result = mapper._filter_content_entities_from_related({"sections": []})
        assert result == {}


class TestSaveRdfDispatch:
    def test_metadata_kg_type(self, mapper, tmp_path):
        with patch.object(mapper, "save_metadata_rdf") as mock_save:
            mapper.save_rdf({}, output_dir=str(tmp_path), kg_type="metadata")
        mock_save.assert_called_once()

    def test_content_kg_type(self, mapper, tmp_path):
        with patch.object(mapper, "save_content_rdf") as mock_save:
            mapper.save_rdf({}, output_dir=str(tmp_path), kg_type="content")
        mock_save.assert_called_once()

    def test_complete_kg_type_default(self, mapper, tmp_path):
        with patch.object(mapper, "save_complete_rdf") as mock_save:
            mapper.save_rdf({}, output_dir=str(tmp_path), kg_type="complete")
        mock_save.assert_called_once()

    def test_uses_configured_default_kg_type(self, mapper, tmp_path):
        mapper.default_kg_type = "metadata"
        with patch.object(mapper, "save_metadata_rdf") as mock_save:
            mapper.save_rdf({}, output_dir=str(tmp_path))
        mock_save.assert_called_once()


class TestSaveMetadataContentComplete:
    def test_save_metadata_rdf_excludes_content(self, mapper, tmp_path):
        paper = _fake_entity("PaperEntity")
        with patch.object(mapper, "serialize_graph"):
            graphs = mapper.save_metadata_rdf({"1": {"entity": paper}}, output_dir=str(tmp_path))
        assert "1" in graphs

    def test_save_content_rdf_filters_entities(self, mapper, tmp_path):
        section = _fake_entity("SectionEntity")
        paper = _fake_entity("PaperEntity")
        with patch.object(mapper, "serialize_graph"):
            graphs = mapper.save_content_rdf(
                {
                    "sec1": {"entity": section},
                    "paper1": {"entity": paper, "related_entities": {}},
                },
                output_dir=str(tmp_path),
            )
        # section entity is content-typed -> kept; bare paper with no content
        # relations and non-content type -> dropped
        assert "sec1" in graphs
        assert "paper1" not in graphs

    def test_save_content_rdf_keeps_paper_with_content_relations(self, mapper, tmp_path):
        paper = _fake_entity("PaperEntity")
        section = MagicMock()
        section.__class__.__name__ = "SectionEntity"
        with patch.object(mapper, "serialize_graph"):
            graphs = mapper.save_content_rdf(
                {"1": {"entity": paper, "related_entities": {"sections": [section]}}},
                output_dir=str(tmp_path),
            )
        assert "1" in graphs

    def test_save_complete_rdf_includes_everything(self, mapper, tmp_path):
        paper = _fake_entity("PaperEntity")
        author = MagicMock()
        author.__class__.__name__ = "AuthorEntity"
        with patch.object(mapper, "serialize_graph"):
            graphs = mapper.save_complete_rdf(
                {"1": {"entity": paper, "related_entities": {"authors": [author]}}},
                output_dir=str(tmp_path),
            )
        assert "1" in graphs
        _, kwargs = paper.to_rdf.call_args
        assert "authors" in kwargs["related_entities"]
