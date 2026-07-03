"""
MCP Server for pyeuropepmc
Provides Model Context Protocol access to Europe PMC API

This module provides MCP tools for searching and retrieving scientific literature
from Europe PMC as part of the pyeuropepmc package.

The MCP server uses pyeuropepmc.SearchClient directly, avoiding code duplication
and leveraging all existing features including caching, rate limiting, and pagination.
"""

from .server import _get_client

__all__ = ["_get_client"]
