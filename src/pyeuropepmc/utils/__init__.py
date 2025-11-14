"""
Utility functions and helpers for PyEuropePMC.

This subpackage provides various utility functions for data export, logging,
text matching, and general helper functions.
"""

from .export import (
    filter_fields,
    map_fields,
    to_csv,
    to_dataframe,
    to_excel,
    to_json,
    to_markdown_table,
)
from .helpers import (
    atomic_download,
    atomic_write,
    deep_merge_dicts,
    load_json,
    safe_int,
    save_to_json,
    save_to_json_with_merge,
    warn_if_empty_hitcount,
)
from .search_logging import (
    SearchLog,
    SearchLogEntry,
    generate_private_key,
    prisma_summary,
    record_export,
    record_peer_review,
    record_platform,
    record_query,
    record_results,
    sign_and_zip_results,
    sign_file,
    start_search,
    zip_results,
)
from .text_match import (
    SemanticModel,
    SemanticModelProtocol,
    all_needles_match,
    any_match,
    any_needles_match,
    as_semantic_model,
    normalize,
    semantic_chunk_match,
    semantic_score,
    split_to_sentences,
    token_fuzzy_score,
    token_jaccard,
    tokens,
)

__all__ = [
    # Export functions
    "filter_fields",
    "map_fields",
    "to_csv",
    "to_dataframe",
    "to_excel",
    "to_json",
    "to_markdown_table",
    # Helper functions
    "atomic_download",
    "atomic_write",
    "deep_merge_dicts",
    "load_json",
    "safe_int",
    "save_to_json",
    "save_to_json_with_merge",
    "warn_if_empty_hitcount",
    # Search logging
    "SearchLog",
    "SearchLogEntry",
    "generate_private_key",
    "prisma_summary",
    "record_export",
    "record_peer_review",
    "record_platform",
    "record_query",
    "record_results",
    "sign_and_zip_results",
    "sign_file",
    "start_search",
    "zip_results",
    # Text matching
    "SemanticModel",
    "SemanticModelProtocol",
    "all_needles_match",
    "any_match",
    "any_needles_match",
    "as_semantic_model",
    "normalize",
    "semantic_chunk_match",
    "semantic_score",
    "split_to_sentences",
    "token_fuzzy_score",
    "token_jaccard",
    "tokens",
]
