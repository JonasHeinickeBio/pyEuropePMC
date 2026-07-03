"""Tests for pyeuropepmc.processing.extensions.batch_processor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.processing.extensions.batch_processor import (
    BatchProcessor,
    BatchResult,
    ProcessingResult,
)

pytestmark = pytest.mark.unit

VALID_XML = '''<?xml version="1.0"?>
<article>
<front><article-meta>
<title-group><article-title>Test</article-title></title-group>
</article-meta></front>
<body><sec><p>Content</p></sec></body>
</article>'''


# ---------------------------------------------------------------------------
# 1. ProcessingResult
# ---------------------------------------------------------------------------
class TestProcessingResult:
    def test_construction_defaults(self):
        r = ProcessingResult(identifier="id1", success=True)
        assert r.identifier == "id1"
        assert r.success is True
        assert r.data is None
        assert r.error == ""
        assert r.duration == 0.0

    def test_to_dict_all_fields(self):
        r = ProcessingResult(
            identifier="id2",
            success=False,
            data={"title": "T"},
            error="boom",
            duration=1.234567,
        )
        d = r.to_dict()
        assert d == {
            "identifier": "id2",
            "success": False,
            "data": {"title": "T"},
            "error": "boom",
            "duration": round(1.234567, 3),
        }

    def test_to_dict_empty_error(self):
        r = ProcessingResult(identifier="id3", success=True, error="")
        d = r.to_dict()
        assert d["error"] == ""
        assert d["data"] is None


# ---------------------------------------------------------------------------
# 2. BatchResult
# ---------------------------------------------------------------------------
class TestBatchResult:
    @staticmethod
    def _make_results():
        return [
            ProcessingResult(identifier="a", success=True),
            ProcessingResult(identifier="b", success=False),
            ProcessingResult(identifier="c", success=True),
        ]

    def test_successes_and_failures(self):
        br = BatchResult(results=self._make_results())
        assert len(br.successes) == 2
        assert len(br.failures) == 1
        assert br.successes[0].identifier == "a"
        assert br.failures[0].identifier == "b"

    def test_success_rate_with_results(self):
        br = BatchResult(results=self._make_results())
        assert br.success_rate == pytest.approx(2 / 3)

    def test_success_rate_empty(self):
        br = BatchResult()
        assert br.success_rate == 0.0

    def test_to_dict(self):
        br = BatchResult(results=self._make_results(), total_duration=5.5)
        d = br.to_dict()
        assert d["total"] == 3
        assert d["successes"] == 2
        assert d["failures"] == 1
        assert d["total_duration"] == round(5.5, 3)
        assert len(d["results"]) == 3
        assert d["results"][0]["identifier"] == "a"


# ---------------------------------------------------------------------------
# 3. BatchProcessor.__init__
# ---------------------------------------------------------------------------
class TestBatchProcessorInit:
    def test_defaults(self):
        bp = BatchProcessor()
        assert bp.max_workers == 4
        assert bp.rate_limit == 3.0
        assert bp.progress_callback is None
        assert bp.error_callback is None

    def test_custom_params(self):
        cb = MagicMock()
        eb = MagicMock()
        bp = BatchProcessor(max_workers=8, rate_limit=5.0, progress_callback=cb, error_callback=eb)
        assert bp.max_workers == 8
        assert bp.rate_limit == 5.0
        assert bp.progress_callback is cb
        assert bp.error_callback is eb

    def test_rate_limit_minimum_enforced(self):
        bp = BatchProcessor(rate_limit=0.01)
        assert bp.rate_limit == 0.1

    def test_rate_limit_zero_enforced(self):
        bp = BatchProcessor(rate_limit=0.0)
        assert bp.rate_limit == 0.1


# ---------------------------------------------------------------------------
# 4. process_xml_strings – happy path, custom extraction, empty
# ---------------------------------------------------------------------------
class TestProcessXmlStringsHappy:
    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    @patch("pyeuropepmc.processing.extensions.batch_processor.FullTextXMLParser")
    def test_two_valid_xml(self, mock_parser_cls, _sleep):
        mock_instance = MagicMock()
        mock_instance.extract_metadata.return_value = {"title": "T"}
        mock_parser_cls.return_value = mock_instance

        bp = BatchProcessor(max_workers=1)
        items = [("id1", VALID_XML), ("id2", VALID_XML)]
        result = bp.process_xml_strings(items)

        assert isinstance(result, BatchResult)
        assert len(result.results) == 2
        assert all(r.success for r in result.results)

    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    @patch("pyeuropepmc.processing.extensions.batch_processor.FullTextXMLParser")
    def test_custom_extraction_fn(self, mock_parser_cls, _sleep):
        custom_fn = MagicMock(return_value={"custom_key": "val"})
        mock_parser_cls.return_value = MagicMock()

        bp = BatchProcessor(max_workers=1)
        result = bp.process_xml_strings([("x", VALID_XML)], extraction_fn=custom_fn)

        assert result.results[0].data == {"custom_key": "val"}
        custom_fn.assert_called_once()

    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    def test_empty_input(self, _sleep):
        bp = BatchProcessor()
        result = bp.process_xml_strings([])
        assert result.results == []
        assert result.success_rate == 0.0


# ---------------------------------------------------------------------------
# 5. process_xml_strings – error & progress callbacks
# ---------------------------------------------------------------------------
class TestProcessXmlStringsCallbacks:
    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    @patch("pyeuropepmc.processing.extensions.batch_processor.FullTextXMLParser")
    def test_error_callback_on_parse_failure(self, mock_parser_cls, _sleep):
        mock_parser_cls.side_effect = ValueError("bad xml")

        error_cb = MagicMock()
        bp = BatchProcessor(max_workers=1, error_callback=error_cb)
        result = bp.process_xml_strings([("bad", "<not xml>")])

        assert len(result.failures) == 1
        assert result.failures[0].error == "bad xml"
        error_cb.assert_called_once()
        args = error_cb.call_args[0]
        assert args[0] == "bad"
        assert isinstance(args[1], ValueError)

    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    @patch("pyeuropepmc.processing.extensions.batch_processor.FullTextXMLParser")
    def test_progress_callback_invoked(self, mock_parser_cls, _sleep):
        mock_parser_cls.return_value = MagicMock()

        progress_cb = MagicMock()
        bp = BatchProcessor(max_workers=1, progress_callback=progress_cb)
        bp.process_xml_strings([("a", VALID_XML), ("b", VALID_XML)])

        assert progress_cb.call_count == 2


# ---------------------------------------------------------------------------
# 6. process_files – tmp_path, mock time.sleep
# ---------------------------------------------------------------------------
class TestProcessFiles:
    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    @patch("pyeuropepmc.processing.extensions.batch_processor.FullTextXMLParser")
    def test_process_xml_files(self, mock_parser_cls, _sleep, tmp_path):
        mock_instance = MagicMock()
        mock_instance.extract_metadata.return_value = {"title": "F"}
        mock_parser_cls.return_value = mock_instance

        f1 = tmp_path / "a.xml"
        f1.write_text(VALID_XML)
        f2 = tmp_path / "b.xml"
        f2.write_text(VALID_XML)

        bp = BatchProcessor(max_workers=1)
        result = bp.process_files([str(f1), str(f2)])

        assert len(result.results) == 2
        assert all(r.success for r in result.results)
        assert result.total_duration >= 0


# ---------------------------------------------------------------------------
# 7. process_directories – subdirectory with XML files
# ---------------------------------------------------------------------------
class TestProcessDirectories:
    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    @patch("pyeuropepmc.processing.extensions.batch_processor.FullTextXMLParser")
    def test_discovers_xml_in_subdirectory(self, mock_parser_cls, _sleep, tmp_path):
        mock_parser_cls.return_value = MagicMock()

        sub = tmp_path / "papers"
        sub.mkdir()
        (sub / "p1.xml").write_text(VALID_XML)
        (sub / "p2.xml").write_text(VALID_XML)
        (sub / "readme.txt").write_text("not xml")

        bp = BatchProcessor(max_workers=1)
        result = bp.process_directories([str(sub)])

        assert len(result.results) == 2


# ---------------------------------------------------------------------------
# 8. process_directories – empty directory, warning logged
# ---------------------------------------------------------------------------
class TestProcessDirectoriesEmpty:
    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    @patch("pyeuropepmc.processing.extensions.batch_processor.logger")
    def test_empty_directory_logs_warning(self, mock_logger, _sleep, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()

        bp = BatchProcessor()
        result = bp.process_directories([str(empty)])

        assert result.results == []
        mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# 9. _extract_data – default, partial failure, custom
# ---------------------------------------------------------------------------
class TestExtractData:
    def test_default_extraction(self):
        parser = MagicMock()
        parser.extract_metadata.return_value = {"m": 1}
        parser.extract_authors.return_value = ["a"]
        parser.get_full_text_sections.return_value = ["s"]
        parser.extract_references.return_value = ["r"]
        parser.extract_figures.return_value = ["f"]
        parser.extract_tables.return_value = ["t"]
        parser.extract_funding.return_value = ["fn"]

        data = BatchProcessor._extract_data(parser)
        assert data["metadata"] == {"m": 1}
        assert data["authors"] == ["a"]
        assert data["sections"] == ["s"]
        assert data["references"] == ["r"]
        assert data["figures"] == ["f"]
        assert data["tables"] == ["t"]
        assert data["funding"] == ["fn"]

    def test_partial_failure_suppressed(self):
        parser = MagicMock()
        parser.extract_metadata.side_effect = Exception("fail")
        parser.extract_authors.return_value = ["ok"]

        data = BatchProcessor._extract_data(parser)
        assert "metadata" not in data
        assert data["authors"] == ["ok"]

    def test_custom_extraction_fn(self):
        parser = MagicMock()
        custom_fn = MagicMock(return_value={"x": 42})

        data = BatchProcessor._extract_data(parser, extraction_fn=custom_fn)
        assert data == {"x": 42}
        custom_fn.assert_called_once_with(parser)


# ---------------------------------------------------------------------------
# 10. _rate_sleep
# ---------------------------------------------------------------------------
class TestRateSleep:
    @patch("pyeuropepmc.processing.extensions.batch_processor.time.sleep")
    def test_calls_sleep(self, mock_sleep):
        bp = BatchProcessor(rate_limit=5.0)
        bp._rate_sleep()
        mock_sleep.assert_called_once_with(0.2)
