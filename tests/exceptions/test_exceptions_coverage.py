"""
Additional unit tests for exceptions module to improve test coverage.

This module focuses on testing the new error code system and less common scenarios
to achieve higher test coverage for the exceptions module.
"""

from pyeuropepmc.core.exceptions import (
    PyEuropePMCError,
    APIClientError,
    SearchError,
    FullTextError,
    ParsingError,
    ValidationError,
    ConfigurationError,
    EuropePMCError,
)
from pyeuropepmc.core.error_codes import ErrorCodes


class TestExceptionsCoverage:
    """Test coverage for exception classes with new error code system."""

    def test_pyeuropepmc_error_basic(self):
        """Test PyEuropePMCError basic functionality."""
        error = PyEuropePMCError(ErrorCodes.NET001)

        assert error.error_code == ErrorCodes.NET001
        assert "Network connection failed" in str(error)
        assert "[NET001]" in str(error)

    def test_pyeuropepmc_error_with_context(self):
        """Test PyEuropePMCError with context."""
        context = {"url": "https://example.com"}
        error = PyEuropePMCError(ErrorCodes.NET001, context)

        assert error.error_code == ErrorCodes.NET001
        assert error.context == context

    def test_pyeuropepmc_error_enum_value_access(self):
        """Test PyEuropePMCError with ErrorCodes enum value access."""
        error = PyEuropePMCError(ErrorCodes.NET001)

        assert error.error_code == ErrorCodes.NET001
        assert error.error_code.value == "NET001"
        assert "Network connection failed" in str(error)

    def test_api_client_error(self):
        """Test APIClientError functionality."""
        context = {"endpoint": "test", "status_code": 500}
        error = APIClientError(ErrorCodes.HTTP500, context)

        assert error.error_code == ErrorCodes.HTTP500
        assert error.context == context
        assert isinstance(error, PyEuropePMCError)

    def test_search_error(self):
        """Test SearchError functionality."""
        context = {"query": "test query"}
        error = SearchError(ErrorCodes.SEARCH001, context)

        assert error.error_code == ErrorCodes.SEARCH001
        assert error.context == context
        assert isinstance(error, PyEuropePMCError)

    def test_fulltext_error(self):
        """Test FullTextError functionality."""
        context = {"pmcid": "12345", "format_type": "pdf"}
        error = FullTextError(ErrorCodes.FULL001, context)

        assert error.error_code == ErrorCodes.FULL001
        assert error.context == context
        assert isinstance(error, PyEuropePMCError)

    def test_parsing_error(self):
        """Test ParsingError functionality."""
        context = {"data_type": "json", "line_number": 42}
        error = ParsingError(ErrorCodes.PARSE001, context)

        assert error.error_code == ErrorCodes.PARSE001
        assert error.context == context
        assert isinstance(error, PyEuropePMCError)

    def test_validation_error(self):
        """Test ValidationError functionality."""
        context = {"field_name": "query", "expected_type": "str"}
        error = ValidationError(ErrorCodes.VALID001, context)

        assert error.error_code == ErrorCodes.VALID001
        assert error.context == context
        assert isinstance(error, PyEuropePMCError)

    def test_configuration_error(self):
        """Test ConfigurationError functionality."""
        context = {"config_key": "api_url"}
        error = ConfigurationError(ErrorCodes.CONFIG001, context)

        assert error.error_code == ErrorCodes.CONFIG001
        assert error.context == context
        assert isinstance(error, PyEuropePMCError)

    def test_error_codes_enum(self):
        """Test ErrorCodes enum."""
        assert hasattr(ErrorCodes, "NET001")
        assert hasattr(ErrorCodes, "SEARCH001")
        assert hasattr(ErrorCodes, "FULL001")
        assert hasattr(ErrorCodes, "PARSE001")
        assert hasattr(ErrorCodes, "VALID001")
        assert hasattr(ErrorCodes, "CONFIG001")

    def test_exception_inheritance(self):
        """Test that all exceptions inherit from PyEuropePMCError."""
        error_classes = [
            APIClientError,
            SearchError,
            FullTextError,
            ParsingError,
            ValidationError,
            ConfigurationError,
        ]

        for error_class in error_classes:
            error = error_class(ErrorCodes.NET001)
            assert isinstance(error, PyEuropePMCError)
            assert isinstance(error, Exception)

    def test_exception_string_representation(self):
        """Test string representation of exceptions."""
        error = APIClientError(ErrorCodes.NET001, {"url": "test.com"})

        str_repr = str(error)
        assert "[NET001]" in str_repr
        assert "Network connection failed" in str_repr

    def test_exception_repr(self):
        """Test repr of exceptions."""
        error = APIClientError(ErrorCodes.NET001, {"url": "test.com"})

        repr_str = repr(error)
        assert "APIClientError" in repr_str
        assert "NET001" in repr_str

    def test_europe_pmc_error_legacy_alias(self):
        """Test that EuropePMCError is an alias for SearchError."""
        assert EuropePMCError is SearchError

        error = EuropePMCError(ErrorCodes.SEARCH001)
        assert isinstance(error, SearchError)
        assert isinstance(error, PyEuropePMCError)

    def test_context_none_handling(self):
        """Test handling of None context."""
        error = APIClientError(ErrorCodes.NET001, None)

        assert error.context == {}
        assert error.error_code == ErrorCodes.NET001

    def test_empty_context_handling(self):
        """Test handling of empty context."""
        error = APIClientError(ErrorCodes.NET001, {})

        assert error.context == {}
        assert error.error_code == ErrorCodes.NET001
