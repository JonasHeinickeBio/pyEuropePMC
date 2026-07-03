"""Tests for geographic validation utilities."""
import pytest

from pyeuropepmc.processing.utils.geo_validators import (
    _clean_country_name_simple,
    GeoValidator,
)


class TestCleanCountryNameSimple:
    """Tests for _clean_country_name_simple."""

    def test_empty_string(self):
        """Test empty string returns empty."""
        assert _clean_country_name_simple("") == ""

    def test_trailing_period(self):
        """Test trailing period is removed."""
        assert _clean_country_name_simple("USA.") == "USA"

    def test_trailing_comma(self):
        """Test trailing comma is removed."""
        assert _clean_country_name_simple("Germany,") == "Germany"

    def test_trailing_multiple_punctuation(self):
        """Test multiple trailing punctuation is removed."""
        assert _clean_country_name_simple("UK!?") == "UK"

    def test_no_trailing_punctuation(self):
        """Test string without trailing punctuation is unchanged."""
        assert _clean_country_name_simple("Canada") == "Canada"

    def test_only_punctuation(self):
        """Test string with only punctuation."""
        assert _clean_country_name_simple(".,!") == ""


class TestIsLikelyStateProvince:
    """Tests for is_likely_state_province."""

    def test_us_state(self):
        """Test US state abbreviation."""
        assert GeoValidator.is_likely_state_province("CA")

    def test_us_state_lowercase(self):
        """Test US state abbreviation lowercase."""
        assert GeoValidator.is_likely_state_province("ny")

    def test_canadian_province(self):
        """Test Canadian province abbreviation."""
        assert GeoValidator.is_likely_state_province("ON")

    def test_australian_state(self):
        """Test Australian state abbreviation."""
        assert GeoValidator.is_likely_state_province("NSW")

    def test_uk_country(self):
        """Test UK country abbreviation."""
        assert GeoValidator.is_likely_state_province("ENG")

    def test_not_a_state(self):
        """Test non-state text returns False."""
        assert not GeoValidator.is_likely_state_province("XYZ")

    def test_empty_string(self):
        """Test empty string returns False."""
        assert not GeoValidator.is_likely_state_province("")


class TestIsLikelyCountry:
    """Tests for is_likely_country."""

    def test_known_country(self):
        """Test known country name."""
        assert GeoValidator.is_likely_country("USA")

    def test_known_country_lowercase(self):
        """Test known country name lowercase."""
        assert GeoValidator.is_likely_country("germany")

    def test_iso_two_letter(self):
        """Test ISO 2-letter code."""
        assert GeoValidator.is_likely_country("FR")

    def test_iso_three_letter_not_found(self):
        """Test 3-letter code — ISO_COUNTRY_CODES keys are 2-letter, so 3-letter returns False."""
        assert not GeoValidator.is_likely_country("DEU")

    def test_country_indicator(self):
        """Test text containing country indicator word."""
        assert GeoValidator.is_likely_country("Czech Republic")

    def test_not_a_country(self):
        """Test non-country text returns False."""
        assert not GeoValidator.is_likely_country("123")

    def test_with_clean_function(self):
        """Test with custom clean function."""
        result = GeoValidator.is_likely_country(
            "USA.", clean_country_fn=lambda s: s.strip(".")
        )
        assert result

    def test_empty_string(self):
        """Test empty string returns False."""
        assert not GeoValidator.is_likely_country("")


class TestIsPostalCode:
    """Tests for is_postal_code."""

    def test_us_zip(self):
        """Test US ZIP code."""
        assert GeoValidator.is_postal_code("90210")

    def test_us_zip_plus4(self):
        """Test US ZIP+4 code."""
        assert GeoValidator.is_postal_code("90210-1234")

    def test_canadian_postal(self):
        """Test Canadian postal code."""
        assert GeoValidator.is_postal_code("K1A 0B1")

    def test_canadian_postal_no_space(self):
        """Test Canadian postal code without space."""
        assert GeoValidator.is_postal_code("K1A0B1")

    def test_uk_postal(self):
        """Test UK postal code."""
        assert GeoValidator.is_postal_code("SW1A 1AA")

    def test_other_digit_postal(self):
        """Test 4-6 digit postal code."""
        assert GeoValidator.is_postal_code("1234")
        assert GeoValidator.is_postal_code("123456")

    def test_not_postal_code(self):
        """Test non-postal text returns False."""
        assert not GeoValidator.is_postal_code("Hello World")

    def test_embedded_postal_pattern(self):
        """Test text containing embedded postal pattern."""
        assert GeoValidator.is_postal_code("unit K1A 0B1 box")

    def test_empty_string(self):
        """Test empty string returns False."""
        assert not GeoValidator.is_postal_code("")


class TestExtractCountry:
    """Tests for extract_country."""

    def test_with_country(self):
        """Test extracting country from components."""
        components = ["University", "Boston", "USA"]
        result = GeoValidator.extract_country(components)
        assert result == "USA"
        assert components == ["University", "Boston"]

    def test_without_country(self):
        """Test when last component is not a country."""
        components = ["University", "Boston"]
        result = GeoValidator.extract_country(components)
        assert result is None
        assert components == ["University", "Boston"]

    def test_empty_list(self):
        """Test empty list returns None."""
        components: list[str] = []
        result = GeoValidator.extract_country(components)
        assert result is None


class TestExtractStateProvince:
    """Tests for extract_state_province."""

    def test_with_state(self):
        """Test extracting state from components."""
        components = ["University", "Los Angeles", "CA"]
        result = GeoValidator.extract_state_province(components)
        assert result == "CA"
        assert components == ["University", "Los Angeles"]

    def test_without_state(self):
        """Test when last component is not a state."""
        components = ["University", "Boston"]
        result = GeoValidator.extract_state_province(components)
        assert result is None
        assert components == ["University", "Boston"]

    def test_empty_list(self):
        """Test empty list returns None."""
        components: list[str] = []
        result = GeoValidator.extract_state_province(components)
        assert result is None


class TestExtractPostalCode:
    """Tests for extract_postal_code."""

    def test_standalone_zip(self):
        """Test extracting standalone ZIP code."""
        components = ["University", "New York", "10001"]
        result = GeoValidator.extract_postal_code(components)
        assert result == "10001"
        assert components == ["University", "New York"]

    def test_embedded_in_component(self):
        """Test extracting postal code embedded in component."""
        components = ["University", "New York 10001"]
        result = GeoValidator.extract_postal_code(components)
        assert result == "10001"
        assert components == ["University", "New York"]

    def test_embedded_full_replacement(self):
        """Test embedded postal code that replaces entire component."""
        components = ["University", "10001"]
        result = GeoValidator.extract_postal_code(components)
        assert result == "10001"
        assert components == ["University"]

    def test_not_found(self):
        """Test no postal code found."""
        components = ["University", "Boston"]
        result = GeoValidator.extract_postal_code(components)
        assert result is None
        assert components == ["University", "Boston"]

    def test_empty_list(self):
        """Test empty list returns None."""
        components: list[str] = []
        result = GeoValidator.extract_postal_code(components)
        assert result is None


class TestExtractCity:
    """Tests for extract_city."""

    def test_two_or_more_components(self):
        """Test extracting city with 2+ components."""
        components = ["University", "Boston"]
        result = GeoValidator.extract_city(components)
        assert result == "Boston"
        assert components == ["University"]

    def test_single_component(self):
        """Test with single component returns None."""
        components = ["University"]
        result = GeoValidator.extract_city(components)
        assert result is None
        assert components == ["University"]

    def test_empty_list(self):
        """Test empty list returns None."""
        components: list[str] = []
        result = GeoValidator.extract_city(components)
        assert result is None
