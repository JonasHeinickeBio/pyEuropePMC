"""
Query building, pagination, filtering, MeSH expansion, and PICO decomposition
utilities for PyEuropePMC.

This subpackage provides tools for constructing Europe PMC search queries,
handling pagination of results, filtering search results, MeSH query expansion,
and PICO framework decomposition for clinical questions.
"""

from pyeuropepmc.features.literature.filters import filter_pmc_papers, filter_pmc_papers_or
from pyeuropepmc.features.literature.pagination import (
    CursorPaginator,
    PaginationCheckpoint,
    PaginationState,
)
from pyeuropepmc.features.literature.query_builder import (
    QueryBuilder,
    get_available_fields,
    get_field_info,
    validate_field_coverage,
)
from pyeuropepmc.features.review.mesh import (
    MeSHExpander,
    MeSHExpansionResult,
    expand_with_mesh,
    lookup_mesh_descriptor,
    suggest_mesh_terms,
    translate_to_mesh,
)
from pyeuropepmc.features.review.pico import (
    PICOElements,
    PICOParser,
    PICOSDecomposer,
    PICOTDecomposer,
    SPIDERDecomposer,
    pico_decompose,
    pico_to_pubmed_query,
    pico_to_query,
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
    # MeSH expansion
    "MeSHExpander",
    "MeSHExpansionResult",
    "expand_with_mesh",
    "lookup_mesh_descriptor",
    "suggest_mesh_terms",
    "translate_to_mesh",
    # PICO decomposition
    "PICOElements",
    "PICOParser",
    "PICOSDecomposer",
    "PICOTDecomposer",
    "SPIDERDecomposer",
    "pico_decompose",
    "pico_to_pubmed_query",
    "pico_to_query",
]
