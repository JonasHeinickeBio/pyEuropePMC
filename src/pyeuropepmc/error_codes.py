"""
Error codes for the PyEuropePMC library.

This module contains all error codes used throughout the PyEuropePMC library,
providing a centralized location for error code definitions and their associated messages.
"""

from enum import Enum


class ErrorCodes(Enum):
    """Enumeration of all error codes used in PyEuropePMC."""

    # API Client Error Codes (NET/HTTP/AUTH)
    NET001 = "NET001"
    NET002 = "NET002"
    HTTP404 = "HTTP404"  # Resource not found (404)
    HTTP403 = "HTTP403"
    HTTP500 = "HTTP500"
    AUTH401 = "AUTH401"
    RATE429 = "RATE429"

    # Search Error Codes (SEARCH)
    SEARCH001 = "SEARCH001"
    SEARCH002 = "SEARCH002"
    SEARCH003 = "SEARCH003"
    SEARCH004 = "SEARCH004"
    SEARCH005 = "SEARCH005"
    SEARCH006 = "SEARCH006"
    SEARCH007 = "SEARCH007"

    # Full Text Error Codes (FULL)
    FULL001 = "FULL001"
    FULL002 = "FULL002"
    FULL003 = "FULL003"
    FULL004 = "FULL004"
    FULL005 = "FULL005"
    FULL006 = "FULL006"
    FULL007 = "FULL007"
    FULL008 = "FULL008"
    FULL009 = "FULL009"
    FULL010 = "FULL010"
    FULL011 = "FULL011"

    # Parsing Error Codes (PARSE)
    PARSE001 = "PARSE001"
    PARSE002 = "PARSE002"
    PARSE003 = "PARSE003"
    PARSE004 = "PARSE004"

    # Validation Error Codes (VALID)
    VALID001 = "VALID001"
    VALID002 = "VALID002"
    VALID003 = "VALID003"
    VALID004 = "VALID004"
    VALID005 = "VALID005"
    VALID006 = "VALID006"  # Save JSON file IO error
    VALID007 = "VALID007"  # JSON serialization error

    # Configuration Error Codes (CONFIG)
    CONFIG001 = "CONFIG001"
    CONFIG002 = "CONFIG002"
    CONFIG003 = "CONFIG003"

    # Generic Error Codes (for auto-generated errors)
    GENERIC001 = "GENERIC001"  # Generic PyEuropePMCError
    GENERIC002 = "GENERIC002"  # Generic APIClientError
    GENERIC003 = "GENERIC003"  # Generic SearchError
    GENERIC004 = "GENERIC004"  # Generic FullTextError
    GENERIC005 = "GENERIC005"  # Generic ParsingError
    GENERIC006 = "GENERIC006"  # Generic ValidationError
    GENERIC007 = "GENERIC007"  # Generic ConfigurationError


# Error messages mapping - centralized error messages
ERROR_MESSAGES: dict[str, str] = {
    # API Client Error Codes (NET/HTTP/AUTH)
    ErrorCodes.NET001.value: "Network connection failed. Check internet connectivity.",
    ErrorCodes.NET002.value: "Request timeout. Server may be overloaded.",
    ErrorCodes.HTTP404.value: (
        "Resource not found at endpoint. The requested resource does not exist or is unavailable."
    ),
    ErrorCodes.HTTP403.value: "Access forbidden. Check permissions.",
    ErrorCodes.HTTP500.value: "Server internal error. Try again later.",
    ErrorCodes.AUTH401.value: "Authentication failed. Check API credentials.",
    ErrorCodes.RATE429.value: "Rate limit exceeded. Wait before retrying.",
    # Search Error Codes (SEARCH)
    ErrorCodes.SEARCH001.value: "Invalid search query format.",
    ErrorCodes.SEARCH002.value: "Page size must be between 1 and 1000.",
    ErrorCodes.SEARCH003.value: "Query too complex or exceeds limits.",
    ErrorCodes.SEARCH004.value: (
        "Invalid format parameter. Use 'json', 'xml', 'dc', 'lite', or 'idlist'."
    ),
    ErrorCodes.SEARCH005.value: "Failed to parse search results.",
    ErrorCodes.SEARCH006.value: "Search endpoint not found.",
    ErrorCodes.SEARCH007.value: "No results found for query.",
    # Full Text Error Codes (FULL)
    ErrorCodes.FULL001.value: "PMC ID cannot be empty.",
    ErrorCodes.FULL002.value: "Invalid PMC ID format. Must be numeric.",
    ErrorCodes.FULL003.value: "Content not found for PMC ID {pmcid}.",
    ErrorCodes.FULL004.value: "Invalid format type. Use 'pdf', 'xml', or 'html'.",
    ErrorCodes.FULL005.value: "Download failed or content corrupted.",
    ErrorCodes.FULL006.value: "PDF validation failed. File too small or invalid.",
    ErrorCodes.FULL007.value: "Session closed. Cannot make requests.",
    ErrorCodes.FULL008.value: "Access denied for content.",
    ErrorCodes.FULL009.value: "File operation failed.",
    ErrorCodes.FULL010.value: "Unsupported format for batch download.",
    ErrorCodes.FULL011.value: "URL construction not supported for format '{format_type}'.",
    # Parsing Error Codes (PARSE)
    ErrorCodes.PARSE001.value: "JSON parsing failed. Invalid format.",
    ErrorCodes.PARSE002.value: "XML parsing failed. Invalid structure.",
    ErrorCodes.PARSE003.value: "Content cannot be None or empty.",
    ErrorCodes.PARSE004.value: "Unsupported data format for parsing.",
    # Validation Error Codes (VALID)
    ErrorCodes.VALID001.value: "Both arguments must be dictionaries. Field validation failed.",
    ErrorCodes.VALID002.value: "Parameter value out of range or invalid.",
    ErrorCodes.VALID003.value: "Required field missing.",
    ErrorCodes.VALID004.value: (
        "JSON file not found. Failed to read JSON file. File not found or inaccessible."
    ),
    ErrorCodes.VALID005.value: "Failed to parse JSON file. Invalid JSON format.",
    ErrorCodes.VALID006.value: "Failed to save JSON file. IO error occurred.",
    ErrorCodes.VALID007.value: "Failed to serialize data to JSON.",
    # Configuration Error Codes (CONFIG)
    ErrorCodes.CONFIG001.value: "Required configuration missing.",
    ErrorCodes.CONFIG002.value: "Invalid configuration value.",
    ErrorCodes.CONFIG003.value: "Dependency error or missing library.",
    # Generic Error Codes (for auto-generated errors)
    ErrorCodes.GENERIC001.value: "An error occurred in PyEuropePMC.",
    ErrorCodes.GENERIC002.value: "An API client error occurred.",
    ErrorCodes.GENERIC003.value: "A search error occurred.",
    ErrorCodes.GENERIC004.value: "A full text retrieval error occurred.",
    ErrorCodes.GENERIC005.value: "A parsing error occurred.",
    ErrorCodes.GENERIC006.value: "A validation error occurred.",
    ErrorCodes.GENERIC007.value: "A configuration error occurred.",
}


def get_error_message(error_code: ErrorCodes) -> str:
    """
    Get the error message for a given error code.

    Args:
        error_code: The error code enum value

    Returns:
        The corresponding error message
    """
    return ERROR_MESSAGES.get(error_code.value, "Unknown error.")


def get_error_message_by_string(error_code_str: str) -> str:
    """
    Get the error message for a given error code string.

    Args:
        error_code_str: The error code as a string

    Returns:
        The corresponding error message
    """
    return ERROR_MESSAGES.get(error_code_str, "Unknown error.")
