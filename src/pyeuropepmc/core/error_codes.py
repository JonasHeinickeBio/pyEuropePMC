"""
Error codes for the PyEuropePMC library.

This module contains all error codes used throughout the PyEuropePMC library,
providing a centralized location for error code definitions and their associated messages.
"""

from enum import Enum
from typing import Any, NoReturn

from .exceptions import PyEuropePMCError


class ErrorCodes(Enum):
    """Enumeration of all error codes used in PyEuropePMC.

    Error codes are grouped by category with the following prefixes:
    - NET: Network connection errors
    - HTTP: HTTP status code errors
    - AUTH: Authentication and authorization errors
    - RATE: Rate limiting errors
    - SEARCH: Search query and result errors
    - FULL: Full text retrieval errors
    - PARSE: Parsing and data format errors
    - VALID: Validation errors
    - CONFIG: Configuration errors
    - QUERY: Query builder errors
    - UNPAY: Unpaywall API errors
    - CLIENT: Client initialization errors
    - API: API-specific errors
    - FILE: File operation errors
    - MODEL: Model/Entity validation errors
    - GENERIC: Generic fallback errors
    """

    # Network Error Codes (NET)
    NET001 = "NET001"
    NET002 = "NET002"
    NET006 = "NET006"
    NET007 = "NET007"

    # HTTP Error Codes (HTTP)
    HTTP400 = "HTTP400"
    HTTP401 = "HTTP401"
    HTTP403 = "HTTP403"
    HTTP404 = "HTTP404"
    HTTP405 = "HTTP405"
    HTTP406 = "HTTP406"
    HTTP407 = "HTTP407"
    HTTP408 = "HTTP408"
    HTTP410 = "HTTP410"
    HTTP413 = "HTTP413"
    HTTP414 = "HTTP414"
    HTTP415 = "HTTP415"
    HTTP416 = "HTTP416"
    HTTP429 = "HTTP429"
    HTTP500 = "HTTP500"
    HTTP501 = "HTTP501"
    HTTP502 = "HTTP502"
    HTTP503 = "HTTP503"
    HTTP504 = "HTTP504"

    # Authentication Error Codes (AUTH)
    AUTH401 = "AUTH401"
    AUTH403 = "AUTH403"

    # Rate Limiting Error Codes (RATE)
    RATE429 = "RATE429"
    RETRY001 = "RETRY001"
    RETRY002 = "RETRY002"

    # Connection Error Codes (NET)
    NET003 = "NET003"
    NET004 = "NET004"
    NET005 = "NET005"

    # Search Error Codes (SEARCH)
    SEARCH001 = "SEARCH001"
    SEARCH002 = "SEARCH002"
    SEARCH003 = "SEARCH003"
    SEARCH004 = "SEARCH004"
    SEARCH005 = "SEARCH005"
    SEARCH006 = "SEARCH006"
    SEARCH007 = "SEARCH007"
    SEARCH008 = "SEARCH008"
    SEARCH009 = "SEARCH009"
    SEARCH010 = "SEARCH010"

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
    FULL012 = "FULL012"
    FULL013 = "FULL013"
    FULL014 = "FULL014"
    FULL015 = "FULL015"
    FULL016 = "FULL016"

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
    VALID006 = "VALID006"
    VALID007 = "VALID007"

    # Configuration Error Codes (CONFIG)
    CONFIG001 = "CONFIG001"
    CONFIG002 = "CONFIG002"
    CONFIG003 = "CONFIG003"

    # Query Builder Error Codes (QUERY)
    QUERY001 = "QUERY001"
    QUERY002 = "QUERY002"
    QUERY003 = "QUERY003"
    QUERY004 = "QUERY004"

    # Unpaywall Error Codes (UNPAY)
    UNPAY001 = "UNPAY001"
    UNPAY002 = "UNPAY002"

    # Generic Error Codes (GENERIC)
    GENERIC001 = "GENERIC001"
    GENERIC002 = "GENERIC002"
    GENERIC003 = "GENERIC003"
    GENERIC004 = "GENERIC004"
    GENERIC005 = "GENERIC005"
    GENERIC006 = "GENERIC006"
    GENERIC007 = "GENERIC007"

    # Client Error Codes (CLIENT)
    CLIENT001 = "CLIENT001"
    CLIENT002 = "CLIENT002"
    CLIENT003 = "CLIENT003"

    # API Error Codes (API)
    API001 = "API001"
    API002 = "API002"
    API003 = "API003"
    API004 = "API004"

    # File Error Codes (FILE)
    FILE001 = "FILE001"
    FILE002 = "FILE002"
    FILE003 = "FILE003"
    FILE004 = "FILE004"

    # Model Error Codes (MODEL)
    MODEL001 = "MODEL001"
    MODEL002 = "MODEL002"
    MODEL003 = "MODEL003"
    MODEL004 = "MODEL004"
    MODEL005 = "MODEL005"

    # Content Availability Error Codes (AVAIL)
    AVAIL001 = "AVAIL001"
    AVAIL002 = "AVAIL002"
    AVAIL003 = "AVAIL003"

    # License Error Codes (LICENSE)
    LICENSE001 = "LICENSE001"
    LICENSE002 = "LICENSE002"


# Error messages mapping - centralized error messages with actionable guidance
ERROR_MESSAGES: dict[str, str] = {
    # Network Error Codes (NET)
    ErrorCodes.NET001.value: "Network connection failed. Check your internet connection and try again. If the issue persists, check your firewall or proxy settings.",
    ErrorCodes.NET002.value: "Request timeout. The server took too long to respond. Try again or increase the timeout parameter for slower connections.",
    # HTTP Error Codes (HTTP)
    ErrorCodes.HTTP404.value: "Resource not found at endpoint. The requested resource does not exist or is unavailable. Verify the endpoint URL and resource identifier.",
    ErrorCodes.HTTP403.value: "Access forbidden. You don't have permission to access this resource. Check your API credentials and ensure you have the required access rights.",
    ErrorCodes.HTTP500.value: "Server internal error. The EuropePMC server encountered an issue. Please try again later. If the problem persists, contact the API support team.",
    # Authentication Error Codes (AUTH)
    ErrorCodes.AUTH401.value: "Authentication failed. Your API credentials are invalid or expired. Check your API key and ensure it is correctly configured. Generate a new key if necessary.",
    # Rate Limiting Error Codes (RATE)
    ErrorCodes.RATE429.value: "Rate limit exceeded. You have made too many requests in a short time. Wait before retrying, increase the rate_limit_delay parameter, or use an API key for higher limits.",
    # Search Error Codes (SEARCH)
    ErrorCodes.SEARCH001.value: "Invalid search query format. Check your query syntax and try again. Review the EuropePMC query documentation for supported operators and fields.",
    ErrorCodes.SEARCH002.value: "Page size must be between 1 and 1000. Please adjust your page_size parameter to a valid value within this range.",
    ErrorCodes.SEARCH003.value: "Query too complex or exceeds limits. Try simplifying your query or splitting it into multiple smaller queries.",
    ErrorCodes.SEARCH004.value: "Invalid format parameter. Use 'json', 'xml', 'dc', 'lite', or 'idlist' for format parameter. Check your format parameter value.",
    ErrorCodes.SEARCH005.value: "Failed to parse search results. The server returned unexpected data format. Please try again. If the issue persists, report the error with details.",
    ErrorCodes.SEARCH006.value: "Search endpoint not found. The EuropePMC search service may be temporarily unavailable. Please try again later.",
    ErrorCodes.SEARCH007.value: "No results found for your query. Try different search terms or broaden your query. Check your query syntax for accuracy.",
    # Full Text Error Codes (FULL)
    ErrorCodes.FULL001.value: "PMC ID cannot be empty. Please provide a valid PMC ID to retrieve full text. Format: 'PMC' followed by 7 digits (e.g., 'PMC1234567').",
    ErrorCodes.FULL002.value: "Invalid PMC ID format. PMC IDs must be numeric (e.g., 'PMC1234567'). Please check your PMC ID and ensure it follows the correct format.",
    ErrorCodes.FULL003.value: "Content not found for PMC ID {pmcid}. The requested content may not be available in EuropePMC. Verify the PMC ID is correct and the content exists.",
    ErrorCodes.FULL004.value: "Invalid format type. Use 'pdf', 'xml', or 'html' for full text retrieval. Check your format_type parameter.",
    ErrorCodes.FULL005.value: "Download failed or content corrupted. The downloaded file may be incomplete. Please try again. Check your network connection.",
    ErrorCodes.FULL006.value: "PDF validation failed. The downloaded file is too small or invalid. Please try again. If the issue persists, try a different format.",
    ErrorCodes.FULL007.value: "Session closed. Cannot make requests. The API client session has ended. Create a new client instance and try again.",
    ErrorCodes.FULL008.value: "Access denied for content. The full text may be behind a paywall or have access restrictions. Check the article's license and access status.",
    ErrorCodes.FULL009.value: "File operation failed. Unable to read or write the file. Check file permissions, disk space, and file path validity.",
    ErrorCodes.FULL010.value: "Unsupported format for batch download. Use supported formats: 'pdf', 'xml', or 'html'. Check your format parameter.",
    ErrorCodes.FULL011.value: "URL construction not supported for format '{format_type}'. This format cannot be retrieved via URL. Use a different format or download method.",
    ErrorCodes.FULL012.value: "Unpaywall API error: {message}. The Unpaywall service encountered an issue. Please try again later. Check your internet connection.",
    ErrorCodes.FULL013.value: "DOI not found in Unpaywall database. The DOI may be invalid or not registered in Unpaywall. Verify the DOI is correct and publicly available.",
    # Parsing Error Codes (PARSE)
    ErrorCodes.PARSE001.value: "JSON parsing failed. The data is not valid JSON format. Check the data source and ensure it contains valid JSON syntax.",
    ErrorCodes.PARSE002.value: "XML parsing failed. The data is not valid XML structure. Check the data source and ensure it contains valid XML syntax.",
    ErrorCodes.PARSE003.value: "Content cannot be None or empty. Please provide valid content to parse. Check your input data.",
    ErrorCodes.PARSE004.value: "Unsupported data format for parsing. The system cannot parse this data format. Check the data format and use a supported format.",
    # Validation Error Codes (VALID)
    ErrorCodes.VALID001.value: "Both arguments must be dictionaries. Field validation requires dictionary inputs. Check your input parameters and ensure they are dictionaries.",
    ErrorCodes.VALID002.value: "Parameter value out of range or invalid. Please check the allowed values for this parameter. Review the documentation for valid options.",
    ErrorCodes.VALID003.value: "Required field missing. This field is mandatory and must be provided. Add the required field to your request.",
    ErrorCodes.VALID004.value: "JSON file not found. The file does not exist or is inaccessible. Check file path and permissions, then try again.",
    ErrorCodes.VALID005.value: "Failed to parse JSON file. The file contains invalid JSON format. Please check the file content and correct any syntax errors.",
    ErrorCodes.VALID006.value: "Failed to save JSON file. An I/O error occurred while writing the file. Check file permissions and disk space.",
    ErrorCodes.VALID007.value: "Failed to serialize data to JSON. The data contains non-serializable objects. Check your data structure and convert non-serializable objects before saving.",
    # Configuration Error Codes (CONFIG)
    ErrorCodes.CONFIG001.value: "Required configuration missing. Please set the required configuration parameter. Check the documentation for required configuration options.",
    ErrorCodes.CONFIG002.value: "Invalid configuration value. The configuration value is not valid. Please check the documentation for valid values and correct your configuration.",
    ErrorCodes.CONFIG003.value: "Dependency error or missing library. Required library is not installed. Run 'pip install [required-library]' to install the missing dependency.",
    # Query Builder Error Codes (QUERY)
    ErrorCodes.QUERY001.value: "Invalid or empty query term or field. Please provide a valid query term and field. Check your query construction.",
    ErrorCodes.QUERY002.value: "Invalid parameter value or range. Please check the allowed values for this parameter. Review the documentation for valid options.",
    ErrorCodes.QUERY003.value: "Invalid logical operator placement. Check your query syntax and operator usage. Ensure operators are properly placed between query terms.",
    ErrorCodes.QUERY004.value: "Query validation failed: {error}. Please fix the query according to the error message. Review the query builder documentation for guidance.",
    # Unpaywall Error Codes (UNPAY)
    ErrorCodes.UNPAY001.value: "Unpaywall lookup failed. The Unpaywall service is temporarily unavailable. Please try again later. Check your internet connection.",
    ErrorCodes.UNPAY002.value: "Invalid DOI format. Please provide a valid DOI identifier. DOIs should be in format '10.xxx/xxxxx'.",
    # Generic Error Codes (GENERIC)
    ErrorCodes.GENERIC001.value: "An unexpected error occurred in PyEuropePMC. Please check your code and try again. If the issue persists, report the error with detailed information.",
    ErrorCodes.GENERIC002.value: "An API client error occurred. Please check your API configuration and try again. Verify your API endpoint and credentials.",
    ErrorCodes.GENERIC003.value: "A search error occurred. Please check your search query and parameters. Review the query documentation for guidance.",
    ErrorCodes.GENERIC004.value: "A full text retrieval error occurred. Please check your PMC ID and format parameters. Verify the content is available for download.",
    ErrorCodes.GENERIC005.value: "A parsing error occurred. Please check the data source and format. Ensure the data is valid JSON or XML.",
    ErrorCodes.GENERIC006.value: "A validation error occurred. Please check your input parameters. Ensure all required fields are provided and valid.",
    ErrorCodes.GENERIC007.value: "A configuration error occurred. Please check your configuration settings. Review the configuration documentation for required options.",
    # Client Error Codes (CLIENT)
    ErrorCodes.CLIENT001.value: "Client initialization failed. Required parameters are missing or invalid. Check your client configuration and ensure all required parameters are provided.",
    ErrorCodes.CLIENT002.value: "Client session expired or invalid. Create a new client instance and try again. Check your session management.",
    ErrorCodes.CLIENT003.value: "Client not properly configured. Required API keys or credentials are missing. Set the required configuration before using the client.",
    # Content Availability Error Codes (AVAIL)
    ErrorCodes.AVAIL001.value: "Content not available for this identifier. The content may have been removed or never existed. Verify the identifier is correct and try a different source.",
    ErrorCodes.AVAIL002.value: "Full text not available. The article does not have full text available in EuropePMC. Check the article's availability or try the publisher's website.",
    ErrorCodes.AVAIL003.value: "Access restricted. The content is behind a paywall or has access restrictions. Check if you have institutional access or use an open access alternative.",
    # License Error Codes (LICENSE)
    ErrorCodes.LICENSE001.value: "License not supported. The article's license does not allow the requested action. Check the article's license and ensure it permits your intended use.",
    ErrorCodes.LICENSE002.value: "License information unavailable. The license details could not be retrieved. Try again later or check the publisher's website for license information.",
    # HTTP Error Codes (HTTP) - Extended
    ErrorCodes.HTTP400.value: (
        "Bad request. The request was invalid or cannot be served.\n"
        "User: Check your request parameters, JSON/XML syntax, and ensure they match the API specification.\n"
        "Quick fix: Validate payload structure → Check required fields → Review API docs.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP400"
    ),
    ErrorCodes.HTTP401.value: (
        "Unauthorized. Your API credentials are missing or invalid.\n"
        "User: Provide a valid API key or check your authentication headers.\n"
        "Quick fix: Generate new API key → Update credentials → Check header format.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP401"
    ),
    ErrorCodes.HTTP403.value: (
        "Forbidden. You don't have permission to access this resource.\n"
        "User: Check your API credentials and access rights.\n"
        "Quick fix: Verify API key permissions → Check access level → Contact support.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP403"
    ),
    ErrorCodes.HTTP404.value: (
        "Resource not found. The requested resource does not exist or has been removed.\n"
        "User: Verify the resource identifier and try again.\n"
        "Quick fix: Check resource ID → Verify endpoint → Try alternative resource.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP404"
    ),
    ErrorCodes.HTTP405.value: (
        "Method not allowed. The HTTP method is not supported for this endpoint.\n"
        "User: Use the correct HTTP method for this operation.\n"
        "Quick fix: Check API docs for correct method → Change POST to GET or vice versa.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP405"
    ),
    ErrorCodes.HTTP406.value: (
        "Not acceptable. The server cannot produce a response matching the requested content type.\n"
        "User: Check your Accept header and supported formats.\n"
        "Quick fix: Use supported format (json/xml) → Check API docs for format support.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP406"
    ),
    ErrorCodes.HTTP407.value: (
        "Proxy authentication required. You need to authenticate with the proxy server.\n"
        "User: Provide proxy authentication credentials.\n"
        "Quick fix: Configure proxy credentials → Check proxy settings → Try again.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP407"
    ),
    ErrorCodes.HTTP408.value: (
        "Request timeout. The server timed out waiting for the request.\n"
        "User: Try again or increase the timeout parameter.\n"
        "Quick fix: Increase timeout → Check network speed → Try again later.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP408"
    ),
    ErrorCodes.HTTP410.value: (
        "Gone. The requested resource is no longer available and has been permanently removed.\n"
        "User: Check for updated documentation or alternative endpoints.\n"
        "Quick fix: Verify endpoint → Check for deprecation notices → Update to new endpoint.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP410"
    ),
    ErrorCodes.HTTP413.value: (
        "Payload too large. The request payload exceeds server limits.\n"
        "User: Reduce the size of your request payload.\n"
        "Quick fix: Split large request → Reduce page size → Batch smaller requests.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP413"
    ),
    ErrorCodes.HTTP414.value: (
        "URI too long. The request URL exceeds server limits.\n"
        "User: Shorten your request URL.\n"
        "Quick fix: Reduce query complexity → Use POST instead of GET → Batch requests.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP414"
    ),
    ErrorCodes.HTTP415.value: (
        "Unsupported media type. The server does not support the request content type.\n"
        "User: Check your Content-Type header and use a supported format.\n"
        "Quick fix: Use supported format (application/json) → Check API docs → Update header.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP415"
    ),
    ErrorCodes.HTTP416.value: (
        "Range not satisfiable. The requested range cannot be satisfied.\n"
        "User: Check your range request parameters.\n"
        "Quick fix: Verify range values → Check content length → Adjust range.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP416"
    ),
    ErrorCodes.HTTP429.value: (
        "Too many requests. You have exceeded the rate limit.\n"
        "User: Wait before retrying, increase rate_limit_delay, or use an API key.\n"
        "Quick fix: Wait for rate limit reset → Increase rate_limit_delay → Use API key.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP429"
    ),
    ErrorCodes.HTTP500.value: (
        "Internal server error. The server encountered an unexpected condition.\n"
        "User: Please try again later.\n"
        "Quick fix: Wait → Retry with backoff → Report if persistent.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP500"
    ),
    ErrorCodes.HTTP501.value: (
        "Not implemented. The server does not support the requested functionality.\n"
        "User: Check if the feature is available or use an alternative approach.\n"
        "Quick fix: Verify feature availability → Check API docs → Use alternative endpoint.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP501"
    ),
    ErrorCodes.HTTP502.value: (
        "Bad gateway. The server received an invalid response from an upstream server.\n"
        "User: Please try again later.\n"
        "Quick fix: Wait → Retry → Report if persistent.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP502"
    ),
    ErrorCodes.HTTP503.value: (
        "Service unavailable. The server is temporarily unable to handle the request.\n"
        "User: Please try again later.\n"
        "Quick fix: Wait → Retry with backoff → Check status page.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP503"
    ),
    ErrorCodes.HTTP504.value: (
        "Gateway timeout. The server did not receive a timely response from an upstream server.\n"
        "User: Please try again later.\n"
        "Quick fix: Wait → Retry → Check network stability.\n"
        "Docs: https://pyeuropepmc.rtfd.io/errors/HTTP504"
    ),
    # Authentication Error Codes (AUTH) - Extended
    ErrorCodes.AUTH401.value: "Authentication failed. Your API credentials are invalid or expired. Check your API key and ensure it is correctly configured.",
    ErrorCodes.AUTH403.value: "Permission denied. Your credentials do not have permission to access this resource. Check your API key permissions.",
    # Rate Limiting Error Codes (RATE) - Extended
    ErrorCodes.RATE429.value: "Rate limit exceeded. You have made too many requests in a short time. Wait before retrying, increase rate_limit_delay, or use an API key.",
    ErrorCodes.RETRY001.value: "Max retries exceeded. The request failed after multiple attempts. Check your network connection and try again later.",
    ErrorCodes.RETRY002.value: "Invalid Retry-After header. The server returned an invalid retry time. Please wait a few minutes and try again.",
    # Network Error Codes (NET) - Extended
    ErrorCodes.NET001.value: "Network connection failed. Check your internet connection and try again. If the issue persists, check your firewall or proxy settings.",
    ErrorCodes.NET002.value: "Request timeout. The server took too long to respond. Try again or increase the timeout parameter for slower connections.",
    ErrorCodes.NET003.value: "DNS resolution failed. Cannot resolve the server hostname. Check your DNS settings or try a different network.",
    ErrorCodes.NET004.value: "Connection refused. The server is not accepting connections. The service may be down or blocked by a firewall.",
    ErrorCodes.NET005.value: "SSL/TLS error. Secure connection could not be established. Check your SSL certificates or try without SSL verification.",
    ErrorCodes.NET006.value: "Connection pool exhausted. All connection slots are in use. Increase the pool size or wait for connections to free up.",
    ErrorCodes.NET007.value: "Network interrupt. Connection was interrupted during transfer. Check your network stability and try again.",
    # Search Error Codes (SEARCH) - Extended
    ErrorCodes.SEARCH001.value: "Invalid search query format. Check your query syntax and try again. Review the EuropePMC query documentation for supported operators and fields.",
    ErrorCodes.SEARCH002.value: "Page size must be between 1 and 1000. Please adjust your page_size parameter to a valid value within this range.",
    ErrorCodes.SEARCH003.value: "Query too complex or exceeds limits. Try simplifying your query or splitting it into multiple smaller queries.",
    ErrorCodes.SEARCH004.value: "Invalid format parameter. Use 'json', 'xml', 'dc', 'lite', or 'idlist' for format parameter. Check your format parameter value.",
    ErrorCodes.SEARCH005.value: "Failed to parse search results. The server returned unexpected data format. Please try again. If the issue persists, report the error with details.",
    ErrorCodes.SEARCH006.value: "Search endpoint not found. The EuropePMC search service may be temporarily unavailable. Please try again later.",
    ErrorCodes.SEARCH007.value: "No results found for your query. Try different search terms or broaden your query. Check your query syntax for accuracy.",
    ErrorCodes.SEARCH008.value: "Invalid search parameter. The search parameter is not valid. Check the allowed values for this parameter.",
    ErrorCodes.SEARCH009.value: "Search query too long. Your query exceeds the maximum length. Try simplifying your query.",
    ErrorCodes.SEARCH010.value: "Search rate limited. You have exceeded the search rate limit. Wait before retrying or use an API key.",
    # Full Text Error Codes (FULL) - Extended
    ErrorCodes.FULL001.value: "PMC ID cannot be empty. Please provide a valid PMC ID to retrieve full text. Format: 'PMC' followed by 7 digits (e.g., 'PMC1234567').",
    ErrorCodes.FULL002.value: "Invalid PMC ID format. PMC IDs must be numeric (e.g., 'PMC1234567'). Please check your PMC ID and ensure it follows the correct format.",
    ErrorCodes.FULL003.value: "Content not found for PMC ID {pmcid}. The requested content may not be available in EuropePMC. Verify the PMC ID is correct and the content exists.",
    ErrorCodes.FULL004.value: "Invalid format type. Use 'pdf', 'xml', or 'html' for full text retrieval. Check your format_type parameter.",
    ErrorCodes.FULL005.value: "Download failed or content corrupted. The downloaded file may be incomplete. Please try again. Check your network connection.",
    ErrorCodes.FULL006.value: "PDF validation failed. The downloaded file is too small or invalid. Please try again. If the issue persists, try a different format.",
    ErrorCodes.FULL007.value: "Session closed. Cannot make requests. The API client session has ended. Create a new client instance and try again.",
    ErrorCodes.FULL008.value: "Access denied for content. The full text may be behind a paywall or have access restrictions. Check the article's license and access status.",
    ErrorCodes.FULL009.value: "File operation failed. Unable to read or write the file. Check file permissions, disk space, and file path validity.",
    ErrorCodes.FULL010.value: "Unsupported format for batch download. Use supported formats: 'pdf', 'xml', or 'html'. Check your format parameter.",
    ErrorCodes.FULL011.value: "URL construction not supported for format '{format_type}'. This format cannot be retrieved via URL. Use a different format or download method.",
    ErrorCodes.FULL012.value: "Unpaywall API error: {message}. The Unpaywall service encountered an issue. Please try again later. Check your internet connection.",
    ErrorCodes.FULL013.value: "DOI not found in Unpaywall database. The DOI may be invalid or not registered in Unpaywall. Verify the DOI is correct and publicly available.",
    ErrorCodes.FULL014.value: "Content Embargoed. The content is under an embargo period and not yet available. Check the publication date and embargo status.",
    ErrorCodes.FULL015.value: "Page range invalid. The requested page range is not valid. Check the page numbers and try again.",
    ErrorCodes.FULL016.value: "Article version not available. The requested article version (e.g., 'VoR', 'PDF') is not available. Try a different version or contact the publisher.",
    # API Error Codes (API)
    ErrorCodes.API001.value: "API request failed. The request could not be completed. Check your request parameters and try again.",
    ErrorCodes.API002.value: "API response malformed. The server returned an unexpected response format. Please try again. If the issue persists, report the error.",
    ErrorCodes.API003.value: "API rate limit warning. You are approaching your rate limit. Slow down your requests or use an API key for higher limits.",
    ErrorCodes.API004.value: "API endpoint not available. The requested API endpoint is not accessible. Check the API documentation for correct endpoint URLs.",
    # File Error Codes (FILE)
    ErrorCodes.FILE001.value: "File not found. The specified file does not exist. Check the file path and ensure the file exists.",
    ErrorCodes.FILE002.value: "Permission denied. You do not have permission to access this file. Check file permissions and ownership.",
    ErrorCodes.FILE003.value: "File is empty or corrupted. The file contains no valid data. Check the file source and provide a valid file.",
    ErrorCodes.FILE004.value: "File operation interrupted. The file operation was interrupted before completion. Try again and ensure stable storage.",
    # Model Error Codes (MODEL)
    ErrorCodes.MODEL001.value: "Invalid model data. The provided data does not match the expected model structure. Check the data format and required fields.",
    ErrorCodes.MODEL002.value: "Model validation failed. One or more fields failed validation. Check the error details for specific field issues.",
    ErrorCodes.MODEL003.value: "Model conversion error. Failed to convert data to model format. Check the source data and conversion parameters.",
    ErrorCodes.MODEL004.value: "Model attribute missing. Required attribute not found in model. Add the required attribute to your data.",
    ErrorCodes.MODEL005.value: "Model type mismatch. Expected a different data type. Check the field type and provide the correct type.",
}


def get_error_message(error_code: ErrorCodes | str, include_help_link: bool = False) -> str:
    """
    Get the error message for a given error code.

    Args:
        error_code: The error code enum value or string identifier
        include_help_link: Whether to include documentation link in the message

    Returns:
        The corresponding error message with actionable guidance
    """
    code_str = error_code.value if isinstance(error_code, ErrorCodes) else error_code
    message = ERROR_MESSAGES.get(code_str, "Unknown error. Please check your input and try again.")

    if include_help_link and "docs" not in message.lower():
        message += f"\nDocs: https://pyeuropepmc.rtfd.io/errors/{code_str}"

    return message


def get_error_message_by_string(error_code_str: str) -> str:
    """
    Get the error message for a given error code string.

    Args:
        error_code_str: The error code as a string (e.g., 'NET001')

    Returns:
        The corresponding error message with actionable guidance
    """
    return ERROR_MESSAGES.get(
        error_code_str, "Unknown error. Please check your input and try again."
    )


def format_error_message(
    error_code: ErrorCodes | str,
    context: dict[str, Any] | None = None,
    include_help_link: bool = True,
) -> str:
    """
    Get and format an error message with context variables.

    Args:
        error_code: The error code enum value or string identifier
        context: Dictionary with values to substitute in the error message
        include_help_link: Whether to include documentation link

    Returns:
        The formatted error message with context applied

    Note:
        If context variables don't match the message format, returns the base message
        without the missing variables. This prevents errors from mismatched context.
    """
    message = get_error_message(error_code, include_help_link=include_help_link)
    context = context or {}
    try:
        return message.format(**context)
    except KeyError as e:
        # Return message with a placeholder for missing context
        missing_key = str(e).strip("'")
        return f"{message}\n(Details: missing '{missing_key}' for detailed information)"
    except (ValueError, AttributeError):
        # If context doesn't match, return the base message
        return message


def is_retryable(error_code: ErrorCodes | str) -> bool:
    """
    Check if an error is retryable (network, rate limits, server errors).

    Args:
        error_code: The error code enum value or string identifier

    Returns:
        True if the error is retryable, False otherwise

    Example:
        >>> is_retryable(ErrorCodes.NET001)
        True
        >>> is_retryable(ErrorCodes.VALID001)
        False
    """
    code_str = error_code.value if isinstance(error_code, ErrorCodes) else error_code

    # Retryable error patterns
    retryable_patterns = [
        "NET",  # Network errors
        "RATE",  # Rate limiting
        "HTTP5",  # Server errors (5xx)
        "RETRY",  # Retry-related
        "HTTP408",  # Request timeout
        "HTTP503",  # Service unavailable
        "HTTP429",  # Too many requests (retryable with backoff)
    ]

    return any(pattern in code_str for pattern in retryable_patterns)


def get_error_severity_level(error_code: ErrorCodes | str) -> int:
    """
    Get numeric severity level for programmatic comparison.

    Args:
        error_code: The error code enum value or string identifier

    Returns:
        Numeric severity: 1 (critical), 2 (warning), 3 (info)

    Example:
        >>> get_error_severity_level(ErrorCodes.AUTH401)
        1
        >>> get_error_severity_level(ErrorCodes.VALID001)
        3
    """
    severity_map: dict[str, int] = {
        "critical": 1,
        "warning": 2,
        "info": 3,
    }

    return severity_map.get(get_error_severity(error_code), 3)


def get_error_suggestion(error_code: ErrorCodes | str, include_code_snippet: bool = False) -> str:
    """
    Get a code snippet or specific action steps for resolving the error.

    Args:
        error_code: The error code enum value or string identifier
        include_code_snippet: Whether to include code examples in the suggestion

    Returns:
        A code snippet or specific action steps for resolving the error

    Example:
        >>> get_error_suggestion(ErrorCodes.NET001)
        'Check your internet connection and try again. If the issue persists, check your firewall or proxy settings.'
    """
    message = get_error_message(error_code)

    if include_code_snippet:
        # Add code examples for common scenarios
        code_snippets: dict[str, str] = {
            "HTTP429": (
                "\n\nCode example (exponential backoff):\n"
                "```python\n"
                "import time\n"
                "from tenacity import retry, stop_after_attempt, wait_exponential\n"
                "\n"
                "@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))\n"
                "def make_request():\n"
                "    try:\n"
                "        return client.search(query='OpenAID')\n"
                "    except RateLimitError as e:\n"
                "        retry_after = e.retry_after or 60\n"
                "        print(f'Rate limited, waiting {retry_after} seconds')\n"
                "        time.sleep(retry_after)\n"
                "        raise\n"
                "```\n"
                "Or use: `client.search(query='OpenAID', rate_limit_delay=2)`"
            ),
            "AUTH401": (
                "\n\nCode example (API key):\n"
                "```python\n"
                "from pyeuropepmc import EuropePMCClient\n"
                "\n"
                "# With API key (recommended for rate limits)\n"
                "client = EuropePMCClient(api_key='your_api_key_here')\n"
                "\n"
                "# Or set environment variable\n"
                "# export EUROPE_PMC_API_KEY='your_api_key_here'\n"
                "```\n"
                "Get API key: https://europepmc.org/api"
            ),
            "VALID002": (
                "\n\nCode example (valid parameters):\n"
                "```python\n"
                "# Valid page_size range: 1-1000\n"
                "results = client.search(query='OpenAID', page_size=25)  # OK\n"
                "results = client.search(query='OpenAID', page_size=500)  # OK\n"
                "# results = client.search(query='OpenAID', page_size=1500)  # ERROR\n"
                "```\n"
                "Check allowed values in documentation."
            ),
        }

        code_snippet = code_snippets.get(
            error_code.value if isinstance(error_code, ErrorCodes) else error_code, ""
        )
        if code_snippet:
            return message + code_snippet

    return message


def get_error_recovery_options(error_code: ErrorCodes | str) -> list[str]:
    """
    Get a list of recovery strategies for the error.

    Args:
        error_code: The error code enum value or string identifier

    Returns:
        A list of recovery strategy options

    Example:
        >>> get_error_recovery_options(ErrorCodes.NET001)
        ['Check internet connection', 'Verify firewall/proxy settings', 'Try using API key']
    """
    code_str = error_code.value if isinstance(error_code, ErrorCodes) else error_code

    recovery_options: dict[str, list[str]] = {
        # Network errors
        "NET001": [
            "Check internet connection",
            "Verify firewall/proxy settings",
            "Try using API key",
            "Test with different network",
        ],
        "NET002": [
            "Increase timeout",
            "Check network speed",
            "Try again later",
            "Use lighter queries",
        ],
        "NET003": [
            "Check DNS settings",
            "Try different network",
            "Use IP address directly",
            "Flush DNS cache",
        ],
        "NET004": [
            "Check server status",
            "Verify port is open",
            "Try again later",
            "Use VPN if blocked",
        ],
        "NET005": [
            "Check SSL certificates",
            "Update certificates",
            "Try without SSL verification",
            "Use system certificates",
        ],
        "NET006": [
            "Increase connection pool size",
            "Wait for connections to free",
            "Use connection pooling",
            "Reduce concurrent requests",
        ],
        "NET007": [
            "Check network stability",
            "Use wired connection",
            "Retry with exponential backoff",
            "Reduce payload size",
        ],
        # HTTP errors
        "HTTP400": [
            "Check request parameters",
            "Verify JSON/XML syntax",
            "Review API documentation",
            "Validate payload structure",
        ],
        "HTTP401": [
            "Check API key",
            "Verify authentication headers",
            "Generate new API key",
            "Check token expiration",
        ],
        "HTTP403": [
            "Check API key permissions",
            "Verify access rights",
            "Contact API support",
            "Review authentication scope",
        ],
        "HTTP404": [
            "Verify resource ID",
            "Check endpoint URL",
            "Review API documentation",
            "Check for deprecation",
        ],
        "HTTP405": [
            "Check API docs for correct method",
            "Change POST to GET or vice versa",
            "Verify endpoint supports method",
            "Use alternative endpoint",
        ],
        "HTTP406": [
            "Check Accept header",
            "Use supported format (json/xml)",
            "Review API docs for format support",
            "Update content negotiation",
        ],
        "HTTP407": [
            "Configure proxy credentials",
            "Check proxy settings",
            "Update authentication headers",
            "Contact network admin",
        ],
        "HTTP408": [
            "Increase timeout",
            "Check network speed",
            "Try again later",
            "Use lighter queries",
        ],
        "HTTP410": [
            "Verify endpoint validity",
            "Check for deprecation notices",
            "Update to new endpoint",
            "Review API changelog",
        ],
        "HTTP413": [
            "Split large request",
            "Reduce page size",
            "Batch smaller requests",
            "Compress payload",
        ],
        "HTTP414": [
            "Shorten query URL",
            "Use POST instead of GET",
            "Reduce query complexity",
            "Batch requests",
        ],
        "HTTP415": [
            "Check Content-Type header",
            "Use supported format",
            "Update request headers",
            "Verify payload format",
        ],
        "HTTP416": [
            "Verify range values",
            "Check content length",
            "Adjust range parameters",
            "Request full content",
        ],
        "HTTP429": [
            "Wait before retrying",
            "Use API key",
            "Implement exponential backoff",
            "Reduce request rate",
        ],
        "HTTP500": [
            "Try again later",
            "Check server status",
            "Contact API support",
            "Implement retry with backoff",
        ],
        "HTTP501": [
            "Verify feature availability",
            "Check API docs",
            "Use alternative endpoint",
            "Contact support",
        ],
        "HTTP502": [
            "Try again later",
            "Check server status",
            "Contact API support",
            "Implement retry with backoff",
        ],
        "HTTP503": [
            "Try again later",
            "Check server status",
            "Use API key for priority",
            "Monitor status page",
        ],
        "HTTP504": [
            "Try again later",
            "Check network stability",
            "Increase timeout",
            "Implement retry with backoff",
        ],
        # Rate limiting
        "RATE429": [
            "Wait before retrying",
            "Use API key",
            "Implement exponential backoff",
            "Reduce request rate",
        ],
        "RETRY001": [
            "Check network connection",
            "Verify server status",
            "Try again with longer backoff",
            "Contact support",
        ],
        "RETRY002": [
            "Wait a few minutes",
            "Check Retry-After header",
            "Implement backoff logic",
            "Use API key",
        ],
        # Content availability
        "AVAIL001": [
            "Verify identifier",
            "Try different source",
            "Check for updated documentation",
            "Contact publisher",
        ],
        "AVAIL002": [
            "Check publisher website",
            "Try alternative source",
            "Contact author",
            "Search in other databases",
        ],
        "AVAIL003": [
            "Check institutional access",
            "Use open access alternatives",
            "Contact library",
            "Request via interlibrary loan",
        ],
        # Authentication
        "AUTH401": [
            "Verify API key format",
            "Check key expiration",
            "Generate new API key",
            "Review authentication docs",
        ],
        "AUTH403": [
            "Check API key permissions",
            "Verify scope of access",
            "Contact API support",
            "Review access requirements",
        ],
        # Search errors
        "SEARCH001": [
            "Check query syntax",
            "Review EuropePMC query docs",
            "Try simpler query",
            "Use query builder tool",
        ],
        "SEARCH002": [
            "Adjust page_size parameter",
            "Use values 1-1000",
            "Implement pagination",
            "Reduce page size",
        ],
        "SEARCH003": [
            "Simplify query",
            "Split into multiple queries",
            "Reduce number of terms",
            "Remove complex operators",
        ],
        "SEARCH004": [
            "Use valid format parameter",
            "Check supported formats",
            "Validate format value",
            "Review API docs",
        ],
        "SEARCH005": [
            "Try again",
            "Check server status",
            "Report error with details",
            "Use different format",
        ],
        "SEARCH006": [
            "Try again later",
            "Check service status",
            "Use alternative endpoint",
            "Contact support",
        ],
        "SEARCH007": [
            "Broaden search terms",
            "Try different keywords",
            "Remove filters",
            "Use wildcard operators",
        ],
        "SEARCH008": [
            "Check allowed parameter values",
            "Review API docs",
            "Validate parameter format",
            "Use valid options",
        ],
        "SEARCH009": [
            "Simplify query",
            "Reduce query length",
            "Use fewer terms",
            "Remove optional parameters",
        ],
        "SEARCH010": [
            "Wait before retrying",
            "Use API key",
            "Implement rate limiting",
            "Reduce query frequency",
        ],
        # Full text errors
        "FULL001": [
            "Provide valid PMC ID",
            "Check PMC ID format",
            "Use valid identifier",
            "Verify PMC ID structure",
        ],
        "FULL002": [
            "Check PMC ID format",
            "Ensure 7-digit numeric ID",
            "Use valid PMC ID",
            "Verify ID structure",
        ],
        "FULL003": [
            "Verify PMC ID",
            "Check content availability",
            "Try alternative source",
            "Contact publisher",
        ],
        "FULL004": [
            "Use valid format type",
            "Check supported formats",
            "Validate format value",
            "Review API docs",
        ],
        "FULL005": [
            "Try again",
            "Check network connection",
            "Verify file download",
            "Use different format",
        ],
        "FULL006": [
            "Try again",
            "Verify file download",
            "Check file integrity",
            "Use XML format as alternative",
        ],
        "FULL007": [
            "Create new client instance",
            "Check session state",
            "Reinitialize client",
            "Review session management",
        ],
        "FULL008": [
            "Check article license",
            "Verify access rights",
            "Use open access alternative",
            "Request via institution",
        ],
        "FULL009": [
            "Check file permissions",
            "Verify disk space",
            "Validate file path",
            "Try different location",
        ],
        "FULL010": [
            "Use supported format",
            "Check format options",
            "Validate format parameter",
            "Review API docs",
        ],
        "FULL011": [
            "Use different format",
            "Check format support",
            "Try alternative download method",
            "Contact support",
        ],
        "FULL012": [
            "Try again later",
            "Check Unpaywall status",
            "Verify DOI",
            "Use alternative source",
        ],
        "FULL013": [
            "Verify DOI",
            "Check DOI registration",
            "Try alternative source",
            "Contact publisher",
        ],
        "FULL014": [
            "Wait for embargo end",
            "Check publication date",
            "Verify embargo status",
            "Contact publisher",
        ],
        "FULL015": [
            "Check page numbers",
            "Verify page range",
            "Request full content",
            "Use different parameters",
        ],
        "FULL016": [
            "Try different version",
            "Check version availability",
            "Contact publisher",
            "Request via alternative channel",
        ],
        # Parsing errors
        "PARSE001": [
            "Check JSON syntax",
            "Validate JSON structure",
            "Use JSON validator",
            "Fix syntax errors",
        ],
        "PARSE002": [
            "Check XML syntax",
            "Validate XML structure",
            "Use XML validator",
            "Fix syntax errors",
        ],
        "PARSE003": [
            "Provide valid content",
            "Check data source",
            "Verify content not empty",
            "Use valid input",
        ],
        "PARSE004": [
            "Use supported format",
            "Check format options",
            "Convert to supported format",
            "Review API docs",
        ],
        # Validation errors
        "VALID001": [
            "Check input types",
            "Ensure dictionaries provided",
            "Validate parameter types",
            "Use correct format",
        ],
        "VALID002": [
            "Check allowed values",
            "Review documentation",
            "Use valid parameter values",
            "Validate input range",
        ],
        "VALID003": [
            "Add required field",
            "Check required parameters",
            "Review API docs",
            "Include mandatory fields",
        ],
        "VALID004": [
            "Check file path",
            "Verify file exists",
            "Check permissions",
            "Use valid file location",
        ],
        "VALID005": [
            "Fix JSON syntax",
            "Validate JSON structure",
            "Use JSON validator",
            "Check file content",
        ],
        "VALID006": [
            "Check permissions",
            "Verify disk space",
            "Validate file path",
            "Try different location",
        ],
        "VALID007": [
            "Convert non-serializable objects",
            "Check data types",
            "Use jsonpickle for complex objects",
            "Serialize first",
        ],
        # Configuration errors
        "CONFIG001": [
            "Set required parameter",
            "Check configuration docs",
            "Review required options",
            "Add missing config",
        ],
        "CONFIG002": [
            "Check valid values",
            "Review documentation",
            "Use valid configuration",
            "Validate config values",
        ],
        "CONFIG003": [
            "Install missing library",
            "Run pip install",
            "Check dependency docs",
            "Install required packages",
        ],
        # Query builder errors
        "QUERY001": [
            "Provide valid query",
            "Check query format",
            "Use valid field names",
            "Review query docs",
        ],
        "QUERY002": [
            "Check allowed values",
            "Review documentation",
            "Use valid parameters",
            "Validate query structure",
        ],
        "QUERY003": [
            "Fix operator placement",
            "Check query syntax",
            "Review operator usage",
            "Use correct syntax",
        ],
        "QUERY004": [
            "Fix query according to error",
            "Review query builder docs",
            "Simplify query",
            "Check syntax rules",
        ],
        # Unpaywall errors
        "UNPAY001": [
            "Try again later",
            "Check Unpaywall status",
            "Verify internet connection",
            "Use alternative source",
        ],
        "UNPAY002": [
            "Use valid DOI format",
            "Check DOI structure",
            "Verify DOI registration",
            "Use standard DOI format",
        ],
        # Client errors
        "CLIENT001": [
            "Check required parameters",
            "Verify configuration",
            "Review initialization docs",
            "Add missing params",
        ],
        "CLIENT002": [
            "Create new client",
            "Check session state",
            "Reinitialize client",
            "Review session management",
        ],
        "CLIENT003": [
            "Set required credentials",
            "Check API key",
            "Configure authentication",
            "Review setup docs",
        ],
        # API errors
        "API001": [
            "Check request parameters",
            "Verify endpoint",
            "Review API docs",
            "Validate request structure",
        ],
        "API002": [
            "Check response format",
            "Try again",
            "Report error with details",
            "Use different endpoint",
        ],
        "API003": [
            "Slow down requests",
            "Use API key",
            "Implement rate limiting",
            "Reduce query frequency",
        ],
        "API004": [
            "Check endpoint URL",
            "Verify endpoint availability",
            "Review API docs",
            "Use correct endpoint",
        ],
        # File errors
        "FILE001": [
            "Check file path",
            "Verify file exists",
            "Use valid location",
            "Create file if needed",
        ],
        "FILE002": [
            "Check file permissions",
            "Run with correct user",
            "Modify permissions",
            "Check file ownership",
        ],
        "FILE003": [
            "Use valid file",
            "Check file source",
            "Verify file integrity",
            "Download fresh copy",
        ],
        "FILE004": [
            "Try again",
            "Check storage stability",
            "Verify file lock",
            "Use atomic operations",
        ],
        # Model errors
        "MODEL001": [
            "Check data structure",
            "Validate model format",
            "Review model docs",
            "Use correct structure",
        ],
        "MODEL002": [
            "Fix validation errors",
            "Check field requirements",
            "Validate data types",
            "Review error details",
        ],
        "MODEL003": [
            "Check source data",
            "Verify conversion parameters",
            "Use compatible data",
            "Review conversion docs",
        ],
        "MODEL004": [
            "Add required attribute",
            "Check model schema",
            "Include mandatory fields",
            "Review model docs",
        ],
        "MODEL005": [
            "Check field type",
            "Use correct data type",
            "Convert to expected type",
            "Validate data types",
        ],
    }

    return recovery_options.get(
        code_str, ["Wait and retry", "Check documentation", "Contact support"]
    )


def create_error_from_response(
    status_code: int, endpoint: str | None = None, response_body: str | None = None, **kwargs: Any
) -> "APIClientError":
    """
    Create an appropriate exception based on HTTP status code.

    Args:
        status_code: The HTTP status code from the response
        endpoint: The API endpoint that failed (optional)
        response_body: The response body (optional, truncated to 1000 chars)
        **kwargs: Additional context to pass to the exception

    Returns:
        An APIClientError (or subclass) with the appropriate error code

    Example:
        >>> create_error_from_response(404, "/api/search")
        APIClientError(error_code=HTTP404, ...)
    """
    # Map status codes to error codes
    error_map: dict[int, ErrorCodes] = {
        400: ErrorCodes.HTTP400,
        401: ErrorCodes.AUTH401,
        403: ErrorCodes.HTTP403,
        404: ErrorCodes.HTTP404,
        405: ErrorCodes.HTTP405,
        408: ErrorCodes.HTTP408,
        410: ErrorCodes.HTTP410,
        429: ErrorCodes.RATE429,
        500: ErrorCodes.HTTP500,
        502: ErrorCodes.HTTP502,
        503: ErrorCodes.HTTP503,
        504: ErrorCodes.HTTP504,
    }

    error_code = error_map.get(status_code, ErrorCodes.API001)

    context = {"endpoint": endpoint, "status_code": status_code}
    if response_body:
        context["response_body"] = (
            response_body[:1000] + "..." if len(response_body) > 1000 else response_body
        )

    context.update(kwargs)

    return APIClientError(
        error_code=error_code,
        context=context,
        endpoint=endpoint,
        status_code=status_code,
    )


def get_error_classification(error_code: ErrorCodes | str) -> dict[str, Any]:
    """
    Get structured classification for an error code.

    Args:
        error_code: The error code enum value or string identifier

    Returns:
        A dictionary with error classification: category, severity, retryable, recovery_options

    Example:
        >>> get_error_classification(ErrorCodes.NET001)
        {'category': 'Network', 'severity': 'critical', 'retryable': True, ...}
    """

    code_str = error_code.value if isinstance(error_code, ErrorCodes) else error_code
    return {
        "error_code": code_str,
        "category": get_error_code_category(error_code),
        "severity": get_error_severity(error_code),
        "retryable": is_retryable(error_code),
        "suggestion": get_error_suggestion(error_code),
        "recovery_options": get_error_recovery_options(error_code),
    }


def get_error_code_category(error_code: ErrorCodes | str) -> str:
    """
    Get the category name for an error code.

    Args:
        error_code: The error code enum value or string identifier

    Returns:
        The category name (e.g., 'Network', 'HTTP', 'Authentication')
    """
    code_str = error_code.value if isinstance(error_code, ErrorCodes) else error_code
    category_map: dict[str, str] = {
        "NET": "Network",
        "HTTP": "HTTP",
        "AUTH": "Authentication",
        "RATE": "Rate Limiting",
        "SEARCH": "Search",
        "FULL": "Full Text",
        "PARSE": "Parsing",
        "VALID": "Validation",
        "CONFIG": "Configuration",
        "QUERY": "Query Builder",
        "UNPAY": "Unpaywall",
        "CLIENT": "Client",
        "API": "API",
        "FILE": "File Operations",
        "MODEL": "Model/Entity",
        "AVAIL": "Content Availability",
        "LICENSE": "License",
    }

    # Get prefix (first 3-4 characters)
    prefix = code_str[:3] if code_str.startswith("HTTP") else code_str[:2]
    return category_map.get(prefix, "General")


def get_error_code_prefix(error_code: ErrorCodes | str) -> str:
    """
    Get the category prefix for an error code.

    Args:
        error_code: The error code enum value or string identifier

    Returns:
        The category prefix (e.g., 'NET', 'HTTP', 'AUTH')

    Example:
        >>> get_error_code_prefix(ErrorCodes.NET001)
        'NET'
        >>> get_error_code_prefix(ErrorCodes.HTTP404)
        'HTTP'
    """
    code_str = error_code.value if isinstance(error_code, ErrorCodes) else error_code
    return code_str[:3] if code_str.startswith("HTTP") else code_str[:2]


def get_error_severity(error_code: ErrorCodes | str) -> str:
    """
    Get the severity level for an error code.

    Args:
        error_code: The error code enum value or string identifier

    Returns:
        The severity level: 'critical', 'warning', or 'info'
    """
    code_str = error_code.value if isinstance(error_code, ErrorCodes) else error_code

    # Critical errors (require immediate action)
    critical_patterns = ["AUTH", "RATE", "HTTP5", "NET", "CLIENT", "RETRY"]

    # Warning errors (user should review)
    warning_patterns = [
        "HTTP4",
        "SEARCH",
        "FULL",
        "PARSE",
        "VALID",
        "UNPAY",
        "API",
        "FILE",
        "MODEL",
        "AVAIL",
        "LICENSE",
    ]

    # Info/General errors (informational)

    for pattern in critical_patterns:
        if pattern in code_str:
            return "critical"

    for pattern in warning_patterns:
        if pattern in code_str:
            return "warning"

    return "info"


def get_expected_resolution_time(
    error_code: ErrorCodes | str, include_recommendation: bool = False
) -> str:
    """
    Estimate how long to wait before retrying based on error type.

    Args:
        error_code: The error code enum value or string identifier
        include_recommendation: Whether to include specific recommendations

    Returns:
        An estimated resolution time (e.g., '5-10 seconds', '1-5 minutes', '24 hours')
    """
    code_str = error_code.value if isinstance(error_code, ErrorCodes) else error_code

    recommendations: dict[str, str] = {
        "NET001": "Check network stability",
        "NET003": "Verify DNS settings",
        "NET004": "Wait for server recovery",
        "RATE": "Rate limit reset",
        "HTTP503": "Server recovery time",
        "HTTP502": "Gateway recovery time",
        "AUTH": "Fix credentials immediately",
        "HTTP400": "Fix request parameters",
        "HTTP404": "Check resource ID",
        "HTTP405": "Use correct HTTP method",
    }

    recommendation = recommendations.get(code_str, "Wait and retry")

    if "NET001" in code_str or "NET004" in code_str:
        result = "5-10 seconds"
    elif "RATE" in code_str or "HTTP429" in code_str:
        result = "1-5 minutes"
    elif "HTTP503" in code_str or "HTTP502" in code_str:
        result = "1-10 minutes"
    elif "HTTP408" in code_str:
        result = "Immediate retry (increased timeout recommended)"
    elif "AUTH" in code_str:
        result = "Immediate (fix credentials)"
    elif "HTTP400" in code_str or "HTTP404" in code_str or "HTTP405" in code_str:
        result = "Not retryable (fix request)"
    elif "NET003" in code_str:
        result = "Immediate (check DNS)"
    else:
        result = "Check specific error details"

    if include_recommendation:
        return f"{result} - {recommendation}"

    return result


def generate_error_code(category: str, number: int) -> str:
    """
    Generate a consistent error code.

    Args:
        category: The error category (e.g., 'NET', 'HTTP', 'AUTH')
        number: The error number

    Returns:
        A formatted error code (e.g., 'NET001')

    Example:
        >>> generate_error_code('NET', 1)
        'NET001'
        >>> generate_error_code('HTTP', 404)
        'HTTP404'
    """
    if category == "HTTP":
        return f"HTTP{number}"
    return f"{category}{number:03d}"


def create_error_from_response_with_recovery(
    status_code: int, endpoint: str | None = None, response_body: str | None = None, **kwargs: Any
) -> "APIClientError":
    """
    Create an appropriate exception with full recovery information.

    This function creates an exception and includes all recovery options
    and recommendations in the context for programmatic access.

    Args:
        status_code: The HTTP status code from the response
        endpoint: The API endpoint that failed (optional)
        response_body: The response body (optional, truncated to 1000 chars)
        **kwargs: Additional context to pass to the exception

    Returns:
        An APIClientError (or subclass) with the appropriate error code and recovery info

    Example:
        >>> error = create_error_from_response_with_recovery(429, "/api/search")
        >>> error.context['recovery_options']  # List of recovery strategies
    """

    error_obj = create_error_from_response(status_code, endpoint, response_body, **kwargs)
    error_obj.context["recovery_options"] = get_error_recovery_options(error_obj.error_code)
    error_obj.context["retryable"] = is_retryable(error_obj.error_code)
    error_obj.context["expected_resolution_time"] = get_expected_resolution_time(
        error_obj.error_code
    )
    error_obj.context["severity"] = get_error_severity(error_obj.error_code)

    return error_obj

    """Generate unique ID for error tracking in logs."""
    import uuid

    return str(uuid.uuid4())[:8]  # Short ID for readability


def format_error_response(
    error: PyEuropePMCError,
    include_traceback: bool = False,
    include_recovery: bool = True,
) -> str:
    """
    Format error for logging or API responses.

    Args:
        error: The exception instance to format
        include_traceback: Whether to include traceback information
        include_recovery: Whether to include recovery recommendations

    Returns:
        A formatted error string suitable for logging or API responses

    Example:
        >>> try:
        ...     raise ValidationError(error_code=ErrorCodes.VALID001)
        ... except ValidationError as e:
        ...     print(format_error_response(e, include_recovery=True))
    """
    import traceback as tb_module

    error_dict = error.to_dict()

    lines = [
        f"[{error.error_code.value}] {error.message}",
        f"Category: {error_dict['category']}",
        f"Severity: {error_dict['severity']}",
        f"Retryable: {error_dict['retryable']}",
    ]

    if include_recovery and error_dict.get("recovery_options"):
        lines.append(f"Recovery: {' | '.join(error_dict['recovery_options'][:3])}")

    if error_dict.get("context"):
        lines.append(f"Context: {error_dict['context']}")

    if include_traceback:
        lines.append(f"Traceback:\n{tb_module.format_exc()}")

    return "\n".join(lines)


def raise_for_status(
    status_code: int, endpoint: str | None = None, response_body: str | None = None, **kwargs: Any
) -> NoReturn:
    """
    Raise an appropriate exception based on HTTP status code.

    This function creates and raises the appropriate error exception for the given
    HTTP status code with contextual information for debugging.

    Args:
        status_code: The HTTP status code from the response
        endpoint: The API endpoint that failed (optional)
        response_body: The response body (optional, truncated to 1000 chars)
        **kwargs: Additional context to pass to the exception

    Raises:
        APIClientError: The appropriate error exception based on status code

    Example:
        >>> raise_for_status(404, "/api/search", response_body="Not found")
        # Raises APIClientError with HTTP404 error code
    """

    error = create_error_from_response(
        status_code=status_code, endpoint=endpoint, response_body=response_body, **kwargs
    )
    raise error


# Import APIClientError at the end to avoid circular dependency
from .exceptions import APIClientError  # noqa: E402
