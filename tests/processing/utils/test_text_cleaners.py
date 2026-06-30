"""Tests for text cleaning utilities."""
import pytest

from pyeuropepmc.processing.utils.text_cleaners import TextCleaner


class TestTextCleaner:
    """Tests for TextCleaner."""

    def test_clean_affiliation_text_removes_email(self):
        """Test that email addresses are removed from affiliation text."""
        result = TextCleaner.clean_affiliation_text(
            "Department of Biology, University of Test, test@example.com"
        )
        assert "test@example.com" not in result
        assert "Department of Biology" in result

    def test_clean_affiliation_text_removes_url(self):
        """Test that URLs are removed from affiliation text."""
        result = TextCleaner.clean_affiliation_text(
            "Lab at http://example.com/lab and https://test.org"
        )
        assert "http://" not in result
        assert "https://" not in result

    def test_clean_affiliation_text_removes_phone(self):
        """Test that phone numbers are removed."""
        result = TextCleaner.clean_affiliation_text("Contact: 555-123-4567")
        assert "555-123-4567" not in result

    def test_clean_affiliation_text_removes_contact_prefix(self):
        """Test that 'Contact:' and similar prefixes are removed."""
        result = TextCleaner.clean_affiliation_text(
            "University of Test. Contact: Dr. Smith. Email: test@test.com"
        )
        # The contact/email part should be stripped (trailing dot also removed)
        assert result == "University of Test"

    def test_clean_affiliation_text_empty(self):
        """Test cleaning empty string."""
        assert TextCleaner.clean_affiliation_text("") == ""

    def test_clean_country_name_no_country(self):
        """Test cleaning None or empty country."""
        assert TextCleaner.clean_country_name("") == ""
        assert TextCleaner.clean_country_name(None) is None   # type: ignore[arg-type]

    def test_clean_country_name_removes_trailing_punctuation(self):
        """Test that trailing punctuation is removed from country names."""
        result = TextCleaner.clean_country_name("United States.")
        assert result == "United States"
        result2 = TextCleaner.clean_country_name("UK,")
        assert result2 == "UK"

    def test_clean_country_name_unchanged(self):
        """Test country that doesn't need cleaning."""
        result = TextCleaner.clean_country_name("Germany")
        assert result == "Germany"

    def test_clean_orcid_none(self):
        """Test cleaning None ORCID."""
        assert TextCleaner.clean_orcid(None) is None

    def test_clean_orcid_with_prefix(self):
        """Test cleaning ORCID with URL prefix."""
        result = TextCleaner.clean_orcid("https://orcid.org/0000-0003-3442-7216")
        assert result == "0000-0003-3442-7216"

    def test_clean_orcid_http_prefix(self):
        """Test cleaning ORCID with http prefix."""
        result = TextCleaner.clean_orcid("http://orcid.org/0000-0003-3442-7216")
        assert result == "0000-0003-3442-7216"

    def test_clean_orcid_without_prefix(self):
        """Test ORCID without URL prefix is unchanged."""
        result = TextCleaner.clean_orcid("0000-0003-3442-7216")
        assert result == "0000-0003-3442-7216"
