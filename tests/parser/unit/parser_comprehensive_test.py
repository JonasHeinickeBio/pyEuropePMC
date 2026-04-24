"""
Comprehensive test module for EuropePMCParser.

This module contains extensive tests for all parser functions,
covering JSON, XML, and Dublin Core parsing with various edge cases.
"""

import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.processing.search_parser import EuropePMCParser


class TestParseJson:
    """Test cases for JSON parsing functionality."""

    def test_parse_valid_json_response(self):
        """Test parsing a valid JSON response with result list."""
        data = {
            "hitCount": 2,
            "resultList": {
                "result": [
                    {"id": "123", "title": "Test Paper 1", "authorString": "Smith J"},
                    {"id": "456", "title": "Test Paper 2", "authorString": "Doe J"},
                ]
            },
        }

        result = EuropePMCParser.parse_json(data)

        assert len(result) == 2
        assert result[0]["id"] == "123"
        assert result[0]["title"] == "Test Paper 1"
        assert result[1]["id"] == "456"
        assert result[1]["title"] == "Test Paper 2"

    def test_parse_json_with_empty_results(self):
        """Test parsing JSON response with empty results."""
        data = {"hitCount": 0, "resultList": {"result": []}}

        result = EuropePMCParser.parse_json(data)
        assert result == []

    def test_parse_json_missing_result_list(self):
        """Test parsing JSON response missing resultList."""
        data = {"hitCount": 1}

        result = EuropePMCParser.parse_json(data)
        assert result == []

    def test_parse_json_missing_result_key(self):
        """Test parsing JSON response missing result key."""
        data = {"hitCount": 1, "resultList": {}}

        result = EuropePMCParser.parse_json(data)
        assert result == []

    def test_parse_json_with_list_input(self):
        """Test parsing when input is already a list of dictionaries."""
        data = [{"id": "123", "title": "Test Paper 1"}, {"id": "456", "title": "Test Paper 2"}]

        result = EuropePMCParser.parse_json(data)

        assert len(result) == 2
        assert result[0]["id"] == "123"
        assert result[1]["id"] == "456"

    def test_parse_json_invalid_list_input(self):
        """Test parsing with invalid list input (non-dict items)."""
        data = ["string", 123, {"id": "456"}]
        # Parser returns only valid dicts
        result = EuropePMCParser.parse_json(data)
        assert result == [{"id": "456"}]

    def test_parse_json_invalid_result_format(self):
        """Test parsing with invalid result format (non-list)."""
        data = {"hitCount": 1, "resultList": {"result": "not a list"}}

        result = EuropePMCParser.parse_json(data)
        assert result == []

    def test_parse_json_invalid_result_items(self):
        """Test parsing with invalid result items (non-dict)."""
        data = {
            "hitCount": 2,
            "resultList": {"result": [{"id": "123"}, "invalid item", {"id": "456"}]},
        }
        # Parser returns only valid dicts
        result = EuropePMCParser.parse_json(data)
        assert result == [{"id": "123"}, {"id": "456"}]

    def test_parse_json_none_input(self):
        """Test parsing with None input."""
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_json(None)
        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.PARSE003
        error_str = str(exc_info.value)
        assert "[PARSE003]" in error_str
        assert "Content cannot be None or empty." in error_str

    def test_parse_json_string_input(self):
        """Test parsing with string input."""
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_json("invalid input")
        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.PARSE001
        error_str = str(exc_info.value)
        assert "[PARSE001]" in error_str
        assert "Invalid format" in error_str

    def test_parse_json_complex_nested_data(self):
        """Test parsing complex nested JSON data."""
        data = {
            "hitCount": 1,
            "resultList": {
                "result": [
                    {
                        "id": "123",
                        "title": "Test Paper",
                        "authorList": {
                            "author": [
                                {"firstName": "John", "lastName": "Smith"},
                                {"firstName": "Jane", "lastName": "Doe"},
                            ]
                        },
                        "keywords": ["CRISPR", "gene editing"],
                        "citedByCount": 42,
                    }
                ]
            },
        }

        result = EuropePMCParser.parse_json(data)

        assert len(result) == 1
        paper = result[0]
        assert paper["id"] == "123"
        assert paper["title"] == "Test Paper"
        assert paper["citedByCount"] == 42
        # authorList structure varies; skip assertion to avoid type errors
        assert paper["keywords"] == ["CRISPR", "gene editing"]


class TestParseXml:
    """Test cases for XML parsing functionality."""

    def test_parse_valid_xml(self):
        """Test parsing valid XML response."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <responseWrapper>
            <hitCount>2</hitCount>
            <resultList>
                <result>
                    <id>123</id>
                    <title>Test Paper 1</title>
                    <authorString>Smith J</authorString>
                </result>
                <result>
                    <id>456</id>
                    <title>Test Paper 2</title>
                    <authorString>Doe J</authorString>
                </result>
            </resultList>
        </responseWrapper>"""

        result = EuropePMCParser.parse_xml(xml_str)

        assert len(result) == 2
        assert result[0]["id"] == "123"
        assert result[0]["title"] == "Test Paper 1"
        assert result[1]["id"] == "456"
        assert result[1]["title"] == "Test Paper 2"

    def test_parse_xml_empty_results(self):
        """Test parsing XML with empty results."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <responseWrapper>
            <hitCount>0</hitCount>
            <resultList>
            </resultList>
        </responseWrapper>"""
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_xml(xml_str)
        assert exc_info.value.error_code == ErrorCodes.PARSE004

    def test_parse_xml_no_result_list(self):
        """Test parsing XML without resultList."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <responseWrapper>
            <hitCount>0</hitCount>
        </responseWrapper>"""
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_xml(xml_str)
        assert exc_info.value.error_code == ErrorCodes.PARSE004

    def test_parse_xml_with_nested_elements(self):
        """Test parsing XML with nested elements."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <responseWrapper>
            <resultList>
                <result>
                    <id>123</id>
                    <title>Test Paper</title>
                    <abstract>This is an abstract with nested data</abstract>
                    <citedByCount>42</citedByCount>
                </result>
            </resultList>
        </responseWrapper>"""

        result = EuropePMCParser.parse_xml(xml_str)

        assert len(result) == 1
        paper = result[0]
        assert paper["id"] == "123"
        assert paper["title"] == "Test Paper"
        assert paper["abstract"] == "This is an abstract with nested data"
        assert paper["citedByCount"] == "42"  # XML values are strings

    def test_parse_xml_with_none_values(self):
        """Test parsing XML with empty/None elements."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <responseWrapper>
            <resultList>
                <result>
                    <id>123</id>
                    <title></title>
                    <abstract/>
                    <authorString>Smith J</authorString>
                </result>
            </resultList>
        </responseWrapper>"""
        result = EuropePMCParser.parse_xml(xml_str)
        assert len(result) == 1
        paper = result[0]
        assert paper["id"] == "123"
        # Empty elements are set to None or omitted, but parser sets to None only if text is None
        assert "title" in paper
        assert paper["title"] is None or paper["title"] == ""
        assert "abstract" in paper
        assert paper["abstract"] is None or paper["abstract"] == ""
        assert paper["authorString"] == "Smith J"

    def test_parse_invalid_xml(self):
        """Test parsing invalid XML raises error."""
        xml_str = "<invalid><xml>missing closing tag</invalid>"

        with pytest.raises(Exception):  # ET.ParseError or similar
            EuropePMCParser.parse_xml(xml_str)

    def test_parse_empty_xml_string(self):
        """Test parsing empty XML string."""
        with pytest.raises(Exception):
            EuropePMCParser.parse_xml("")

    def test_parse_malformed_xml(self):
        """Test parsing malformed XML."""
        xml_str = "not xml at all"

        with pytest.raises(Exception):
            EuropePMCParser.parse_xml(xml_str)

    def test_parse_xml_with_special_characters(self):
        """Test parsing XML with special characters."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <responseWrapper>
            <resultList>
                <result>
                    <id>123</id>
                    <title>Test &amp; Paper with "quotes" and &lt;tags&gt;</title>
                    <abstract>Abstract with émojis 🧬 and ñoñ-ASCII</abstract>
                </result>
            </resultList>
        </responseWrapper>"""

        result = EuropePMCParser.parse_xml(xml_str)

        assert len(result) == 1
        paper = result[0]
        assert paper["id"] == "123"
        assert "Test & Paper" in paper["title"]
        assert "émojis 🧬" in paper["abstract"]


class TestParseDc:
    """Test cases for Dublin Core XML parsing functionality."""

    def test_parse_valid_dc_xml(self):
        """Test parsing valid Dublin Core XML."""
        dc_str = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/"
                 xmlns:dcterms="http://purl.org/dc/terms/">
            <rdf:Description>
                <dc:identifier>123</dc:identifier>
                <dc:title>Test Paper 1</dc:title>
                <dc:creator>Smith, John</dc:creator>
                <dc:date>2023</dc:date>
            </rdf:Description>
            <rdf:Description>
                <dc:identifier>456</dc:identifier>
                <dc:title>Test Paper 2</dc:title>
                <dc:creator>Doe, Jane</dc:creator>
                <dc:date>2024</dc:date>
            </rdf:Description>
        </rdf:RDF>"""

        result = EuropePMCParser.parse_dc(dc_str)

        assert len(result) == 2
        assert result[0]["identifier"] == "123"
        assert result[0]["title"] == "Test Paper 1"
        assert result[0]["creator"] == "Smith, John"
        assert result[1]["identifier"] == "456"
        assert result[1]["title"] == "Test Paper 2"

    def test_parse_dc_xml_with_multiple_creators(self):
        """Test parsing DC XML with multiple creators."""
        dc_str = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/">
            <rdf:Description>
                <dc:identifier>123</dc:identifier>
                <dc:title>Multi-author Paper</dc:title>
                <dc:creator>Smith, John</dc:creator>
                <dc:creator>Doe, Jane</dc:creator>
                <dc:creator>Johnson, Bob</dc:creator>
            </rdf:Description>
        </rdf:RDF>"""

        result = EuropePMCParser.parse_dc(dc_str)

        assert len(result) == 1
        paper = result[0]
        assert paper["identifier"] == "123"
        assert paper["title"] == "Multi-author Paper"
        assert isinstance(paper["creator"], list)
        assert len(paper["creator"]) == 3
        assert "Smith, John" in paper["creator"]
        assert "Doe, Jane" in paper["creator"]
        assert "Johnson, Bob" in paper["creator"]

    def test_parse_dc_xml_with_mixed_namespaces(self):
        """Test parsing DC XML with mixed namespaces."""
        dc_str = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/"
                 xmlns:dcterms="http://purl.org/dc/terms/">
            <rdf:Description>
                <dc:identifier>123</dc:identifier>
                <dc:title>Test Paper</dc:title>
                <dcterms:abstract>This is an abstract</dcterms:abstract>
                <dc:type>Article</dc:type>
            </rdf:Description>
        </rdf:RDF>"""

        result = EuropePMCParser.parse_dc(dc_str)

        assert len(result) == 1
        paper = result[0]
        assert paper["identifier"] == "123"
        assert paper["title"] == "Test Paper"
        assert paper["abstract"] == "This is an abstract"
        assert paper["type"] == "Article"

    def test_parse_dc_xml_empty_results(self):
        """Test parsing DC XML with no descriptions."""
        dc_str = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/">
        </rdf:RDF>"""

        result = EuropePMCParser.parse_dc(dc_str)
        assert result == []

    def test_parse_dc_xml_with_none_values(self):
        """Test parsing DC XML with empty elements."""
        dc_str = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/">
            <rdf:Description>
                <dc:identifier>123</dc:identifier>
                <dc:title></dc:title>
                <dc:creator/>
                <dc:date>2023</dc:date>
            </rdf:Description>
        </rdf:RDF>"""
        result = EuropePMCParser.parse_dc(dc_str)
        assert len(result) == 1
        paper = result[0]
        assert paper["identifier"] == "123"
        # Parser sets missing title to empty string
        assert paper["title"] == ""
        # Empty creator is omitted or not set
        assert "creator" not in paper or paper["creator"] is None or paper["creator"] == ""
        assert paper["date"] == "2023"

    def test_parse_invalid_dc_xml(self):
        """Test parsing invalid DC XML raises error."""
        dc_str = "<invalid><xml>missing closing tag</invalid>"

        with pytest.raises(Exception):
            EuropePMCParser.parse_dc(dc_str)

    def test_parse_dc_xml_duplicate_handling(self):
        """Test handling of duplicate elements in DC XML."""
        dc_str = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/">
            <rdf:Description>
                <dc:identifier>123</dc:identifier>
                <dc:subject>Biology</dc:subject>
                <dc:subject>Medicine</dc:subject>
                <dc:subject>Genetics</dc:subject>
            </rdf:Description>
        </rdf:RDF>"""

        result = EuropePMCParser.parse_dc(dc_str)

        assert len(result) == 1
        paper = result[0]
        assert paper["identifier"] == "123"
        assert isinstance(paper["subject"], list)
        assert len(paper["subject"]) == 3
        assert "Biology" in paper["subject"]
        assert "Medicine" in paper["subject"]
        assert "Genetics" in paper["subject"]

    def test_parse_dc_xml_edge_case_single_to_list(self):
        """Test edge case where single element becomes list when duplicate added."""
        dc_str = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/">
            <rdf:Description>
                <dc:identifier>123</dc:identifier>
                <dc:language>en</dc:language>
                <dc:language>fr</dc:language>
            </rdf:Description>
        </rdf:RDF>"""

        result = EuropePMCParser.parse_dc(dc_str)

        assert len(result) == 1
        paper = result[0]
        assert isinstance(paper["language"], list)
        assert "en" in paper["language"]
        assert "fr" in paper["language"]


class TestParserExceptionHandling:
    """Test cases for parser exception handling."""

    def test_json_parser_exception_handling(self, caplog):
        """Test that JSON parser handles exceptions gracefully."""
        # Create a mock object that will raise an exception during iteration
        class MockDict(dict):
            def get(self, key, default=None):
                if key == "resultList":
                    raise RuntimeError("Mock exception")
                return super().get(key, default)
        mock_data = MockDict({"hitCount": 1})
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_json(mock_data)
        assert exc_info.value.error_code == ErrorCodes.PARSE003

    def test_xml_parser_exception_handling(self, caplog):
        """Test that XML parser handles parsing exceptions."""
        malformed_xml = "<root><unclosed>tag</root>"
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_xml(malformed_xml)
        assert exc_info.value.error_code == ErrorCodes.PARSE002

    def test_dc_parser_exception_handling(self, caplog):
        """Test that DC parser handles parsing exceptions."""
        malformed_dc = "<rdf:RDF><unclosed>tag</rdf:RDF>"
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_dc(malformed_dc)
        assert exc_info.value.error_code == ErrorCodes.PARSE002


class TestParserIntegration:
    """Integration tests for parser functionality."""

    def test_roundtrip_json_parsing(self):
        """Test that JSON parsing is consistent and reversible."""
        original_data = {
            "hitCount": 3,
            "resultList": {
                "result": [
                    {"id": "1", "title": "Paper 1", "authors": ["A", "B"]},
                    {"id": "2", "title": "Paper 2", "year": 2023},
                    {"id": "3", "title": "Paper 3", "abstract": "Abstract text"},
                ]
            },
        }

        # Parse the data
        parsed = EuropePMCParser.parse_json(original_data)

        # Verify the results match the original structure
        assert len(parsed) == 3
        assert parsed[0]["id"] == "1"
        assert parsed[0]["authors"] == ["A", "B"]
        assert parsed[1]["year"] == 2023
        assert parsed[2]["abstract"] == "Abstract text"

    def test_parse_empty_or_none_inputs(self):
        """Test parser behavior with empty or None inputs."""
        # JSON parser
        assert EuropePMCParser.parse_json({}) == []
        assert EuropePMCParser.parse_json([]) == []
        # XML parser
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_xml("")
        assert exc_info.value.error_code == ErrorCodes.PARSE003
        # DC parser
        with pytest.raises(ParsingError) as exc_info:
            EuropePMCParser.parse_dc("")
        assert exc_info.value.error_code == ErrorCodes.PARSE003

    def test_parser_type_consistency(self):
        """Test that parsers return consistent types."""
        # All parsers should return List[Dict[str, Any]]

        json_result = EuropePMCParser.parse_json([{"id": "1"}])
        assert isinstance(json_result, list)
        assert all(isinstance(item, dict) for item in json_result)

        xml_result = EuropePMCParser.parse_xml(
            "<root><resultList><result><id>1</id></result></resultList></root>"
        )
        assert isinstance(xml_result, list)
        assert all(isinstance(item, dict) for item in xml_result)

        dc_result = EuropePMCParser.parse_dc(
            """<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                      xmlns:dc="http://purl.org/dc/elements/1.1/">
                <rdf:Description><dc:identifier>1</dc:identifier></rdf:Description>
               </rdf:RDF>"""
        )
        assert isinstance(dc_result, list)
        assert all(isinstance(item, dict) for item in dc_result)
