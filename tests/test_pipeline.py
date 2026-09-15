"""Unit tests for the paper processing pipeline."""

from pathlib import Path
import tempfile
from unittest.mock import patch

from pyeuropepmc.pipeline import PaperProcessingPipeline, PipelineConfig


class TestPipelineConfig:
    """Tests for PipelineConfig."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = PipelineConfig()

        assert config.enable_cache is True
        assert config.cache_size_mb == 500
        assert config.enable_enrichment is True
        assert config.enable_crossref is True
        assert config.enable_semantic_scholar is True
        assert config.enable_openalex is True
        assert config.enable_ror is True
        assert config.rdf_config_path is None
        assert config.output_format == "turtle"
        assert config.output_dir == "output"

    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = PipelineConfig(
            enable_cache=False,
            cache_size_mb=1024,
            enable_enrichment=False,
            enable_crossref=False,
            enable_semantic_scholar=False,
            enable_openalex=False,
            enable_ror=False,
            crossref_email="test@example.com",
            rdf_config_path="/path/to/config.yml",
            output_format="xml",
            output_dir="/tmp/output",
        )

        assert config.enable_cache is False
        assert config.cache_size_mb == 1024
        assert config.enable_enrichment is False
        assert config.crossref_email == "test@example.com"
        assert config.rdf_config_path == "/path/to/config.yml"
        assert config.output_format == "xml"
        assert config.output_dir == "/tmp/output"

    def test_to_cache_config(self):
        """Test conversion to CacheConfig."""
        config = PipelineConfig(enable_cache=True, cache_size_mb=256)
        cache_config = config.to_cache_config()

        assert cache_config.enabled is True
        assert cache_config.size_limit_mb == 256

    def test_to_enrichment_config(self):
        """Test conversion to EnrichmentConfig."""
        config = PipelineConfig(
            enable_crossref=True,
            enable_semantic_scholar=True,
            enable_openalex=True,
            enable_ror=True,
            crossref_email="test@example.com",
        )
        enrichment_config = config.to_enrichment_config()

        assert enrichment_config.enable_crossref is True
        assert enrichment_config.enable_semantic_scholar is True
        assert enrichment_config.enable_openalex is True
        assert enrichment_config.enable_ror is True
        assert enrichment_config.enable_unpaywall is False  # Always False per pipeline.py
        assert enrichment_config.crossref_email == "test@example.com"


class TestPaperProcessingPipeline:
    """Tests for PaperProcessingPipeline."""

    def test_initialization(self):
        """Test pipeline initialization."""
        config = PipelineConfig(
            enable_cache=False,  # Disable cache for testing
            enable_enrichment=False,  # Disable enrichment for testing
        )
        pipeline = PaperProcessingPipeline(config)

        assert pipeline.config == config
        assert pipeline.parser is not None
        assert pipeline.fulltext_client is not None
        assert pipeline.search_client is not None
        assert pipeline.rdf_mapper is not None
        assert pipeline.enricher is None  # Disabled
        assert pipeline.output_dir.exists()

    def test_initialization_with_enrichment(self):
        """Test pipeline initialization with enrichment enabled."""
        config = PipelineConfig(enable_enrichment=True, crossref_email="test@example.com")
        pipeline = PaperProcessingPipeline(config)

        assert pipeline.enricher is not None
        assert "crossref" in pipeline.enricher.clients

    def test_initialization_creates_output_dir(self):
        """Test that output directory is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PipelineConfig(output_dir=tmpdir)
            PaperProcessingPipeline(config)

            assert Path(tmpdir).exists()

    def test_process_paper_with_mocked_xml(self):
        """Test processing paper with mocked XML content."""
        # Mock XML content
        mock_xml = """<?xml version="1.0"?>
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
            <front>
                <article-meta>
                    <article-id pub-id-type="doi">10.1234/test.doi</article-id>
                    <article-id pub-id-type="pmc">1234567</article-id>
                    <title-group>
                        <article-title>Test Article Title</article-title>
                    </title-group>
                    <contrib-group>
                        <contrib contrib-type="author">
                            <name>
                                <surname>Doe</surname>
                                <given-names>John</given-names>
                            </name>
                        </contrib>
                    </contrib-group>
                </article-meta>
            </front>
            <body>
                <sec>
                    <title>Introduction</title>
                    <p>Test paragraph.</p>
                </sec>
            </body>
        </article>"""

        config = PipelineConfig(
            enable_cache=False,
            enable_enrichment=False,
            output_dir=tempfile.gettempdir(),
        )
        pipeline = PaperProcessingPipeline(config)

        from pyeuropepmc.models import PaperEntity

        paper = PaperEntity(
            pmcid="PMC1234567",
            doi="10.1234/test.doi",
            title="Test Article Title",
            authors=[],
        )

        entities = {
            "paper": paper,
            "authors": [],
            "sections": [],
            "tables": [],
            "figures": [],
            "references": [],
        }

        with (
            patch.object(pipeline, "_download_xml", return_value=None),
            patch.object(pipeline, "_parse_xml", return_value=entities),
            patch("pyeuropepmc.builders.from_parser.build_paper_entities") as mock_build,
        ):
            mock_build.return_value = (paper, [], [], [], [], [])

            with (
                patch.object(pipeline.rdf_mapper, "map_fields", return_value=None),
                patch.object(pipeline.rdf_mapper, "add_provenance", return_value=None),
            ):
                result = pipeline.process_paper(
                    xml_content=mock_xml,
                    doi="10.1234/test.doi",
                    save_rdf=False,
                )

                assert result is not None
                assert "entities" in result
                assert "rdf_graph" in result
                assert "triple_count" in result
                assert result["triple_count"] >= 0
                assert result["output_file"] is None  # save_rdf=False

    def test_process_papers_with_multiple_papers(self):
        """Test processing multiple papers."""
        mock_xml = """<?xml version="1.0"?>
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
            <front>
                <article-meta>
                    <article-id pub-id-type="doi">10.1234/test.doi</article-id>
                    <article-id pub-id-type="pmc">1234567</article-id>
                    <title-group>
                        <article-title>Test Article Title</article-title>
                    </title-group>
                    <contrib-group>
                        <contrib contrib-type="author">
                            <name>
                                <surname>Doe</surname>
                                <given-names>John</given-names>
                            </name>
                        </contrib>
                    </contrib-group>
                </article-meta>
            </front>
            <body>
                <sec>
                    <title>Introduction</title>
                    <p>Test paragraph.</p>
                </sec>
            </body>
        </article>"""

        config = PipelineConfig(
            enable_cache=False,
            enable_enrichment=False,
            output_dir=tempfile.gettempdir(),
        )
        pipeline = PaperProcessingPipeline(config)

        from pyeuropepmc.models import PaperEntity

        paper = PaperEntity(
            pmcid="PMC1234567",
            doi="10.1234/test.doi",
            title="Test Article",
            authors=[],
        )

        entities = {
            "paper": paper,
            "authors": [],
            "sections": [],
            "tables": [],
            "figures": [],
            "references": [],
        }

        xml_contents = {
            "10.1234/test.doi": mock_xml,
            "10.1234/test.doi2": mock_xml,
        }

        with (
            patch.object(pipeline, "_download_xml", return_value=None),
            patch.object(pipeline, "_parse_xml", return_value=entities),
            patch("pyeuropepmc.builders.from_parser.build_paper_entities") as mock_build,
        ):
            mock_build.return_value = (paper, [], [], [], [], [])

            with (
                patch.object(pipeline.rdf_mapper, "map_fields", return_value=None),
                patch.object(pipeline.rdf_mapper, "add_provenance", return_value=None),
            ):
                results = pipeline.process_papers(xml_contents, save_rdf=False)

                assert len(results) == 2
                for _identifier, result in results.items():
                    assert "entities" in result
                    assert "rdf_graph" in result
                    assert "triple_count" in result

    def test_process_papers_with_error_handling(self):
        """Test error handling in process_papers."""
        mock_xml = """<?xml version="1.0"?>
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
            <front>
                <article-meta>
                    <article-id pub-id-type="doi">10.1234/test.doi</article-id>
                    <title-group>
                        <article-title>Test Article</article-title>
                    </title-group>
                </article-meta>
            </front>
        </article>"""

        config = PipelineConfig(enable_cache=False, enable_enrichment=False)
        pipeline = PaperProcessingPipeline(config)

        xml_contents = {
            "10.1234/test.doi": mock_xml,
            "invalid_doi": "some content",
        }

        # This should handle errors gracefully
        with (
            patch.object(pipeline, "_download_xml", return_value=None),
            patch.object(pipeline.parser, "parse", side_effect=Exception("Parse error")),
        ):
            results = pipeline.process_papers(xml_contents, save_rdf=False)

            assert len(results) == 2
            # One should have an error
            has_error = any("error" in result for result in results.values())
            assert has_error

    def test_get_pmcid_from_doi_success(self):
        """Test getting PMCID from DOI."""
        config = PipelineConfig(enable_cache=False)
        pipeline = PaperProcessingPipeline(config)

        mock_search_result = {
            "resultList": {"result": [{"pmcid": "PMC1234567", "doi": "10.1234/test.doi"}]}
        }

        with patch.object(pipeline.search_client, "search", return_value=mock_search_result):
            pmcid = pipeline._get_pmcid_from_doi("10.1234/test.doi")
            assert pmcid == "PMC1234567"

    def test_get_pmcid_from_doi_not_found(self):
        """Test getting PMCID from DOI when not found."""
        config = PipelineConfig(enable_cache=False)
        pipeline = PaperProcessingPipeline(config)

        mock_search_result = {"resultList": {"result": []}}

        with patch.object(pipeline.search_client, "search", return_value=mock_search_result):
            pmcid = pipeline._get_pmcid_from_doi("10.1234/test.doi")
            assert pmcid is None

    def test_names_match(self):
        """Test name matching function."""
        config = PipelineConfig(enable_cache=False)
        pipeline = PaperProcessingPipeline(config)

        # Exact match
        assert pipeline._names_match("John Doe", "John Doe") is True

        # Case insensitive
        assert pipeline._names_match("john doe", "John Doe") is True

        # With titles
        assert pipeline._names_match("Dr. John Doe", "John Doe") is True
        assert pipeline._names_match("Prof. Jane Smith", "Jane Smith") is True

        # Different names
        assert pipeline._names_match("John Doe", "Jane Smith") is False

        # Empty strings
        assert pipeline._names_match("", "") is True

    def test_names_match_with_common_suffixes(self):
        """Test name matching with common suffixes."""
        config = PipelineConfig(enable_cache=False)
        pipeline = PaperProcessingPipeline(config)

        assert pipeline._names_match("John Doe PhD", "John Doe") is True
        assert pipeline._names_match("John Doe Ph.D.", "John Doe") is True
        assert pipeline._names_match("John Doe MD", "John Doe") is True

    def test_pipeline_context_manager(self):
        """Test pipeline can be used as context manager."""
        config = PipelineConfig(enable_cache=False, enable_enrichment=False)

        with PaperProcessingPipeline(config) as pipeline:
            assert pipeline is not None
            assert pipeline.enricher is None
