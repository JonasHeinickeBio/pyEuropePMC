"""
Common base class for API clients.

Provides shared infrastructure for HTTP session management, retries, caching,
and resource cleanup. This base class is designed to be inherited by specialized
clients for enrichment, search, and other API interactions.

Intended for use with external APIs (CrossRef, OpenAlex, PubMed, etc.).
For Europe PMC internal services, use `pyeuropepmc.core.base.BaseAPIClient` instead.
"""

from pyeuropepmc.features.common.base import BaseAPIClient, BaseHTTPClient

__all__ = ["BaseHTTPClient", "BaseAPIClient"]
