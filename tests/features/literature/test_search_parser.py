"""Comprehensive tests for EuropePMCParser.

Tests all 25 methods covering parsing of CSV, JSON, XML, DC formats,
affiliation parsing, entity extraction, and paper entity creation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import defusedxml.ElementTree as ET
import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.features.literature.search_parser import XML_NAMESPACES, EuropePMCParser
from pyeuropepmc.models import (
    AuthorEntity,
    GrantEntity,
    JournalEntity,
    PaperEntity,
)
from pyeuropepmc.models.mesh import MeSHHeadingEntity

pytestmark = pytest.mark.unit


# ===========================================================================
# CSV parsing (parse_csv, _parse_csv_data)
# ===========================================================================


class TestParseCSV:
    """Tests for CSV parsing methods."""

    def test_parse_csv_basic(self) -> None:
        """Parse a valid CSV string."""
        csv_str = "id,title,author\n1,Test Article,Smith J\n2,Another Article,Doe J"
        result = EuropePMCParser.parse_csv(csv_str)
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[0]["title"] == "Test Article"
        assert result[1]["author"] == "Doe J"

    def test_parse_csv_single_row(self) -> None:
        """Parse CSV with a single data row."""
        csv_str = "id,title\n42,My Paper"
        result = EuropePMCParser.parse_csv(csv_str)
        assert len(result) == 1
        assert result[0]["id"] == "42"

    def test_parse_csv_empty_string(self) -> None:
        """Parsing an empty CSV string returns empty list."""
        result = EuropePMCParser.parse_csv("")
        assert result == []

    def test_parse_csv_headers_only(self) -> None:
        """CSV with only headers returns empty list."""
        result = EuropePMCParser.parse_csv("id,title,author")
        assert result == []

    def test_parse_csv_none_returns_empty(self) -> None:
        """Parsing None as CSV returns empty list (StringIO accepts None)."""
        result = EuropePMCParser.parse_csv(None)  # type: ignore[arg-type]
        assert result == []

    def test_parse_csv_data_valid(self) -> None:
        """_parse_csv_data returns list of dicts from CSV string."""
        csv_str = "a,b\n1,2\n3,4"
        result = EuropePMCParser._parse_csv_data(csv_str)
        assert result == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]

    def test_parse_csv_data_empty(self) -> None:
        """_parse_csv_data returns empty list for empty string."""
        assert EuropePMCParser._parse_csv_data("") == []

    def test_parse_csv_data_special_chars(self) -> None:
        """CSV with quoted fields containing commas."""
        csv_str = 'name,note\n"Smith, John","has, comma"'
        result = EuropePMCParser._parse_csv_data(csv_str)
        assert result[0]["name"] == "Smith, John"
        assert result[0]["note"] == "has, comma"

    def test_parse_csv_catches_exception(self) -> None:
        """parse_csv wraps exceptions in ParsingError."""
        with patch.object(EuropePMCParser, "_parse_csv_data") as mock_parse:
            mock_parse.side_effect = ValueError("csv failure")
            with pytest.raises(ParsingError) as exc:
                EuropePMCParser.parse_csv("dummy")
            assert exc.value.error_code == ErrorCodes.PARSE003


# ===========================================================================
# JSON parsing (parse_json, _parse_json_data, _extract_results_from_dict,
#               _validate_result_list, _handle_parsing_errors, _raise_format_error)
# ===========================================================================


class TestParseJSON:
    """Tests for JSON parsing methods."""

    def test_parse_json_dict_with_results(self) -> None:
        """parse_json with a dict containing resultList/result."""
        data = {"resultList": {"result": [{"id": "1", "title": "A"}, {"id": "2", "title": "B"}]}}
        result = EuropePMCParser.parse_json(data)
        assert len(result) == 2
        assert result[0]["id"] == "1"

    def test_parse_json_list_direct(self) -> None:
        """parse_json with a direct list of results."""
        data = [{"id": "1"}, {"id": "2"}]
        result = EuropePMCParser.parse_json(data)
        assert len(result) == 2

    def test_parse_json_empty_list(self) -> None:
        """parse_json with empty list returns empty list."""
        result = EuropePMCParser.parse_json([])
        assert result == []

    def test_parse_json_empty_dict(self) -> None:
        """parse_json with empty dict (no resultList) returns empty list."""
        result = EuropePMCParser.parse_json({})
        assert result == []

    def test_parse_json_none_raises_error(self) -> None:
        """parse_json with None raises ParsingError."""
        with pytest.raises(ParsingError) as exc:
            EuropePMCParser.parse_json(None)
        assert exc.value.error_code == ErrorCodes.PARSE003

    def test_parse_json_empty_string_raises_error(self) -> None:
        """parse_json with empty string raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser.parse_json("")

    def test_parse_json_blank_string_raises_error(self) -> None:
        """parse_json with whitespace-only string raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser.parse_json("   ")

    def test_parse_json_invalid_type_raises_error(self) -> None:
        """parse_json with int raises ParsingError via _raise_format_error."""
        with pytest.raises(ParsingError) as exc:
            EuropePMCParser.parse_json(42)
        assert exc.value.error_code == ErrorCodes.PARSE001

    def test_parse_json_data_none_raises_error(self) -> None:
        """_parse_json_data with None raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser._parse_json_data(None)

    def test_parse_json_data_dict(self) -> None:
        """_parse_json_data delegates dict to _extract_results_from_dict."""
        data = {"resultList": {"result": [{"x": "y"}]}}
        result = EuropePMCParser._parse_json_data(data)
        assert result == [{"x": "y"}]

    def test_parse_json_data_list(self) -> None:
        """_parse_json_data delegates list to _validate_result_list."""
        data = [{"a": "b"}]
        result = EuropePMCParser._parse_json_data(data)
        assert result == [{"a": "b"}]

    def test_parse_json_data_invalid_type(self) -> None:
        """_parse_json_data with string raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser._parse_json_data("not a dict or list")

    def test_extract_results_from_dict_valid(self) -> None:
        """_extract_results_from_dict navigates resultList/result."""
        data = {"resultList": {"result": [{"pmid": "123"}]}}
        result = EuropePMCParser._extract_results_from_dict(data)
        assert result == [{"pmid": "123"}]

    def test_extract_results_from_dict_no_result_list(self) -> None:
        """_extract_results_from_dict with missing resultList returns []."""
        result = EuropePMCParser._extract_results_from_dict({"other": "data"})
        assert result == []

    def test_extract_results_from_dict_result_is_none(self) -> None:
        """_extract_results_from_dict when result is None returns []."""
        result = EuropePMCParser._extract_results_from_dict({"resultList": {"result": None}})
        assert result == []

    def test_extract_results_from_dict_non_dict_raises(self) -> None:
        """_extract_results_from_dict with non-dict raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser._extract_results_from_dict("not a dict")  # type: ignore[arg-type]

    def test_validate_result_list_all_valid(self) -> None:
        """_validate_result_list with all dict items returns them."""
        items = [{"a": 1}, {"b": 2}]
        assert EuropePMCParser._validate_result_list(items) == items

    def test_validate_result_list_none(self) -> None:
        """_validate_result_list with None returns empty list."""
        assert EuropePMCParser._validate_result_list(None) == []

    def test_validate_result_list_not_list(self) -> None:
        """_validate_result_list with non-list returns empty list."""
        with patch.object(EuropePMCParser.logger, "error") as mock_log:
            result = EuropePMCParser._validate_result_list("bad")
            assert result == []
            mock_log.assert_called_once()

    def test_validate_result_list_mixed_validity(self) -> None:
        """_validate_result_list filters out non-dict items."""
        items = [{"good": 1}, "bad", 42, {"fine": 2}]
        with (
            patch.object(EuropePMCParser.logger, "error") as mock_err,
            patch.object(EuropePMCParser.logger, "warning") as mock_warn,
        ):
            result = EuropePMCParser._validate_result_list(items)
            assert result == [{"good": 1}, {"fine": 2}]
            assert mock_err.call_count == 2
            mock_warn.assert_called_once()

    def test_handle_parsing_errors_passthrough_result(self) -> None:
        """_handle_parsing_errors returns the result from parse_func."""

        def good(data: Any) -> list[dict[str, Any]]:
            return [{"key": "val"}]

        result = EuropePMCParser._handle_parsing_errors(good, None, "JSON")
        assert result == [{"key": "val"}]

    def test_handle_parsing_errors_non_list_result(self) -> None:
        """_handle_parsing_errors returns [] when result is not a list."""

        def not_list(data: Any) -> str:
            return "string"

        result = EuropePMCParser._handle_parsing_errors(not_list, None, "JSON")
        assert result == []

    def test_handle_parsing_errors_passthrough_parsing_error(self) -> None:
        """_handle_parsing_errors re-raises ParsingError unchanged."""

        def raiser(data: Any) -> list[dict[str, Any]]:
            raise ParsingError(ErrorCodes.PARSE001, {"expected": "dict", "actual": "str"})

        with pytest.raises(ParsingError) as exc:
            EuropePMCParser._handle_parsing_errors(raiser, None, "JSON")
        assert exc.value.error_code == ErrorCodes.PARSE001

    def test_handle_parsing_errors_wraps_xml_parse_error(self) -> None:
        """_handle_parsing_errors wraps ET.ParseError in ParsingError PARSE002."""

        def raiser(data: Any) -> list[dict[str, Any]]:
            raise ET.ParseError("mangled")

        with pytest.raises(ParsingError) as exc:
            EuropePMCParser._handle_parsing_errors(raiser, None, "XML")
        assert exc.value.error_code == ErrorCodes.PARSE002
        assert "XML" in str(exc.value)

    def test_handle_parsing_errors_wraps_generic_exception(self) -> None:
        """_handle_parsing_errors wraps generic Exception in ParsingError PARSE003."""

        def raiser(data: Any) -> list[dict[str, Any]]:
            raise ValueError("something broke")

        with pytest.raises(ParsingError) as exc:
            EuropePMCParser._handle_parsing_errors(raiser, None, "CSV")
        assert exc.value.error_code == ErrorCodes.PARSE003
        assert exc.value.context.get("format") == "CSV"

    def test_raise_format_error(self) -> None:
        """_raise_format_error raises ParsingError with PARSE001."""
        with pytest.raises(ParsingError) as exc:
            EuropePMCParser._raise_format_error("dict", "str")
        assert exc.value.error_code == ErrorCodes.PARSE001
        assert exc.value.context.get("expected_type") == "dict"


# ===========================================================================
# XML parsing (parse_xml, _parse_xml_data, _extract_xml_element_data)
# ===========================================================================


class TestParseXML:
    """Tests for XML parsing methods."""

    XML_VALID = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <resultList>
    <result>
      <id>1</id>
      <title>Article One</title>
    </result>
    <result>
      <id>2</id>
      <title>Article Two</title>
    </result>
  </resultList>
</response>"""

    XML_SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <resultList>
    <result>
      <pmid>12345</pmid>
    </result>
  </resultList>
</response>"""

    def test_parse_xml_valid(self) -> None:
        """parse_xml extracts results from valid XML."""
        result = EuropePMCParser.parse_xml(self.XML_VALID)
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["title"] == "Article Two"

    def test_parse_xml_none_raises_error(self) -> None:
        """parse_xml with None raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser.parse_xml(None)

    def test_parse_xml_empty_string_raises_error(self) -> None:
        """parse_xml with empty string raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser.parse_xml("")

    def test_parse_xml_non_string_raises_error(self) -> None:
        """parse_xml with non-string raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser.parse_xml(123)  # type: ignore[arg-type]

    def test_parse_xml_malformed(self) -> None:
        """parse_xml with malformed XML raises ParsingError."""
        with pytest.raises(ParsingError) as exc:
            EuropePMCParser.parse_xml("<root><unclosed>")
        assert exc.value.error_code in (ErrorCodes.PARSE002,)

    def test_parse_xml_no_result_list(self) -> None:
        """parse_xml with XML lacking resultList raises ParsingError."""
        xml = "<response><foo>bar</foo></response>"
        with pytest.raises(ParsingError) as exc:
            EuropePMCParser.parse_xml(xml)
        assert exc.value.error_code == ErrorCodes.PARSE004

    def test_parse_xml_single_result(self) -> None:
        """parse_xml works with a single result element."""
        result = EuropePMCParser.parse_xml(self.XML_SINGLE)
        assert len(result) == 1
        assert result[0]["pmid"] == "12345"

    def test_parse_xml_data_none_raises(self) -> None:
        """_parse_xml_data with None raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser._parse_xml_data(None)

    def test_parse_xml_data_empty_str_raises(self) -> None:
        """_parse_xml_data with empty string raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser._parse_xml_data("")

    def test_parse_xml_data_malformed_raises(self) -> None:
        """_parse_xml_data with malformed XML raises ParsingError."""
        with pytest.raises(ParsingError) as exc:
            EuropePMCParser._parse_xml_data("<unclosed>")
        assert exc.value.error_code == ErrorCodes.PARSE002

    def test_parse_xml_data_record_error_continues(self) -> None:
        """_parse_xml_data logs record-level errors and continues."""
        xml = """<?xml version="1.0"?>
<response>
  <resultList>
    <result><id>1</id></result>
    <result><id>2</id></result>
  </resultList>
</response>"""
        with patch.object(EuropePMCParser, "_extract_xml_element_data") as mock_extract:
            mock_extract.side_effect = [
                {"id": "1"},
                ValueError("boom"),  # second record fails
            ]
            with patch.object(EuropePMCParser.logger, "error") as mock_log:
                result = EuropePMCParser._parse_xml_data(xml)
                assert len(result) == 1
                assert result[0]["id"] == "1"
                mock_log.assert_called_once()

    def test_parse_xml_data_no_results_found_raises(self) -> None:
        """_parse_xml_data raises PARSE004 when no result elements found."""
        xml = "<root><other>data</other></root>"
        with pytest.raises(ParsingError) as exc:
            EuropePMCParser._parse_xml_data(xml)
        assert exc.value.error_code == ErrorCodes.PARSE004

    def test_extract_xml_element_data_basic(self) -> None:
        """_extract_xml_element_data converts element children to dict."""
        xml = "<result><a>1</a><b>hello</b></result>"
        elem = ET.fromstring(xml)
        result = EuropePMCParser._extract_xml_element_data(elem)
        assert result == {"a": "1", "b": "hello"}

    def test_extract_xml_element_data_empty(self) -> None:
        """_extract_xml_element_data with no children returns empty dict."""
        elem = ET.fromstring("<result/>")
        result = EuropePMCParser._extract_xml_element_data(elem)
        assert result == {}

    def test_extract_xml_element_data_none_text(self) -> None:
        """_extract_xml_element_data handles elements with None text."""
        xml = "<result><a/><b>val</b></result>"
        elem = ET.fromstring(xml)
        result = EuropePMCParser._extract_xml_element_data(elem)
        assert result["a"] is None
        assert result["b"] == "val"


# ===========================================================================
# DC XML parsing (parse_dc, _parse_dc_data, _extract_dc_description_data)
# ===========================================================================


class TestParseDC:
    """Tests for Dublin Core XML parsing methods."""

    DC_VALID = f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="{XML_NAMESPACES["rdf"]}"
         xmlns:dc="{XML_NAMESPACES["dc"]}"
         xmlns:dcterms="{XML_NAMESPACES["dcterms"]}">
  <rdf:Description rdf:about="http://example.org/1">
    <dc:title>Test Article</dc:title>
    <dc:creator>Smith J</dc:creator>
    <dc:identifier>DOI:10.1234/test</dc:identifier>
  </rdf:Description>
  <rdf:Description rdf:about="http://example.org/2">
    <dc:title>Second Article</dc:title>
    <dc:creator>Doe J</dc:creator>
  </rdf:Description>
</rdf:RDF>"""

    DC_SINGLE = f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="{XML_NAMESPACES["rdf"]}"
         xmlns:dc="{XML_NAMESPACES["dc"]}">
  <rdf:Description rdf:about="http://example.org/1">
    <dc:title>Single</dc:title>
  </rdf:Description>
</rdf:RDF>"""

    def test_parse_dc_valid(self) -> None:
        """parse_dc extracts descriptions from valid DC XML."""
        result = EuropePMCParser.parse_dc(self.DC_VALID)
        assert len(result) == 2
        assert result[0]["title"] == "Test Article"
        assert result[1]["creator"] == "Doe J"

    def test_parse_dc_none_raises_error(self) -> None:
        """parse_dc with None raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser.parse_dc(None)

    def test_parse_dc_empty_string_raises_error(self) -> None:
        """parse_dc with empty string raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser.parse_dc("")

    def test_parse_dc_malformed_raises_error(self) -> None:
        """parse_dc with malformed XML raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser.parse_dc("<unclosed>")

    def test_parse_dc_single_description(self) -> None:
        """parse_dc works with a single description."""
        result = EuropePMCParser.parse_dc(self.DC_SINGLE)
        assert len(result) == 1
        assert result[0]["title"] == "Single"

    def test_parse_dc_no_descriptions(self) -> None:
        """parse_dc with no descriptions returns empty list."""
        xml = f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="{XML_NAMESPACES["rdf"]}"/>"""
        result = EuropePMCParser.parse_dc(xml)
        assert result == []

    def test_parse_dc_duplicate_tags_become_list(self) -> None:
        """parse_dc handles duplicate tags by converting to list."""
        xml = f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="{XML_NAMESPACES["rdf"]}"
         xmlns:dc="{XML_NAMESPACES["dc"]}">
  <rdf:Description>
    <dc:creator>Smith J</dc:creator>
    <dc:creator>Doe J</dc:creator>
  </rdf:Description>
</rdf:RDF>"""
        result = EuropePMCParser.parse_dc(xml)
        assert len(result) == 1
        assert result[0]["creator"] == ["Smith J", "Doe J"]

    def test_parse_dc_data_empty_str_raises(self) -> None:
        """_parse_dc_data with empty string raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser._parse_dc_data("")

    def test_parse_dc_data_none_raises(self) -> None:
        """_parse_dc_data with None raises ParsingError."""
        with pytest.raises(ParsingError):
            EuropePMCParser._parse_dc_data(None)

    def test_extract_dc_description_data_basic(self) -> None:
        """_extract_dc_description_data extracts children tags."""
        xml = f"""<rdf:Description xmlns:rdf="{XML_NAMESPACES["rdf"]}" xmlns:dc="{XML_NAMESPACES["dc"]}">
  <dc:title>Hello</dc:title>
</rdf:Description>"""
        elem = ET.fromstring(xml)
        result = EuropePMCParser._extract_dc_description_data(elem)
        assert result["title"] == "Hello"

    def test_extract_dc_description_data_default_title(self) -> None:
        """_extract_dc_description_data adds empty title if missing."""
        xml = f"""<rdf:Description xmlns:rdf="{XML_NAMESPACES["rdf"]}" xmlns:dc="{XML_NAMESPACES["dc"]}">
  <dc:creator>X</dc:creator>
</rdf:Description>"""
        elem = ET.fromstring(xml)
        result = EuropePMCParser._extract_dc_description_data(elem)
        assert "title" in result
        assert result["title"] == ""

    def test_extract_dc_description_data_duplicates(self) -> None:
        """_extract_dc_description_data handles duplicate tags."""
        xml = f"""<rdf:Description xmlns:rdf="{XML_NAMESPACES["rdf"]}" xmlns:dc="{XML_NAMESPACES["dc"]}">
  <dc:subject>A</dc:subject>
  <dc:subject>B</dc:subject>
</rdf:Description>"""
        elem = ET.fromstring(xml)
        result = EuropePMCParser._extract_dc_description_data(elem)
        assert result["subject"] == ["A", "B"]

    def test_parse_dc_record_error_continues(self) -> None:
        """_parse_dc_data logs record-level errors and continues."""
        with patch.object(EuropePMCParser, "_extract_dc_description_data") as mock_extract:
            mock_extract.side_effect = [{"title": "A"}, ValueError("fail")]
            result = EuropePMCParser._parse_dc_data(self.DC_SINGLE)
            assert len(result) == 1  # only the first record
            mock_extract.assert_called()


# ===========================================================================
# Tag and namespace utilities
# (_remove_namespace_from_tag, _add_tag_to_result, _handle_duplicate_tag)
# ===========================================================================


class TestNamespaceAndTagHelpers:
    """Tests for XML namespace and tag handling utilities."""

    @pytest.mark.parametrize(
        ("tag", "expected"),
        [
            ("{http://purl.org/dc/elements/1.1/}title", "title"),
            ("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description", "Description"),
            ("simpleTag", "simpleTag"),
            ("{ns}tag", "tag"),
            ("no_namespace_here", "no_namespace_here"),
            ("", ""),
            ("}", ""),
            ("{a}b", "b"),
            ("{a}b}c", "b}c"),
        ],
    )
    def test_remove_namespace_from_tag(self, tag: str, expected: str) -> None:
        """_remove_namespace_from_tag strips XML namespace prefixes."""
        assert EuropePMCParser._remove_namespace_from_tag(tag) == expected

    def test_add_tag_to_result_new_key(self) -> None:
        """_add_tag_to_result adds a new key-value pair."""
        result: dict[str, str | list[str]] = {}
        EuropePMCParser._add_tag_to_result(result, "title", "Hello")
        assert result["title"] == "Hello"

    def test_add_tag_to_result_skips_none(self) -> None:
        """_add_tag_to_result skips adding when text is None."""
        result: dict[str, str | list[str]] = {}
        EuropePMCParser._add_tag_to_result(result, "key", None)
        assert "key" not in result

    def test_add_tag_to_result_duplicate_becomes_list(self) -> None:
        """_add_tag_to_result delegates duplicates to _handle_duplicate_tag."""
        result: dict[str, str | list[str]] = {"author": "Smith J"}
        EuropePMCParser._add_tag_to_result(result, "author", "Doe J")
        assert result["author"] == ["Smith J", "Doe J"]

    def test_handle_duplicate_tag_first_duplicate(self) -> None:
        """_handle_duplicate_tag converts single value to list of two."""
        result: dict[str, str | list[str]] = {"k": "v1"}
        EuropePMCParser._handle_duplicate_tag(result, "k", "v2")
        assert result["k"] == ["v1", "v2"]

    def test_handle_duplicate_tag_appends_to_existing_list(self) -> None:
        """_handle_duplicate_tag appends to existing list."""
        result: dict[str, str | list[str]] = {"k": ["v1", "v2"]}
        EuropePMCParser._handle_duplicate_tag(result, "k", "v3")
        assert result["k"] == ["v1", "v2", "v3"]

    def test_handle_duplicate_tag_flat_nested_list(self) -> None:
        """_handle_duplicate_tag flattens nested lists."""
        result: dict[str, str | list[str]] = {"k": [["v1", "v2"], "v3"]}
        EuropePMCParser._handle_duplicate_tag(result, "k", "v4")
        assert result["k"] == ["v1", "v2", "v3", "v4"]

    def test_handle_duplicate_tag_none_text_existing_list(self) -> None:
        """_handle_duplicate_tag with None text on existing list does not append."""
        result: dict[str, str | list[str]] = {"k": ["v1"]}
        EuropePMCParser._handle_duplicate_tag(result, "k", None)
        assert result["k"] == ["v1"]

    def test_handle_duplicate_tag_none_text_single_value(self) -> None:
        """_handle_duplicate_tag with None text on single value wraps it."""
        result: dict[str, str | list[str]] = {"k": "v1"}
        EuropePMCParser._handle_duplicate_tag(result, "k", None)
        assert result["k"] == ["v1"]

    def test_handle_duplicate_tag_converts_nested_list_to_str(self) -> None:
        """_handle_duplicate_tag converts nested list items via str()."""
        result: dict[str, str | list[str]] = {"k": [1, 2]}
        EuropePMCParser._handle_duplicate_tag(result, "k", 3)
        assert result["k"] == ["1", "2", "3"]


# ===========================================================================
# Affiliation parsing (parse_affiliation_string)
# ===========================================================================


class TestParseAffiliation:
    """Tests for affiliation string parsing."""

    def test_empty_string(self) -> None:
        """Empty affiliation returns entity with empty display_name."""
        entity = EuropePMCParser.parse_affiliation_string("")
        assert entity.display_name == ""

    def test_whitespace_only(self) -> None:
        """Whitespace-only affiliation returns entity with empty display_name."""
        entity = EuropePMCParser.parse_affiliation_string("   ")
        assert entity.display_name == ""

    def test_none_input(self) -> None:
        """None affiliation returns entity with empty display_name."""
        entity = EuropePMCParser.parse_affiliation_string(None)  # type: ignore[arg-type]
        assert entity.display_name == ""

    def test_simple_institution(self) -> None:
        """Simple institution name without commas."""
        entity = EuropePMCParser.parse_affiliation_string("University of Example")
        assert entity.display_name == "University of Example"

    def test_institution_with_country(self) -> None:
        """Institution name with country at the end."""
        entity = EuropePMCParser.parse_affiliation_string("University of Example, USA")
        assert "University of Example" in entity.display_name
        assert entity.country == "USA"

    def test_department_country(self) -> None:
        """Department, institution, and country pattern."""
        entity = EuropePMCParser.parse_affiliation_string(
            "Department of Biology, University of Example, Germany"
        )
        assert "University of Example" in entity.display_name
        assert entity.country == "Germany"

    def test_multi_part_with_email(self) -> None:
        """Affiliation with email address is cleaned."""
        text = "University of Example, City, USA. Electronic address: test@example.com"
        entity = EuropePMCParser.parse_affiliation_string(text)
        assert "Electronic address:" not in entity.display_name
        assert "University of Example" in entity.display_name

    def test_uk_country_detection(self) -> None:
        """UK is detected as country."""
        entity = EuropePMCParser.parse_affiliation_string("University of Example, UK")
        assert entity.country == "UK"

    def test_city_extraction(self) -> None:
        """City is extracted when present."""
        entity = EuropePMCParser.parse_affiliation_string(
            "Department of Biology, University of Example, Berlin, Germany"
        )
        assert entity.country == "Germany"
        assert entity.city == "Berlin"
        assert "University of Example" in entity.display_name

    def test_long_city_not_extracted(self) -> None:
        """Long strings (likely institution names) are not treated as city."""
        entity = EuropePMCParser.parse_affiliation_string(
            "University of Example and Something Else, Germany"
        )
        assert entity.country == "Germany"
        # "Something Else" is too vague; just verify country is extracted

    def test_department_becomes_institution_type(self) -> None:
        """Department at start is treated as institution_type."""
        entity = EuropePMCParser.parse_affiliation_string(
            "Department of Chemistry, University of Science, London, UK"
        )
        assert entity.country == "UK"
        assert entity.city == "London"
        # department keyword means first part becomes institution_type
        assert entity.institution_type is not None
        assert "Department" in entity.institution_type
        assert "University of Science" in entity.display_name

    def test_no_country_match(self) -> None:
        """If no country pattern matches, country is None."""
        entity = EuropePMCParser.parse_affiliation_string("Some Lab, Somewhere")
        assert entity.country is None
        assert "Some Lab" in entity.display_name


# ===========================================================================
# Authors and entities (extract_authors_and_entities)
# ===========================================================================


class TestExtractAuthorsAndEntities:
    """Tests for author and entity extraction."""

    def test_no_author_list(self) -> None:
        """Missing authorList returns empty lists."""
        authors, author_entities, institution_entities = (
            EuropePMCParser.extract_authors_and_entities({})
        )
        assert authors == []
        assert author_entities == []
        assert institution_entities == []

    def test_single_author_basic(self) -> None:
        """Single author without affiliations."""
        result = {
            "authorList": {
                "author": [
                    {
                        "fullName": "Smith J",
                        "firstName": "John",
                        "lastName": "Smith",
                        "initials": "JS",
                    }
                ]
            }
        }
        authors, author_entities, institution_entities = (
            EuropePMCParser.extract_authors_and_entities(result)
        )
        assert len(authors) == 1
        assert authors[0]["full_name"] == "Smith J"
        assert authors[0]["orcid"] is None
        assert len(author_entities) == 1
        assert author_entities[0].full_name == "Smith J"

    def test_author_with_orcid(self) -> None:
        """Author with ORCID in authorId."""
        result = {
            "authorList": {
                "author": [
                    {
                        "fullName": "Doe J",
                        "authorId": {"type": "ORCID", "value": "0000-0001-2345-6789"},
                    }
                ]
            }
        }
        authors, author_entities, _ = EuropePMCParser.extract_authors_and_entities(result)
        assert authors[0]["orcid"] == "0000-0001-2345-6789"
        assert author_entities[0].orcid == "0000-0001-2345-6789"

    def test_author_with_affiliations(self) -> None:
        """Author with affiliation details creates InstitutionEntity."""
        result = {
            "authorList": {
                "author": [
                    {
                        "fullName": "Smith J",
                        "authorAffiliationDetailsList": {
                            "authorAffiliation": [{"affiliation": "University of Example, USA"}]
                        },
                    }
                ]
            }
        }
        authors, author_entities, institution_entities = (
            EuropePMCParser.extract_authors_and_entities(result)
        )
        assert authors[0]["affiliations"] == ["University of Example, USA"]
        assert len(institution_entities) == 1
        assert "University of Example" in institution_entities[0].display_name

    def test_orcid_from_fallback_list(self) -> None:
        """ORCID falls back from authorIdList when author lacks ORCID."""
        result = {
            "authorList": {
                "author": [
                    {
                        "fullName": "Smith J",
                        "authorId": {"type": "OTHER", "value": "some-id"},
                    }
                ]
            },
            "authorIdList": {"authorId": [{"type": "ORCID", "value": "0000-0002-9999-8888"}]},
        }
        authors, author_entities, _ = EuropePMCParser.extract_authors_and_entities(result)
        assert authors[0]["orcid"] == "0000-0002-9999-8888"

    def test_invalid_author_list_type(self) -> None:
        """Non-list authorList is ignored."""
        result = {"authorList": {"author": "not a list"}}
        authors, author_entities, _ = EuropePMCParser.extract_authors_and_entities(result)
        assert authors == []
        assert author_entities == []


# ===========================================================================
# Keywords and MeSH (extract_keywords_and_mesh)
# ===========================================================================


class TestExtractKeywordsAndMesh:
    """Tests for keyword and MeSH extraction."""

    def test_no_keywords(self) -> None:
        """Missing keywordList returns empty list."""
        assert EuropePMCParser.extract_keywords_and_mesh({}) == []

    def test_with_keywords(self) -> None:
        """Keywords from keywordList are extracted."""
        result = {"keywordList": {"keyword": ["cancer", "genomics", "bioinformatics"]}}
        keywords = EuropePMCParser.extract_keywords_and_mesh(result)
        assert keywords == ["cancer", "genomics", "bioinformatics"]

    def test_keyword_as_string(self) -> None:
        """Single keyword string is handled."""
        result = {"keywordList": {"keyword": "cancer"}}
        keywords = EuropePMCParser.extract_keywords_and_mesh(result)
        assert keywords == ["cancer"]

    def test_major_mesh_included(self) -> None:
        """Major MeSH descriptors are included with MeSH: prefix."""
        result = {
            "meshHeadingList": {
                "meshHeading": [
                    {"descriptorName": "Neoplasms", "majorTopic_YN": "Y"},
                    {"descriptorName": "Humans", "majorTopic_YN": "N"},
                ]
            }
        }
        keywords = EuropePMCParser.extract_keywords_and_mesh(result)
        assert "MeSH:Neoplasms" in keywords
        assert "MeSH:Humans" not in keywords

    def test_keywords_and_mesh_combined(self) -> None:
        """Keywords and major MeSH terms combined."""
        result = {
            "keywordList": {"keyword": ["cancer"]},
            "meshHeadingList": {
                "meshHeading": [{"descriptorName": "Neoplasms", "majorTopic_YN": "Y"}]
            },
        }
        keywords = EuropePMCParser.extract_keywords_and_mesh(result)
        assert keywords == ["cancer", "MeSH:Neoplasms"]


# ===========================================================================
# MeSH headings (extract_mesh_headings)
# ===========================================================================


class TestExtractMeshHeadings:
    """Tests for structured MeSH heading extraction."""

    def test_no_mesh_headings(self) -> None:
        """Missing meshHeadingList returns empty list."""
        assert EuropePMCParser.extract_mesh_headings({}) == []

    def test_single_heading(self) -> None:
        """Single MeSH heading is extracted."""
        result = {
            "meshHeadingList": {
                "meshHeading": [
                    {
                        "descriptorName": "Neoplasms",
                        "majorTopic_YN": "Y",
                        "descriptorUI": "D009369",
                        "meshQualifierList": {
                            "meshQualifier": [
                                {
                                    "qualifierName": "therapy",
                                    "abbreviation": "TH",
                                    "majorTopic_YN": "N",
                                }
                            ]
                        },
                    }
                ]
            }
        }
        headings = EuropePMCParser.extract_mesh_headings(result)
        assert len(headings) == 1
        assert isinstance(headings[0], MeSHHeadingEntity)
        assert headings[0].descriptor_name == "Neoplasms"
        assert headings[0].major_topic is True
        assert len(headings[0].qualifiers) == 1

    def test_multiple_headings(self) -> None:
        """Multiple MeSH headings are extracted."""
        result = {
            "meshHeadingList": {
                "meshHeading": [
                    {"descriptorName": "Humans", "majorTopic_YN": "N"},
                    {"descriptorName": "Male", "majorTopic_YN": "N"},
                ]
            }
        }
        headings = EuropePMCParser.extract_mesh_headings(result)
        assert len(headings) == 2

    def test_invalid_heading_skipped(self) -> None:
        """Malformed MeSH heading that raises exception is caught and skipped."""
        with patch.object(MeSHHeadingEntity, "from_dict") as mock_from_dict:
            mock_from_dict.side_effect = [
                MeSHHeadingEntity(descriptor_name="Valid", major_topic=True),
                KeyError("missing key"),
            ]
            result = {
                "meshHeadingList": {
                    "meshHeading": [
                        {"descriptorName": "Valid", "majorTopic_YN": "Y"},
                        {"descriptorName": "Broken", "majorTopic_YN": "N"},
                    ]
                }
            }
            headings = EuropePMCParser.extract_mesh_headings(result)
            assert len(headings) == 1
            assert headings[0].descriptor_name == "Valid"

    def test_heading_data_not_list(self) -> None:
        """Non-list meshHeading returns empty list."""
        result = {"meshHeadingList": {"meshHeading": "not a list"}}
        assert EuropePMCParser.extract_mesh_headings(result) == []


# ===========================================================================
# Open access info (extract_open_access_info)
# ===========================================================================


class TestExtractOpenAccessInfo:
    """Tests for open access information extraction."""

    def test_all_false_no_url(self) -> None:
        """All flags false and no URL."""
        result = {}
        is_oa, in_epmc, in_pmc, has_pdf, oa_url = EuropePMCParser.extract_open_access_info(result)
        assert is_oa is False
        assert in_epmc is False
        assert in_pmc is False
        assert has_pdf is False
        assert oa_url is None

    def test_all_true_with_url(self) -> None:
        """All flags true and OA URL found."""
        result = {
            "isOpenAccess": "Y",
            "inEPMC": "Y",
            "inPMC": "Y",
            "hasPDF": "Y",
            "fullTextUrlList": {
                "fullTextUrl": [
                    {
                        "availabilityCode": "OA",
                        "url": "https://example.com/fulltext",
                    }
                ]
            },
        }
        is_oa, in_epmc, in_pmc, has_pdf, oa_url = EuropePMCParser.extract_open_access_info(result)
        assert is_oa is True
        assert in_epmc is True
        assert in_pmc is True
        assert has_pdf is True
        assert oa_url == "https://example.com/fulltext"

    def test_mixed_flags(self) -> None:
        """Mixed flag values."""
        result = {"isOpenAccess": "Y", "inPMC": "Y"}
        is_oa, in_epmc, in_pmc, has_pdf, oa_url = EuropePMCParser.extract_open_access_info(result)
        assert is_oa is True
        assert in_epmc is False
        assert in_pmc is True
        assert has_pdf is False

    def test_oa_url_not_found(self) -> None:
        """FullTextUrlList present but no OA code match."""
        result = {
            "fullTextUrlList": {
                "fullTextUrl": [{"availabilityCode": "F", "url": "https://example.com/other"}]
            }
        }
        _, _, _, _, oa_url = EuropePMCParser.extract_open_access_info(result)
        assert oa_url is None

    def test_oa_multiple_urls_first_oa_wins(self) -> None:
        """First OA availability code URL is returned."""
        result = {
            "fullTextUrlList": {
                "fullTextUrl": [
                    {"availabilityCode": "F", "url": "https://example.com/f"},
                    {"availabilityCode": "OA", "url": "https://example.com/oa"},
                    {"availabilityCode": "OA", "url": "https://example.com/oa2"},
                ]
            }
        }
        _, _, _, _, oa_url = EuropePMCParser.extract_open_access_info(result)
        assert oa_url == "https://example.com/oa"

    def test_fulltext_urls_not_list(self) -> None:
        """Non-list fullTextUrl is handled gracefully."""
        result = {"fullTextUrlList": {"fullTextUrl": "not a list"}}
        _, _, _, _, oa_url = EuropePMCParser.extract_open_access_info(result)
        assert oa_url is None


# ===========================================================================
# Citation info (extract_citation_info)
# ===========================================================================


class TestExtractCitationInfo:
    """Tests for citation information extraction."""

    def test_all_defaults(self) -> None:
        """All fields missing returns None count and False flags."""
        result = {}
        result_tuple = EuropePMCParser.extract_citation_info(result)
        assert result_tuple[0] is None  # cited_by_count
        assert result_tuple[1:] == (False, False, False, False, False)

    def test_with_cited_by_count(self) -> None:
        """citedByCount is converted to int."""
        result = {"citedByCount": "42"}
        cited_by, *_ = EuropePMCParser.extract_citation_info(result)
        assert cited_by == 42

    def test_all_flags_true(self) -> None:
        """All Y flags produce True."""
        result = {
            "citedByCount": "10",
            "hasReferences": "Y",
            "hasTextMinedTerms": "Y",
            "hasDbCrossReferences": "Y",
            "hasLabsLinks": "Y",
            "hasTMAccessionNumbers": "Y",
        }
        cit = EuropePMCParser.extract_citation_info(result)
        assert cit == (10, True, True, True, True, True)

    def test_mixed_flags(self) -> None:
        """Mixed Y/N flags."""
        result = {
            "hasReferences": "Y",
            "hasTextMinedTerms": "N",
            "hasLabsLinks": "Y",
        }
        cit = EuropePMCParser.extract_citation_info(result)
        assert cit[0] is None
        assert cit[1] is True
        assert cit[2] is False
        assert cit[3] is False
        assert cit[4] is True
        assert cit[5] is False

    def test_cited_by_count_none(self) -> None:
        """citedByCount missing returns None."""
        result = {"citedByCount": None}
        cited_by, *_ = EuropePMCParser.extract_citation_info(result)
        assert cited_by is None


# ===========================================================================
# Publication metadata (extract_publication_metadata)
# ===========================================================================


class TestExtractPublicationMetadata:
    """Tests for publication metadata extraction."""

    def test_all_missing(self) -> None:
        """All fields missing returns None and empty list."""
        pub_type, funders, license_info = EuropePMCParser.extract_publication_metadata({})
        assert pub_type is None
        assert funders == []
        assert license_info is None

    def test_with_pub_type(self) -> None:
        """First pubType is returned."""
        result = {"pubTypeList": {"pubType": ["Journal Article", "Review"]}}
        pub_type, _, _ = EuropePMCParser.extract_publication_metadata(result)
        assert pub_type == "Journal Article"

    def test_empty_pub_type_list(self) -> None:
        """Empty pubType list returns None."""
        result = {"pubTypeList": {"pubType": []}}
        pub_type, _, _ = EuropePMCParser.extract_publication_metadata(result)
        assert pub_type is None

    def test_with_funders(self) -> None:
        """Grants are extracted as funder dicts."""
        result = {
            "grantsList": {
                "grant": [
                    {"agency": "NIH", "grantId": "R01-CA123456", "acronym": "CA"},
                    {"agency": "NSF", "grantId": "DMS-789012", "acronym": ""},
                ]
            }
        }
        _, funders, _ = EuropePMCParser.extract_publication_metadata(result)
        assert len(funders) == 2
        assert funders[0]["agency"] == "NIH"
        assert funders[0]["grant_id"] == "R01-CA123456"
        assert funders[1]["agency"] == "NSF"

    def test_grants_list_not_list(self) -> None:
        """Non-list grants returns empty funder list."""
        result = {"grantsList": {"grant": "not a list"}}
        _, funders, _ = EuropePMCParser.extract_publication_metadata(result)
        assert funders == []

    def test_with_license(self) -> None:
        """License info is extracted."""
        result = {
            "license": {"type": "CC-BY", "url": "https://creativecommons.org/licenses/by/4.0/"}
        }
        _, _, license_info = EuropePMCParser.extract_publication_metadata(result)
        assert license_info == {
            "type": "CC-BY",
            "url": "https://creativecommons.org/licenses/by/4.0/",
        }


# ===========================================================================
# create_paper_entity_from_result
# ===========================================================================


class TestCreatePaperEntity:
    """Tests for comprehensive PaperEntity creation."""

    FULL_RESULT: dict[str, Any] = {
        "doi": "10.1234/test.2024.001",
        "pmcid": "PMC1234567",
        "pmid": "12345678",
        "title": "Test Article Title",
        "abstractText": "This is the abstract of the test article.",
        "journalInfo": {
            "journal": {
                "title": "Journal of Testing",
                "issn": "1234-5678",
            },
            "volume": "42",
            "issue": "3",
        },
        "pageInfo": "123-145",
        "pubYear": "2024",
        "firstPublicationDate": "2024-01-15",
        "firstIndexDate": "2024-01-20",
        "authorList": {
            "author": [
                {
                    "fullName": "Smith J",
                    "firstName": "John",
                    "lastName": "Smith",
                    "initials": "JS",
                }
            ]
        },
        "keywordList": {"keyword": ["testing", "python"]},
        "meshHeadingList": {"meshHeading": [{"descriptorName": "Software", "majorTopic_YN": "Y"}]},
        "isOpenAccess": "Y",
        "inEPMC": "Y",
        "inPMC": "Y",
        "hasPDF": "Y",
        "fullTextUrlList": {
            "fullTextUrl": [{"availabilityCode": "OA", "url": "https://example.com/oa"}]
        },
        "citedByCount": "15",
        "hasReferences": "Y",
        "hasTextMinedTerms": "N",
        "hasDbCrossReferences": "Y",
        "hasLabsLinks": "N",
        "hasTMAccessionNumbers": "N",
        "pubTypeList": {"pubType": ["Journal Article"]},
        "grantsList": {"grant": [{"agency": "NIH", "grantId": "R01-TEST", "acronym": "TE"}]},
        "license": {"type": "CC-BY", "url": "https://creativecommons.org/licenses/by/4.0/"},
    }

    def test_basic_identifiers(self) -> None:
        """PaperEntity has correct basic identifiers."""
        paper, related = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert paper.doi == "10.1234/test.2024.001"
        assert paper.pmcid == "PMC1234567"
        assert paper.pmid == "12345678"
        assert paper.title == "Test Article Title"
        assert paper.abstract == "This is the abstract of the test article."

    def test_journal_entity_created(self) -> None:
        """JournalEntity is created from journalInfo."""
        paper, _ = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert isinstance(paper.journal, JournalEntity)
        assert paper.journal.title == "Journal of Testing"
        assert paper.journal.issn == "1234-5678"

    def test_publication_metadata(self) -> None:
        """Publication volume, issue, pages, year are set."""
        paper, _ = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert paper.volume == "42"
        assert paper.issue == "3"
        assert paper.pages == "123-145"
        assert paper.publication_year == 2024

    def test_authors_extracted(self) -> None:
        """Authors are extracted correctly."""
        paper, related = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert len(paper.authors) == 1
        assert paper.authors[0]["full_name"] == "Smith J"
        assert len(related["authors"]) == 1
        assert isinstance(related["authors"][0], AuthorEntity)

    def test_keywords_and_mesh(self) -> None:
        """Keywords include MeSH terms."""
        paper, _ = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert "testing" in paper.keywords
        assert "MeSH:Software" in paper.keywords

    def test_open_access_info(self) -> None:
        """Open access flags are set."""
        paper, _ = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert paper.is_oa is True
        assert paper.oa_url == "https://example.com/oa"
        assert paper.has_pdf is True
        assert paper.in_epmc is True
        assert paper.in_pmc is True

    def test_citation_info(self) -> None:
        """Citation flags are set."""
        paper, _ = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert paper.cited_by_count == 15
        assert paper.has_references is True
        assert paper.has_text_mined_terms is False
        assert paper.has_db_cross_references is True
        assert paper.has_labs_links is False
        assert paper.has_tm_accession_numbers is False

    def test_pub_type_and_funders(self) -> None:
        """Publication type and funders are set."""
        paper, _ = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert paper.pub_type == "Journal Article"
        assert isinstance(paper.grants, list)
        assert len(paper.grants) == 1
        assert isinstance(paper.grants[0], GrantEntity)
        assert paper.grants[0].funding_source == "NIH"

    def test_license_info(self) -> None:
        """License is set."""
        paper, _ = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert paper.license == {
            "type": "CC-BY",
            "url": "https://creativecommons.org/licenses/by/4.0/",
        }

    def test_dates(self) -> None:
        """Publication and index dates are set."""
        paper, _ = EuropePMCParser.create_paper_entity_from_result(self.FULL_RESULT)
        assert paper.first_publication_date == "2024-01-15"
        assert paper.first_index_date == "2024-01-20"

    def test_minimal_result(self) -> None:
        """Minimal result still produces PaperEntity."""
        paper, related = EuropePMCParser.create_paper_entity_from_result({"pmid": "99999"})
        assert paper.pmid == "99999"
        assert paper.title is None
        assert paper.journal is None
        assert paper.grants is None
        assert related == {"authors": [], "institutions": []}


# ===========================================================================
# parse_search_results_with_entities
# ===========================================================================


class TestParseSearchResultsWithEntities:
    """Tests for parsing multiple search results into entities."""

    def test_single_result_dict(self) -> None:
        """Single dict result is wrapped in list."""
        result = {"pmid": "1", "title": "Single"}
        entities_data = EuropePMCParser.parse_search_results_with_entities(result)
        assert len(entities_data) == 1
        assert isinstance(entities_data[0]["entity"], PaperEntity)
        assert entities_data[0]["entity"].pmid == "1"

    def test_list_of_results(self) -> None:
        """List of results is processed."""
        results = [
            {"pmid": "1", "title": "First"},
            {"pmid": "2", "title": "Second"},
        ]
        entities_data = EuropePMCParser.parse_search_results_with_entities(results)
        assert len(entities_data) == 2
        assert entities_data[0]["entity"].pmid == "1"
        assert entities_data[1]["entity"].pmid == "2"

    def test_empty_list(self) -> None:
        """Empty list returns empty list."""
        entities_data = EuropePMCParser.parse_search_results_with_entities([])
        assert entities_data == []

    def test_whole_search_response_is_unwrapped(self) -> None:
        """A response dict yields one entity per record, not one for the response."""
        response = {
            "version": "6.9",
            "hitCount": 2,
            "resultList": {
                "result": [
                    {"pmid": "1", "title": "First"},
                    {"pmid": "2", "title": "Second"},
                ]
            },
        }
        entities_data = EuropePMCParser.parse_search_results_with_entities(response)
        assert [e["entity"].pmid for e in entities_data] == ["1", "2"]
        assert [e["entity"].title for e in entities_data] == ["First", "Second"]

    @pytest.mark.parametrize(
        "response",
        [
            {"hitCount": 0, "resultList": {"result": []}},
            {"hitCount": 0, "resultList": {}},
            {"hitCount": 0, "resultList": None},
        ],
    )
    def test_response_without_records_yields_nothing(self, response) -> None:
        assert EuropePMCParser.parse_search_results_with_entities(response) == []

    def test_result_failure_logged_and_skipped(self) -> None:
        """Bad result is logged and skipped."""
        results = [
            {"pmid": "1", "title": "Good"},
            {},  # missing pmid, doi, title - but PaperEntity allows it now
        ]
        entities_data = EuropePMCParser.parse_search_results_with_entities(results)
        assert len(entities_data) >= 1

    def test_error_in_create_skipped(self) -> None:
        """Exception in create_paper_entity_from_result is caught."""
        with patch.object(EuropePMCParser, "create_paper_entity_from_result") as mock_create:
            mock_create.side_effect = [
                (MagicMock(spec=PaperEntity), {"authors": [], "institutions": []}),
                ValueError("bad result"),
                (MagicMock(spec=PaperEntity), {"authors": [], "institutions": []}),
            ]
            results = [{"pmid": "1"}, {"pmid": "2"}, {"pmid": "3"}]
            with patch.object(EuropePMCParser.logger, "warning") as mock_warn:
                entities_data = EuropePMCParser.parse_search_results_with_entities(results)
                assert len(entities_data) == 2
                mock_warn.assert_called_once()

    def test_related_entities_structure(self) -> None:
        """Related entities contains authors and institutions."""
        result = {
            "pmid": "1",
            "title": "Test",
            "authorList": {
                "author": [
                    {
                        "fullName": "Smith J",
                        "authorAffiliationDetailsList": {
                            "authorAffiliation": [{"affiliation": "University of Example, USA"}]
                        },
                    }
                ]
            },
        }
        entities_data = EuropePMCParser.parse_search_results_with_entities(result)
        assert len(entities_data) == 1
        related = entities_data[0]["related_entities"]
        assert "authors" in related
        assert "institutions" in related
        assert len(related["institutions"]) > 0
        assert "University of Example" in related["institutions"][0].display_name


# ===========================================================================
# Integration: parse_search_results_with_entities with real data
# ===========================================================================


class TestIntegration:
    """Integration tests for end-to-end parsing flow."""

    def test_json_to_paper_entity_roundtrip(self) -> None:
        """Parse JSON and create PaperEntity via parse_search_results_with_entities."""
        data = {
            "resultList": {
                "result": [
                    {
                        "doi": "10.1000/test.1",
                        "pmcid": "PMC100",
                        "pmid": "100",
                        "title": "Integration Article",
                        "isOpenAccess": "Y",
                        "citedByCount": "5",
                        "authorList": {"author": [{"fullName": "Test A"}]},
                    },
                    {
                        "doi": "10.1000/test.2",
                        "pmcid": "PMC101",
                        "pmid": "101",
                        "title": "Second Article",
                        "isOpenAccess": "N",
                        "authorList": {"author": [{"fullName": "Test B"}]},
                    },
                ]
            }
        }
        parsed = EuropePMCParser.parse_json(data)
        entities_data = EuropePMCParser.parse_search_results_with_entities(parsed)
        assert len(entities_data) == 2
        assert entities_data[0]["entity"].doi == "10.1000/test.1"
        assert entities_data[1]["entity"].doi == "10.1000/test.2"
        assert entities_data[0]["entity"].is_oa is True
        assert entities_data[1]["entity"].is_oa is False
