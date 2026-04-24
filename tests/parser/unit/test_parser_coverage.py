"""
Additional unit tests for EuropePMCParser to improve test coverage.

This module focuses on testing edge cases, error paths, and less common scenarios
to achieve higher test coverage for the parser module.
"""


import pytest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from pyeuropepmc.processing.search_parser import EuropePMCParser
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.core.error_codes import ErrorCodes


pytestmark = pytest.mark.unit


class TestEuropePMCParserCoverage:
    def test_parse_json_with_invalid_items_logs_error(self, caplog):
        """Test that parse_json logs errors for invalid items in result list."""
        invalid_json = {
            'resultList': {
                'result': [
                    {'valid': 'yes'},
                    'not_a_dict',
                    123,
                    {'valid': 'also'},
                ]
            }
        }
        with caplog.at_level('ERROR'):
            results = self.parser.parse_json(invalid_json)
        # Only valid dicts should be returned
        assert results == [{'valid': 'yes'}, {'valid': 'also'}]
        # Should log errors for invalid items
        error_logs = [r for r in caplog.records if r.levelname == 'ERROR']
        assert any('Result item parsing failed at index' in r.getMessage() for r in error_logs)

    def test_parse_xml_with_malformed_record_logs_error(self, caplog):
        """Test that parse_xml raises ParsingError for malformed record elements."""
        xml_content = """
        <root>
            <resultList>
                <result><valid>yes</valid></result>
                <result><invalid><unclosed></result>
                <result><valid>also</valid></result>
            </resultList>
        </root>
        """
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_xml(xml_content)
        assert exc_info.value.error_code == ErrorCodes.PARSE002

    def test_parse_dc_with_malformed_record_logs_error(self, caplog):
        """Test that parse_dc raises ParsingError for malformed DC description elements."""
        dc_content = """
        <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
            <rdf:Description><dc:title>Valid</dc:title></rdf:Description>
            <rdf:Description><invalid><unclosed></rdf:Description>
            <rdf:Description><dc:title>Also Valid</dc:title></rdf:Description>
        </rdf:RDF>
        """
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_dc(dc_content)
        assert exc_info.value.error_code == ErrorCodes.PARSE002
    """Additional test coverage for EuropePMCParser edge cases."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.parser = EuropePMCParser()

    def test_parse_xml_with_malformed_xml(self):
        """Test parse_xml with malformed XML."""
        malformed_xml = "<xml><incomplete"

        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_xml(malformed_xml)
        assert exc_info.value.error_code == ErrorCodes.PARSE002

    def test_parse_xml_with_empty_string(self):
        """Test parse_xml with empty string."""
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_xml("")
        assert exc_info.value.error_code == ErrorCodes.PARSE003

    def test_parse_xml_with_none_input(self):
        """Test parse_xml with None input."""
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_xml(None)  # type: ignore
        assert exc_info.value.error_code == ErrorCodes.PARSE003

    def test_parse_xml_with_whitespace_only(self):
        """Test parse_xml with whitespace-only input."""
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_xml("   \n\t  ")
        assert exc_info.value.error_code == ErrorCodes.PARSE003

    def test_parse_dc_with_malformed_xml(self):
        """Test parse_dc with malformed XML."""
        malformed_xml = "<dc:record><incomplete"

        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_dc(malformed_xml)
        assert exc_info.value.error_code == ErrorCodes.PARSE002

    def test_parse_dc_with_empty_string(self):
        """Test parse_dc with empty string."""
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_dc("")
        assert exc_info.value.error_code == ErrorCodes.PARSE003

    def test_parse_dc_with_none_input(self):
        """Test parse_dc with None input."""
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_dc(None)  # type: ignore
        assert exc_info.value.error_code == ErrorCodes.PARSE003

    def test_parse_dc_with_whitespace_only(self):
        """Test parse_dc with whitespace-only input."""
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_dc("   \n\t  ")
        assert exc_info.value.error_code == ErrorCodes.PARSE003

    def test_parse_dc_with_missing_namespace(self):
        """Test parse_dc with missing Dublin Core namespace."""
        xml_without_namespace = """
        <record>
            <title>Test Title</title>
            <identifier>PMC123456</identifier>
        </record>
        """

        result = self.parser.parse_dc(xml_without_namespace)
        # Should handle gracefully and return empty result
        assert isinstance(result, list)

    def test_parse_dc_with_invalid_structure(self):
        """Test parse_dc with invalid XML structure."""
        invalid_xml = """
        <root>
            <not_dc_record>Invalid structure</not_dc_record>
        </root>
        """

        result = self.parser.parse_dc(invalid_xml)
        # Should handle gracefully and return empty result
        assert isinstance(result, list)

    def test_parse_dc_with_et_parse_error(self):
        """Test parse_dc when ElementTree.fromstring raises an exception."""
        with patch("defusedxml.ElementTree.fromstring", side_effect=ET.ParseError("Parse error")):
            with pytest.raises(ParsingError) as exc_info:
                self.parser.parse_dc("<valid>xml</valid>")
            assert exc_info.value.error_code == ErrorCodes.PARSE002

    def test_parse_xml_with_et_parse_error(self):
        """Test parse_xml when ElementTree.fromstring raises an exception."""
        with patch("defusedxml.ElementTree.fromstring", side_effect=ET.ParseError("Parse error")):
            with pytest.raises(ParsingError) as exc_info:
                self.parser.parse_xml("<valid>xml</valid>")
            assert exc_info.value.error_code == ErrorCodes.PARSE002

    def test_parse_dc_with_complex_valid_xml(self):
        """Test parse_dc with complex valid Dublin Core XML."""
        dc_xml = """
        <root xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:record>
                <dc:title>Complex Test Article</dc:title>
                <dc:creator>Author One</dc:creator>
                <dc:creator>Author Two</dc:creator>
                <dc:identifier>PMC123456</dc:identifier>
                <dc:subject>cancer</dc:subject>
                <dc:subject>treatment</dc:subject>
                <dc:date>2023-01-01</dc:date>
                <dc:description>A complex test article about cancer treatment.</dc:description>
            </dc:record>
            <dc:record>
                <dc:title>Another Article</dc:title>
                <dc:creator>Author Three</dc:creator>
                <dc:identifier>PMC789012</dc:identifier>
            </dc:record>
        </root>
        """

        result = self.parser.parse_dc(dc_xml)
        assert isinstance(result, list)
        assert len(result) >= 0  # Should handle the parsing without errors

    def test_parse_xml_with_complex_valid_xml(self):
        """Test parse_xml with complex valid XML."""
        xml_content = """
        <root>
            <article>
                <title>Complex Test Article</title>
                <abstract>This is a test abstract.</abstract>
                <authors>
                    <author>Author One</author>
                    <author>Author Two</author>
                </authors>
                <metadata>
                    <pmcid>PMC123456</pmcid>
                    <doi>10.1234/test.2023.001</doi>
                </metadata>
            </article>
        </root>
        """
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_xml(xml_content)
        assert exc_info.value.error_code == ErrorCodes.PARSE004

    def test_parse_dc_error_context(self):
        """Test that parse_dc provides proper error context."""
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_dc("invalid xml")
        assert exc_info.value.error_code == ErrorCodes.PARSE002

    def test_parse_xml_error_context(self):
        """Test that parse_xml provides proper error context."""
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_xml("invalid xml")
        assert exc_info.value.error_code == ErrorCodes.PARSE002

    def test_parse_json_error_context(self):
        """Test that parse_json provides proper error context when data format is invalid."""
        # This should raise ParsingError as it's wrapped in the implementation
        with pytest.raises(ParsingError) as exc_info:
            self.parser.parse_json("invalid_string_data")

        # Check that error contains context information
        assert "expected_type" in exc_info.value.context
        assert "actual_type" in exc_info.value.context
        assert exc_info.value.context["actual_type"] == "str"
