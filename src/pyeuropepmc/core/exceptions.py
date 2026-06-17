"""
Custom exceptions for the PyEuropePMC library.

This module contains all custom exceptions used throughout the PyEuropePMC library,
providing a centralized location for error handling and consistent error messaging.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from pyeuropepmc.core.error_codes import (
        ErrorCodes,
    )


class PyEuropePMCError(Exception):
    """
    Base exception class for all PyEuropePMC library errors.

    This class automatically looks up error messages from the ERROR_CODES library
    and supports message formatting with context variables. All exceptions provide
    actionable guidance to help users resolve issues.

    Error messages follow a consistent format:
    - Clear description of what went wrong
    - Specific guidance on how to fix it
    - Context variables for dynamic information (PMC ID, query, etc.)

    Attributes:
        error_code: The error code enum value from ErrorCodes
        context: Dict with keys for formatting the error message
        message: The formatted error message
        custom_message: Custom message if provided (overrides error code lookup)
        endpoint: API endpoint that failed (if applicable)
        status_code: HTTP status code (if applicable)
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """
        Args:
            error_code: Optional error code enum value from ErrorCodes. If not provided,
                       a generic error code will be auto-generated based on the exception type.
            context: Dict with keys for formatting the error message (e.g., {'pmcid': 'PMC123', 'format_type': 'pdf'})
            message: Optional custom error message. If provided, this will be used
                    instead of the default error message from the error codes library.
                    Required if error_code is None.
            endpoint: API endpoint that failed (optional)
            status_code: HTTP status code (optional)
        """
        # Validate that either error_code or message is provided
        if error_code is None and message is None:
            raise ValueError(
                "Either 'error_code' or 'message' must be provided. "
                "Cannot create exception without an error code or custom message."
            )

        # Auto-generate error code if not provided
        if error_code is None:
            error_code = self._get_default_error_code()

        self.error_code = error_code
        self.context = context or {}
        self.custom_message = message

        # Add endpoint and status_code to context if provided
        if endpoint:
            self.context["endpoint"] = endpoint
        if status_code:
            self.context["status_code"] = status_code

        # Use custom message if provided, otherwise look up and format from error codes
        if message:
            self.message = message
        else:
            # Look up and format the message using the context
            from pyeuropepmc.core.error_codes import (
                format_error_message,
            )

            self.message = format_error_message(error_code, self.context)

        # Store endpoint and status_code as attributes for easy access
        self.endpoint = endpoint
        self.status_code = status_code

        super().__init__(self.message)

    def _get_default_error_code(self) -> ErrorCodes:
        """
        Generate default error code based on exception type.

        Returns:
            Default ErrorCode appropriate for the exception type.
        """
        from pyeuropepmc.core.error_codes import ErrorCodes

        class_name = self.__class__.__name__
        if "Search" in class_name:
            return ErrorCodes.GENERIC003  # Generic search error
        elif "FullText" in class_name:
            return ErrorCodes.GENERIC004  # Generic fulltext error
        elif "Parsing" in class_name:
            return ErrorCodes.GENERIC005  # Generic parsing error
        elif "Validation" in class_name:
            return ErrorCodes.GENERIC006  # Generic validation error
        elif "Configuration" in class_name:
            return ErrorCodes.GENERIC007  # Generic config error
        elif "APIClient" in class_name:
            return ErrorCodes.GENERIC002  # Generic API client error
        else:
            return ErrorCodes.GENERIC001  # Generic PyEuropePMC error

    def __str__(self) -> str:
        """
        Return a user-friendly error message with error code prefix.

        Format: [ERROR_CODE] Clear description and actionable guidance
        """
        return f"[{self.error_code.value}] {self.message}"

    def __repr__(self) -> str:
        """Return a detailed representation for debugging."""
        return (
            f"{self.__class__.__name__}(error_code={self.error_code!r}, context={self.context!r})"
        )

    def get_user_friendly_message(self, include_severity: bool = False) -> str:
        """
        Get a user-friendly error message without the error code prefix.

        Args:
            include_severity: Whether to include severity level in the message

        Returns:
            A clear, actionable message suitable for end users
        """
        message = self.message
        if include_severity:
            severity = self.get_severity()
            severity_prefix = {
                "critical": "[CRITICAL]",
                "warning": "[WARNING]",
                "info": "[INFO]",
            }.get(severity, "")
            message = f"{severity_prefix} {message}"
        return message

    def get_user_friendly_summary(self) -> dict[str, str]:
        """
        Get a comprehensive summary of the error for end users.

        Returns:
            A dictionary with: title, message, action, recovery_options
        """
        return {
            "title": f"Error: {self.get_error_category()}",
            "message": self.get_user_friendly_message(),
            "action": self.get_actionable_advice(),
            "recovery_options": " | ".join(self.get_recovery_options()[:3]),
            "severity": self.get_severity(),
            "retryable": str(self.is_retryable()),
        }

    def get_error_category(self) -> str:
        from pyeuropepmc.core.error_codes import (
            get_error_code_category,
        )

        return get_error_code_category(self.error_code)

    def get_severity_level(self) -> int:
        from pyeuropepmc.core.error_codes import (
            get_error_severity_level,
        )

        return get_error_severity_level(self.error_code)

    def get_severity(self) -> str:
        from pyeuropepmc.core.error_codes import get_error_severity

        return get_error_severity(self.error_code)

    def get_actionable_advice(self, include_category: bool = True) -> str:
        """
        Get actionable advice for resolving this error.

        Args:
            include_category: Whether to include category-specific advice

        Returns:
            A recommendation for how to resolve or work around the error
        """
        # Get the base error message which includes actionable guidance
        base_advice = self.message

        if not include_category:
            return base_advice

        # Add specific advice based on error category
        category = self.get_error_category()

        category_advice: dict[str, str] = {
            "Network": "Check your internet connection, firewall settings, and try again.",
            "HTTP": "Verify the URL and parameters are correct. Try again in a moment.",
            "Authentication": "Check your API credentials and ensure they are valid and not expired.",
            "Rate Limiting": "Wait before retrying. Increase rate_limit_delay or use an API key.",
            "Search": "Review your query syntax. Try simpler or broader search terms.",
            "Full Text": "Verify the PMC ID is correct. Check if the content is available for download.",
            "Parsing": "Check the data source format. Ensure it's valid JSON or XML.",
            "Validation": "Review the error details. Check all required fields and parameter values.",
            "Configuration": "Check your configuration settings. Ensure all required options are set.",
            "Content Availability": "Verify the identifier. Try a different source or publisher website.",
            "License": "Check the article's license. Ensure it permits your intended use.",
        }

        if category in category_advice:
            return f"{base_advice} Action: {category_advice[category]}"

        return base_advice

    def is_retryable(self) -> bool:
        """
        Check if this error is retryable.

        Returns:
            True if the error is retryable, False otherwise

        Note:
            Retryable errors include network issues, rate limits, and server errors (5xx).
        """
        from pyeuropepmc.core.error_codes import (
            is_retryable as _is_retryable,
        )

        return _is_retryable(self.error_code)

    def get_suggestion(self, include_code_snippet: bool = False) -> str:
        """Get a suggestion for resolving this error."""
        from pyeuropepmc.core.error_codes import get_error_suggestion

        return get_error_suggestion(self.error_code, include_code_snippet=include_code_snippet)

    def get_recovery_options(self) -> list[str]:
        """Get recovery options for this error."""
        from pyeuropepmc.core.error_codes import (
            get_error_recovery_options,
        )

        return get_error_recovery_options(self.error_code)

    def get_classification(self) -> dict[str, Any]:
        """Get classification for this error."""
        from pyeuropepmc.core.error_codes import (
            get_error_classification,
        )

        return get_error_classification(self.error_code)

    def get_expected_resolution_time(self) -> str:
        """Get expected resolution time for this error."""
        from pyeuropepmc.core.error_codes import (
            get_expected_resolution_time,
        )

        return get_expected_resolution_time(self.error_code)

    def to_dict(
        self, include_context: bool = True, include_recovery: bool = True
    ) -> dict[str, Any]:
        """
        Convert the error to a dictionary for logging or API responses.

        Args:
            include_context: Whether to include context variables
            include_recovery: Whether to include recovery information

        Returns:
            A dictionary representation of the error with all relevant fields
        """
        result: dict[str, Any] = {
            "error_code": self.error_code.value,
            "category": self.get_error_category(),
            "severity": self.get_severity(),
            "message": self.message,
            "user_friendly_message": self.get_user_friendly_message(),
            "advice": self.get_actionable_advice(),
            "retryable": self.is_retryable(),
            "suggestion": self.get_suggestion(),
            "expected_resolution_time": self.get_expected_resolution_time(),
        }

        if include_context:
            result["context"] = self.context

        if include_recovery:
            result["recovery_options"] = self.get_recovery_options()
            result["severity_level"] = self.get_severity_level()
            result["classification"] = self.get_classification()

        if self.endpoint:
            result["endpoint"] = self.endpoint
        if self.status_code:
            result["status_code"] = self.status_code

        return result


# Helper function for creating errors from HTTP responses
def raise_for_status(
    status_code: int, endpoint: str | None = None, response_body: str | None = None, **kwargs: Any
) -> NoReturn:
    """
    Raise an appropriate exception for an HTTP status code.

    Args:
        status_code: The HTTP status code from the response
        endpoint: The API endpoint that failed (optional)
        response_body: The response body (optional, truncated to 1000 chars)
        **kwargs: Additional context to pass to the exception

    Raises:
        APIClientError: An appropriate exception based on the status code

    Example:
        >>> raise_for_status(404, "/api/search")
        # Raises APIClientError with HTTP404 error code
    """

    from pyeuropepmc.core.error_codes import (
        create_error_from_response_with_recovery,
    )

    error = create_error_from_response_with_recovery(
        status_code, endpoint, response_body, **kwargs
    )
    raise error


class APIClientError(PyEuropePMCError):
    """
    Exception raised for API client-related errors.

    This exception is used for low-level HTTP communication errors,
    network issues, and API response problems.

    Common scenarios:
    - Network connection failures
    - Server timeouts
    - Authentication failures
    - Rate limiting
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the API client error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
        """
        super().__init__(error_code, context, message, endpoint, status_code)


class SearchError(PyEuropePMCError):
    """
    Exception raised for search-related errors.

    This exception covers search query validation, search execution failures,
    and search result processing errors.

    Common scenarios:
    - Invalid search syntax
    - Page size out of range
    - Search service unavailable
    - No results found
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        query: str | None = None,
        search_type: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the search error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
            query: The search query that failed
            search_type: Type of search performed (e.g., 'search', 'cites')
            page: Page number requested
            page_size: Page size requested
        """
        # Add search-specific context
        if context is None:
            context = {}
        if query:
            context["query"] = query
        if search_type:
            context["search_type"] = search_type
        if page:
            context["page"] = page
        if page_size:
            context["page_size"] = page_size

        super().__init__(error_code, context, message, endpoint, status_code)
        self.query = query
        self.search_type = search_type
        self.page = page
        self.page_size = page_size


class FullTextError(PyEuropePMCError):
    """
    Exception raised for full text retrieval errors.

    This exception covers PDF downloads, XML retrieval, HTML access,
    content validation, and file operation errors.

    Common scenarios:
    - Invalid PMC ID
    - Content not available
    - Download failures
    - File access issues
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        pmcid: str | None = None,
        format_type: str | None = None,
        operation: str | None = None,
        doi: str | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the full text error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
            pmcid: The PMC ID that failed
            format_type: The requested format (pdf, xml, html)
            operation: The operation being performed (download, parse, save)
            doi: DOI if relevant
        """
        # Add full text specific context
        if context is None:
            context = {}
        if pmcid:
            context["pmcid"] = pmcid
        if format_type:
            context["format_type"] = format_type
        if operation:
            context["operation"] = operation
        if doi:
            context["doi"] = doi

        super().__init__(error_code, context, message, endpoint, status_code)
        self.pmcid = pmcid
        self.format_type = format_type
        self.operation = operation
        self.doi = doi


class ParsingError(PyEuropePMCError):
    """
    Exception raised for data parsing errors.

    This exception covers JSON parsing, XML parsing, content validation,
    and data format conversion errors.

    Common scenarios:
    - Invalid JSON format
    - Malformed XML
    - Unexpected data structure
    - Unsupported format
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        data_type: str | None = None,
        parser_type: str | None = None,
        line_number: int | None = None,
        original_data: str | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the parsing error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
            data_type: Type of data being parsed (json, xml, etc.)
            parser_type: Type of parser used
            line_number: Line number where error occurred (if applicable)
            original_data: The original data that failed to parse (truncated if too long)
        """
        # Add parsing-specific context
        if context is None:
            context = {}
        if data_type:
            context["data_type"] = data_type
        if parser_type:
            context["parser_type"] = parser_type
        if line_number:
            context["line_number"] = line_number
        if original_data:
            # Truncate for context
            context["original_data"] = (
                original_data[:200] + "..." if len(original_data) > 200 else original_data
            )

        super().__init__(error_code, context, message, endpoint, status_code)
        self.data_type = data_type
        self.parser_type = parser_type
        self.line_number = line_number
        self.original_data = original_data


class ValidationError(PyEuropePMCError):
    """
    Exception raised for data validation errors.

    This exception covers input validation, parameter validation,
    content validation, and format validation errors.

    Common scenarios:
    - Invalid parameter values
    - Missing required fields
    - Type mismatches
    - Out of range values
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        field_name: str | None = None,
        expected_type: str | None = None,
        actual_value: Any | None = None,
        min_value: Any | None = None,
        max_value: Any | None = None,
        allowed_values: list[Any] | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the validation error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
            field_name: Name of the field that failed validation
            expected_type: Expected data type
            actual_value: The actual value that failed validation
            min_value: Minimum allowed value (for numeric ranges)
            max_value: Maximum allowed value (for numeric ranges)
            allowed_values: List of allowed values (for enum checks)
        """
        # Add validation-specific context
        if context is None:
            context = {}
        if field_name:
            context["field_name"] = field_name
        if expected_type:
            context["expected_type"] = expected_type
        if actual_value is not None:
            context["actual_value"] = str(actual_value)[:100]  # Truncate large values
        if min_value is not None:
            context["min_value"] = str(min_value)
        if max_value is not None:
            context["max_value"] = str(max_value)
        if allowed_values is not None:
            context["allowed_values"] = ", ".join(str(v) for v in allowed_values)

        super().__init__(error_code, context, message, endpoint, status_code)
        self.field_name = field_name
        self.expected_type = expected_type
        self.actual_value = actual_value
        self.min_value = min_value
        self.max_value = max_value
        self.allowed_values = allowed_values
        self.details = context  # Provide access to context as details


class ConfigurationError(PyEuropePMCError):
    """
    Exception raised for configuration-related errors.

    This exception covers invalid settings, missing configuration,
    environment setup issues, and dependency problems.

    Common scenarios:
    - Missing API key
    - Invalid configuration value
    - Missing environment variable
    - Missing dependency
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        config_key: str | None = None,
        config_section: str | None = None,
        env_var: str | None = None,
        required_dependency: str | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the configuration error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
            config_key: The configuration key that failed
            config_section: The configuration section
            env_var: Environment variable that is missing
            required_dependency: The missing dependency name
        """
        # Add configuration-specific context
        if context is None:
            context = {}
        if config_key:
            context["config_key"] = config_key
        if config_section:
            context["config_section"] = config_section
        if env_var:
            context["env_var"] = env_var
        if required_dependency:
            context["required_dependency"] = required_dependency

        super().__init__(error_code, context, message, endpoint, status_code)
        self.config_key = config_key
        self.config_section = config_section
        self.env_var = env_var
        self.required_dependency = required_dependency


class RateLimitError(APIClientError):
    """
    Exception raised for rate limiting errors.

    This exception covers cases where the API rate limit has been exceeded.
    These errors are typically retryable after a waiting period.

    Common scenarios:
    - Too many requests in a short time
    - Exceeding rate limit thresholds
    - Missing or insufficient API key for higher limits
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the rate limit error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (typically 429)
            retry_after: Seconds to wait before retrying (from Retry-After header)
        """
        # Add rate limit specific context
        if context is None:
            context = {}
        if retry_after:
            context["retry_after"] = retry_after

        super().__init__(error_code, context, message, endpoint, status_code)
        self.retry_after = retry_after


class QueryBuilderError(PyEuropePMCError):
    """
    Exception raised for query builder errors.

    This exception covers query construction errors, validation failures,
    and invalid query syntax issues.

    Common scenarios:
    - Invalid query syntax
    - Invalid field names
    - Invalid operators
    - Missing query terms
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        query_part: str | None = None,
        position: int | None = None,
        expected: str | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the query builder error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
            query_part: The problematic part of the query
            position: Position in the query string
            expected: What was expected at this position
        """
        # Add query builder specific context
        if context is None:
            context = {}
        if query_part:
            context["query_part"] = query_part
        if position:
            context["position"] = position
        if expected:
            context["expected"] = expected

        super().__init__(error_code, context, message, endpoint, status_code)
        self.query_part = query_part
        self.position = position
        self.expected = expected


class UnpaywallError(PyEuropePMCError):
    """
    Exception raised for Unpaywall API errors.

    This exception covers Unpaywall lookup failures, network errors,
    and response parsing issues.

    Common scenarios:
    - DOI not found
    - Network errors to Unpaywall
    - Invalid DOI format
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        doi: str | None = None,
        unpaywall_url: str | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the Unpaywall error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
            doi: The DOI that failed lookup
            unpaywall_url: The Unpaywall URL that was accessed
        """
        # Add Unpaywall-specific context
        if context is None:
            context = {}
        if doi:
            context["doi"] = doi
        if unpaywall_url:
            context["unpaywall_url"] = unpaywall_url

        super().__init__(error_code, context, message, endpoint, status_code)
        self.doi = doi
        self.unpaywall_url = unpaywall_url


class ClientError(PyEuropePMCError):
    """
    Exception raised for API client initialization or session errors.

    This exception covers client configuration issues, session problems,
    and client state errors.

    Common scenarios:
    - Missing required configuration
    - Invalid client parameters
    - Session expiration
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        client_type: str | None = None,
        config_keys: list[str] | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the client error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            status_code: HTTP status code from response (if available)
            client_type: Type of client that failed
            config_keys: List of configuration keys that are missing or invalid
        """
        # Add client-specific context
        if context is None:
            context = {}
        if client_type:
            context["client_type"] = client_type
        if config_keys:
            context["config_keys"] = ", ".join(config_keys)

        super().__init__(error_code, context, message, endpoint, status_code)
        self.client_type = client_type
        self.config_keys = config_keys


class APIError(PyEuropePMCError):
    """
    Exception raised for API-specific errors.

    This exception covers API request failures, response parsing issues,
    and API rate limit warnings.

    Common scenarios:
    - Request failures
    - Malformed responses
    - Rate limit warnings
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        endpoint: str | None = None,
        request_id: str | None = None,
        response_status: int | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the API error
            context: Context variables for message formatting
            message: Custom error message
            endpoint: The API endpoint that failed
            request_id: The request ID for troubleshooting
            response_status: HTTP status code from response
        """
        # Add API-specific context
        if context is None:
            context = {}
        if endpoint:
            context["endpoint"] = endpoint
        if request_id:
            context["request_id"] = request_id
        if response_status:
            context["response_status"] = response_status

        super().__init__(error_code, context, message, endpoint, response_status)
        self.endpoint = endpoint
        self.request_id = request_id
        self.response_status = response_status


class FileError(PyEuropePMCError):
    """
    Exception raised for file operation errors.

    This exception covers file access, read/write operations,
    and file validation errors.

    Common scenarios:
    - File not found
    - Permission denied
    - Empty or corrupted files
    - File operation interruptions
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        file_path: str | None = None,
        operation: str | None = None,
        file_size: int | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the file error
            context: Context variables for message formatting
            message: Custom error message
            file_path: Path to the file that failed
            operation: The operation being performed (read, write, validate)
            file_size: Size of the file in bytes (for validation errors)
        """
        # Add file-specific context
        if context is None:
            context = {}
        if file_path:
            context["file_path"] = file_path
        if operation:
            context["operation"] = operation
        if file_size is not None:
            context["file_size"] = file_size

        super().__init__(error_code, context, message)
        self.file_path = file_path
        self.operation = operation
        self.file_size = file_size


class ModelError(PyEuropePMCError):
    """
    Exception raised for model/entity validation errors.

    This exception covers model data validation, conversion errors,
    and attribute validation issues.

    Common scenarios:
    - Invalid model data structure
    - Model validation failures
    - Model conversion errors
    - Missing required attributes
    - Type mismatches
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        model_type: str | None = None,
        field_name: str | None = None,
        expected_type: str | None = None,
        actual_value: Any | None = None,
    ) -> None:
        """
        Args:
            error_code: The error code for the model error
            context: Context variables for message formatting
            message: Custom error message
            model_type: Type of model that failed
            field_name: Name of the field that failed validation
            expected_type: Expected data type
            actual_value: The actual value that failed validation
        """
        # Add model-specific context
        if context is None:
            context = {}
        if model_type:
            context["model_type"] = model_type
        if field_name:
            context["field_name"] = field_name
        if expected_type:
            context["expected_type"] = expected_type
        if actual_value is not None:
            context["actual_value"] = str(actual_value)[:100]

        super().__init__(error_code, context, message)
        self.model_type = model_type
        self.field_name = field_name
        self.expected_type = expected_type
        self.actual_value = actual_value


# Convenience aliases for backward compatibility
EuropePMCError = SearchError  # Legacy alias


def create_error_from_response(
    status_code: int,
    endpoint: str | None = None,
    error_code: ErrorCodes | None = None,
    context: dict[str, Any] | None = None,
    message: str | None = None,
) -> PyEuropePMCError:
    """
    Create an appropriate exception based on HTTP status code.

    Args:
        status_code: The HTTP status code from the response
        endpoint: The API endpoint that failed
        error_code: Optional specific error code to use
        context: Context variables for message formatting
        message: Custom error message

    Returns:
        An appropriate PyEuropePMCError subclass based on the status code

    Example:
        >>> try:
        ...     response = requests.get(url)
        ...     response.raise_for_status()
        ... except requests.HTTPError as e:
        ...     error = create_error_from_response(e.response.status_code, url)
        ...     raise error
    """
    context = context or {}

    if endpoint:
        context["endpoint"] = endpoint

    from pyeuropepmc.core.error_codes import ErrorCodes

    # Map status codes to appropriate error codes
    if status_code == 401:
        error_code = error_code or ErrorCodes.AUTH401
        return APIClientError(
            error_code=error_code,
            context=context,
            message=message,
            endpoint=endpoint,
            status_code=status_code,
        )
    elif status_code == 403:
        error_code = error_code or ErrorCodes.HTTP403
        return APIClientError(
            error_code=error_code,
            context=context,
            message=message,
            endpoint=endpoint,
            status_code=status_code,
        )
    elif status_code == 404:
        error_code = error_code or ErrorCodes.HTTP404
        return APIClientError(
            error_code=error_code,
            context=context,
            message=message,
            endpoint=endpoint,
            status_code=status_code,
        )
    elif status_code == 429:
        error_code = error_code or ErrorCodes.RATE429
        return APIClientError(
            error_code=error_code,
            context=context,
            message=message,
            endpoint=endpoint,
            status_code=status_code,
        )
    elif 500 <= status_code < 600:
        error_code = error_code or ErrorCodes.HTTP500
        return APIClientError(
            error_code=error_code,
            context=context,
            message=message,
            endpoint=endpoint,
            status_code=status_code,
        )
    elif 400 <= status_code < 500:
        error_code = error_code or ErrorCodes.API001
        return APIClientError(
            error_code=error_code,
            context=context,
            message=message,
            endpoint=endpoint,
            status_code=status_code,
        )
    else:
        error_code = error_code or ErrorCodes.GENERIC001
        return PyEuropePMCError(error_code=error_code, context=context, message=message)
