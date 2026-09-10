"""
Translate one user query into each source's native query dialect.

``UnifiedSearch`` accepts a single query string but every backend expects a
different syntax:

===============  ==========================================================
Source           Expected form
===============  ==========================================================
europepmc        Europe PMC query syntax (``TITLE:"..." AND ...``) — passed through
pubmed           Entrez ``term`` (field tags like ``[tiab]``, ``[au]``) — passed through
arxiv            ``all:"<query>"`` (or field-prefixed ``ti:``, ``au:``)
openalex         free-text ``search=`` — quotes/boolean operators stripped
semantic_scholar free-text — boolean operators stripped
crossref         free-text bibliographic query
dblp / core / …  free-text
===============  ==========================================================

When the optional `search-query` package is available and the query parses as
a structured boolean query, it is used to render a clean per-platform string;
otherwise lightweight heuristics are applied.  Translation is best-effort and
never raises — a failure falls back to the original query.
"""

from __future__ import annotations

import contextlib
import io
import logging
import re

logger = logging.getLogger(__name__)

__all__ = ["translate_query", "SUPPORTED"]

#: Sources that take the query verbatim (their syntax *is* the lingua franca here).
_PASSTHROUGH = {"europepmc", "pubmed", "clinicaltrials"}

#: Sources that want a plain free-text string (no field tags / boolean operators).
_FREETEXT = {"openalex", "semantic_scholar", "crossref", "doaj", "dblp", "hal", "core", "zenodo"}

SUPPORTED = _PASSTHROUGH | _FREETEXT | {"arxiv"}

_BOOL_OP = re.compile(r"\b(AND|OR|NOT)\b")
_FIELD_TAG = re.compile(r"\b\w+:\s*")  # e.g. "ti:", "TITLE:"
_ENTREZ_TAG = re.compile(r"\[[^\]]+\]")  # e.g. "[tiab]", "[Mesh]"
_QUOTES = re.compile(r'["“”]')
_WS = re.compile(r"\s+")


def _to_freetext(query: str) -> str:
    """Strip boolean operators, field tags and quotes -> bag-of-words string."""
    q = _ENTREZ_TAG.sub(" ", query)
    q = _FIELD_TAG.sub(" ", q)
    q = _BOOL_OP.sub(" ", q)
    q = _QUOTES.sub(" ", q)
    q = q.replace("(", " ").replace(")", " ")
    return _WS.sub(" ", q).strip()


def _to_arxiv(query: str) -> str:
    """arXiv wants ``all:"..."`` for free text, or field-prefixed terms."""
    # Already in arXiv field syntax? leave it.
    if re.search(r"\b(all|ti|au|abs|cat|jr):", query):
        return query
    freetext = _to_freetext(query)
    if not freetext:
        return query
    return f'all:"{freetext}"'


def _try_search_query(query: str, source: str) -> str | None:
    """Use the optional ``search-query`` package for a structured translation."""
    try:
        from search_query.parser import parse
    except Exception:
        return None

    platform_map = {
        "pubmed": "pubmed",
        "europepmc": "pubmed",  # closest available dialect
    }
    target = platform_map.get(source)
    if target is None:
        return None
    try:
        # search-query prints parser warnings straight to the streams; mute them.
        sink = io.StringIO()
        with contextlib.redirect_stderr(sink), contextlib.redirect_stdout(sink):
            parsed = parse(query)
            rendered = parsed.to_string(target)
        return str(rendered)
    except Exception as exc:  # noqa: BLE001 - best effort
        logger.debug("search-query translation failed for %s: %s", source, exc)
    return None


def translate_query(query: str, source: str) -> str:
    """
    Return ``query`` rewritten for ``source``.

    Never raises; unknown sources and any failure return ``query`` unchanged.
    """
    query = (query or "").strip()
    if not query:
        return query

    if source in _PASSTHROUGH:
        structured = _try_search_query(query, source)
        return structured or query

    if source == "arxiv":
        return _to_arxiv(query)

    if source in _FREETEXT:
        return _to_freetext(query) or query

    # Unknown source: leave the query alone.
    return query
