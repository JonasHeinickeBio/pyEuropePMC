"""
Extra coverage tests for pyeuropepmc.exceptions.py
"""
import pytest
from pyeuropepmc.exceptions import (
    PyEuropePMCError, APIClientError, SearchError, FullTextError, ParsingError, ValidationError, ConfigurationError
)
from pyeuropepmc.error_codes import ErrorCodes

def test_value_error_if_no_code_or_message():
    with pytest.raises(ValueError):
        PyEuropePMCError()

def test_auto_generate_error_code():
    class DummySearchError(PyEuropePMCError):
        pass
    err = DummySearchError(error_code=None, message="dummy")
    assert err.error_code == ErrorCodes.GENERIC003
    class DummyFullTextError(PyEuropePMCError):
        pass
    err2 = DummyFullTextError(error_code=None, message="dummy")
    assert err2.error_code == ErrorCodes.GENERIC004
    class DummyParsingError(PyEuropePMCError):
        pass
    err3 = DummyParsingError(error_code=None, message="dummy")
    assert err3.error_code == ErrorCodes.GENERIC005
    class DummyValidationError(PyEuropePMCError):
        pass
    err4 = DummyValidationError(error_code=None, message="dummy")
    assert err4.error_code == ErrorCodes.GENERIC006
    class DummyConfigurationError(PyEuropePMCError):
        pass
    err5 = DummyConfigurationError(error_code=None, message="dummy")
    assert err5.error_code == ErrorCodes.GENERIC007
    class DummyAPIClientError(PyEuropePMCError):
        pass
    err6 = DummyAPIClientError(error_code=None, message="dummy")
    assert err6.error_code == ErrorCodes.GENERIC002
    class DummyOtherError(PyEuropePMCError):
        pass
    err7 = DummyOtherError(error_code=None, message="dummy")
    assert err7.error_code == ErrorCodes.GENERIC001

def test_context_formatting_fallback():
    # Provide incomplete context to trigger fallback
    err = PyEuropePMCError(ErrorCodes.NET001, context={"missing": "value"})
    assert "Network connection failed" in err.message

# Test context enrichment and attribute assignment for all custom errors
def test_search_error_context_enrichment():
    err = SearchError(ErrorCodes.SEARCH001, query="foo", search_type="basic")
    assert err.context["query"] == "foo"
    assert err.context["search_type"] == "basic"
    assert err.query == "foo"
    assert err.search_type == "basic"

def test_fulltext_error_context_enrichment():
    err = FullTextError(ErrorCodes.FULL001, pmcid="123", format_type="pdf", operation="download")
    assert err.context["pmcid"] == "123"
    assert err.context["format_type"] == "pdf"
    assert err.context["operation"] == "download"
    assert err.pmcid == "123"
    assert err.format_type == "pdf"
    assert err.operation == "download"

def test_parsing_error_context_enrichment():
    err = ParsingError(ErrorCodes.PARSE001, data_type="json", parser_type="fast", line_number=42)
    assert err.context["data_type"] == "json"
    assert err.context["parser_type"] == "fast"
    assert err.context["line_number"] == 42
    assert err.data_type == "json"
    assert err.parser_type == "fast"
    assert err.line_number == 42

def test_validation_error_context_enrichment():
    err = ValidationError(ErrorCodes.VALID001, field_name="foo", expected_type="int", actual_value=123)
    assert err.context["field_name"] == "foo"
    assert err.context["expected_type"] == "int"
    assert err.context["actual_value"] == "123"
    assert err.field_name == "foo"
    assert err.expected_type == "int"
    assert err.actual_value == 123
    assert err.details["field_name"] == "foo"

def test_configuration_error_context_enrichment():
    err = ConfigurationError(ErrorCodes.CONFIG001, config_key="api_url", config_section="network")
    assert err.context["config_key"] == "api_url"
    assert err.context["config_section"] == "network"
    assert err.config_key == "api_url"
    assert err.config_section == "network"
