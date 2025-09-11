"""
Custom exceptions for the PyEuropePMC library.

This module contains all custom exceptions used throughout the PyEuropePMC library,
providing a centralized location for error handling and consistent error messaging.
"""

from typing import Any

from .error_codes import ErrorCodes, get_error_message_by_string


class PyEuropePMCError(Exception):
    """
    Base exception class for all PyEuropePMC library errors.

    This class automatically looks up error messages from the ERROR_CODES library
    and supports message formatting with context variables.
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> None:
        """
        Args:
            error_code: Optional error code enum value from ErrorCodes. If not provided,
                       a generic error code will be auto-generated based on the exception type.
            context: Dict with keys for formatting the error message.
            message: Optional custom error message. If provided, this will be used
                    instead of the default error message from the error codes library.
                    Required if error_code is None.
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

        # Use custom message if provided, otherwise look up from error codes
        if message:
            self.message = message
        else:
            # Look up and format the message using the context
            template = get_error_message_by_string(error_code.value)
            try:
                self.message = template.format(**self.context)
            except Exception:
                self.message = template  # fallback if context is incomplete

        super().__init__(self.message)

    def _get_default_error_code(self) -> ErrorCodes:
        """
        Generate default error code based on exception type.

        Returns:
            Default ErrorCode appropriate for the exception type.
        """
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
        return f"[{self.error_code.value}] {self.message}"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(error_code={self.error_code!r}, context={self.context!r})"
        )


class APIClientError(PyEuropePMCError):
    """
    Exception raised for API client-related errors.

    This exception is used for low-level HTTP communication errors,
    network issues, and API response problems.
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(error_code, context, message)


class SearchError(PyEuropePMCError):
    """
    Exception raised for search-related errors.

    This exception covers search query validation, search execution failures,
    and search result processing errors.
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        query: str | None = None,
        search_type: str | None = None,
    ) -> None:
        # Add search-specific context
        if context is None:
            context = {}
        if query:
            context["query"] = query
        if search_type:
            context["search_type"] = search_type

        super().__init__(error_code, context, message)
        self.query = query
        self.search_type = search_type


class FullTextError(PyEuropePMCError):
    """
    Exception raised for full text retrieval errors.

    This exception covers PDF downloads, XML retrieval, HTML access,
    content validation, and file operation errors.
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        pmcid: str | None = None,
        format_type: str | None = None,
        operation: str | None = None,
    ) -> None:
        # Add full text specific context
        if context is None:
            context = {}
        if pmcid:
            context["pmcid"] = pmcid
        if format_type:
            context["format_type"] = format_type
        if operation:
            context["operation"] = operation

        super().__init__(error_code, context, message)
        self.pmcid = pmcid
        self.format_type = format_type
        self.operation = operation


class ParsingError(PyEuropePMCError):
    """
    Exception raised for data parsing errors.

    This exception covers JSON parsing, XML parsing, content validation,
    and data format conversion errors.
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        data_type: str | None = None,
        parser_type: str | None = None,
        line_number: int | None = None,
    ) -> None:
        # Add parsing-specific context
        if context is None:
            context = {}
        if data_type:
            context["data_type"] = data_type
        if parser_type:
            context["parser_type"] = parser_type
        if line_number:
            context["line_number"] = line_number

        super().__init__(error_code, context, message)
        self.data_type = data_type
        self.parser_type = parser_type
        self.line_number = line_number


class ValidationError(PyEuropePMCError):
    """
    Exception raised for data validation errors.

    This exception covers input validation, parameter validation,
    content validation, and format validation errors.
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        field_name: str | None = None,
        expected_type: str | None = None,
        actual_value: Any | None = None,
    ) -> None:
        # Add validation-specific context
        if context is None:
            context = {}
        if field_name:
            context["field_name"] = field_name
        if expected_type:
            context["expected_type"] = expected_type
        if actual_value is not None:
            context["actual_value"] = str(actual_value)[:100]  # Truncate large values

        super().__init__(error_code, context, message)
        self.field_name = field_name
        self.expected_type = expected_type
        self.actual_value = actual_value
        self.details = context  # Provide access to context as details


class ConfigurationError(PyEuropePMCError):
    """
    Exception raised for configuration-related errors.

    This exception covers invalid settings, missing configuration,
    environment setup issues, and dependency problems.
    """

    def __init__(
        self,
        error_code: ErrorCodes | None = None,
        context: dict[str, Any] | None = None,
        message: str | None = None,
        config_key: str | None = None,
        config_section: str | None = None,
    ) -> None:
        # Add configuration-specific context
        if context is None:
            context = {}
        if config_key:
            context["config_key"] = config_key
        if config_section:
            context["config_section"] = config_section

        super().__init__(error_code, context, message)
        self.config_key = config_key
        self.config_section = config_section


# Convenience aliases for backward compatibility
EuropePMCError = SearchError  # Legacy alias
