"""
Utility functions and helpers for PyEuropePMC.

This subpackage provides various utility functions for data export, logging,
text matching, and general helper functions.

Names are imported lazily (PEP 562) so that ``import pyeuropepmc.utils`` (or
importing a single helper) does not pull in pandas via :mod:`pyeuropepmc.utils.export`.
The export helpers need ``pip install pyeuropepmc[analytics]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyeuropepmc._lazy import lazy_module

_EXPORT = "pyeuropepmc.utils.export"
_HELPERS = "pyeuropepmc.utils.helpers"
_LOGGING = "pyeuropepmc.utils.search_logging"
_TEXT = "pyeuropepmc.utils.text_match"

_LAZY = {
    **{
        n: f"{_EXPORT}:{n}"
        for n in (
            "filter_fields",
            "map_fields",
            "to_csv",
            "to_dataframe",
            "to_excel",
            "to_json",
            "to_markdown_table",
        )
    },
    **{
        n: f"{_HELPERS}:{n}"
        for n in (
            "atomic_download",
            "atomic_write",
            "deep_merge_dicts",
            "load_json",
            "safe_int",
            "save_to_json",
            "save_to_json_with_merge",
            "warn_if_empty_hitcount",
        )
    },
    **{
        n: f"{_LOGGING}:{n}"
        for n in (
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
        )
    },
    **{
        n: f"{_TEXT}:{n}"
        for n in (
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
        )
    },
}

_lazy_getattr, __dir__, __all__ = lazy_module(__name__, _LAZY)


def __getattr__(name: str) -> Any:
    """Resolve a public attribute lazily (see :mod:`pyeuropepmc._lazy`)."""
    return _lazy_getattr(name)


if TYPE_CHECKING:
    from pyeuropepmc.utils.export import (
        filter_fields as filter_fields,
        map_fields as map_fields,
        to_csv as to_csv,
        to_dataframe as to_dataframe,
        to_excel as to_excel,
        to_json as to_json,
        to_markdown_table as to_markdown_table,
    )
    from pyeuropepmc.utils.helpers import (
        atomic_download as atomic_download,
        atomic_write as atomic_write,
        deep_merge_dicts as deep_merge_dicts,
        load_json as load_json,
        safe_int as safe_int,
        save_to_json as save_to_json,
        save_to_json_with_merge as save_to_json_with_merge,
        warn_if_empty_hitcount as warn_if_empty_hitcount,
    )
    from pyeuropepmc.utils.search_logging import (
        SearchLog as SearchLog,
        SearchLogEntry as SearchLogEntry,
        generate_private_key as generate_private_key,
        prisma_summary as prisma_summary,
        record_export as record_export,
        record_peer_review as record_peer_review,
        record_platform as record_platform,
        record_query as record_query,
        record_results as record_results,
        sign_and_zip_results as sign_and_zip_results,
        sign_file as sign_file,
        start_search as start_search,
        zip_results as zip_results,
    )
    from pyeuropepmc.utils.text_match import (
        SemanticModel as SemanticModel,
        SemanticModelProtocol as SemanticModelProtocol,
        all_needles_match as all_needles_match,
        any_match as any_match,
        any_needles_match as any_needles_match,
        as_semantic_model as as_semantic_model,
        normalize as normalize,
        semantic_chunk_match as semantic_chunk_match,
        semantic_score as semantic_score,
        split_to_sentences as split_to_sentences,
        token_fuzzy_score as token_fuzzy_score,
        token_jaccard as token_jaccard,
        tokens as tokens,
    )
