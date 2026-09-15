"""Tests covering remaining gaps in RDF converter functions.

Covers: _merge_rdf_graph, convert_pipeline_to_rdf (caching, annotations-only),
convert_incremental_to_rdf (caching, namespaces), create_named_graph,
convert_to_rdf (comprehensive), and _convert_to_rdf (extraction_info).
"""

from unittest.mock import Mock, patch

import pytest
from rdflib import Dataset, Graph, URIRef

from pyeuropepmc.cache.cache import CacheDataType
from pyeuropepmc.mappers.converters import (
    RDFConversionError,
    _convert_to_rdf,
    _merge_rdf_graph,
    convert_incremental_to_rdf,
    convert_pipeline_to_rdf,
    convert_to_rdf,
    create_named_graph,
)

S = URIRef("http://example.org/s")
P = URIRef("http://example.org/p")
O = URIRef("http://example.org/o")


# ---------------------------------------------------------------------------
# _merge_rdf_graph
# ---------------------------------------------------------------------------


class TestMergeRdfGraph:
    """Tests for _merge_rdf_graph — merging triples/quads between graphs."""

    def test_merge_plain_graph_into_dataset(self):
        target = Dataset()
        source = Graph()
        source.add((S, P, O))
        _merge_rdf_graph(target, source)
        assert (S, P, O) in target

    def test_merge_dataset_with_quads(self):
        target = Dataset()
        source = Dataset()
        ctx = URIRef("http://example.org/ctx")
        source.add((S, P, O, ctx))
        _merge_rdf_graph(target, source)
        assert (S, P, O, ctx) in target

    def test_merge_quad_with_none_context_falls_back_to_triple(self):
        target = Dataset()
        source = Dataset()
        source.add((S, P, O))
        _merge_rdf_graph(target, source)
        assert (S, P, O) in target

    def test_merge_empty_source_does_not_alter_target(self):
        target = Dataset()
        target.add((S, P, O))
        source = Graph()
        _merge_rdf_graph(target, source)
        assert len(target) == 1

    def test_merge_multiple_quads_across_contexts(self):
        target = Dataset()
        source = Dataset()
        ctx1 = URIRef("http://example.org/ctx1")
        ctx2 = URIRef("http://example.org/ctx2")
        source.add((S, P, O, ctx1))
        source.add((URIRef("http://ex.org/s2"), P, O, ctx2))
        _merge_rdf_graph(target, source)
        assert (S, P, O, ctx1) in target
        assert (URIRef("http://ex.org/s2"), P, O, ctx2) in target


# ---------------------------------------------------------------------------
# convert_pipeline_to_rdf — caching and annotations-only paths
# ---------------------------------------------------------------------------


class TestConvertPipelineCaching:
    """Tests for convert_pipeline_to_rdf with caching and partial data."""

    @patch("pyeuropepmc.mappers.converters._merge_rdf_graph")
    @patch("pyeuropepmc.mappers.converters.convert_annotations_to_rdf")
    @patch("pyeuropepmc.mappers.converters.convert_enrichment_to_rdf")
    @patch("pyeuropepmc.mappers.converters.convert_xml_to_rdf")
    @patch("pyeuropepmc.mappers.converters.convert_search_to_rdf")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    def test_pipeline_with_all_sources_caches_result(
        self,
        mock_setup,
        mock_search,
        mock_xml,
        mock_enrich,
        mock_annot,
        mock_merge,
    ):
        ds = Mock()
        mock_setup.return_value = ds
        mock_search.return_value = Mock()
        mock_xml.return_value = Mock()
        mock_enrich.return_value = Mock()
        mock_annot.return_value = Mock()
        cache = Mock()

        result = convert_pipeline_to_rdf(
            search_results=[{"doi": "10.1"}],
            xml_data={"paper": {"title": "T"}},
            enrichment_data={"paper": {"title": "T"}},
            annotations_data=[{"source": "MED"}],
            cache_backend=cache,
        )

        assert result is ds
        assert mock_search.called
        assert mock_xml.called
        assert mock_enrich.called
        assert mock_annot.called
        assert mock_merge.call_count == 4
        cache.set.assert_called_once()
        key, val = cache.set.call_args[0][0], cache.set.call_args[0][1]
        assert key.startswith("pipeline_rdf_")
        assert val is ds
        assert cache.set.call_args[1]["data_type"] == CacheDataType.FULLTEXT

    @patch("pyeuropepmc.mappers.converters._merge_rdf_graph")
    @patch("pyeuropepmc.mappers.converters.convert_annotations_to_rdf")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    def test_pipeline_with_annotations_only(self, mock_setup, mock_annot, mock_merge):
        ds = Mock()
        mock_setup.return_value = ds
        mock_annot.return_value = Mock()

        result = convert_pipeline_to_rdf(annotations_data=[{"source": "MED", "extId": "12345"}])

        assert result is ds
        mock_annot.assert_called_once()
        mock_merge.assert_called_once()

    @patch("pyeuropepmc.mappers.converters._merge_rdf_graph")
    @patch("pyeuropepmc.mappers.converters.convert_search_to_rdf")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    def test_pipeline_caching_key_and_type(self, mock_setup, mock_search, mock_merge):
        ds = Mock()
        mock_setup.return_value = ds
        mock_search.return_value = Mock()
        cache = Mock()

        convert_pipeline_to_rdf(search_results=[{"doi": "10.1"}], cache_backend=cache)

        cache.set.assert_called_once()
        call = cache.set.call_args
        assert call[0][0].startswith("pipeline_rdf_")
        assert call[1]["data_type"] == CacheDataType.FULLTEXT

    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    def test_pipeline_error_wraps_exception(self, mock_setup):
        mock_setup.side_effect = Exception("Setup failure")
        with pytest.raises(RDFConversionError, match="Failed to convert pipeline data to RDF"):
            convert_pipeline_to_rdf(search_results=[{"doi": "10.1"}])


# ---------------------------------------------------------------------------
# convert_incremental_to_rdf — caching, namespaces, extraction_info
# ---------------------------------------------------------------------------


class TestConvertIncrementalEnhanced:
    """Tests for convert_incremental_to_rdf with caching, namespaces, etc."""

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters._extract_entities_from_enrichment")
    def test_incremental_with_caching(self, mock_extract, mock_get_mapper):
        entity = Mock()
        entity.to_rdf.return_value = None
        mock_extract.return_value = [{"entity": entity, "related_entities": {}}]
        mock_get_mapper.return_value = Mock()
        cache = Mock()

        result = convert_incremental_to_rdf(
            Graph(), {"paper": {"title": "T"}}, cache_backend=cache
        )

        assert isinstance(result, Graph)
        cache.set.assert_called_once()
        key = cache.set.call_args[0][0]
        assert key.startswith("incremental_rdf_")
        assert cache.set.call_args[1]["data_type"] == CacheDataType.RECORD

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters._extract_entities_from_enrichment")
    def test_incremental_with_namespaces(self, mock_extract, mock_get_mapper):
        entity = Mock()
        entity.to_rdf.return_value = None
        mock_extract.return_value = [{"entity": entity, "related_entities": {}}]
        mock_get_mapper.return_value = Mock()

        result = convert_incremental_to_rdf(
            Graph(),
            {"paper": {"title": "T"}},
            namespaces={"ex": "http://example.org/", "custom": "http://custom.org/"},
        )

        ns = dict(result.namespaces())
        assert str(ns["ex"]) == "http://example.org/"
        assert str(ns["custom"]) == "http://custom.org/"

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters._extract_entities_from_enrichment")
    def test_incremental_with_extraction_info(self, mock_extract, mock_get_mapper):
        entity = Mock()
        entity.to_rdf.return_value = None
        mock_extract.return_value = [{"entity": entity, "related_entities": {}}]
        mock_get_mapper.return_value = Mock()
        info = {"method": "test", "timestamp": "2024-01-01T00:00:00Z"}

        convert_incremental_to_rdf(Graph(), {"paper": {"title": "T"}}, extraction_info=info)

        entity.to_rdf.assert_called_once()
        assert entity.to_rdf.call_args[1]["extraction_info"] == info

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters._extract_entities_from_enrichment")
    def test_incremental_entity_conversion_failure_continues(self, mock_extract, mock_get_mapper):
        bad = Mock()
        bad.to_rdf.side_effect = Exception("Entity error")
        good = Mock()
        good.to_rdf.return_value = None
        mock_extract.return_value = [
            {"entity": bad, "related_entities": {}},
            {"entity": good, "related_entities": {}},
        ]
        mock_get_mapper.return_value = Mock()

        result = convert_incremental_to_rdf(Graph(), {"paper": {"title": "T"}})

        assert isinstance(result, Graph)
        bad.to_rdf.assert_called_once()
        good.to_rdf.assert_called_once()

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters._extract_entities_from_enrichment")
    def test_incremental_caching_and_namespaces_together(self, mock_extract, mock_get_mapper):
        entity = Mock()
        entity.to_rdf.return_value = None
        mock_extract.return_value = [{"entity": entity, "related_entities": {}}]
        mock_get_mapper.return_value = Mock()
        cache = Mock()

        result = convert_incremental_to_rdf(
            Graph(),
            {"paper": {"title": "T"}},
            namespaces={"ex": "http://example.org/"},
            cache_backend=cache,
        )

        ns = dict(result.namespaces())
        assert str(ns["ex"]) == "http://example.org/"
        cache.set.assert_called_once()


# ---------------------------------------------------------------------------
# create_named_graph
# ---------------------------------------------------------------------------


class TestCreateNamedGraph:
    """Tests for create_named_graph helper."""

    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_create_named_graph_binds_ontologies_and_standard_ns(self, mock_cfg):
        mock_cfg.return_value = {
            "ontologies": {"ex": "http://example.org/", "cito": "http://purl.org/spar/cito/"}
        }
        ng = create_named_graph("test", "Title", "Description")
        ns = dict(ng.namespaces())
        assert str(ns["ex"]) == "http://example.org/"
        assert str(ns["cito"]) == "http://purl.org/spar/cito/"
        assert "rdf" in ns
        assert "rdfs" in ns
        assert "xsd" in ns

    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_create_named_graph_empty_ontologies(self, mock_cfg):
        mock_cfg.return_value = {"ontologies": {}}
        ng = create_named_graph("test", "Title", "Description")
        ns = dict(ng.namespaces())
        assert "rdf" in ns
        assert "rdfs" in ns
        assert "xsd" in ns

    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_create_named_graph_missing_ontologies_key(self, mock_cfg):
        mock_cfg.return_value = {}
        ng = create_named_graph("test", "Title", "Description")
        ns = dict(ng.namespaces())
        assert "rdf" in ns
        assert "rdfs" in ns
        assert "xsd" in ns


# ---------------------------------------------------------------------------
# convert_to_rdf  — comprehensive conversion
# ---------------------------------------------------------------------------


def _default_config(**overrides):
    """Return a minimal valid named-graph config for convert_to_rdf tests."""
    cfg = {
        "named_graphs": {
            "publications": {"enabled": True, "uri_base": "http://ex.org/publications"},
            "authors": {"enabled": True, "uri_base": "http://ex.org/authors"},
            "institutions": {"enabled": True, "uri_base": "http://ex.org/institutions"},
            "provenance": {"enabled": True, "uri_base": "http://ex.org/provenance"},
        },
        "required_named_graphs": ["publications", "authors", "institutions", "provenance"],
        "ontologies": {},
    }
    cfg.update(overrides)
    return cfg


class TestConvertToRdf:
    """Tests for the comprehensive convert_to_rdf function."""

    @patch("pyeuropepmc.mappers.converters.add_shacl_validation_shapes")
    @patch("pyeuropepmc.mappers.converters.add_provenance_and_metadata")
    @patch("pyeuropepmc.mappers.converters.add_quality_metrics")
    @patch("pyeuropepmc.mappers.converters.build_institutional_hierarchies")
    @patch("pyeuropepmc.mappers.converters.build_collaboration_networks")
    @patch("pyeuropepmc.mappers.converters.build_citation_networks")
    @patch("pyeuropepmc.mappers.converters.process_enrichment_for_rdf")
    @patch("pyeuropepmc.mappers.converters.process_xml_for_rdf")
    @patch("pyeuropepmc.mappers.converters.process_search_for_rdf")
    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_all_sources(
        self,
        mock_cfg,
        mock_setup_ds,
        mock_mapper,
        mock_proc_search,
        mock_proc_xml,
        mock_proc_enrich,
        mock_citation,
        mock_collab,
        mock_hierarchy,
        mock_quality,
        mock_provenance,
        mock_shacl,
    ):
        mock_cfg.return_value = _default_config()
        ds = Mock()
        mock_setup_ds.return_value = ds
        m = Mock()
        mock_mapper.return_value = m
        sr = [{"doi": "10.1"}]
        xd = {"paper": {"title": "T"}}
        ed = {"paper": {"title": "T"}}

        dataset, uris = convert_to_rdf(search_results=sr, xml_data=xd, enrichment_data=ed)

        assert dataset is ds
        assert sorted(uris) == ["authors", "institutions", "provenance", "publications"]
        mock_proc_search.assert_called_once_with(sr, ds, uris, m, None)
        mock_proc_xml.assert_called_once_with(xd, ds, uris, m, None)
        mock_proc_enrich.assert_called_once_with(ed, ds, uris, m, None)
        mock_citation.assert_called_once()
        mock_collab.assert_called_once()
        mock_hierarchy.assert_called_once()
        mock_quality.assert_called_once()
        mock_provenance.assert_called_once()
        mock_shacl.assert_not_called()

    @patch("pyeuropepmc.mappers.converters.add_provenance_and_metadata")
    @patch("pyeuropepmc.mappers.converters.add_quality_metrics")
    @patch("pyeuropepmc.mappers.converters.build_institutional_hierarchies")
    @patch("pyeuropepmc.mappers.converters.build_collaboration_networks")
    @patch("pyeuropepmc.mappers.converters.build_citation_networks")
    @patch("pyeuropepmc.mappers.converters.process_enrichment_for_rdf")
    @patch("pyeuropepmc.mappers.converters.process_xml_for_rdf")
    @patch("pyeuropepmc.mappers.converters.process_search_for_rdf")
    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_disabled_networks_skipped(
        self,
        mock_cfg,
        mock_setup_ds,
        mock_mapper,
        mock_proc_search,
        mock_proc_xml,
        mock_proc_enrich,
        mock_citation,
        mock_collab,
        mock_hierarchy,
        mock_quality,
        mock_provenance,
    ):
        mock_cfg.return_value = _default_config(
            named_graphs={
                "publications": {"enabled": True, "uri_base": "http://ex.org/pubs"},
                "authors": {"enabled": True, "uri_base": "http://ex.org/authors"},
                "institutions": {"enabled": False, "uri_base": "http://ex.org/inst"},
                "provenance": {"enabled": True, "uri_base": "http://ex.org/prov"},
            },
            required_named_graphs=["publications", "authors", "provenance"],
        )
        ds = Mock()
        mock_setup_ds.return_value = ds
        mock_mapper.return_value = Mock()

        dataset, uris = convert_to_rdf(
            search_results=[{"doi": "10.1"}],
            enable_citation_networks=False,
            enable_collaboration_networks=False,
            enable_institutional_hierarchies=False,
            enable_quality_metrics=False,
        )

        assert "institutions" not in uris
        assert sorted(uris) == ["authors", "provenance", "publications"]
        mock_citation.assert_not_called()
        mock_collab.assert_not_called()
        mock_hierarchy.assert_not_called()
        mock_quality.assert_not_called()
        mock_provenance.assert_called_once()

    @patch("pyeuropepmc.mappers.converters.add_provenance_and_metadata")
    @patch("pyeuropepmc.mappers.converters.add_quality_metrics")
    @patch("pyeuropepmc.mappers.converters.build_institutional_hierarchies")
    @patch("pyeuropepmc.mappers.converters.build_collaboration_networks")
    @patch("pyeuropepmc.mappers.converters.build_citation_networks")
    @patch("pyeuropepmc.mappers.converters.process_enrichment_for_rdf")
    @patch("pyeuropepmc.mappers.converters.process_xml_for_rdf")
    @patch("pyeuropepmc.mappers.converters.process_search_for_rdf")
    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_with_annotations(
        self,
        mock_cfg,
        mock_setup_ds,
        mock_mapper,
        mock_proc_search,
        mock_proc_xml,
        mock_proc_enrich,
        mock_citation,
        mock_collab,
        mock_hierarchy,
        mock_quality,
        mock_provenance,
    ):
        mock_cfg.return_value = _default_config()
        ds = Mock()
        mock_setup_ds.return_value = ds
        mock_mapper.return_value = Mock()

        with (
            patch("pyeuropepmc.mappers.converters.convert_annotations_to_rdf") as mc_annot,
            patch("pyeuropepmc.mappers.converters._merge_rdf_graph") as mc_merge,
        ):
            mc_annot.return_value = Mock()
            annotations = [{"source": "MED", "extId": "12345"}]

            dataset, uris = convert_to_rdf(annotations_data=annotations)

            mc_annot.assert_called_once_with(annotations, None, None, None, None)
            mc_merge.assert_called_once()
            assert len(uris) == 4

    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_required_graph_missing_raises(self, mock_cfg, mock_setup_ds):
        mock_cfg.return_value = _default_config(
            named_graphs={"authors": {"enabled": True}},
            required_named_graphs=["publications", "authors"],
        )
        mock_setup_ds.return_value = Mock()
        with pytest.raises(
            RDFConversionError, match="Required named graph 'publications' not found"
        ):
            convert_to_rdf(search_results=[{"doi": "10.1"}])

    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_required_graph_disabled_raises(self, mock_cfg, mock_setup_ds):
        mock_cfg.return_value = _default_config(
            named_graphs={
                "publications": {"enabled": False},
                "authors": {"enabled": True},
            },
            required_named_graphs=["publications", "authors"],
        )
        mock_setup_ds.return_value = Mock()
        with pytest.raises(
            RDFConversionError, match="Required named graph 'publications' is disabled"
        ):
            convert_to_rdf(search_results=[{"doi": "10.1"}])

    @patch("pyeuropepmc.mappers.converters.add_provenance_and_metadata")
    @patch("pyeuropepmc.mappers.converters.add_quality_metrics")
    @patch("pyeuropepmc.mappers.converters.build_institutional_hierarchies")
    @patch("pyeuropepmc.mappers.converters.build_collaboration_networks")
    @patch("pyeuropepmc.mappers.converters.build_citation_networks")
    @patch("pyeuropepmc.mappers.converters.process_search_for_rdf")
    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_with_caching(
        self,
        mock_cfg,
        mock_setup_ds,
        mock_mapper,
        mock_proc_search,
        mock_citation,
        mock_collab,
        mock_hierarchy,
        mock_quality,
        mock_provenance,
    ):
        mock_cfg.return_value = _default_config()
        ds = Mock()
        mock_setup_ds.return_value = ds
        mock_mapper.return_value = Mock()
        cache = Mock()

        dataset, uris = convert_to_rdf(search_results=[{"doi": "10.1"}], cache_backend=cache)

        cache.set.assert_called_once()
        key, val = cache.set.call_args[0][0], cache.set.call_args[0][1]
        assert key.startswith("rdf_")
        assert val is ds
        assert cache.set.call_args[1]["data_type"] == CacheDataType.FULLTEXT

    @patch("pyeuropepmc.mappers.converters.add_provenance_and_metadata")
    @patch("pyeuropepmc.mappers.converters.add_quality_metrics")
    @patch("pyeuropepmc.mappers.converters.build_institutional_hierarchies")
    @patch("pyeuropepmc.mappers.converters.build_collaboration_networks")
    @patch("pyeuropepmc.mappers.converters.build_citation_networks")
    @patch("pyeuropepmc.mappers.converters.process_search_for_rdf")
    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_with_shacl_validation(
        self,
        mock_cfg,
        mock_setup_ds,
        mock_mapper,
        mock_proc_search,
        mock_citation,
        mock_collab,
        mock_hierarchy,
        mock_quality,
        mock_provenance,
    ):
        mock_cfg.return_value = _default_config()
        ds = Mock()
        mock_setup_ds.return_value = ds
        mock_mapper.return_value = Mock()

        with patch("pyeuropepmc.mappers.converters.add_shacl_validation_shapes") as m_shacl:
            dataset, uris = convert_to_rdf(
                search_results=[{"doi": "10.1"}], enable_shacl_validation=True
            )
            m_shacl.assert_called_once_with(ds, uris)

    @patch("pyeuropepmc.mappers.converters.add_provenance_and_metadata")
    @patch("pyeuropepmc.mappers.converters.add_quality_metrics")
    @patch("pyeuropepmc.mappers.converters.build_institutional_hierarchies")
    @patch("pyeuropepmc.mappers.converters.build_collaboration_networks")
    @patch("pyeuropepmc.mappers.converters.build_citation_networks")
    @patch("pyeuropepmc.mappers.converters.process_search_for_rdf")
    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_passes_extraction_info(
        self,
        mock_cfg,
        mock_setup_ds,
        mock_mapper,
        mock_proc_search,
        mock_citation,
        mock_collab,
        mock_hierarchy,
        mock_quality,
        mock_provenance,
    ):
        mock_cfg.return_value = _default_config()
        ds = Mock()
        mock_setup_ds.return_value = ds
        mock_mapper.return_value = Mock()
        info = {"method": "test", "timestamp": "2024-01-01T00:00:00Z"}

        dataset, uris = convert_to_rdf(search_results=[{"doi": "10.1"}], extraction_info=info)

        mock_proc_search.assert_called_once_with(
            [{"doi": "10.1"}], ds, uris, mock_mapper.return_value, info
        )
        mock_provenance.assert_called_once_with(ds, uris, info)

    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    @patch("pyeuropepmc.mappers.converters.load_rdf_config")
    def test_error_path(self, mock_cfg, mock_setup_ds):
        mock_cfg.return_value = _default_config()
        mock_setup_ds.return_value = Mock()
        with (
            patch("pyeuropepmc.mappers.converters._get_default_mapper") as m_mapper,
        ):
            m_mapper.side_effect = Exception("Mapper fail")
            with pytest.raises(RDFConversionError, match="Failed to convert data to RDF"):
                convert_to_rdf(search_results=[{"doi": "10.1"}])


# ---------------------------------------------------------------------------
# _convert_to_rdf — extraction_info and entity-failure paths
# ---------------------------------------------------------------------------


class TestConvertToRdfDetails:
    """Focused tests for _convert_to_rdf internals."""

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    def test_passes_extraction_info_to_entity(self, mock_setup_ds, mock_mapper):
        m = Mock()
        mock_mapper.return_value = m
        ds = Mock()
        mock_setup_ds.return_value = ds
        entity = Mock()
        entity.to_rdf.return_value = None
        info = {"method": "xml", "timestamp": "2024-01-01T00:00:00Z"}

        _convert_to_rdf(
            data={"x": 1},
            validator=Mock(),
            processor=Mock(return_value=[{"entity": entity, "related_entities": {}}]),
            cache_key_prefix="t",
            cache_data_type=CacheDataType.SEARCH,
            extraction_info=info,
        )

        entity.to_rdf.assert_called_once()
        assert entity.to_rdf.call_args[1]["extraction_info"] == info

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    def test_entity_failure_logs_and_continues(self, mock_setup_ds, mock_mapper):
        m = Mock()
        mock_mapper.return_value = m
        ds = Mock()
        mock_setup_ds.return_value = ds
        bad = Mock()
        bad.to_rdf.side_effect = Exception("Entity error")
        good = Mock()
        good.to_rdf.return_value = None

        result = _convert_to_rdf(
            data={"x": 1},
            validator=Mock(),
            processor=Mock(
                return_value=[
                    {"entity": bad, "related_entities": {}},
                    {"entity": good, "related_entities": {}},
                ]
            ),
            cache_key_prefix="t",
            cache_data_type=CacheDataType.SEARCH,
        )

        bad.to_rdf.assert_called_once()
        good.to_rdf.assert_called_once()
        assert result is ds

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    def test_passes_related_entities(self, mock_setup_ds, mock_mapper):
        m = Mock()
        mock_mapper.return_value = m
        ds = Mock()
        mock_setup_ds.return_value = ds
        entity = Mock()
        entity.to_rdf.return_value = None
        related = {"authors": [Mock()]}

        _convert_to_rdf(
            data={"x": 1},
            validator=Mock(),
            processor=Mock(return_value=[{"entity": entity, "related_entities": related}]),
            cache_key_prefix="t",
            cache_data_type=CacheDataType.SEARCH,
        )

        entity.to_rdf.assert_called_once()
        assert entity.to_rdf.call_args[1]["related_entities"] == related

    @patch("pyeuropepmc.mappers.converters._get_default_mapper")
    @patch("pyeuropepmc.mappers.converters.setup_dataset")
    def test_no_related_entities_key(self, mock_setup_ds, mock_mapper):
        m = Mock()
        mock_mapper.return_value = m
        ds = Mock()
        mock_setup_ds.return_value = ds
        entity = Mock()
        entity.to_rdf.return_value = None

        _convert_to_rdf(
            data={"x": 1},
            validator=Mock(),
            processor=Mock(return_value=[{"entity": entity}]),
            cache_key_prefix="t",
            cache_data_type=CacheDataType.SEARCH,
        )

        entity.to_rdf.assert_called_once()
        call_kwargs = entity.to_rdf.call_args[1]
        assert call_kwargs["related_entities"] == {}
