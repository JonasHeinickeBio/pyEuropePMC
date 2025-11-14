"""
Core functionality for PyEuropePMC.

This module contains the base classes, exceptions, and error codes
that form the foundation of the PyEuropePMC library.
"""

from .base import APIClientError, BaseAPIClient
from .error_codes import ErrorCodes
from .exceptions import (
    ConfigurationError,
    EuropePMCError,
    FullTextError,
    ParsingError,
    PyEuropePMCError,
    QueryBuilderError,
    SearchError,
    ValidationError,
)

__all__ = [
    "APIClientError",
    "BaseAPIClient",
    "ErrorCodes",
    "ConfigurationError",
    "EuropePMCError",
    "FullTextError",
    "ParsingError",
    "PyEuropePMCError",
    "QueryBuilderError",
    "SearchError",
    "ValidationError",
]
