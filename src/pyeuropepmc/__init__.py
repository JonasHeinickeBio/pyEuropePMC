"""
PyEuropePMC - Python toolkit for Europe PMC API

A comprehensive Python library for searching and retrieving scientific literature
from Europe PMC with robust error handling, pagination, and multiple output formats.

Example usage:
    >>> import pyeuropepmc
    >>> client = pyeuropepmc.SearchClient()
    >>> results = client.search("CRISPR gene editing", pageSize=10)
    >>> papers = client.search_and_parse("COVID-19", format="json")
"""

__version__ = "1.0.0"
__author__ = "Jonas Heinicke"
__email__ = "jonas.heinicke@helmholtz-hzi.de"
__url__ = "https://github.com/JonasHeinickeBio/pyEuropePMC"

# Import main classes for convenient access
from .base import APIClientError, BaseAPIClient
from .parser import EuropePMCParser
from .search import EuropePMCError, SearchClient

# Convenience imports for common usage patterns
Client = SearchClient  # Alias for backwards compatibility
Parser = EuropePMCParser  # Alias for convenience

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__url__",
    # Main classes
    "SearchClient",
    "EuropePMCParser",
    "BaseAPIClient",
    # Exceptions
    "EuropePMCError",
    "APIClientError",
    # Aliases
    "Client",
    "Parser",
]
