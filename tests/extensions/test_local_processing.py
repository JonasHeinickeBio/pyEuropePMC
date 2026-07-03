"""Unit tests for pyeuropepmc.processing.extensions.local_processing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ============================================================================
# Fixtures
# ============================================================================

VALID_XML = '''<?xml version="1.0"?>
<article>
<front><article-meta>
<article-id pub-id-type="pmcid">PMC1234567</article-id>
<article-id pub-id-type="doi">10.1234/test</article-id>
<article-id pub-id-type="pmid">12345678</article-id>
<title-group><article-title>Test Article</article-title></title-group>
</article-meta></front>
<body><sec><p>Content</p></sec></body>
</article>'''

VALID_XML_2 = '''<?xml version="1.0"?>
<article>
<front><article-meta>
<article-id pub-id-type="pmcid">PMC9999999</article-id>
<article-id pub-id-type="doi">10.5678/other</article-id>
<title-group><article-title>Second Article</article-title></title-group>
</article-meta></front>
<body><sec><p>More content</p></sec></body>
</article>'''

INVALID_XML = "this is not valid xml at all"


# ============================================================================
# parse_xml_file
# ============================================================================


class TestParseXmlFile:
    def test_valid_file_returns_parser(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import parse_xml_file

        xml_file = tmp_path / "article.xml"
        xml_file.write_text(VALID_XML, encoding="utf-8")

        parser = parse_xml_file(xml_file)
        assert parser is not None
        assert "Test Article" in parser.xml_content

    def test_valid_file_with_string_path(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import parse_xml_file

        xml_file = tmp_path / "article.xml"
        xml_file.write_text(VALID_XML, encoding="utf-8")

        parser = parse_xml_file(str(xml_file))
        assert parser is not None

    def test_nonexistent_file_raises_file_not_found(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import parse_xml_file

        with pytest.raises(FileNotFoundError, match="not found"):
            parse_xml_file(tmp_path / "missing.xml")

    def test_directory_path_raises_value_error(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import parse_xml_file

        with pytest.raises(ValueError, match="not a file"):
            parse_xml_file(tmp_path)


# ============================================================================
# parse_xml_directory
# ============================================================================


class TestParseXmlDirectory:
    def test_valid_directory_with_xml_files(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            parse_xml_directory,
        )

        (tmp_path / "a.xml").write_text(VALID_XML, encoding="utf-8")
        (tmp_path / "b.xml").write_text(VALID_XML_2, encoding="utf-8")

        parsers = parse_xml_directory(tmp_path)
        assert len(parsers) == 2

    def test_empty_directory(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            parse_xml_directory,
        )

        parsers = parse_xml_directory(tmp_path)
        assert parsers == {}

    def test_nonexistent_directory_raises_file_not_found(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            parse_xml_directory,
        )

        with pytest.raises(FileNotFoundError, match="not found"):
            parse_xml_directory("/nonexistent/path/abc123")

    def test_non_directory_path_raises_value_error(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            parse_xml_directory,
        )

        file = tmp_path / "file.xml"
        file.write_text(VALID_XML, encoding="utf-8")

        with pytest.raises(ValueError, match="not a directory"):
            parse_xml_directory(file)

    def test_recursive_false(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            parse_xml_directory,
        )

        (tmp_path / "top.xml").write_text(VALID_XML, encoding="utf-8")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.xml").write_text(VALID_XML_2, encoding="utf-8")

        parsers = parse_xml_directory(tmp_path, recursive=False)
        assert len(parsers) == 1
        assert "top.xml" in list(parsers.keys())[0]

    def test_recursive_true(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            parse_xml_directory,
        )

        (tmp_path / "top.xml").write_text(VALID_XML, encoding="utf-8")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.xml").write_text(VALID_XML_2, encoding="utf-8")

        parsers = parse_xml_directory(tmp_path, recursive=True)
        assert len(parsers) == 2

    def test_custom_glob_pattern(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            parse_xml_directory,
        )

        (tmp_path / "a.xml").write_text(VALID_XML, encoding="utf-8")
        (tmp_path / "b.json").write_text('{"key": "value"}', encoding="utf-8")

        parsers_xml = parse_xml_directory(tmp_path, glob_pattern="*.xml")
        assert len(parsers_xml) == 1

        parsers_json = parse_xml_directory(tmp_path, glob_pattern="*.json")
        assert len(parsers_json) == 0

    def test_partial_failure_one_valid_one_invalid(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            parse_xml_directory,
        )

        (tmp_path / "good.xml").write_text(VALID_XML, encoding="utf-8")
        (tmp_path / "bad.xml").write_text(INVALID_XML, encoding="utf-8")

        parsers = parse_xml_directory(tmp_path)
        assert len(parsers) == 1
        assert any("good.xml" in k for k in parsers)


# ============================================================================
# extract_article_id_from_xml
# ============================================================================


class TestExtractArticleIdFromXml:
    def test_string_input_pmcid_priority(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        article_id = extract_article_id_from_xml(VALID_XML)
        assert article_id == "PMC1234567"

    def test_string_input_doi_only(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        xml = '''<?xml version="1.0"?>
        <article><front><article-meta>
        <article-id pub-id-type="doi">10.9999/journal</article-id>
        </article-meta></front></article>'''
        article_id = extract_article_id_from_xml(xml)
        assert article_id == "10.9999/journal"

    def test_string_input_pmid_only(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        xml = '''<?xml version="1.0"?>
        <article><front><article-meta>
        <article-id pub-id-type="pmid">87654321</article-id>
        </article-meta></front></article>'''
        article_id = extract_article_id_from_xml(xml)
        assert article_id == "87654321"

    def test_element_input(self) -> None:
        from xml.etree import ElementTree as ET

        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        root = ET.fromstring(VALID_XML)
        article_id = extract_article_id_from_xml(root)
        assert article_id == "PMC1234567"

    def test_no_ids_returns_none(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        xml = '''<?xml version="1.0"?>
        <article><front><article-meta>
        <title-group><article-title>No IDs</article-title></title-group>
        </article-meta></front></article>'''
        article_id = extract_article_id_from_xml(xml)
        assert article_id is None

    def test_invalid_xml_returns_none(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        article_id = extract_article_id_from_xml(INVALID_XML)
        assert article_id is None

    def test_priority_pmcid_over_doi(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        xml = '''<?xml version="1.0"?>
        <article><front><article-meta>
        <article-id pub-id-type="doi">10.1111/example</article-id>
        <article-id pub-id-type="pmcid">PMC1111111</article-id>
        </article-meta></front></article>'''
        article_id = extract_article_id_from_xml(xml)
        assert article_id == "PMC1111111"


# ============================================================================
# LocalXMLProcessor
# ============================================================================


class TestLocalXMLProcessor:
    def test_init_default_config(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        proc = LocalXMLProcessor()
        assert proc.config is None

    def test_init_custom_config(self) -> None:
        from pyeuropepmc.processing.config.element_patterns import ElementPatterns
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        cfg = ElementPatterns()
        proc = LocalXMLProcessor(config=cfg)
        assert proc.config is cfg

    def test_process_single_default_extraction(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        xml_file = tmp_path / "article.xml"
        xml_file.write_text(VALID_XML, encoding="utf-8")

        proc = LocalXMLProcessor()
        result = proc.process_single(xml_file)

        assert isinstance(result, dict)
        assert "metadata" in result
        assert "sections" in result

    def test_process_single_custom_extract_fn(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        xml_file = tmp_path / "article.xml"
        xml_file.write_text(VALID_XML, encoding="utf-8")

        def custom_extract(parser):
            return {"custom_key": "custom_value", "title": "extracted"}

        proc = LocalXMLProcessor()
        result = proc.process_single(xml_file, extract_fn=custom_extract)

        assert result == {"custom_key": "custom_value", "title": "extracted"}

    def test_process_directory_multiple_files(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        (tmp_path / "a.xml").write_text(VALID_XML, encoding="utf-8")
        (tmp_path / "b.xml").write_text(VALID_XML_2, encoding="utf-8")

        proc = LocalXMLProcessor()
        results = proc.process_directory(tmp_path)

        assert len(results) == 2
        for path, data in results.items():
            assert isinstance(data, dict)
            assert "metadata" in data

    def test_process_directory_custom_extract_fn(self, tmp_path: Path) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        (tmp_path / "a.xml").write_text(VALID_XML, encoding="utf-8")

        def custom_extract(parser):
            return {"ok": True}

        proc = LocalXMLProcessor()
        results = proc.process_directory(tmp_path, extract_fn=custom_extract)

        assert len(results) == 1
        for data in results.values():
            assert data == {"ok": True}

    def test_process_directory_error_in_one_file(self, tmp_path: Path) -> None:
        """Invalid XML is skipped by parse_xml_directory; only good file is processed."""
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        (tmp_path / "good.xml").write_text(VALID_XML, encoding="utf-8")
        (tmp_path / "bad.xml").write_text(INVALID_XML, encoding="utf-8")

        proc = LocalXMLProcessor()
        results = proc.process_directory(tmp_path)

        assert len(results) == 1
        for path, data in results.items():
            assert "good.xml" in path
            assert "metadata" in data

    def test_process_directory_extract_error_logged(self, tmp_path: Path) -> None:
        """Custom extract_fn that raises is caught and recorded as error."""
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        (tmp_path / "a.xml").write_text(VALID_XML, encoding="utf-8")
        (tmp_path / "b.xml").write_text(VALID_XML_2, encoding="utf-8")

        def failing_extract(parser):
            raise RuntimeError("extraction blew up")

        proc = LocalXMLProcessor()
        results = proc.process_directory(tmp_path, extract_fn=failing_extract)

        assert len(results) == 2
        for data in results.values():
            assert "error" in data
            assert "extraction blew up" in data["error"]


# ============================================================================
# LocalXMLProcessor._extract_all
# ============================================================================


class TestExtractAll:
    def test_extract_all_calls_all_methods(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        mock_parser = MagicMock()
        mock_parser.xml_content = VALID_XML
        mock_parser.extract_metadata.return_value = {"title": "Test"}
        mock_parser.extract_authors.return_value = []
        mock_parser.get_full_text_sections.return_value = []
        mock_parser.extract_references.return_value = []
        mock_parser.extract_figures.return_value = []
        mock_parser.extract_tables.return_value = []
        mock_parser.extract_funding.return_value = []
        mock_parser.extract_keywords.return_value = []

        result = LocalXMLProcessor._extract_all(mock_parser)

        assert result["metadata"] == {"title": "Test"}
        mock_parser.extract_metadata.assert_called_once()
        mock_parser.extract_authors.assert_called_once()
        mock_parser.get_full_text_sections.assert_called_once()
        mock_parser.extract_references.assert_called_once()
        mock_parser.extract_figures.assert_called_once()
        mock_parser.extract_tables.assert_called_once()
        mock_parser.extract_funding.assert_called_once()
        mock_parser.extract_keywords.assert_called_once()

    def test_extract_all_handles_metadata_error(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        mock_parser = MagicMock()
        mock_parser.xml_content = VALID_XML
        mock_parser.extract_metadata.side_effect = RuntimeError("parse fail")
        mock_parser.extract_authors.return_value = []
        mock_parser.get_full_text_sections.return_value = []

        result = LocalXMLProcessor._extract_all(mock_parser)

        assert "error" in result["metadata"]
        assert "parse fail" in result["metadata"]["error"]

    def test_extract_all_short_content(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        mock_parser = MagicMock()
        mock_parser.xml_content = "short"
        mock_parser.extract_metadata.return_value = {}
        mock_parser.extract_authors.return_value = []

        result = LocalXMLProcessor._extract_all(mock_parser)

        assert result["source"] == "short"


# ============================================================================
# process_single_pmc
# ============================================================================


class TestProcessSinglePmc:
    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_success(self, mock_urlopen, mock_sleep) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            process_single_pmc,
        )

        mock_resp = MagicMock()
        mock_resp.read.return_value = VALID_XML.encode("utf-8")
        mock_urlopen.return_value = mock_resp

        parser = process_single_pmc("PMC1234567")

        assert parser is not None
        mock_urlopen.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_404_raises_connection_error(self, mock_urlopen, mock_sleep) -> None:
        import urllib.error

        from pyeuropepmc.processing.extensions.local_processing import (
            process_single_pmc,
        )

        error_404 = urllib.error.HTTPError(
            url="http://test", code=404, msg="Not Found", hdrs=None, fp=None
        )
        mock_urlopen.side_effect = error_404

        with pytest.raises(ConnectionError, match="not found"):
            process_single_pmc("PMC0000000")

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_empty_response_raises_value_error(self, mock_urlopen, mock_sleep) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            process_single_pmc,
        )

        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_urlopen.return_value = mock_resp

        with pytest.raises(ConnectionError):
            process_single_pmc("PMC0000000", max_retries=1)

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_retry_then_success(self, mock_urlopen, mock_sleep) -> None:
        import urllib.error

        from pyeuropepmc.processing.extensions.local_processing import (
            process_single_pmc,
        )

        error = urllib.error.URLError("timeout")
        mock_resp = MagicMock()
        mock_resp.read.return_value = VALID_XML.encode("utf-8")

        mock_urlopen.side_effect = [error, mock_resp]

        parser = process_single_pmc("PMC1234567", max_retries=2)

        assert parser is not None
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once_with(2)

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_all_retries_exhausted_raises(self, mock_urlopen, mock_sleep) -> None:
        import urllib.error

        from pyeuropepmc.processing.extensions.local_processing import (
            process_single_pmc,
        )

        error = urllib.error.URLError("network down")
        mock_urlopen.side_effect = error

        with pytest.raises(ConnectionError, match="Failed to fetch"):
            process_single_pmc("PMC1111111", max_retries=2)

        assert mock_urlopen.call_count == 2
        assert mock_sleep.call_count == 1

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_invalid_pmc_id_prefix_normalization(self, mock_urlopen, mock_sleep) -> None:
        from pyeuropepmc.processing.extensions.local_processing import (
            PMC_FULLTEXT_BASE,
            process_single_pmc,
        )

        mock_resp = MagicMock()
        mock_resp.read.return_value = VALID_XML.encode("utf-8")
        mock_urlopen.return_value = mock_resp

        process_single_pmc("1234567")

        expected_url = PMC_FULLTEXT_BASE.format(pmcid="PMC1234567")
        actual_url = mock_urlopen.call_args[0][0]
        assert actual_url == expected_url


# ============================================================================
# _safe_parse
# ============================================================================


class TestSafeParse:
    def test_valid_xml(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import _safe_parse

        root = _safe_parse(VALID_XML)
        assert root is not None
        assert root.tag == "article"

    def test_invalid_xml_returns_none(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import _safe_parse

        result = _safe_parse(INVALID_XML)
        assert result is None


# ============================================================================
# parse_bits_book
# ============================================================================


class TestParseBitsBook:
    def test_raw_xml_string(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import parse_bits_book

        parser = parse_bits_book(VALID_XML)
        assert parser is not None

    def test_bits_root_detection(self) -> None:
        from pyeuropepmc.processing.extensions.local_processing import parse_bits_book

        bits_xml = '''<?xml version="1.0"?>
        <book xmlns:xlink="http://www.w3.org/1999/xlink">
        <book-meta>
        <book-title>BITS Book</book-title>
        </book-meta>
        <book-body>
        <chapter>
        <chapter-title>Chapter 1</chapter-title>
        <p>Book content</p>
        </chapter>
        </book-body>
        </book>'''

        with patch(
            "pyeuropepmc.processing.extensions.local_processing.FullTextXMLParser"
        ) as MockParser:
            parse_bits_book(bits_xml)

            _, kwargs = MockParser.call_args
            assert "config" in kwargs
            cfg = kwargs["config"]
            assert "element-citation" in cfg.citation_types["types"]
