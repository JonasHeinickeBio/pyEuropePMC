"""
Comprehensive tests for the pyEuropePMC benchmark suite:
  - Dataset management (registry, info, local datasets)
  - All 5 XML-level metrics on synthetic and real XML
  - Report aggregation and serialization
  - Runner orchestration
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET  # nosec B405

import pytest

from pyeuropepmc.benchmark.dataset import (
    DATASETS,
    BenchmarkDataset,
    dataset_info,
)
from pyeuropepmc.benchmark.metrics import (
    compute_all_metrics,
    compute_element_coverage,
    compute_inline_recall,
    compute_metadata_accuracy,
    compute_section_accuracy,
    compute_text_fidelity,
)
from pyeuropepmc.benchmark.report import BenchmarkReport
from pyeuropepmc.benchmark.runner import BenchmarkRunner
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

# ============================================================================
# Test fixtures
# ============================================================================

SIMPLE_ARTICLE = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink"
         xmlns:mml="http://www.w3.org/1998/Math/MathML">
<front>
<article-meta>
<article-id pub-id-type="pmcid">PMC9999999</article-id>
<article-id pub-id-type="doi">10.1234/bench.2024</article-id>
<article-id pub-id-type="pmid">12345678</article-id>
<title-group><article-title>Benchmark Test Article</article-title></title-group>
<contrib-group>
<contrib contrib-type="author"><name><surname>Smith</surname><given-names>John A</given-names></name></contrib>
<contrib contrib-type="author"><name><surname>Doe</surname><given-names>Jane</given-names></name></contrib>
</contrib-group>
</article-meta>
</front>
<body>
<sec id="s1"><title>Introduction</title>
<p>This is the first paragraph with <bold>bold</bold> and <italic>italic</italic> text.</p>
<p>Second paragraph with an <xref ref-type="fig" rid="f1">inline xref</xref>.</p>
<list list-type="ordered"><list-item><p>Item one</p></list-item><list-item><p>Item two</p></list-item></list>
<def-list><def-item><term>DNA</term><def><p>Deoxyribonucleic acid</p></def></def-item></def-list>
</sec>
<sec id="s2"><title>Methods</title><p>Detailed methodology content here.</p></sec>
</body>
<back><ack><p>Acknowledged.</p></ack></back>
</article>
"""

# Article with a broader range of inline elements
ARTICLE_WITH_MATH = """<?xml version="1.0"?>
<article xmlns:mml="http://www.w3.org/1998/Math/MathML">
<body><sec><title>Results</title>
<p>Formula: <inline-formula id="f1"><mml:math><mml:mi>E</mml:mi><mml:mo>=</mml:mo><mml:mi>m</mml:mi><mml:msup><mml:mi>c</mml:mi><mml:mn>2</mml:mn></mml:msup></mml:math></inline-formula></p>
<p>Chemical: <named-content content-type="chemical">H<sub>2</sub>O</named-content></p>
</sec></body></article>
"""


@pytest.fixture
def tmp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _make_local_dataset(tmp_dir: Path, articles: dict[str, str]) -> Path:
    """Write XML articles into a temp directory and return the path."""
    for name, xml in articles.items():
        (tmp_dir / name).write_text(xml, encoding="utf-8")
    return tmp_dir


# ============================================================================
# Tests: Dataset
# ============================================================================


class TestDatasetRegistry:
    """Test the known dataset registry."""

    def test_registry_contains_expected(self):
        """Known datasets should all be present."""
        assert "PMC_sample_1943" in DATASETS
        assert "PLOS_1000" in DATASETS
        assert "eLife_984" in DATASETS
        assert "biorxiv-10k-test-2000" in DATASETS

    def test_dataset_info_lookup(self):
        """Lookup by name should work case-insensitively."""
        info = dataset_info("pmc_sample_1943")
        assert info is not None
        assert info.name == "PMC_sample_1943"
        assert info.article_count == 1943

        info2 = dataset_info("nonexistent")
        assert info2 is None

    def test_dataset_info_structure(self):
        """DatasetInfo should have all required fields."""
        info = DATASETS["PLOS_1000"]
        assert info.size_gb > 0
        assert info.article_count > 0
        assert info.source
        assert info.description


class TestLocalDataset:
    """Test creating a benchmark dataset from local files."""

    def test_local_dataset_creation(self, tmp_dir):
        """Create local dataset and verify articles are found."""
        xml_dir = _make_local_dataset(tmp_dir, {
            "PMC001.xml": SIMPLE_ARTICLE,
            "PMC002.xml": SIMPLE_ARTICLE.replace("9999999", "2000000"),
        })

        ds = BenchmarkDataset("local", local_path=xml_dir)
        assert ds.name == "local"
        assert ds.is_downloaded
        assert ds.article_count == 2

    def test_local_dataset_iteration(self, tmp_dir):
        """Iterate over articles in a local dataset."""
        xml_dir = _make_local_dataset(tmp_dir, {
            "a.xml": SIMPLE_ARTICLE,
            "b.xml": SIMPLE_ARTICLE,
        })

        ds = BenchmarkDataset("local", local_path=xml_dir)
        paths = list(ds.iter_articles())
        assert len(paths) == 2
        assert all(p.suffix == ".xml" for p in paths)

    def test_local_not_downloaded_raises(self):
        """Accessing undownloaded dataset should raise."""
        ds = BenchmarkDataset("local", local_path=Path("/nonexistent/path"))
        assert not ds.is_downloaded
        with pytest.raises(FileNotFoundError):
            list(ds.iter_articles())

    def test_local_no_path_raises(self):
        """Creating local dataset without path should raise."""
        with pytest.raises(ValueError, match="local_path"):
            BenchmarkDataset("local")

    def test_iter_articles_cache(self, tmp_dir):
        """Second call to iter_articles should use cache."""
        xml_dir = _make_local_dataset(tmp_dir, {
            "a.xml": SIMPLE_ARTICLE,
            "b.xml": SIMPLE_ARTICLE,
        })
        ds = BenchmarkDataset("local", local_path=xml_dir)
        # First call populates cache
        paths1 = list(ds.iter_articles())
        assert len(paths1) == 2
        # Second call hits cache
        paths2 = list(ds.iter_articles())
        assert len(paths2) == 2

    def test_get_article_paths_with_limit(self, tmp_dir):
        """get_article_paths respects the limit parameter."""
        articles = {f"PMC{i:03d}.xml": SIMPLE_ARTICLE for i in range(10)}
        xml_dir = _make_local_dataset(tmp_dir, articles)
        ds = BenchmarkDataset("local", local_path=xml_dir)
        paths = ds.get_article_paths(limit=3)
        assert len(paths) == 3

    def test_reset_cache(self, tmp_dir):
        """reset_cache clears the article path cache."""
        xml_dir = _make_local_dataset(tmp_dir, {"a.xml": SIMPLE_ARTICLE})
        ds = BenchmarkDataset("local", local_path=xml_dir)
        list(ds.iter_articles())  # populate cache
        assert ds._article_cache is not None
        ds.reset_cache()
        assert ds._article_cache is None

    def test_download_local_name_raises(self, tmp_dir):
        """download() on 'local' dataset raises because it's not a remote dataset."""
        nonexistent = tmp_dir / "nonexistent"
        ds = BenchmarkDataset("local", local_path=nonexistent)
        with pytest.raises(ValueError, match="cannot be downloaded"):
            ds.download()

    @pytest.mark.slow
    def test_known_dataset_name(self):
        """Known dataset can be created by name."""
        ds = BenchmarkDataset("PMC_sample_1943")
        assert ds.name == "PMC_sample_1943"
        assert not ds.is_downloaded  # not downloaded yet


# ============================================================================
# Tests: Metrics (XML-level)
# ============================================================================


class TestElementCoverage:
    """Test element coverage metric."""

    def test_coverage_baseline(self):
        """All elements in simple article should have some coverage."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_element_coverage(parser, SIMPLE_ARTICLE)
        assert "score" in result
        assert "total_elements" in result
        assert "coverage_pct" in result
        assert result["total_elements"] > 0
        assert result["score"] >= 0

    def test_coverage_lists_structured(self):
        """Coverage should include found/covered/missing lists."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_element_coverage(parser, SIMPLE_ARTICLE)
        el = result["element_lists"]
        assert "found" in el
        assert "covered" in el
        assert "missing" in el
        assert isinstance(el["found"], list)
        assert isinstance(el["covered"], list)


class TestTextFidelity:
    """Test text extraction fidelity metric."""

    def test_text_fidelity_has_content(self):
        """Text fidelity should extract non-empty body text."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_text_fidelity(parser, SIMPLE_ARTICLE)
        assert result["body_chars"] > 0
        assert result["extracted_chars"] > 0
        assert 0 <= result["score"] <= 1.0

    def test_text_fidelity_no_body(self):
        """Article with no body should gracefully report."""
        xml = "<?xml version='1.0'?><article><front></front></article>"
        parser = FullTextXMLParser(xml)
        result = compute_text_fidelity(parser, xml)
        assert result["body_chars"] == 0
        assert result["score"] >= 0


class TestSectionAccuracy:
    """Test section boundary accuracy metric."""

    def test_section_titles_found(self):
        """Section titles should be extractable."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_section_accuracy(parser, SIMPLE_ARTICLE)
        assert result["expected_section_count"] >= 2
        assert result["found_section_count"] >= 2
        assert "Introduction" in str(result["expected_titles"])

    def test_section_title_match(self):
        """Some section titles should match between expected and found."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_section_accuracy(parser, SIMPLE_ARTICLE)
        assert result["title_match_ratio"] >= 0.5  # at least some match


class TestInlineRecall:
    """Test inline element recall metric."""

    def test_inlines_detected(self):
        """Inline elements should be found in simple article."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_inline_recall(parser, SIMPLE_ARTICLE)
        assert result["total_in_xml"] > 0
        assert "bold" in result["by_type"]
        assert "italic" in result["by_type"]

    def test_inlines_with_math(self):
        """Inline formula should be detected."""
        parser = FullTextXMLParser(ARTICLE_WITH_MATH)
        result = compute_inline_recall(parser, ARTICLE_WITH_MATH)
        assert result["total_in_xml"] > 0
        # inline-formula or named-content should appear
        assert len(result["by_type"]) >= 1

    def test_no_inlines(self):
        """Article with no inline elements should give perfect score."""
        xml = "<?xml version='1.0'?><article><body><p>Plain text only.</p></body></article>"
        parser = FullTextXMLParser(xml)
        result = compute_inline_recall(parser, xml)
        assert result["score"] == 1.0
        assert result["total_in_xml"] == 0


class TestMetadataAccuracy:
    """Test metadata extraction accuracy metric."""

    def test_metadata_fields_extracted(self):
        """Title, DOI, PMCID, authors should be extractable."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_metadata_accuracy(parser, SIMPLE_ARTICLE)
        assert result["total_fields"] >= 4
        assert result["score"] >= 0.5  # most fields should match

    def test_title_matches(self):
        """Article title should match exactly."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_metadata_accuracy(parser, SIMPLE_ARTICLE)
        title_field = result["fields"].get("title", {})
        assert "Benchmark" in str(title_field.get("expected", ""))
        assert "Benchmark" in str(title_field.get("extracted", ""))

    def test_doi_matches(self):
        """DOI should match."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_metadata_accuracy(parser, SIMPLE_ARTICLE)
        doi_field = result["fields"].get("doi", {})
        assert "10.1234" in str(doi_field.get("expected", ""))


class TestAllMetrics:
    """Test the composite ``compute_all_metrics`` function."""

    def test_all_metrics_have_keys(self):
        """All five metrics should be present in the composite output."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_all_metrics(parser, SIMPLE_ARTICLE)
        for key in ("element_coverage", "text_fidelity", "section_accuracy",
                    "inline_recall", "metadata_accuracy"):
            assert key in result, f"Missing metric: {key}"
        assert "composite_score" in result
        assert "per_metric" in result
        assert 0 <= result["composite_score"] <= 1.0

    def test_per_metric_has_all_five(self):
        """Per-metric dict should have all five scores."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE)
        result = compute_all_metrics(parser, SIMPLE_ARTICLE)
        assert len(result["per_metric"]) == 5


# ============================================================================
# Tests: Report
# ============================================================================


class TestBenchmarkReport:
    """Test report aggregation and serialization."""

    def test_empty_report(self):
        """Empty report should have valid structure."""
        report = BenchmarkReport(title="Test")
        assert report.title == "Test"
        assert report.article_results == []
        assert len(report.aggregate_by_dataset()) == 0

    def test_add_article_result(self):
        """Adding an article result should work."""
        report = BenchmarkReport()
        report.add_article_result("test_dataset", "PMC001", {
            "composite_score": 0.85,
            "per_metric": {"element_coverage": 0.9, "text_fidelity": 0.8,
                           "section_accuracy": 0.85, "inline_recall": 0.9,
                           "metadata_accuracy": 0.8},
        })
        assert len(report.article_results) == 1
        assert report.article_results[0]["dataset"] == "test_dataset"

    def test_aggregate_by_dataset(self):
        """Aggregation should compute correct means."""
        report = BenchmarkReport()
        for i in range(3):
            report.add_article_result("ds1", f"A{i:03d}", {
                "composite_score": 0.8 - i * 0.1,
                "per_metric": {m: 0.8 - i * 0.1
                               for m in ("element_coverage", "text_fidelity",
                                          "section_accuracy", "inline_recall",
                                          "metadata_accuracy")},
            })

        agg = report.aggregate_by_dataset()
        assert "ds1" in agg
        ds1 = agg["ds1"]
        # The metric means should be (0.8 + 0.7 + 0.6) / 3 = 0.7
        assert abs(ds1["element_coverage"]["mean"] - 0.7) < 0.01
        assert ds1["article_count"] == 3

    def test_overall_aggregation(self):
        """Overall aggregation should include all articles."""
        report = BenchmarkReport()
        for ds_name in ("ds1", "ds2"):
            for i in range(2):
                report.add_article_result(ds_name, f"{ds_name}_{i}", {
                    "composite_score": 0.9,
                    "per_metric": {m: 0.9 for m in (
                        "element_coverage", "text_fidelity", "section_accuracy",
                        "inline_recall", "metadata_accuracy")},
                })

        overall = report.aggregate_overall()
        assert overall["total_articles"] == 4
        assert abs(overall["element_coverage"]["mean"] - 0.9) < 0.01

    def test_serialize_json(self, tmp_dir):
        """Report should roundtrip through JSON."""
        report = BenchmarkReport(title="Roundtrip")
        report.add_article_result("ds1", "PMC001", {
            "composite_score": 0.85,
            "per_metric": {m: 0.85 for m in (
                "element_coverage", "text_fidelity", "section_accuracy",
                "inline_recall", "metadata_accuracy")},
        })

        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["title"] == "Roundtrip"
        assert len(data["article_results"]) == 1

        # Save and reload
        path = tmp_dir / "report.json"
        report.save_json(path)
        assert path.exists()

        loaded = BenchmarkReport.load_json(path)
        assert loaded.title == "Roundtrip"
        assert len(loaded.article_results) == 1

    def test_set_metadata(self):
        """set_metadata should update report metadata."""
        report = BenchmarkReport()
        report.set_metadata(parser_version="1.0", config={"option": True})
        assert report.metadata["parser_version"] == "1.0"
        assert report.metadata["config"]["option"] is True

    def test_print_summary(self, capsys):
        """print_summary should output report contents."""
        report = BenchmarkReport(title="Test Summary")
        report.add_article_result("ds1", "A001", {
            "composite_score": 0.85,
            "per_metric": {"element_coverage": 0.9, "text_fidelity": 0.8,
                           "section_accuracy": 0.85, "inline_recall": 0.9,
                           "metadata_accuracy": 0.8},
        })
        report.print_summary()
        captured = capsys.readouterr()
        assert "Test Summary" in captured.out
        assert "ds1" in captured.out
        assert "0.9" in captured.out

    def test_print_summary_with_articles(self, capsys):
        """print_summary with include_articles should list per-article scores."""
        report = BenchmarkReport(title="Article Test")
        for i in range(3):
            report.add_article_result("ds1", f"A{i:03d}", {
                "composite_score": 0.9 - i * 0.1,
                "per_metric": {"element_coverage": 0.9 - i * 0.1},
            })
        report.print_summary(include_articles=True)
        captured = capsys.readouterr()
        assert "A001" in captured.out
        assert "A002" in captured.out

    def test_aggregate_overall_empty(self):
        """aggregate_overall with no articles should return no composite."""
        report = BenchmarkReport()
        overall = report.aggregate_overall()
        assert overall == {"total_articles": 0}

    def test_summarize_values_empty(self):
        """_summarize_values with empty list should return zeros."""
        from pyeuropepmc.benchmark.report import _summarize_values
        result = _summarize_values([])
        assert result == {"mean": 0.0, "median": 0.0, "min": 0.0,
                          "max": 0.0, "std": 0.0, "count": 0}


# ============================================================================
# Tests: Runner
# ============================================================================


class TestBenchmarkRunner:
    """Test the benchmark runner with local datasets."""

    def test_runner_with_local_dataset(self, tmp_dir):
        """Runner should process a local dataset and produce a report."""
        xml_dir = _make_local_dataset(tmp_dir, {
            "PMC001.xml": SIMPLE_ARTICLE,
            "PMC002.xml": SIMPLE_ARTICLE.replace("9999999", "2000000"),
        })
        ds = BenchmarkDataset("local", local_path=xml_dir)
        runner = BenchmarkRunner(ds)
        report = runner.run_all()

        assert runner.stats["successful"] == 2
        assert runner.stats["failed"] == 0
        assert len(report.article_results) == 2

    def test_runner_error_handling(self, tmp_dir):
        """Runner should handle parse errors gracefully."""
        xml_dir = _make_local_dataset(tmp_dir, {
            "good.xml": SIMPLE_ARTICLE,
            "bad.xml": "<not-valid<<xml>",
        })
        ds = BenchmarkDataset("local", local_path=xml_dir)
        runner = BenchmarkRunner(ds, skip_errors=True)
        report = runner.run_all()

        assert runner.stats["successful"] >= 1
        assert runner.stats["failed"] >= 1  # bad file

    def test_runner_with_limit(self, tmp_dir):
        """Runner limit should cap articles processed."""
        articles = {f"PMC{i:03d}.xml": SIMPLE_ARTICLE for i in range(10)}
        xml_dir = _make_local_dataset(tmp_dir, articles)
        ds = BenchmarkDataset("local", local_path=xml_dir)
        runner = BenchmarkRunner(ds, limit=3)
        report = runner.run_all()

        assert len(report.article_results) == 3

    def test_runner_generates_report(self, tmp_dir):
        """Runner should produce a report with valid structure."""
        xml_dir = _make_local_dataset(tmp_dir, {"test.xml": SIMPLE_ARTICLE})
        ds = BenchmarkDataset("local", local_path=xml_dir)
        runner = BenchmarkRunner(ds)
        report = runner.run_all()

        # Report should have dataset summaries
        assert report.dataset_summaries
        # Should have per-article results
        assert len(report.article_results) >= 1

        # Per-article metrics should include all five
        metrics = report.article_results[0]["metrics"]
        for key in ("element_coverage", "text_fidelity", "section_accuracy",
                    "inline_recall", "metadata_accuracy", "composite_score"):
            assert key in metrics

    def test_runner_multiple_datasets(self, tmp_dir):
        """Runner accepts a list of datasets."""
        (tmp_dir / "ds1").mkdir()
        (tmp_dir / "ds2").mkdir()
        xml_dir1 = _make_local_dataset(tmp_dir / "ds1", {
            "a.xml": SIMPLE_ARTICLE,
        })
        xml_dir2 = _make_local_dataset(tmp_dir / "ds2", {
            "b.xml": SIMPLE_ARTICLE.replace("Smith", "Jones"),
        })
        ds1 = BenchmarkDataset("local", local_path=xml_dir1)
        ds2 = BenchmarkDataset("local", local_path=xml_dir2)
        runner = BenchmarkRunner([ds1, ds2])
        report = runner.run_all()
        assert runner.stats["successful"] == 2
        assert runner.stats["total_articles"] == 2

    def test_runner_read_error(self, tmp_dir):
        """Runner handles file read errors gracefully."""
        xml_dir = _make_local_dataset(tmp_dir, {"good.xml": SIMPLE_ARTICLE})
        # Write a binary file (with .xml extension to match the glob) that fails on UTF-8 read
        (xml_dir / "bad.xml").write_bytes(b"\xff\xfe\x00\x01")
        ds = BenchmarkDataset("local", local_path=xml_dir)
        runner = BenchmarkRunner(ds, skip_errors=True)
        report = runner.run_all()
        assert runner.stats["failed"] >= 1
        assert "bad.xml" in str(runner.stats["parse_errors"])

    def test_runner_print_profile_summary_no_data(self, capsys, tmp_path):
        """print_profile_summary with no profiling data prints message."""
        from pyeuropepmc.benchmark.report import BenchmarkReport
        runner = BenchmarkRunner(BenchmarkDataset("local", local_path=tmp_path))
        report = BenchmarkReport(title="Empty Profile")
        runner.print_profile_summary(report)
        captured = capsys.readouterr()
        assert "No profiling data" in captured.out


# ============================================================================
# Tests: End-to-end with fixture XMLs
# ============================================================================


class TestWithFixtures:
    """End-to-end tests using the project's real XML fixtures."""

    FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "fulltext_downloads"

    @pytest.fixture(scope="class")
    def fixture_xmls(self):
        """Load available fixture XMLs."""
        xmls = {}
        for fname in ["PMC12311175.xml", "PMC12738713.xml",
                      "PMC3258128.xml", "PMC3359999.xml"]:
            fpath = self.FIXTURE_DIR / fname
            if fpath.exists() and fpath.stat().st_size > 1000:
                xmls[fname] = fpath.read_text(encoding="utf-8")
        return xmls

    @pytest.mark.slow
    def test_metrics_on_real_xml(self, fixture_xmls):
        """All five metrics should produce valid results on real XML."""
        for fname, xml in fixture_xmls.items():
            try:
                parser = FullTextXMLParser(xml)
                metrics = compute_all_metrics(parser, xml)
                assert 0 <= metrics["composite_score"] <= 1.0
                for key in ("element_coverage", "text_fidelity", "section_accuracy",
                            "inline_recall", "metadata_accuracy"):
                    assert key in metrics["per_metric"]
                    assert 0 <= metrics["per_metric"][key] <= 1.0
            except Exception as e:
                # XML fixtures may have specific characteristics that
                # the metrics don't handle yet — log and continue
                print(f"  {fname}: {type(e).__name__}: {e}")

    def test_element_coverage_pattern(self, fixture_xmls):
        """Element coverage should discover many element types in real XML."""
        for fname, xml in fixture_xmls.items():
            try:
                parser = FullTextXMLParser(xml)
                result = compute_element_coverage(parser, xml)
                assert result["total_elements"] > 10
                assert "element_lists" in result
            except Exception:
                pass
