"""
Configuration classes for fulltext parser.

This module exports all configuration dataclasses used by the parser.
"""

from .document_schema import DocumentSchema
from .element_patterns import ElementPatterns

__all__ = ["DocumentSchema", "ElementPatterns"]
