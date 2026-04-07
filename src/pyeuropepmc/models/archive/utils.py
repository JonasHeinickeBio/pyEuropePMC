"""Utility functions for data model operations with XSD-compliant validation and normalization."""

from collections.abc import Callable
from datetime import date
import re
from typing import Any, cast
from urllib.parse import urlparse

# XSD-compatible type constants for documentation
XSD_STRING = str
XSD_INT = int
XSD_BOOLEAN = bool
XSD_DATE = date
XSD_ANY_URI = str  # URI strings that should be validated


# ===== ROBUST HELPER FUNCTIONS =====


def normalize_string(value: str | None, allow_empty: bool = True) -> str | None:
    """
    Normalize a string by trimming whitespace and handling empty values.

    Parameters
    ----------
    value : str or None
        The string to normalize
    allow_empty : bool
        If False, return None for empty strings after trimming

    Returns
    -------
    str or None
        Normalized string, or None if input was None or empty (when allow_empty=False)
    """
    if value is None:
        return None

    value = value.strip()
    if not allow_empty and not value:
        return None

    return value if value else None


def validate_regex(value: str, pattern: str, error_msg: str) -> str:
    """
    Validate a string against a regex pattern.

    Parameters
    ----------
    value : str
        The string to validate
    pattern : str
        Regex pattern to match against
    error_msg : str
        Error message if validation fails

    Returns
    -------
    str
        The validated string

    Raises
    ------
    ValueError
        If the string doesn't match the pattern
    """
    if not re.match(pattern, value):
        raise ValueError(f"{error_msg}: {value}")
    return value


def convert_to_type(
    value: Any, target_type: type, converter: Callable[[Any], Any], error_msg: str
) -> Any:
    """
    Convert a value to a target type using a converter function.

    Parameters
    ----------
    value : Any
        The value to convert
    target_type : type
        The expected target type
    converter : Callable
        Function to perform the conversion
    error_msg : str
        Error message if conversion fails

    Returns
    -------
    Any
        The converted value

    Raises
    ------
    ValueError
        If conversion fails or result is not of target type
    """
    try:
        converted = converter(value)
        if not isinstance(converted, target_type):
            raise ValueError(f"Conversion result is not of type {target_type.__name__}")
        return converted
    except (ValueError, TypeError) as e:
        raise ValueError(f"{error_msg}: {value}") from e


def validate_range(
    value: int | float, min_val: int | float, max_val: int | float, error_msg: str
) -> int | float:
    """
    Validate that a numeric value is within a specified range.

    Parameters
    ----------
    value : int or float
        The value to validate
    min_val : int or float
        Minimum allowed value (inclusive)
    max_val : int or float
        Maximum allowed value (inclusive)
    error_msg : str
        Error message if validation fails

    Returns
    -------
    int or float
        The validated value

    Raises
    ------
    ValueError
        If the value is outside the allowed range
    """
    if not (min_val <= value <= max_val):
        raise ValueError(f"{error_msg}: {value}")
    return value


def validate_format(value: str, validator_func: Callable[[str], bool], error_msg: str) -> str:
    """
    Validate a string using a custom validator function.

    Parameters
    ----------
    value : str
        The string to validate
    validator_func : Callable
        Function that returns True if valid, False otherwise
    error_msg : str
        Error message if validation fails

    Returns
    -------
    str
        The validated string

    Raises
    ------
    ValueError
        If validation fails
    """
    if not validator_func(value):
        raise ValueError(f"{error_msg}: {value}")
    return value


def normalize_and_validate(
    value: Any,
    normalizer: Callable[..., Any] | None = None,
    validator: Callable[..., Any] | None = None,
    converter: Callable[..., Any] | None = None,
    converter_target_type: type | None = None,
    converter_func: Callable[..., Any] | None = None,
    converter_error_msg: str = "Conversion failed",
    allow_none: bool = True,
) -> Any:
    """
    Generic function to normalize, convert, and validate a value.

    Parameters
    ----------
    value : Any
        The value to process
    normalizer : Callable or None
        Function to normalize the value
    validator : Callable or None
        Function to validate the value
    converter : Callable or None
        Function to convert the value
    converter_target_type : type or None
        Target type for conversion
    converter_func : Callable or None
        Converter function
    converter_error_msg : str
        Error message for conversion
    allow_none : bool
        Whether to allow None values

    Returns
    -------
    Any
        Processed value

    Raises
    ------
    ValueError
        If validation or conversion fails
    """
    if value is None:
        if not allow_none:
            raise ValueError("Value cannot be None")
        return None

    if normalizer:
        value = normalizer(value)

    if converter and converter_target_type and converter_func:
        value = converter(value, converter_target_type, converter_func, converter_error_msg)

    if validator:
        value = validator(value)

    return value


# ===== HIGH-LEVEL VALIDATION FUNCTIONS =====


def normalize_doi(doi: str | None) -> str | None:
    """
    Normalize a DOI by lowercasing and removing URL prefixes.

    Parameters
    ----------
    doi : str or None
        The DOI to normalize

    Returns
    -------
    str or None
        Normalized DOI, or None if input was None

    Examples
    --------
    >>> normalize_doi("10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi("https://doi.org/10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi("http://dx.doi.org/10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi(None)
    """

    def normalize_doi_value(value: str) -> str:
        # Lowercase first, then remove URL prefixes
        normalized = value.lower()
        normalized = normalized.replace("https://doi.org/", "")
        normalized = normalized.replace("http://dx.doi.org/", "")
        normalized = normalized.replace("http://doi.org/", "")
        return normalized

    return cast(
        str | None,
        normalize_and_validate(
            doi,
            normalizer=lambda x: normalize_string(x, allow_empty=False),
            validator=normalize_doi_value,
            allow_none=True,
        ),
    )


def validate_and_normalize_uri(uri: str | None) -> str | None:
    """
    Validate and normalize a URI string.

    Parameters
    ----------
    uri : str or None
        The URI to validate and normalize

    Returns
    -------
    str or None
        Normalized URI, or None if input was None

    Raises
    ------
    ValueError
        If URI is invalid
    """

    def validate_uri(value: str) -> str:
        try:
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid URI format: {value}")
            return value
        except Exception as e:
            raise ValueError(f"Invalid URI: {value}") from e

    return cast(
        str | None,
        normalize_and_validate(
            uri,
            normalizer=lambda x: normalize_string(x, allow_empty=False),
            validator=validate_uri,
            allow_none=True,
        ),
    )


def validate_and_normalize_email(email: str | None) -> str | None:
    """
    Validate and normalize an email address.

    Parameters
    ----------
    email : str or None
        The email to validate and normalize

    Returns
    -------
    str or None
        Normalized email, or None if input was None

    Raises
    ------
    ValueError
        If email format is invalid
    """
    return cast(
        str | None,
        normalize_and_validate(
            email,
            normalizer=lambda x: normalize_string(x, allow_empty=False),
            validator=lambda x: validate_regex(
                x.lower(),
                r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                "Invalid email format",
            ),
            allow_none=True,
        ),
    )


def validate_and_normalize_orcid(orcid: str | None) -> str | None:
    """
    Validate and normalize an ORCID identifier.

    Parameters
    ----------
    orcid : str or None
        The ORCID to validate and normalize

    Returns
    -------
    str or None
        Normalized ORCID, or None if input was None

    Raises
    ------
    ValueError
        If ORCID format is invalid
    """
    return cast(
        str | None,
        normalize_and_validate(
            orcid,
            normalizer=lambda x: normalize_string(x, allow_empty=False),
            validator=lambda x: validate_regex(
                x, r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", "Invalid ORCID format"
            ),
            allow_none=True,
        ),
    )


def validate_and_normalize_pmcid(pmcid: str | None) -> str | None:
    """
    Validate and normalize a PMCID identifier.

    Parameters
    ----------
    pmcid : str or None
        The PMCID to validate and normalize

    Returns
    -------
    str or None
        Normalized PMCID, or None if input was None

    Raises
    ------
    ValueError
        If PMCID format is invalid
    """

    def normalize_pmcid(value: str) -> str:
        value = value.upper()
        if not value.startswith("PMC"):
            value = f"PMC{value}"
        return value

    return cast(
        str | None,
        normalize_and_validate(
            pmcid,
            normalizer=lambda x: normalize_string(x, allow_empty=False),
            validator=lambda x: validate_format(
                normalize_pmcid(x),
                lambda y: y.startswith("PMC") and y[3:].isdigit(),
                "Invalid PMCID format",
            ),
            allow_none=True,
        ),
    )


def validate_and_normalize_pmid(pmid: str | None) -> str | None:
    """
    Validate and normalize a PMID identifier.

    Parameters
    ----------
    pmid : str or None
        The PMID to validate and normalize

    Returns
    -------
    str or None
        Normalized PMID, or None if input was None

    Raises
    ------
    ValueError
        If PMID format is invalid
    """
    return cast(
        str | None,
        normalize_and_validate(
            pmid,
            normalizer=lambda x: normalize_string(x, allow_empty=False),
            validator=lambda x: validate_format(
                x, lambda y: y.isdigit() and 6 <= len(y) <= 10, "Invalid PMID format"
            ),
            allow_none=True,
        ),
    )


def validate_and_normalize_year(year: int | str | None) -> int | None:
    """
    Validate and normalize a publication year.

    Parameters
    ----------
    year : int, str, or None
        The year to validate and normalize

    Returns
    -------
    int or None
        Normalized year as integer, or None if input was None

    Raises
    ------
    ValueError
        If year is invalid
    """
    if year is None:
        return None

    if isinstance(year, str):
        year = normalize_and_validate(
            year,
            normalizer=lambda x: normalize_string(x, allow_empty=False),
            converter=convert_to_type,
            converter_target_type=int,
            converter_func=int,
            converter_error_msg="Year must be a valid integer",
            allow_none=False,
        )

    if not isinstance(year, int):
        raise ValueError(f"Year must be an integer: {year}")

    return int(validate_range(year, 1000, 2100, "Year must be between 1000-2100"))


def validate_and_normalize_date(date_input: str | date | None) -> date | str | None:
    """
    Validate and normalize a date field.

    Parameters
    ----------
    date_input : str, date, or None
        The date to validate and normalize

    Returns
    -------
    date, str, or None
        Normalized date (date object if parseable, string otherwise), or None if input was None

    Raises
    ------
    ValueError
        If date is invalid
    """
    if date_input is None:
        return None

    if isinstance(date_input, date):
        return date_input

    if isinstance(date_input, str):
        date_str = normalize_string(date_input, allow_empty=False)
        if date_str is None:
            return None

        # Try to parse common date formats
        from dateutil import parser

        try:
            parsed_date = parser.parse(date_str, fuzzy=True)
            return date.fromisoformat(parsed_date.date().isoformat())  # Ensure proper date type
        except (ValueError, TypeError):
            # If parsing fails, return the cleaned string
            return date_str

    raise ValueError(f"Invalid date format: {date_input}")


def validate_and_normalize_volume(volume: int | str | None) -> int | str | None:
    """
    Validate and normalize a publication volume.

    Parameters
    ----------
    volume : int, str, or None
        The volume to validate and normalize

    Returns
    -------
    int, str, or None
        Normalized volume (int if numeric, str otherwise), or None if input was None

    Raises
    ------
    ValueError
        If volume is invalid
    """
    if volume is None:
        return None

    if isinstance(volume, str):
        volume_str = normalize_string(volume, allow_empty=False)
        if volume_str is None:
            return None
        # Try to convert to int if it's numeric
        try:
            return int(volume_str)
        except ValueError:
            # Keep as string for special cases like "Suppl 1"
            return volume_str

    if isinstance(volume, int):
        return int(validate_range(volume, 0, float("inf"), "Volume cannot be negative"))

    raise ValueError(f"Volume must be int or str: {volume}")


def validate_and_normalize_boolean(value: bool | str | int | None) -> bool | None:
    """
    Validate and normalize a boolean field.

    Parameters
    ----------
    value : bool, str, int, or None
        The value to validate and normalize

    Returns
    -------
    bool or None
        Normalized boolean, or None if input was None

    Raises
    ------
    ValueError
        If value cannot be converted to boolean
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return bool(value)

    if isinstance(value, str):
        value_str = normalize_string(value, allow_empty=False)
        if value_str is None:
            return False  # Empty string is falsy

        value_lower = value_str.lower()
        if value_lower in ("true", "1", "yes", "y", "on"):
            return True
        elif value_lower in ("false", "0", "no", "n", "off"):
            return False
        else:
            raise ValueError(f"Cannot convert string to boolean: {value_str}")

    raise ValueError(f"Cannot convert to boolean: {value}")


def normalize_string_field(value: str | None) -> str | None:
    """
    Normalize a string field by trimming whitespace.

    Parameters
    ----------
    value : str or None
        The string to normalize

    Returns
    -------
    str or None
        Normalized string, or None if input was None
    """
    return normalize_string(value, allow_empty=True)


def validate_positive_integer(value: int | str | None) -> int | None:
    """
    Validate and convert to positive integer.

    Parameters
    ----------
    value : int, str, or None
        The value to validate

    Returns
    -------
    int or None
        Positive integer, or None if input was None

    Raises
    ------
    ValueError
        If value is not a positive integer
    """
    if value is None:
        return None

    if isinstance(value, str):
        value = normalize_and_validate(
            value,
            normalizer=lambda x: normalize_string(x, allow_empty=False),
            converter=convert_to_type,
            converter_target_type=int,
            converter_func=int,
            converter_error_msg="Must be a valid integer",
            allow_none=False,
        )

    if not isinstance(value, int):
        raise ValueError(f"Must be an integer: {value}")

    return int(validate_range(value, 0, float("inf"), "Must be non-negative"))


def validate_latitude_longitude(
    lat: float | str | None, lon: float | str | None
) -> tuple[float | None, float | None]:
    """
    Validate latitude and longitude coordinates.

    Parameters
    ----------
    lat : float, str, or None
        Latitude value
    lon : float, str, or None
        Longitude value

    Returns
    -------
    tuple[float | None, float | None]
        Validated (latitude, longitude) pair

    Raises
    ------
    ValueError
        If coordinates are invalid
    """

    def to_float(value: float | str | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, str):
            value_str = normalize_string(value, allow_empty=False)
            if value_str is None:
                return None
            return float(convert_to_type(value_str, float, float, "Invalid coordinate format"))
        return float(value)

    lat_val = to_float(lat)
    lon_val = to_float(lon)

    if lat_val is not None:
        validate_range(lat_val, -90, 90, "Latitude must be between -90 and 90")
    if lon_val is not None:
        validate_range(lon_val, -180, 180, "Longitude must be between -180 and 180")

    return lat_val, lon_val


# ===== COUNTRY NORMALIZATION =====

# Country name mappings for standardization
COUNTRY_NAME_MAPPINGS = {
    # Common abbreviations and variations
    "USA": "United States",
    "US": "United States",
    "U.S.A.": "United States",
    "U.S.": "United States",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "GREAT BRITAIN": "United Kingdom",
    "ENGLAND": "United Kingdom",
    "UAE": "United Arab Emirates",
    "PRC": "China",
    "P.R. CHINA": "China",
    "P.R.C.": "China",
    "ROC": "Taiwan",
    "REPUBLIC OF CHINA": "Taiwan",
    "SOUTH KOREA": "Korea, Republic of",
    "NORTH KOREA": "Korea, Democratic People's Republic of",
    "RUSSIA": "Russian Federation",
    "IRAN": "Iran, Islamic Republic of",
    "VIETNAM": "Viet Nam",
    "VENEZUELA": "Venezuela, Bolivarian Republic of",
    "BOLIVIA": "Bolivia, Plurinational State of",
    "MOLDOVA": "Moldova, Republic of",
    "TANZANIA": "Tanzania, United Republic of",
    "SYRIA": "Syrian Arab Republic",
    "LAOS": "Lao People's Democratic Republic",
    "BRUNEI": "Brunei Darussalam",
    "IVORY COAST": "Côte d'Ivoire",
    "COTE D'IVOIRE": "Côte d'Ivoire",
    "CAPE VERDE": "Cabo Verde",
    "MICRONESIA": "Micronesia, Federated States of",
    "PALESTINE": "Palestine, State of",
    "VATICAN CITY": "Holy See",
    "VATICAN": "Holy See",
    "EAST TIMOR": "Timor-Leste",
    "SÃO TOMÉ AND PRÍNCIPE": "Sao Tome and Principe",
    "SÃO TOMÉ": "Sao Tome and Principe",
    "PRÍNCIPE": "Sao Tome and Principe",
}

# ISO country codes (alpha-2 to full name)
ISO_COUNTRY_CODES = {
    "AF": "Afghanistan",
    "AX": "Åland Islands",
    "AL": "Albania",
    "DZ": "Algeria",
    "AS": "American Samoa",
    "AD": "Andorra",
    "AO": "Angola",
    "AI": "Anguilla",
    "AQ": "Antarctica",
    "AG": "Antigua and Barbuda",
    "AR": "Argentina",
    "AM": "Armenia",
    "AW": "Aruba",
    "AU": "Australia",
    "AT": "Austria",
    "AZ": "Azerbaijan",
    "BS": "Bahamas",
    "BH": "Bahrain",
    "BD": "Bangladesh",
    "BB": "Barbados",
    "BY": "Belarus",
    "BE": "Belgium",
    "BZ": "Belize",
    "BJ": "Benin",
    "BM": "Bermuda",
    "BT": "Bhutan",
    "BO": "Bolivia, Plurinational State of",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "BA": "Bosnia and Herzegovina",
    "BW": "Botswana",
    "BV": "Bouvet Island",
    "BR": "Brazil",
    "IO": "British Indian Ocean Territory",
    "BN": "Brunei Darussalam",
    "BG": "Bulgaria",
    "BF": "Burkina Faso",
    "BI": "Burundi",
    "KH": "Cambodia",
    "CM": "Cameroon",
    "CA": "Canada",
    "CV": "Cabo Verde",
    "KY": "Cayman Islands",
    "CF": "Central African Republic",
    "TD": "Chad",
    "CL": "Chile",
    "CN": "China",
    "CX": "Christmas Island",
    "CC": "Cocos (Keeling) Islands",
    "CO": "Colombia",
    "KM": "Comoros",
    "CG": "Congo",
    "CD": "Congo, Democratic Republic of the",
    "CK": "Cook Islands",
    "CR": "Costa Rica",
    "CI": "Côte d'Ivoire",
    "HR": "Croatia",
    "CU": "Cuba",
    "CW": "Curaçao",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DK": "Denmark",
    "DJ": "Djibouti",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "EC": "Ecuador",
    "EG": "Egypt",
    "SV": "El Salvador",
    "GQ": "Equatorial Guinea",
    "ER": "Eritrea",
    "EE": "Estonia",
    "SZ": "Eswatini",
    "ET": "Ethiopia",
    "FK": "Falkland Islands (Malvinas)",
    "FO": "Faroe Islands",
    "FJ": "Fiji",
    "FI": "Finland",
    "FR": "France",
    "GF": "French Guiana",
    "PF": "French Polynesia",
    "TF": "French Southern Territories",
    "GA": "Gabon",
    "GM": "Gambia",
    "GE": "Georgia",
    "DE": "Germany",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GR": "Greece",
    "GL": "Greenland",
    "GD": "Grenada",
    "GP": "Guadeloupe",
    "GU": "Guam",
    "GT": "Guatemala",
    "GG": "Guernsey",
    "GN": "Guinea",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HT": "Haiti",
    "HM": "Heard Island and McDonald Islands",
    "VA": "Holy See",
    "HN": "Honduras",
    "HK": "Hong Kong",
    "HU": "Hungary",
    "IS": "Iceland",
    "IN": "India",
    "ID": "Indonesia",
    "IR": "Iran, Islamic Republic of",
    "IQ": "Iraq",
    "IE": "Ireland",
    "IM": "Isle of Man",
    "IL": "Israel",
    "IT": "Italy",
    "JM": "Jamaica",
    "JP": "Japan",
    "JE": "Jersey",
    "JO": "Jordan",
    "KZ": "Kazakhstan",
    "KE": "Kenya",
    "KI": "Kiribati",
    "KP": "Korea, Democratic People's Republic of",
    "KR": "Korea, Republic of",
    "KW": "Kuwait",
    "KG": "Kyrgyzstan",
    "LA": "Lao People's Democratic Republic",
    "LV": "Latvia",
    "LB": "Lebanon",
    "LS": "Lesotho",
    "LR": "Liberia",
    "LY": "Libya",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "MO": "Macao",
    "MK": "North Macedonia",
    "MG": "Madagascar",
    "MW": "Malawi",
    "MY": "Malaysia",
    "MV": "Maldives",
    "ML": "Mali",
    "MT": "Malta",
    "MH": "Marshall Islands",
    "MQ": "Martinique",
    "MR": "Mauritania",
    "MU": "Mauritius",
    "YT": "Mayotte",
    "MX": "Mexico",
    "FM": "Micronesia, Federated States of",
    "MD": "Moldova, Republic of",
    "MC": "Monaco",
    "MN": "Mongolia",
    "ME": "Montenegro",
    "MS": "Montserrat",
    "MA": "Morocco",
    "MZ": "Mozambique",
    "MM": "Myanmar",
    "NA": "Namibia",
    "NR": "Nauru",
    "NP": "Nepal",
    "NL": "Netherlands",
    "NC": "New Caledonia",
    "NZ": "New Zealand",
    "NI": "Nicaragua",
    "NE": "Niger",
    "NG": "Nigeria",
    "NU": "Niue",
    "NF": "Norfolk Island",
    "MP": "Northern Mariana Islands",
    "NO": "Norway",
    "OM": "Oman",
    "PK": "Pakistan",
    "PW": "Palau",
    "PS": "Palestine, State of",
    "PA": "Panama",
    "PG": "Papua New Guinea",
    "PY": "Paraguay",
    "PE": "Peru",
    "PH": "Philippines",
    "PN": "Pitcairn",
    "PL": "Poland",
    "PT": "Portugal",
    "PR": "Puerto Rico",
    "QA": "Qatar",
    "RE": "Réunion",
    "RO": "Romania",
    "RU": "Russian Federation",
    "RW": "Rwanda",
    "BL": "Saint Barthélemy",
    "SH": "Saint Helena, Ascension and Tristan da Cunha",
    "KN": "Saint Kitts and Nevis",
    "LC": "Saint Lucia",
    "MF": "Saint Martin (French part)",
    "PM": "Saint Pierre and Miquelon",
    "VC": "Saint Vincent and the Grenadines",
    "WS": "Samoa",
    "SM": "San Marino",
    "ST": "Sao Tome and Principe",
    "SA": "Saudi Arabia",
    "SN": "Senegal",
    "RS": "Serbia",
    "SC": "Seychelles",
    "SL": "Sierra Leone",
    "SG": "Singapore",
    "SX": "Sint Maarten (Dutch part)",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "SB": "Solomon Islands",
    "SO": "Somalia",
    "ZA": "South Africa",
    "GS": "South Georgia and the South Sandwich Islands",
    "SS": "South Sudan",
    "ES": "Spain",
    "LK": "Sri Lanka",
    "SD": "Sudan",
    "SR": "Suriname",
    "SJ": "Svalbard and Jan Mayen",
    "SE": "Sweden",
    "CH": "Switzerland",
    "SY": "Syrian Arab Republic",
    "TW": "Taiwan",
    "TJ": "Tajikistan",
    "TZ": "Tanzania, United Republic of",
    "TH": "Thailand",
    "TL": "Timor-Leste",
    "TG": "Togo",
    "TK": "Tokelau",
    "TO": "Tonga",
    "TT": "Trinidad and Tobago",
    "TN": "Tunisia",
    "TR": "Türkiye",
    "TM": "Turkmenistan",
    "TC": "Turks and Caicos Islands",
    "TV": "Tuvalu",
    "UG": "Uganda",
    "UA": "Ukraine",
    "AE": "United Arab Emirates",
    "GB": "United Kingdom",
    "US": "United States",
    "UM": "United States Minor Outlying Islands",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VU": "Vanuatu",
    "VE": "Venezuela, Bolivarian Republic of",
    "VN": "Viet Nam",
    "VG": "Virgin Islands, British",
    "VI": "Virgin Islands, U.S.",
    "WF": "Wallis and Futuna",
    "EH": "Western Sahara",
    "YE": "Yemen",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}


def normalize_country(country: str | None) -> str | None:
    """
    Normalize country names to standard forms.

    Handles common abbreviations, variations, and ISO codes.

    Parameters
    ----------
    country : str or None
        Country name, abbreviation, or ISO code to normalize

    Returns
    -------
    str or None
        Normalized country name, or None if input is None or empty

    Examples
    --------
    >>> normalize_country("USA")
    'United States'
    >>> normalize_country("UK")
    'United Kingdom'
    >>> normalize_country("US")
    'United States'
    >>> normalize_country("CN")
    'China'
    >>> normalize_country("Canada.")
    'Canada'
    """
    if country is None:
        return None

    country = normalize_string(country, allow_empty=False)
    if country is None:
        return None

    # Remove trailing punctuation that might remain
    country = re.sub(r"[.,;:!?]+$", "", country).strip()

    # Check mappings first (case-insensitive)
    country_upper = country.upper()
    if country_upper in COUNTRY_NAME_MAPPINGS:
        return COUNTRY_NAME_MAPPINGS[country_upper]

    # Check if it's an ISO code (2-3 letters, all caps)
    if (
        len(country) in (2, 3)
        and country.isalpha()
        and country.isupper()
        and country in ISO_COUNTRY_CODES
    ):
        return ISO_COUNTRY_CODES[country]

    # Return as-is if already a standard name or no mapping found
    return country


def validate_and_normalize_country(country: str | None) -> str | None:
    """
    Validate and normalize country information.

    Parameters
    ----------
    country : str or None
        Country name to validate and normalize

    Returns
    -------
    str or None
        Normalized country name, or None if invalid

    Raises
    ------
    ValueError
        If country format is invalid
    """
    if country is None:
        return None

    normalized = normalize_country(country)
    if normalized is None:
        return None

    # Basic validation - ensure it's not just numbers or too short
    if len(normalized) < 2 or normalized.isdigit():
        raise ValueError(f"Invalid country name: {country}")

    return normalized
