"""
Query building, pagination, and filtering utilities for PyEuropePMC.

This subpackage provides tools for constructing Europe PMC search queries,
handling pagination of results, and filtering search results based on various criteria.
"""

from .filters import filter_pmc_papers, filter_pmc_papers_or
from .pagination import CursorPaginator, PaginationCheckpoint, PaginationState
from .query_builder import (
    QueryBuilder,
    get_available_fields,
    get_field_info,
    validate_field_coverage,
)

__all__ = [
    # Filtering functions
    "filter_pmc_papers",
    "filter_pmc_papers_or",
    # Pagination classes
    "CursorPaginator",
    "PaginationCheckpoint",
    "PaginationState",
    # Query building
    "QueryBuilder",
    "get_available_fields",
    "get_field_info",
    "validate_field_coverage",
]
