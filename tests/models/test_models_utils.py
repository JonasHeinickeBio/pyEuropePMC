"""
Tests for models/utils.py covering edge cases missed by the existing suite.

Focuses on uncovered branches across all validation/normalization functions.
"""

from __future__ import annotations

import pytest

from pyeuropepmc.models.utils import (
    convert_to_type,
    normalize_and_validate,
    normalize_country,
    normalize_doi,
    normalize_string,
    validate_and_normalize_boolean,
    validate_and_normalize_country,
    validate_and_normalize_date,
    validate_and_normalize_email,
    validate_and_normalize_orcid,
    validate_and_normalize_pmcid,
    validate_and_normalize_pmid,
    validate_and_normalize_uri,
    validate_and_normalize_volume,
    validate_and_normalize_year,
    validate_format,
    validate_latitude_longitude,
    validate_positive_integer,
    validate_range,
    validate_regex,
)


# ============================================================================
# normalize_string
# ============================================================================

class TestNormalizeString:
    def test_allow_empty_false_with_empty(self) -> None:
        """allow_empty=False with empty string returns None."""
        assert normalize_string("  ", allow_empty=False) is None

    def test_allow_empty_false_with_value(self) -> None:
        """allow_empty=False with non-empty string works normally."""
        assert normalize_string(" hello ", allow_empty=False) == "hello"


# ============================================================================
# validate_regex
# ============================================================================

class TestValidateRegex:
    def test_no_match_raises(self) -> None:
        """Regex mismatch raises ValueError."""
        with pytest.raises(ValueError, match="must match"):
            validate_regex("abc", r"\d+", "must match pattern")


# ============================================================================
# convert_to_type
# ============================================================================

class TestConvertToType:
    def test_converter_raises_typeerror(self) -> None:
        """Converter raising TypeError is caught and re-raised as ValueError."""
        def bad(_x: object) -> int:
            raise TypeError("bad conversion")
        with pytest.raises(ValueError, match="convert error"):
            convert_to_type(123, int, bad, "convert error")

    def test_result_wrong_type(self) -> None:
        """Result not matching target_type raises ValueError."""
        with pytest.raises(ValueError, match="wrong type"):
            convert_to_type("abc", int, lambda x: x, "wrong type")  # type: ignore[return-value]


# ============================================================================
# validate_range
# ============================================================================

class TestValidateRange:
    def test_out_of_range(self) -> None:
        """Value outside range raises ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            validate_range(150, 0, 100, "out of range")


# ============================================================================
# validate_format
# ============================================================================

class TestValidateFormat:
    def test_validator_returns_false(self) -> None:
        """Validator returning False raises ValueError."""
        with pytest.raises(ValueError, match="invalid format"):
            validate_format("test", lambda x: False, "invalid format")


# ============================================================================
# normalize_and_validate
# ============================================================================

class TestNormalizeAndValidate:
    def test_allow_none_false_with_none(self) -> None:
        """allow_none=False with None raises ValueError."""
        with pytest.raises(ValueError, match="cannot be None"):
            normalize_and_validate(None, allow_none=False)

    def test_with_normalizer(self) -> None:
        """normalizer is applied."""
        result = normalize_and_validate("  hello  ", normalizer=lambda x: x.strip())
        assert result == "hello"

    def test_with_converter(self) -> None:
        """converter pipeline runs."""
        def normalizer(x: object) -> object:
            return x
        result = normalize_and_validate("123", normalizer=normalizer, converter=convert_to_type,
                                        converter_target_type=int, converter_func=int,
                                        converter_error_msg="conv fail")
        assert result == 123

    def test_with_validator(self) -> None:
        """validator is applied."""
        def normalizer(x: str) -> str:
            return x.strip()
        result = normalize_and_validate("abc", normalizer=normalizer,
                                        validator=lambda x: x.upper())
        assert result == "ABC"


# ============================================================================
# normalize_doi
# ============================================================================

class TestNormalizeDoi:
    def test_none_input(self) -> None:
        """None in, None out."""
        assert normalize_doi(None) is None


# ============================================================================
# validate_and_normalize_uri
# ============================================================================

class TestValidateAndNormalizeUri:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_uri(None) is None

    def test_invalid_uri(self) -> None:
        """Invalid URI raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URI"):
            validate_and_normalize_uri("not-a-uri")

    def test_valid_uri(self) -> None:
        """Valid URI is normalized."""
        result = validate_and_normalize_uri("http://example.com/path")
        assert result is not None
        assert result.startswith("http://")


# ============================================================================
# validate_and_normalize_email
# ============================================================================

class TestValidateAndNormalizeEmail:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_email(None) is None

    def test_invalid_email(self) -> None:
        """Invalid email raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email"):
            validate_and_normalize_email("not-an-email")


# ============================================================================
# validate_and_normalize_orcid
# ============================================================================

class TestValidateAndNormalizeOrcid:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_orcid(None) is None

    def test_invalid_format(self) -> None:
        """Invalid ORCID raises ValueError.

        The regex is ``\\d{4}-\\d{4}-\\d{4}-\\d{3}[\\dX]`` — ``X`` is a valid
        final character, so ``...678X`` *is* valid. Use a clearly invalid one.
        """
        with pytest.raises(ValueError, match="valid ORCID"):
            validate_and_normalize_orcid("0000-0001-2345-67XX")

    def test_valid_orcid(self) -> None:
        """Valid ORCID passes."""
        result = validate_and_normalize_orcid("0000-0001-2345-6789")
        assert result == "0000-0001-2345-6789"


# ============================================================================
# validate_and_normalize_pmcid
# ============================================================================

class TestValidateAndNormalizePmcid:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_pmcid(None) is None

    def test_invalid_format(self) -> None:
        """Invalid PMCID raises ValueError."""
        with pytest.raises(ValueError, match="valid PMCID"):
            validate_and_normalize_pmcid("PMCabc")

    def test_with_prefix(self) -> None:
        """PMC prefix is preserved."""
        result = validate_and_normalize_pmcid("PMC1234567")
        assert result == "PMC1234567"


# ============================================================================
# validate_and_normalize_pmid
# ============================================================================

class TestValidateAndNormalizePmid:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_pmid(None) is None

    def test_invalid_format(self) -> None:
        """Invalid PMID raises ValueError."""
        with pytest.raises(ValueError, match="valid PMID"):
            validate_and_normalize_pmid("abc")


# ============================================================================
# validate_and_normalize_year
# ============================================================================

class TestValidateAndNormalizeYear:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_year(None) is None

    def test_invalid_type(self) -> None:
        """Non-int/str value raises ValueError."""
        with pytest.raises(ValueError, match="must be an integer"):
            validate_and_normalize_year([2024])  # type: ignore[arg-type]

    def test_out_of_range(self) -> None:
        """Year out of historical range raises ValueError.

        Range is 1000-2100, so 999 is out of range.
        """
        with pytest.raises(ValueError, match="between 1000"):
            validate_and_normalize_year(999)

    def test_valid_int(self) -> None:
        """Valid integer year is normalized."""
        assert validate_and_normalize_year(2024) == 2024

    def test_valid_year_string(self) -> None:
        """Valid year string is converted."""
        assert validate_and_normalize_year("2024") == 2024


# ============================================================================
# validate_and_normalize_date
# ============================================================================

class TestValidateAndNormalizeDate:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_date(None) is None

    def test_invalid_string_returns_cleaned_string(self) -> None:
        """Unparseable date string is returned as-is (fuzzy parser is lenient)."""
        result = validate_and_normalize_date("not-a-date")
        assert result == "not-a-date"

    def test_invalid_type_raises(self) -> None:
        """Non-str/date/None input raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date"):
            validate_and_normalize_date(12345)  # type: ignore[arg-type]

    def test_date_object(self) -> None:
        """datetime.date object is preserved."""
        from datetime import date
        d = date(2024, 6, 15)
        assert validate_and_normalize_date(d) == d


# ============================================================================
# validate_and_normalize_volume
# ============================================================================

class TestValidateAndNormalizeVolume:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_volume(None) is None

    def test_invalid_type_raises(self) -> None:
        """Non-int/str/None input raises ValueError."""
        with pytest.raises(ValueError):
            validate_and_normalize_volume([42])  # type: ignore[arg-type]

    def test_non_numeric_string_passes_through(self) -> None:
        """Non-numeric strings (e.g. 'abc') pass through as-is."""
        result = validate_and_normalize_volume("abc")
        assert result == "abc"

    def test_valid_int(self) -> None:
        """Valid integer volume."""
        assert validate_and_normalize_volume(42) == 42

    def test_valid_string(self) -> None:
        """Valid volume string with Roman numeral."""
        result = validate_and_normalize_volume("IV")
        assert result == "IV"


# ============================================================================
# validate_and_normalize_boolean
# ============================================================================

class TestValidateAndNormalizeBoolean:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_boolean(None) is None

    def test_true_string(self) -> None:
        """String 'true' returns True."""
        assert validate_and_normalize_boolean("true") is True

    def test_false_string(self) -> None:
        """String 'false' returns False."""
        assert validate_and_normalize_boolean("false") is False

    def test_yes_string(self) -> None:
        """String 'yes' returns True."""
        assert validate_and_normalize_boolean("yes") is True

    def test_no_string(self) -> None:
        """String 'no' returns False."""
        assert validate_and_normalize_boolean("no") is False

    def test_one_int(self) -> None:
        """Integer 1 returns True."""
        assert validate_and_normalize_boolean(1) is True

    def test_zero_int(self) -> None:
        """Integer 0 returns False."""
        assert validate_and_normalize_boolean(0) is False

    def test_boolean_true(self) -> None:
        """Boolean True returns True."""
        assert validate_and_normalize_boolean(True) is True

    def test_boolean_false(self) -> None:
        """Boolean False returns False."""
        assert validate_and_normalize_boolean(False) is False

    def test_invalid_type(self) -> None:
        """Unsupported type raises ValueError."""
        with pytest.raises(ValueError, match="Cannot convert"):
            validate_and_normalize_boolean([True])  # type: ignore[arg-type]

    def test_invalid_string(self) -> None:
        """Unrecognized string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot convert"):
            validate_and_normalize_boolean("maybe")


# ============================================================================
# validate_positive_integer
# ============================================================================

class TestValidatePositiveInteger:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_positive_integer(None) is None

    def test_zero_is_valid(self) -> None:
        """Zero is valid (range is 0 to inf)."""
        assert validate_positive_integer(0) == 0

    def test_negative(self) -> None:
        """Negative raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            validate_positive_integer(-5)

    def test_float_string(self) -> None:
        """Float string raises ValueError."""
        with pytest.raises(ValueError, match="valid integer"):
            validate_positive_integer("12.5")

    def test_valid_int(self) -> None:
        """Valid positive int."""
        assert validate_positive_integer(42) == 42

    def test_valid_string(self) -> None:
        """Valid positive int string."""
        assert validate_positive_integer("42") == 42


# ============================================================================
# validate_latitude_longitude
# ============================================================================

class TestValidateLatitudeLongitude:
    def test_none_both(self) -> None:
        """Both None returns (None, None)."""
        lat, lon = validate_latitude_longitude(None, None)
        assert lat is None and lon is None

    def test_latitude_out_of_range(self) -> None:
        """Latitude outside -90..90 raises ValueError."""
        with pytest.raises(ValueError, match="Latitude must be"):
            validate_latitude_longitude(100, 0)

    def test_longitude_out_of_range(self) -> None:
        """Longitude outside -180..180 raises ValueError."""
        with pytest.raises(ValueError, match="Longitude must be"):
            validate_latitude_longitude(0, 200)

    def test_valid(self) -> None:
        """Valid lat/lon pass through."""
        lat, lon = validate_latitude_longitude(51.5, -0.12)
        assert lat == 51.5
        assert lon == -0.12


# ============================================================================
# normalize_country / validate_and_normalize_country
# ============================================================================

class TestNormalizeCountry:
    def test_none_input(self) -> None:
        """None returns None."""
        assert normalize_country(None) is None

    def test_empty_string(self) -> None:
        """Empty string returns None."""
        assert normalize_country("") is None

    def test_whitespace(self) -> None:
        """Whitespace-only returns None."""
        assert normalize_country("  ") is None


class TestValidateAndNormalizeCountry:
    def test_none_input(self) -> None:
        """None returns None."""
        assert validate_and_normalize_country(None) is None

    def test_unknown_country_passes_through(self) -> None:
        """Unknown country passes through (no raise for long enough non-digit strings)."""
        result = validate_and_normalize_country("Atlantis")
        assert result == "Atlantis"

    def test_too_short_raises(self) -> None:
        """Country name shorter than 2 chars raises ValueError."""
        with pytest.raises(ValueError, match="Invalid country"):
            validate_and_normalize_country("X")

    def test_all_digits_raises(self) -> None:
        """All-digit string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid country"):
            validate_and_normalize_country("12345")

    def test_known_country(self) -> None:
        """Known country passes."""
        result = validate_and_normalize_country("United States")
        assert result == "United States"
