"""
Unit tests for ArticleClient validation methods.

Comprehensive tests for all validation helper methods to maximize coverage.
"""

import pytest
from pyeuropepmc.clients.article import ArticleClient
from pyeuropepmc.core.exceptions import ValidationError
from pyeuropepmc.core.error_codes import ErrorCodes


class TestArticleClientValidation:
    """Test suite focused on ArticleClient validation methods."""

    @pytest.fixture
    def client(self):
        """Create ArticleClient instance for testing."""
        return ArticleClient()

    # Test _validate_source_and_id
    def test_validate_source_and_id_valid_sources(self, client):
        """Test validation with all valid source codes."""
        valid_sources = ["MED", "PMC", "PPR", "CBA", "CTX", "ETH"]
        for source in valid_sources:
            client._validate_source_and_id(source, "12345")  # Should not raise

    def test_validate_source_and_id_invalid_source_type(self, client):
        """Test validation with non-string source."""
        with pytest.raises(ValidationError) as exc:
            client._validate_source_and_id(123, "12345")
        assert exc.value.error_code == ErrorCodes.VALID001
        assert exc.value.field_name == "source"

    def test_validate_source_and_id_invalid_source_length(self, client):
        """Test validation with wrong source length."""
        with pytest.raises(ValidationError) as exc:
            client._validate_source_and_id("MEDLINE", "12345")
        assert "3-letter" in exc.value.message

    def test_validate_source_and_id_empty_source(self, client):
        """Test validation with empty source."""
        with pytest.raises(ValidationError):
            client._validate_source_and_id("", "12345")

    def test_validate_source_and_id_none_source(self, client):
        """Test validation with None source."""
        with pytest.raises(ValidationError):
            client._validate_source_and_id(None, "12345")

    def test_validate_source_and_id_invalid_article_id_type(self, client):
        """Test validation with non-string article ID."""
        with pytest.raises(ValidationError) as exc:
            client._validate_source_and_id("MED", 12345)
        assert exc.value.field_name == "article_id"

    def test_validate_source_and_id_empty_article_id(self, client):
        """Test validation with empty article ID."""
        with pytest.raises(ValidationError):
            client._validate_source_and_id("MED", "")

    def test_validate_source_and_id_none_article_id(self, client):
        """Test validation with None article ID."""
        with pytest.raises(ValidationError):
            client._validate_source_and_id("MED", None)

    # Test _validate_pagination
    def test_validate_pagination_valid_ranges(self, client):
        """Test pagination validation with valid ranges."""
        valid_combinations = [
            (1, 1),
            (1, 25),
            (10, 100),
            (999, 1000)
        ]
        for page, page_size in valid_combinations:
            client._validate_pagination(page, page_size)  # Should not raise

    def test_validate_pagination_invalid_page_type(self, client):
        """Test pagination validation with non-integer page."""
        with pytest.raises(ValidationError) as exc:
            client._validate_pagination("1", 25)
        assert exc.value.field_name == "page"

    def test_validate_pagination_invalid_page_size_type(self, client):
        """Test pagination validation with non-integer page size."""
        with pytest.raises(ValidationError) as exc:
            client._validate_pagination(1, "25")
        assert exc.value.field_name == "page_size"

    def test_validate_pagination_page_too_small(self, client):
        """Test pagination validation with page < 1."""
        with pytest.raises(ValidationError) as exc:
            client._validate_pagination(0, 25)
        assert "positive integer" in exc.value.message

    def test_validate_pagination_page_size_too_small(self, client):
        """Test pagination validation with page_size < 1."""
        with pytest.raises(ValidationError) as exc:
            client._validate_pagination(1, 0)
        assert "between 1 and 1000" in exc.value.message

    def test_validate_pagination_page_size_too_large(self, client):
        """Test pagination validation with page_size > 1000."""
        with pytest.raises(ValidationError) as exc:
            client._validate_pagination(1, 1001)
        assert "between 1 and 1000" in exc.value.message

    # Test _validate_citations_format
    def test_validate_citations_format_valid(self, client):
        """Test format validation with valid formats."""
        valid_formats = ["json", "xml"]
        for fmt in valid_formats:
            client._validate_citations_format(fmt)  # Should not raise

    def test_validate_citations_format_invalid_type(self, client):
        """Test format validation with non-string format."""
        with pytest.raises(ValidationError) as exc:
            client._validate_citations_format(123)
        assert exc.value.field_name == "format"

    def test_validate_citations_format_invalid_value(self, client):
        """Test format validation with invalid format value."""
        with pytest.raises(ValidationError) as exc:
            client._validate_citations_format("csv")
        assert "json" in exc.value.message and "xml" in exc.value.message

    def test_validate_citations_format_none(self, client):
        """Test format validation with None format."""
        with pytest.raises(ValidationError):
            client._validate_citations_format(None)

    def test_validate_citations_format_empty(self, client):
        """Test format validation with empty format."""
        with pytest.raises(ValidationError):
            client._validate_citations_format("")

    # Test _validate_callback
    def test_validate_callback_none_valid(self, client):
        """Test callback validation with None (valid case)."""
        client._validate_callback(None, "json")  # Should not raise
        client._validate_callback(None, "xml")   # Should not raise

    def test_validate_callback_valid_string_json(self, client):
        """Test callback validation with valid string and JSON format."""
        client._validate_callback("myCallback", "json")
        client._validate_callback("processData", "json")
        client._validate_callback("callback_123", "json")

    def test_validate_callback_invalid_type(self, client):
        """Test callback validation with non-string callback."""
        with pytest.raises(ValidationError) as exc:
            client._validate_callback(123, "json")
        assert exc.value.field_name == "callback"
        assert "must be a string" in exc.value.message

    def test_validate_callback_list_type(self, client):
        """Test callback validation with list type."""
        with pytest.raises(ValidationError):
            client._validate_callback(["callback"], "json")

    def test_validate_callback_dict_type(self, client):
        """Test callback validation with dict type."""
        with pytest.raises(ValidationError):
            client._validate_callback({"callback": "value"}, "json")

    def test_validate_callback_with_xml_format(self, client):
        """Test callback validation with XML format (invalid)."""
        with pytest.raises(ValidationError) as exc:
            client._validate_callback("myCallback", "xml")
        assert exc.value.field_name == "callback"
        assert "requires format to be 'json'" in exc.value.message

    def test_validate_callback_empty_string_xml(self, client):
        """Test callback validation with empty string and XML."""
        with pytest.raises(ValidationError):
            client._validate_callback("", "xml")

    # Integration tests combining multiple validations
    def test_multiple_validation_calls(self, client):
        """Test multiple validation calls in sequence."""
        # This should all pass without exceptions
        client._validate_source_and_id("MED", "12345")
        client._validate_pagination(1, 25)
        client._validate_citations_format("json")
        client._validate_callback("myCallback", "json")

    def test_validation_error_contexts(self, client):
        """Test that validation errors include proper context."""
        try:
            client._validate_source_and_id("INVALID", "12345")
        except ValidationError as e:
            assert e.error_code == ErrorCodes.VALID001
            assert e.field_name == "source"
            assert e.actual_value == "INVALID"
            assert "3-letter" in e.message

    def test_validation_with_unicode_strings(self, client):
        """Test validation with unicode characters."""
        # These should work
        client._validate_source_and_id("MED", "123é45")
        client._validate_callback("callbackÄÖÜ", "json")

        # This should fail due to length, not unicode
        with pytest.raises(ValidationError):
            client._validate_source_and_id("MEDé", "12345")

    def test_validation_with_special_characters(self, client):
        """Test validation with special characters in strings."""
        # Valid cases
        client._validate_source_and_id("MED", "PMC-123_456")
        client._validate_callback("my.callback.function", "json")

        # Edge cases that should still pass
        client._validate_source_and_id("MED", "123/456")
        client._validate_callback("callback$special", "json")
