"""
MCP server for pyeuropepmc — unified literature search, citation graph traversal,
clinical trials, full-text indexing, figure extraction, bibliography tooling, and
optional LLM-powered analysis.

Built on the official Model Context Protocol Python SDK (``mcp``), so it gets
spec-compliant error semantics, concurrent async tool execution, and a choice of
transports — this single server works equally well wired into Claude Desktop over
stdio, or exposed to remote/non-Claude agents over streamable HTTP or SSE.

Usage:
    pyeuropepmc-mcp                              # stdio transport (default)
    pyeuropepmc-mcp --transport streamable-http  # network transport for remote agents
    python -m pyeuropepmc.mcp.server --help

Environment variables (fallbacks for the CLI flags below):
    PYEUROPEPMC_MCP_TRANSPORT   stdio | sse | streamable-http (default: stdio)
    PYEUROPEPMC_MCP_HOST        bind host for sse/streamable-http (default: 127.0.0.1)
    PYEUROPEPMC_MCP_PORT        bind port for sse/streamable-http (default: 8000)
    PYEUROPEPMC_MCP_LOG_LEVEL   DEBUG | INFO | WARNING | ERROR (default: INFO)

Tools:
    Core:
        unified_search       — Search across PubMed, arXiv, Semantic Scholar, OpenAlex,
                                ClinicalTrials.gov (auto-deduped)
        search_papers        — [Legacy] single-source Europe PMC search
        count_papers         — Hit count for a query (with the same filters)
        get_paper_details    — Paper metadata by ID (via Europe PMC)
        search_authors       — Author search (via Europe PMC)

    Citation:
        get_paper_citations  — Forward citations (cited-by)
        get_paper_references — Reference list (backward citations)
        citation_snowball    — Recursive citation graph walking (forward/backward/both)
        analyze_citations    — LLM-powered citation context analysis
        compare_citations    — LLM-powered paper comparison
        summarize_citations  — LLM-powered citation summary

    Clinical trials:
        clinical_trial_search — Search ClinicalTrials.gov by condition, intervention, or keyword

    Full-text & figures:
        fulltext_index_query  — Search local SQLite FTS5 full-text index
        get_paper_fulltext    — Structured full text of an open-access paper
        paper_figures         — Figures, tables and supplementary files of a PMC article
        epmc_status           — Is Europe PMC up? Probes the endpoints this server uses
        cache_status          — Entries, hits and misses of the server's caches (counts only)
        clear_cache           — Empty one of the in-memory caches
        validate_query        — Check a Europe PMC query for the mistakes it silently accepts
        build_query           — Build a query from structured input
        translate_query       — Rewrite a query for PubMed and other databases
        evaluate_query        — Recall of a query against papers you already know
        export_papers         — BibTeX, RIS, CSL-JSON, CSV, JSON or Markdown for a query/ids
        get_papers_batch      — Metadata of many papers (PMIDs, PMCIDs, DOIs) in one call
        get_papers_fulltext_batch — Full text of several open-access papers within a budget
        find_open_access      — Free copies of a paper via Unpaywall (needs UNPAYWALL_EMAIL)
        get_paper_annotations — Text-mined genes, chemicals, diseases, ... of a paper
        find_papers_by_entity — Papers in which an entity (gene, chemical, ...) is mentioned
        get_paper_data_links  — Datasets, accessions and database records linked to a paper
        get_paper_lab_links   — Links to a paper from third-party providers (BioStudies, ...)

    Screening & review:
        paper_screening       — PRISMA-compliant automated screening
        literature_review     — LLM-generated literature reviews
        research_question_analysis — Expand & analyze research questions (LLM)
        preprint_analysis     — Preprint quality assessment (LLM)
        knowledge_graph       — Build knowledge graphs (LLM)

    Bibliography:
        bib_parse_string  ref_resolve_doi   ref_resolve_pmid
        bib_validate      bib_to_ris        bib_to_csl
        bib_merge
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from collections.abc import Callable
import datetime
from functools import partial
from importlib.metadata import PackageNotFoundError, version as _pkg_version
import json
import logging
import os
import re
import sys
import threading
from typing import Annotated, Any, Generic, Literal, TypeVar, cast

import anyio
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
import requests

from pyeuropepmc import SearchClient
from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import (
    EuropePMCError,
    FullTextError,
    ParsingError,
    UnpaywallError,
)
from pyeuropepmc.features.literature.annotations import AnnotationsClient
from pyeuropepmc.features.literature.article import ArticleClient
from pyeuropepmc.mcp import (
    _annotations as ann,
    _batch as bm,
    _export as ex,
    _fulltext as ft,
    _links as lk,
    _openaccess as oa,
    _query as qm,
    _status as st,
)

# The pyeuropepmc modules below import without any extra: each one loads its
# optional libraries lazily. A flag that only records whether the module
# imported is therefore True in a bare install, and it is no evidence that a
# tool will work. Flags for tools that need an extra check that extra itself.

# Part of the core install
try:
    from pyeuropepmc.features.search import UnifiedSearch

    UNIFIED_AVAILABLE = True
except ImportError:
    UNIFIED_AVAILABLE = False

try:
    from pyeuropepmc.features.citations.walker import CitationWalker, SnowballingStrategy

    CITATION_WALKER_AVAILABLE = True
except ImportError:
    CITATION_WALKER_AVAILABLE = False

try:
    from pyeuropepmc.features.search import ClinicalTrialsClient

    CLINICAL_TRIALS_AVAILABLE = True
except ImportError:
    CLINICAL_TRIALS_AVAILABLE = False

try:
    from pyeuropepmc.features.fulltext.index import FullTextIndex

    FTS_AVAILABLE = True
except ImportError:
    FTS_AVAILABLE = False

try:
    from pyeuropepmc import FullTextClient
    from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

    FULLTEXT_AVAILABLE = True
except ImportError:
    FULLTEXT_AVAILABLE = False

try:
    from pyeuropepmc.features.fulltext.figures import FigureExtractor

    FIGURE_EXTRACTOR_AVAILABLE = True
except ImportError:
    FIGURE_EXTRACTOR_AVAILABLE = False

# LLM tools: need the `agentic` extra. Without LangChain the client imports,
# disables itself and the tools returned empty analyses instead of an error.
try:
    from pyeuropepmc.agentic.agents import SmartCitationAnalysis
    from pyeuropepmc.agentic.llm_client import LANGCHAIN_AVAILABLE, create_llm_client

    LLM_AVAILABLE = LANGCHAIN_AVAILABLE
except ImportError:
    LLM_AVAILABLE = False

# Bibliography tools: the bib_* tools parse BibTeX and need the `bibliography`
# extra (bibtexparser); the ref_* tools resolve identifiers over HTTP and need
# nothing beyond the core install.
try:
    from pyeuropepmc.features.bibliography import (
        BIBTEXPARSER_AVAILABLE,
        BibtexManager,
        CitationConverter,
        ReferenceResolver,
    )

    BIBLIOGRAPHY_AVAILABLE = True
except ImportError:
    BIBLIOGRAPHY_AVAILABLE = False
    BIBTEXPARSER_AVAILABLE = False


logger = logging.getLogger("pyeuropepmc.mcp")
logger.addHandler(logging.NullHandler())


def _server_version() -> str:
    try:
        return _pkg_version("pyeuropepmc")
    except PackageNotFoundError:
        return "0.0.0+unknown"


mcp = FastMCP(
    "pyeuropepmc-mcp",
    instructions=(
        "Tools for searching and analysing biomedical/scientific literature via "
        "Europe PMC and related sources (PubMed, arXiv, Semantic Scholar, OpenAlex, "
        "ClinicalTrials.gov). Start with `unified_search` for broad multi-source "
        "discovery, `get_paper_details` to resolve a single PMID/PMCID/DOI, and "
        "`citation_snowball` to walk a citation graph. Tools whose descriptions say "
        "'requires an LLM provider' need an LLM API key configured in the server's "
        "environment (see pyeuropepmc.agentic.llm_client) and will return a clear "
        "error otherwise. Availability of some tools depends on optional extras "
        "(`pip install pyeuropepmc[all]`) — an unavailable tool reports exactly what "
        "to install."
    ),
)
mcp._mcp_server.version = _server_version()


# ---------------------------------------------------------------------------
# Thread-safe lazy singletons
# ---------------------------------------------------------------------------
#
# Reused across calls instead of being rebuilt per request: this preserves
# each client's own rate limiting / caching / connection reuse (a *fresh*
# CitationWalker or SmartCitationAnalysis on every call defeats their
# internal throttling and analysis caches), and avoids paying construction
# cost on the hot path. Construction is guarded by a lock (double-checked)
# so concurrent tool calls under the HTTP/SSE transports can't race to build
# two instances.

_T = TypeVar("_T")


class _Lazy(Generic[_T]):
    """A thread-safe, lazily-constructed, resettable singleton."""

    def __init__(self, factory: Any) -> None:
        self._factory = factory
        self._value: _T | None = None
        self._lock = threading.Lock()

    def get(self) -> _T:
        if self._value is None:
            with self._lock:
                if self._value is None:
                    self._value = self._factory()
        return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = None

    def peek(self) -> _T | None:
        """The value if it has been built; never builds it (a status report must not create
        a client, and with it a cache, just to say that there is none)."""
        return self._value

    def set(self, value: _T) -> None:
        """Inject a pre-built value (tests: bypass the factory with a mock)."""
        with self._lock:
            self._value = value


_client_cache: _Lazy[SearchClient] = _Lazy(
    lambda: SearchClient(cache_config=CacheConfig(enabled=True))
)
_article_client_cache: _Lazy[ArticleClient] = _Lazy(
    lambda: ArticleClient(cache_config=CacheConfig(enabled=True))
)
_fulltext_client_cache: _Lazy[Any] = _Lazy(
    lambda: FullTextClient() if FULLTEXT_AVAILABLE else None
)
_fulltext_xml_cache = ft.XmlCache()
_status_cache = st.StatusCache()
_status_lock = threading.Lock()


def _make_unpaywall_client() -> Any:
    """An Unpaywall client with the contact e-mail from the environment.

    Unpaywall's terms ask every caller for an e-mail address, so there is deliberately no
    default: without one the tool says which variable to set. ``UNPAYWALL_EMAIL`` and
    ``CROSSREF_EMAIL`` are the names the rest of the library already reads.
    """
    from pyeuropepmc.features.enrich.sources.unpaywall_client import UnpaywallClient

    email = (os.environ.get("UNPAYWALL_EMAIL") or os.environ.get("CROSSREF_EMAIL") or "").strip()
    if not email:
        raise ToolError(
            "find_open_access needs a contact e-mail address for Unpaywall: set the "
            "UNPAYWALL_EMAIL environment variable of the MCP server (Unpaywall's terms ask "
            "for one; it is sent with each request)."
        )
    try:
        return UnpaywallClient(email)
    except UnpaywallError as exc:
        raise ToolError(f"UNPAYWALL_EMAIL is not usable: {exc}") from exc


_unpaywall_client_cache: _Lazy[Any] = _Lazy(_make_unpaywall_client)
_annotations_client_cache: _Lazy[AnnotationsClient] = _Lazy(
    lambda: AnnotationsClient(cache_config=CacheConfig(enabled=True))
)
_unified_cache: _Lazy[Any] = _Lazy(lambda: UnifiedSearch() if UNIFIED_AVAILABLE else None)
_citation_walker_cache: _Lazy[Any] = _Lazy(
    lambda: CitationWalker() if CITATION_WALKER_AVAILABLE else None
)
_clinical_trials_cache: _Lazy[Any] = _Lazy(
    lambda: ClinicalTrialsClient() if CLINICAL_TRIALS_AVAILABLE else None
)
_figure_extractor_cache: _Lazy[Any] = _Lazy(
    lambda: FigureExtractor() if FIGURE_EXTRACTOR_AVAILABLE else None
)
_llm_agent_cache: _Lazy[Any] = _Lazy(
    lambda: SmartCitationAnalysis(
        llm_client=create_llm_client(),
        literature_client=_get_client(),  # type: ignore[arg-type]
    )
)
_bib_manager_cache: _Lazy[Any] = _Lazy(lambda: BibtexManager() if BIBLIOGRAPHY_AVAILABLE else None)
_bib_converter_cache: _Lazy[Any] = _Lazy(
    lambda: CitationConverter() if BIBLIOGRAPHY_AVAILABLE else None
)
_bib_resolver_cache: _Lazy[Any] = _Lazy(
    lambda: ReferenceResolver() if BIBLIOGRAPHY_AVAILABLE else None
)


def _get_client() -> SearchClient:
    """Get (or create) the process-wide cached SearchClient instance."""
    return _client_cache.get()


def _get_unified() -> Any | None:
    """Get (or create) the process-wide cached UnifiedSearch instance."""
    return _unified_cache.get() if UNIFIED_AVAILABLE else None


def _get_article_client() -> ArticleClient:
    """Get (or create) the process-wide cached ArticleClient instance."""
    return _article_client_cache.get()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_serializable(obj: Any) -> Any:
    """Recursively convert non-serialisable objects to dicts/lists/strings."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_serializable(v) for k, v in vars(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_to_serializable(i) for i in obj]
    return obj


def _as_dict(obj: Any) -> dict[str, Any]:
    """``_to_serializable``, narrowed for call sites that are always dict-shaped
    (LLM agent results, single-record lookups) — keeps the tool signatures honest
    about their declared ``dict[str, Any]`` return type."""
    return cast(dict[str, Any], _to_serializable(obj))


_R = TypeVar("_R")


async def _run_blocking(fn: Callable[..., _R], *args: Any, **kwargs: Any) -> _R:
    """Run a blocking (network/disk) call in a worker thread.

    Every underlying client in this package (SearchClient, CitationWalker, ...)
    does synchronous I/O via ``requests``. Calling it directly from a tool
    coroutine would block the event loop for the duration of the request,
    stalling every other in-flight tool call. Offloading to a thread lets the
    server serve multiple agents/tool calls concurrently.
    """
    return await anyio.to_thread.run_sync(partial(fn, *args, **kwargs))


def _require_available(flag: bool, feature: str, extra: str | None = None) -> None:
    if flag:
        return
    if extra is None:
        # No extra would help: the module is part of the core install.
        raise ToolError(
            f"{feature} not available: it is part of the core install but failed to "
            "import. Reinstall pyeuropepmc."
        )
    raise ToolError(f"{feature} not available. Install with: pip install pyeuropepmc[{extra}]")


def _dedup_report(report: Any) -> dict[str, Any]:
    return {
        "total_input": report.total_input,
        "total_output": report.total_output,
        "duplicates_removed": report.duplicates_removed,
    }


def _paper_summary_from_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Build the minimal paper dict shared by LLM tools from a raw Europe PMC record."""
    return {
        "pmid": raw.get("pmid", ""),
        "pmcid": raw.get("pmcid", ""),
        "doi": raw.get("doi", ""),
        "title": raw.get("title", ""),
        "authors": [{"name": a.get("author", "")} for a in raw.get("authorInfo", [])],
        "publication_year": raw.get("firstPublicationYear", ""),
        "journal": raw.get("journalTitle", ""),
        "abstract": raw.get("abstract", ""),
    }


async def _fetch_paper_summary(pmid: str, client: SearchClient) -> dict[str, Any] | None:
    """Fetch a minimal paper dict for LLM tools, or None if not found."""
    results = await _run_blocking(client.search_all, f"ext_id:{pmid}", page_size=1, max_results=1)
    if not results:
        return None
    return _paper_summary_from_raw(results[0])


_PMID_RE = re.compile(r"^\d{1,9}$")
_PMCID_RE = re.compile(r"^PMC\d+$", re.IGNORECASE)
_DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
_SOURCE_RE = re.compile(r"^[A-Za-z]{2,5}$")


_PMC_ID_RE = re.compile(r"^(?:PMC)?(\d{1,10})$", re.IGNORECASE)


def _fulltext_query(pmcid: str, pmid: str, doi: str) -> str:
    """Europe PMC query that finds the one record behind a PMCID, PMID or DOI."""
    if pmcid:
        match = _PMC_ID_RE.match(pmcid.strip())
        if not match:
            raise ToolError(f"pmcid must look like PMC1234567, got {pmcid!r}")
        return f"PMCID:PMC{match.group(1)}"
    if pmid:
        if not pmid.strip().isdigit():
            raise ToolError(f"pmid must be digits only, got {pmid!r}")
        return f"EXT_ID:{pmid.strip()} AND SRC:MED"
    if doi:
        return f'DOI:"{doi.strip()}"'
    raise ToolError("One of pmcid, pmid, or doi is required")


async def _locate_fulltext(
    pmcid: str = "", pmid: str = "", doi: str = ""
) -> tuple[str, dict[str, Any]]:
    """Resolve any identifier to ``(PMCID, search record)`` and check the full text exists.

    Europe PMC answers a full-text request for an article outside its open-access set
    with HTTP 500 after several retries (about 20 s), which reads like an outage. The
    search record already says whether the XML is served (``isOpenAccess``), so ask
    that first and fail fast with a message that names the real reason.
    """
    query = _fulltext_query(pmcid, pmid, doi)
    results = await _run_blocking(
        _get_client().search_all, query, page_size=1, max_results=1, resultType="lite"
    )
    if not results:
        raise ToolError(f"No Europe PMC record found for {pmcid or pmid or doi!r}")
    record = _as_dict(results[0])
    resolved = str(record.get("pmcid") or "")
    if not resolved:
        raise ToolError(
            f"{pmcid or pmid or doi!r} has no PMCID: the article is not in PubMed Central, "
            "so Europe PMC has no full text for it"
        )
    if record.get("isOpenAccess") != "Y":
        raise ToolError(
            f"{resolved} is not Open Access: Europe PMC serves full-text XML only for "
            "open-access articles"
        )
    return resolved, record


async def _annotation_article_id(pmcid: str, pmid: str, doi: str) -> str:
    """The ``SRC:ID`` form the Annotations API wants; a bare PMCID is answered with HTTP 400."""
    if pmcid:
        match = _PMC_ID_RE.match(pmcid.strip())
        if not match:
            raise ToolError(f"pmcid must look like PMC1234567, got {pmcid!r}")
        return f"PMC:PMC{match.group(1)}"
    if pmid:
        if not pmid.strip().isdigit():
            raise ToolError(f"pmid must be digits only, got {pmid!r}")
        return f"MED:{pmid.strip()}"
    if doi:
        results = await _run_blocking(
            _get_client().search_all,
            f'DOI:"{doi.strip()}"',
            page_size=1,
            max_results=1,
            resultType="lite",
        )
        if not results:
            raise ToolError(f"No Europe PMC record found for DOI {doi!r}")
        record = _as_dict(results[0])
        ext_id = str(record.get("id") or "").strip()
        if not ext_id:
            raise ToolError(f"The Europe PMC record for DOI {doi!r} has no id")
        return f"{record.get('source') or 'MED'}:{ext_id}"
    raise ToolError("One of pmcid, pmid, or doi is required")


def _fulltext_error(exc: FullTextError, pmcid: str) -> ToolError:
    code = exc.error_code
    status = exc.context.get("status_code") if isinstance(exc.context, dict) else None
    if code == ErrorCodes.FULL003:
        return ToolError(f"Europe PMC has no full-text XML for {pmcid}")
    if code == ErrorCodes.FULL008:
        return ToolError(f"Access to the full text of {pmcid} is restricted")
    if code == ErrorCodes.FULL005 and isinstance(status, int) and status >= 500:
        return ToolError(
            f"Europe PMC could not serve the full text of {pmcid} (HTTP {status}). "
            "It is marked open access, so this is likely temporary; retry later."
        )
    return ToolError(str(exc))


async def _fulltext_xml(pmcid: str) -> str:
    """The article's full-text XML, fetched once and kept for the next tool call."""
    cached = _fulltext_xml_cache.get(pmcid)
    if cached is not None:
        return cached
    _require_available(FULLTEXT_AVAILABLE, "FullTextClient")
    client = _fulltext_client_cache.get()
    try:
        xml: str = await _run_blocking(client.get_fulltext_content, pmcid, "xml")
    except FullTextError as exc:
        raise _fulltext_error(exc, pmcid) from exc
    if not xml:
        raise ToolError(f"Europe PMC returned an empty full text for {pmcid}")
    _fulltext_xml_cache.set(pmcid, xml)
    return xml


def _with_filters(
    query: str,
    *,
    date_from: str = "",
    date_to: str = "",
    open_access: bool = False,
    has_fulltext: bool = False,
    source: str = "",
) -> str:
    """AND Europe PMC field filters onto ``query``; with no filter it is returned unchanged.

    The clauses come from ``_query.filter_clauses``, the one place that writes them, so a
    filter means the same here, in ``build_query`` and in anything built on the query builder.
    """
    try:
        return qm.apply_filters(
            query,
            date_from=date_from,
            date_to=date_to,
            open_access=open_access,
            has_fulltext=has_fulltext,
            source=source,
        )
    except qm.QueryProblem as exc:
        raise ToolError(str(exc)) from exc


def _s2_identifier(identifier: str) -> str:
    """Prefix a bare PMID/PMCID/DOI the way Semantic Scholar expects.

    S2 only recognises an external ID when it carries its type (``PMID:123``); a bare
    ``123`` is treated as a paper ID and resolves to nothing. Anything already prefixed,
    and S2's own 40-hex paper IDs, pass through untouched.
    """
    ident = identifier.strip()
    if _PMID_RE.match(ident):
        return f"PMID:{ident}"
    if _PMCID_RE.match(ident):
        return f"PMCID:{ident.upper()}"
    if ident.startswith("10."):
        return f"DOI:{ident}"
    return ident


def _ro(title: str, *, local: bool = False, idempotent: bool = True) -> ToolAnnotations:
    """Annotations for a read-only tool (never mutates anything the client owns)."""
    return ToolAnnotations(
        title=title,
        readOnlyHint=True,
        openWorldHint=not local,
        idempotentHint=idempotent,
    )


# ---------------------------------------------------------------------------
# Core search tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_ro("Unified literature search"))
async def unified_search(
    query: Annotated[str, Field(description="Search query")],
    sources: Annotated[
        list[str] | None,
        Field(
            description="Sources to query, e.g. ['europepmc', 'arxiv', 'semantic_scholar', "
            "'openalex', 'clinicaltrials']. Defaults to the server's configured source set."
        ),
    ] = None,
    limit: Annotated[int, Field(description="Max results per source", ge=1, le=200)] = 25,
    ctx: Context[Any, Any, Any] | None = None,
) -> dict[str, Any]:
    """Search across multiple literature sources (PubMed, arXiv, Semantic Scholar, OpenAlex,
    ClinicalTrials.gov) in parallel, with automatic cross-source deduplication."""
    _require_available(UNIFIED_AVAILABLE, "UnifiedSearch")
    unified = _get_unified()
    assert unified is not None  # guaranteed by _require_available above

    if ctx:
        await ctx.info(f"Searching {sources or 'default sources'} for {query!r}")
    results, report = await _run_blocking(unified.search, query, sources=sources, limit=limit)
    if ctx:
        await ctx.info(
            f"{report.total_output} results after removing {report.duplicates_removed} duplicates"
        )
    return {
        "results": [_to_serializable(r) for r in results],
        "dedup": _dedup_report(report),
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="[Legacy] Search Europe PMC",
        readOnlyHint=True,
        openWorldHint=True,
        idempotentHint=True,
    )
)
async def search_papers(
    query: Annotated[str, Field(description="Search query")],
    limit: Annotated[int, Field(description="Number of results", ge=1, le=1000)] = 25,
    sort: Annotated[str, Field(description="Sort order, e.g. 'cited' or 'date'")] = "",
    result_type: Annotated[str, Field(description="Europe PMC result type")] = "core",
    date_from: Annotated[
        str, Field(description="First publication date, from (YYYY, YYYY-MM or YYYY-MM-DD)")
    ] = "",
    date_to: Annotated[
        str, Field(description="First publication date, to (YYYY, YYYY-MM or YYYY-MM-DD)")
    ] = "",
    open_access: Annotated[bool, Field(description="Only open-access articles")] = False,
    has_fulltext: Annotated[bool, Field(description="Only articles with full text")] = False,
    source: Annotated[
        str, Field(description="Restrict to one source, e.g. MED, PMC or PPR (preprints)")
    ] = "",
    synonym: Annotated[bool, Field(description="Expand the query with MeSH synonyms")] = False,
) -> list[dict[str, Any]]:
    """Search Europe PMC for papers (single source — prefer `unified_search` for
    multi-source coverage). At most ``limit`` records are fetched; optional filters
    narrow the query by date, open access, full text availability and source."""
    client = _get_client()
    full_query = _with_filters(
        query,
        date_from=date_from,
        date_to=date_to,
        open_access=open_access,
        has_fulltext=has_fulltext,
        source=source,
    )
    kwargs: dict[str, Any] = {"page_size": limit, "max_results": limit, "resultType": result_type}
    if sort:
        kwargs["sort"] = sort
    if synonym:
        kwargs["synonym"] = True
    results = await _run_blocking(client.search_all, full_query, **kwargs)
    return [_to_serializable(r) for r in results]


@mcp.tool(annotations=_ro("Count papers"))
async def count_papers(
    query: Annotated[str, Field(description="Search query")],
    date_from: Annotated[
        str, Field(description="First publication date, from (YYYY, YYYY-MM or YYYY-MM-DD)")
    ] = "",
    date_to: Annotated[
        str, Field(description="First publication date, to (YYYY, YYYY-MM or YYYY-MM-DD)")
    ] = "",
    open_access: Annotated[bool, Field(description="Only open-access articles")] = False,
    has_fulltext: Annotated[bool, Field(description="Only articles with full text")] = False,
    source: Annotated[
        str, Field(description="Restrict to one source, e.g. MED, PMC or PPR (preprints)")
    ] = "",
    synonym: Annotated[bool, Field(description="Expand the query with MeSH synonyms")] = False,
) -> dict[str, Any]:
    """Number of Europe PMC records matching a query, without fetching them. Use it to
    size a search before choosing ``limit`` for `search_papers`."""
    client = _get_client()
    full_query = _with_filters(
        query,
        date_from=date_from,
        date_to=date_to,
        open_access=open_access,
        has_fulltext=has_fulltext,
        source=source,
    )
    try:
        extra: dict[str, Any] = {"synonym": True} if synonym else {}
        count = await _run_blocking(client.get_hit_count, full_query, **extra)
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc
    return {"query": full_query, "hit_count": count}


@mcp.tool(annotations=_ro("Get paper details"))
async def get_paper_details(
    pmid: Annotated[str, Field(description="PubMed ID")] = "",
    pmcid: Annotated[str, Field(description="PMCID")] = "",
    doi: Annotated[str, Field(description="DOI")] = "",
) -> dict[str, Any]:
    """Get detailed paper information by PMID, PMCID, or DOI (Europe PMC)."""
    if pmid:
        query = f"ext_id:{pmid}"
    elif pmcid:
        query = f"ext_id:{pmcid}"
    elif doi:
        query = f"doi:{doi}"
    else:
        raise ToolError("At least one ID (pmid, pmcid, doi) is required")

    client = _get_client()
    results = await _run_blocking(client.search_all, query, page_size=1, max_results=1)
    if not results:
        raise ToolError("No results found")
    return _as_dict(results[0])


@mcp.tool(annotations=_ro("Search authors"))
async def search_authors(
    query: Annotated[str, Field(description="Author name or affiliation")],
    limit: Annotated[int, Field(description="Number of results", ge=1, le=1000)] = 25,
) -> list[dict[str, Any]]:
    """Search for authors in Europe PMC."""
    client = _get_client()
    results = await _run_blocking(
        client.search_all, f'AUTH:"{query}"', page_size=limit, max_results=limit
    )
    return [_to_serializable(r) for r in results]


# ---------------------------------------------------------------------------
# Citation tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_ro("Get paper citations"))
async def get_paper_citations(
    pmid: Annotated[str, Field(description="Article ID, usually a PubMed ID")],
    limit: Annotated[int, Field(description="Max citing papers to return", ge=1, le=1000)] = 100,
    source: Annotated[
        str, Field(description="Europe PMC source code of the ID: MED (PMID), PMC or PPR")
    ] = "MED",
) -> list[dict[str, Any]]:
    """Get papers that cite a given paper (Europe PMC)."""
    if not _SOURCE_RE.match(source):
        raise ToolError(f"source must be a short code such as MED, PMC or PPR, got {source!r}")
    client = _get_article_client()
    # The citations endpoint works for every source. A ``CITES:`` search only matches MED
    # records, and ``CITED:`` filters on the citation count, so it matches nothing here.
    try:
        response = await _run_blocking(
            client.get_citations, source.upper(), pmid, page=1, page_size=limit
        )
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc
    citations = (response.get("citationList") or {}).get("citation") or []
    return [_to_serializable(c) for c in citations]


@mcp.tool(annotations=_ro("Get paper references"))
async def get_paper_references(
    article_id: Annotated[str, Field(description="Article ID, e.g. a PMID or PMCID")],
    source: Annotated[
        str, Field(description="Europe PMC source code: MED (PMID), PMC (PMCID) or PPR")
    ] = "MED",
    limit: Annotated[int, Field(description="Max references to return", ge=1, le=1000)] = 100,
) -> dict[str, Any]:
    """Get the reference list of a paper (backward citations, Europe PMC)."""
    client = _get_article_client()
    try:
        response = await _run_blocking(
            client.get_references, source.upper(), article_id, page=1, page_size=limit
        )
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc
    return _as_dict(response)


@mcp.tool(annotations=_ro("Citation snowball walk"))
async def citation_snowball(
    identifier: Annotated[str, Field(description="Paper ID (PMID, DOI, or Semantic Scholar ID)")],
    strategy: Annotated[
        Literal["forward", "backward", "both"],
        Field(description="Snowball direction"),
    ] = "forward",
    max_papers: Annotated[int, Field(description="Max papers per level", ge=1, le=1000)] = 50,
    max_depth: Annotated[int, Field(description="Recursion depth (0 = no limit)", ge=0)] = 1,
    min_citations: Annotated[int, Field(description="Minimum citation count filter", ge=0)] = 0,
    ctx: Context[Any, Any, Any] | None = None,
) -> dict[str, Any]:
    """Walk the citation graph forward (cited-by), backward (references), or both, with
    configurable depth and a minimum-citation-count filter."""
    _require_available(CITATION_WALKER_AVAILABLE, "CitationWalker")
    walker = _citation_walker_cache.get()

    strategy_map = {
        "forward": SnowballingStrategy.FORWARD,
        "backward": SnowballingStrategy.BACKWARD,
        "both": SnowballingStrategy.BOTH,
    }

    if ctx:
        await ctx.info(f"Snowballing {strategy} from {identifier} (depth={max_depth})")
    results, report = await _run_blocking(
        walker.snowball,
        identifier=_s2_identifier(identifier),
        strategy=strategy_map[strategy],
        max_papers=max_papers,
        max_depth=max_depth,
        min_citations=min_citations,
    )
    return {
        "paper_count": len(results),
        "dedup": _dedup_report(report),
        "papers": [_to_serializable(r) for r in results],
    }


# ---------------------------------------------------------------------------
# Clinical trials
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_ro("Search ClinicalTrials.gov"))
async def clinical_trial_search(
    query: Annotated[str, Field(description="Free-text search query")] = "",
    condition: Annotated[str | None, Field(description="Medical condition filter")] = None,
    intervention: Annotated[str | None, Field(description="Intervention/treatment filter")] = None,
    limit: Annotated[int, Field(description="Max results", ge=1, le=1000)] = 25,
    status: Annotated[
        str | None,
        Field(description="Recruitment status filter, e.g. ACTIVE, COMPLETED, RECRUITING"),
    ] = None,
) -> dict[str, Any]:
    """Search ClinicalTrials.gov for studies by condition, intervention, or free-text query."""
    _require_available(CLINICAL_TRIALS_AVAILABLE, "ClinicalTrialsClient")
    client_ = _clinical_trials_cache.get()

    if condition and intervention:
        results = await _run_blocking(client_.search_by_condition, condition, limit=limit * 2)
        intervention_lower = intervention.lower()
        results = [
            r
            for r in results
            if intervention_lower in ((r.extra_metadata or {}).get("interventions") or "").lower()
        ][:limit]
    elif condition:
        results = await _run_blocking(client_.search_by_condition, condition, limit=limit)
    elif intervention:
        results = await _run_blocking(client_.search_by_intervention, intervention, limit=limit)
    else:
        results = await _run_blocking(client_.search, query, limit=limit)

    if status:
        results = [
            r
            for r in results
            if (r.extra_metadata or {}).get("status", "").upper() == status.upper()
        ]

    return {
        "trial_count": len(results),
        "trials": [_to_serializable(r) for r in results],
    }


# ---------------------------------------------------------------------------
# Full-text & figures
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_ro("Query local full-text index", local=True))
async def fulltext_index_query(
    query: Annotated[str, Field(description="Full-text search query")],
    limit: Annotated[int, Field(description="Max results", ge=1, le=1000)] = 25,
    index_path: Annotated[
        str | None, Field(description="Path to the SQLite index file (optional)")
    ] = None,
) -> dict[str, Any]:
    """Search the local SQLite FTS5 full-text index for papers whose full text matches
    a query.

    A fresh index handle is opened per call rather than cached: SQLite connections are
    only safe to use from the thread that created them, and each call may run on a
    different worker thread.
    """
    _require_available(FTS_AVAILABLE, "FullTextIndex")

    def _query() -> dict[str, Any]:
        idx = FullTextIndex(db_path=index_path) if index_path else FullTextIndex()
        results = idx.search(query, limit=limit)
        stats = idx.stats() if hasattr(idx, "stats") else {}
        return {"results": results, "stats": stats}

    return await _run_blocking(_query)


@mcp.tool(annotations=_ro("Get paper full text"))
async def get_paper_fulltext(
    pmcid: Annotated[str, Field(description="PMC ID of the article, e.g. PMC1234567")] = "",
    pmid: Annotated[str, Field(description="PubMed ID (alternative to pmcid)")] = "",
    doi: Annotated[str, Field(description="DOI (alternative to pmcid)")] = "",
    format: Annotated[
        Literal["markdown", "sections", "outline"],
        Field(
            description="markdown: readable text with tables (default). sections: typed "
            "blocks (paragraph, heading, list, figure, table) for programmatic use. "
            "outline: only section titles, block counts and sizes - use it first on a "
            "long paper to pick which sections to request."
        ),
    ] = "markdown",
    sections: Annotated[
        list[str] | None,
        Field(
            description="Only these sections: case-insensitive substrings of a section "
            "title, e.g. ['methods', 'results']. Default: all sections."
        ),
    ] = None,
    include_references: Annotated[
        bool, Field(description="Also return the parsed reference list (DOI/PMID per entry)")
    ] = False,
    max_chars: Annotated[
        int,
        Field(
            description="Cut the content at a block boundary after this many characters",
            ge=1000,
            le=500000,
        ),
    ] = 30000,
) -> dict[str, Any]:
    """Fetch the structured full text of an open-access paper from Europe PMC.

    Returns metadata, the list of available section titles, and the content in the
    requested format. When the content is longer than ``max_chars`` it is cut at a block
    boundary and ``truncated`` is true: ask again with ``sections`` for the part you need.
    Only open-access articles have full text; anything else fails with the reason.
    """
    _require_available(FULLTEXT_AVAILABLE, "FullTextXMLParser")
    resolved, record = await _locate_fulltext(pmcid, pmid, doi)
    xml = await _fulltext_xml(resolved)

    def _build() -> dict[str, Any]:
        parser = FullTextXMLParser(xml)
        all_sections = parser.get_full_text_sections_structured()
        chosen = ft.select_sections(all_sections, sections)
        meta = parser.extract_metadata()
        journal = meta.get("journal")
        license_info = parser.extract_license()
        result: dict[str, Any] = {
            "pmcid": resolved,
            "pmid": record.get("pmid") or meta.get("pmid") or "",
            "doi": record.get("doi") or meta.get("doi") or "",
            "title": meta.get("title") or record.get("title") or "",
            "journal": journal.get("title") if isinstance(journal, dict) else journal,
            "pub_date": meta.get("pub_date"),
            "license": (license_info.get("type") or license_info.get("url") or None)
            if isinstance(license_info, dict)
            else None,
            "sections_available": ft.section_titles(all_sections),
            "format": format,
        }
        if sections and not chosen:
            raise ToolError(
                f"No section matches {sections!r}. Available sections: "
                f"{result['sections_available']}"
            )
        if format == "outline":
            content: Any = ft.outline(chosen)
            total = returned = len(json.dumps(content, separators=(",", ":")))
            truncated = False
        else:
            units = ft.render_units(chosen, format)
            kept, total, truncated = ft.take_within(
                units, max_chars, fit_first=ft.shrink_block_json if format == "sections" else None
            )
            if format == "markdown":
                content = ft.units_to_markdown(kept)
            else:
                content = ft.units_to_sections(chosen, kept)
            returned = sum(len(u[2]) + 2 for u in kept)
        result.update(
            content=content,
            total_chars=total,
            returned_chars=returned,
            truncated=truncated,
        )
        refs = parser.extract_references()
        result["reference_count"] = len(refs)
        if include_references:
            result["references"] = [_to_serializable(r) for r in refs]
        return result

    try:
        return await _run_blocking(_build)
    except ParsingError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(annotations=_ro("Extract paper figures"))
async def paper_figures(
    pmcid: Annotated[str, Field(description="PMC ID of the article, e.g. PMC1234567")] = "",
    pmid: Annotated[str, Field(description="PubMed ID (alternative to pmcid)")] = "",
    doi: Annotated[str, Field(description="DOI (alternative to pmcid)")] = "",
    include_tables: Annotated[bool, Field(description="Include <table-wrap> elements")] = True,
    include_supplements: Annotated[
        bool, Field(description="Include supplementary material")
    ] = True,
) -> dict[str, Any]:
    """Extract figures, tables and supplementary files from a PMC Open Access article.

    Each item carries its label, caption and the Europe PMC URL its file can be
    downloaded from. A figure supplement also names the figure it belongs to.
    """
    _require_available(FIGURE_EXTRACTOR_AVAILABLE, "FigureExtractor")
    if not any([pmcid, pmid, doi]):
        raise ToolError("One of pmcid, pmid, or doi is required")

    extractor = _figure_extractor_cache.get()
    resolved, _record = await _locate_fulltext(pmcid, pmid, doi)
    xml = await _fulltext_xml(resolved)
    try:
        figures = await _run_blocking(
            extractor.extract_from_xml,
            xml,
            pmcid=resolved,
            include_tables=include_tables,
            include_supplements=include_supplements,
        )
    except ParsingError as exc:
        # A refused document is not "no figures": say so instead of reporting 0.
        raise ToolError(str(exc)) from exc

    items = [_as_dict(f) for f in figures]
    return {
        "figure_count": len(items),
        "counts_by_type": dict(Counter(item.get("figure_type", "") for item in items)),
        "figures": items,
    }


# ---------------------------------------------------------------------------
# Service status and caches
# ---------------------------------------------------------------------------


def _status_snapshot() -> dict[str, Any]:
    """The service status, probed at most once per ``StatusCache.ttl`` however often it is asked.

    The lock is held across the probe so that several callers arriving together wait for one
    probe instead of each starting their own.
    """
    with _status_lock:
        cached = _status_cache.get()
        if cached is not None:
            result, age = cached
            return {**result, "cached": True, "age_seconds": round(age)}
        results = st.probe(requests.get)
        result = st.build_result(results, datetime.datetime.now(datetime.timezone.utc))
        _status_cache.set(result)
        return {**result, "cached": False, "age_seconds": 0}


@mcp.tool(annotations=_ro("Europe PMC service status"))
async def epmc_status() -> dict[str, Any]:
    """Is Europe PMC up right now? Probes the endpoints this server depends on (search, full
    text, citations, annotations) and returns ok, degraded (some fail), down (none answers) or
    unknown (only 4xx answers: a blocked probe or a moved endpoint), with the HTTP status and
    the time in milliseconds of each. Use it before retrying a tool that failed with a network
    error, a timeout or a 5xx. The answer is kept for 30 seconds, so asking again does not
    probe again (`cached` says so), and it contains no URLs or response bodies.
    """
    return await _run_blocking(_status_snapshot)


def _client_cache_stats(lazy: _Lazy[Any]) -> dict[str, Any]:
    """Counts for one client's cache; ``created: false`` if the client was never needed."""
    client = lazy.peek()
    if client is None:
        return {"created": False, "entries": 0}
    try:
        stats = client.get_cache_stats()
        overall = stats.get("overall", {})
        layer = stats.get("layers", {}).get("l1", {})
    except Exception:  # noqa: BLE001 - a broken cache must not break the report
        return {"created": True, "error": "statistics unavailable"}
    return {
        "created": True,
        "entries": layer.get("entry_count", 0),
        "max_entries": layer.get("maxsize"),
        "size_bytes": layer.get("size_bytes"),
        "hits": overall.get("hits", 0),
        "misses": overall.get("misses", 0),
        "hit_rate": overall.get("hit_rate"),
    }


@mcp.tool(annotations=_ro("Cache status", local=True))
async def cache_status() -> dict[str, Any]:
    """How full are the server's caches and how often do they help? For the search, article and
    annotation clients and for the full-text XML cache: entries, capacity, size, hits, misses
    and hit rate. Counts only: no cache keys (they can contain query text), no cached content
    and no file paths.
    """
    return {
        "search": _client_cache_stats(_client_cache),
        "article": _client_cache_stats(_article_client_cache),
        "annotations": _client_cache_stats(_annotations_client_cache),
        "xml": _fulltext_xml_cache.stats(),
        "service_status": {"cached": _status_cache.get() is not None},
    }


_CACHE_SCOPES: dict[str, _Lazy[Any]] = {
    "search": _client_cache,
    "article": _article_client_cache,
    "annotations": _annotations_client_cache,
}


def _clear_one(scope: str) -> dict[str, Any]:
    if scope == "xml":
        return {"cleared": True, "entries_dropped": _fulltext_xml_cache.clear()}
    client = _CACHE_SCOPES[scope].peek()
    if client is None:
        return {"cleared": False, "entries_dropped": 0, "reason": "nothing cached yet"}
    before = _client_cache_stats(_CACHE_SCOPES[scope]).get("entries", 0)
    ok = bool(client.clear_cache())
    return {"cleared": ok, "entries_dropped": before if ok else 0}


@mcp.tool(
    annotations=ToolAnnotations(
        title="Clear a server cache",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def clear_cache(
    scope: Annotated[
        Literal["search", "article", "annotations", "xml", "all"],
        Field(
            description="Which cache: search (search results, batch lookups, counts), article "
            "(citations, references), annotations, xml (downloaded full text) or all of them"
        ),
    ],
) -> dict[str, Any]:
    """Empty one of the server's in-memory caches, so that the next call asks Europe PMC again.
    Only worth doing when you suspect a cached answer is stale (the caches hold results for a
    day); every cleared entry has to be fetched again, which is load on Europe PMC. It changes
    server state, so a client may ask for approval. It never touches files on disk.
    """
    scopes = ["search", "article", "annotations", "xml"] if scope == "all" else [scope]
    return {
        "scope": scope,
        "results": {name: _clear_one(name) for name in scopes},
    }


# ---------------------------------------------------------------------------
# Query tools
# ---------------------------------------------------------------------------


def _problems(issues: list[qm.Issue]) -> str:
    return "; ".join(f"{i.message}" for i in issues if i.severity == "error")


@mcp.tool(annotations=_ro("Validate a Europe PMC query", local=True))
async def validate_query(
    query: Annotated[str, Field(description="A Europe PMC search query")],
) -> dict[str, Any]:
    """Check a Europe PMC query before running it. Europe PMC does not reject a malformed query,
    it answers a different one: an unclosed parenthesis or a dangling operator is dropped
    silently, an unknown field, a flag that is not y/n and a date range with a missing or
    reversed bound match nothing, and AND mixed with OR without parentheses is not read as
    either grouping. Each problem comes with its position. `valid` is false when there are
    errors; warnings are things worth a second look. `normalized` is the cleaned-up query
    (capital operators, explicit AND) and is only given for a query without errors.
    """
    result = qm.lint(query)
    return {
        "valid": not result.errors,
        "problems": [i.to_dict() for i in result.errors],
        "warnings": [i.to_dict() for i in result.warnings],
        "normalized": result.normalized,
    }


@mcp.tool(annotations=_ro("Build a Europe PMC query", local=True))
async def build_query(
    all_of: Annotated[
        list[str] | None,
        Field(
            description="Terms that must all match. A plain word or phrase is searched as "
            "written ('heart attack' becomes a phrase); write FIELD:value, a quoted string "
            "or a parenthesised expression to say more, e.g. 'TITLE:crispr'."
        ),
    ] = None,
    any_of: Annotated[
        list[str] | None, Field(description="Terms of which at least one must match")
    ] = None,
    none_of: Annotated[list[str] | None, Field(description="Terms that must not match")] = None,
    date_from: Annotated[
        str, Field(description="First publication date, from (YYYY, YYYY-MM or YYYY-MM-DD)")
    ] = "",
    date_to: Annotated[
        str, Field(description="First publication date, to (YYYY, YYYY-MM or YYYY-MM-DD)")
    ] = "",
    open_access: Annotated[bool, Field(description="Only open-access records")] = False,
    has_fulltext: Annotated[bool, Field(description="Only records with full text")] = False,
    source: Annotated[
        str, Field(description="Only this source, e.g. MED, PMC or PPR (preprints)")
    ] = "",
    cites: Annotated[str, Field(description="Only records that cite this PMID")] = "",
) -> dict[str, Any]:
    """Build a Europe PMC query from structured input instead of writing syntax by hand, and
    check the result. Returns the query, a plain-language explanation of what it asks for, and
    any warnings. At least one of all_of, any_of or a filter is needed (none_of alone would
    match almost everything). The same filters are available on `search_papers`.
    """
    try:
        query, explanation = qm.build(
            all_of or [],
            any_of or [],
            none_of or [],
            date_from=date_from,
            date_to=date_to,
            open_access=open_access,
            has_fulltext=has_fulltext,
            source=source,
            cites=cites,
        )
    except qm.QueryProblem as exc:
        raise ToolError(str(exc)) from exc
    result = qm.lint(query)
    if result.errors:
        raise ToolError(
            f"The query built from this input is not valid: {_problems(result.issues)}"
        )
    return {
        "query": query,
        "explanation": explanation,
        "warnings": [i.to_dict() for i in result.warnings],
    }


_FREE_TEXT_TARGETS = ("arxiv", "openalex", "semantic_scholar", "crossref")


@mcp.tool(annotations=_ro("Translate a Europe PMC query", local=True))
async def translate_query(
    query: Annotated[str, Field(description="A Europe PMC search query")],
    target: Annotated[
        Literal["pubmed", "arxiv", "openalex", "semantic_scholar", "crossref"],
        Field(description="Database to translate the query for"),
    ] = "pubmed",
) -> dict[str, Any]:
    """Rewrite a Europe PMC query for another database. For PubMed the field codes map where
    they have an equivalent (TITLE[ti], AUTH[au], JOURNAL[ta], dates[dp], ...); a construct
    that does not map (CITES, HAS_*, CITED, ...) is left out and named in `warnings` and
    `dropped`, and `exact` is false whenever the translation is narrower, broader or only
    approximate. The other targets search free text, so field codes and operators are stripped
    and `exact` is always false. A query with errors is refused; see `validate_query`.
    """
    result = qm.lint(query)
    if result.errors:
        raise ToolError(f"Fix the query first: {_problems(result.issues)}")
    if target == "pubmed":
        translation = qm.translate_pubmed(query)
        return {
            "target": target,
            "query": translation.query,
            "exact": translation.exact,
            "warnings": translation.warnings,
            "dropped": translation.dropped,
        }
    from pyeuropepmc.features.search.query_translation import translate_query as to_source

    return {
        "target": target,
        "query": to_source(result.normalized or query, target),
        "exact": False,
        "warnings": [
            f"{target} searches free text: field codes, operators and quotation marks were "
            "removed, so this is a keyword approximation of the original."
        ],
        "dropped": [],
    }


async def _seed_hits(query: str, pmids: list[str]) -> tuple[set[str], set[str]]:
    """Of ``pmids``, those Europe PMC knows and, among them, those the query matches."""
    client = _get_client()
    known: set[str] = set()
    matched: set[str] = set()
    for start in range(0, len(pmids), bm.CHUNK_SIZE):
        chunk = pmids[start : start + bm.CHUNK_SIZE]
        ids = "(" + " OR ".join(f"(EXT_ID:{p} AND SRC:MED)" for p in chunk) + ")"
        for found, text in ((known, ids), (matched, f"({query}) AND {ids}")):
            results = await _run_blocking(
                client.search_all,
                text,
                page_size=len(chunk),
                max_results=len(chunk),
                resultType="idlist",
            )
            found.update(
                str(r.get("pmid") or r.get("id"))
                for r in (_as_dict(x) for x in results)
                if r.get("source", "MED") == "MED"
            )
    return known, matched


def _pmid_list(values: list[str], label: str) -> list[str]:
    bad = [v for v in values if not str(v).strip().isdigit()]
    if bad:
        raise ToolError(f"{label} must be PMIDs (digits only), got {bad[0]!r}")
    return list(dict.fromkeys(str(v).strip() for v in values))


@mcp.tool(annotations=_ro("Evaluate a query against known papers"))
async def evaluate_query(
    query: Annotated[str, Field(description="A Europe PMC search query")],
    included_pmids: Annotated[
        list[str],
        Field(description="PMIDs the query should find", min_length=1, max_length=200),
    ],
    excluded_pmids: Annotated[
        list[str] | None,
        Field(description="PMIDs the query should not find", max_length=200),
    ] = None,
) -> dict[str, Any]:
    """Score a Europe PMC query against papers you already know, for systematic-review work:
    recall (how many of the included PMIDs it finds) and how many excluded ones it still
    finds, with the PMIDs it misses. This runs the query on Europe PMC itself, so it measures
    what the search really returns, not a local reading of the syntax. PMIDs that Europe PMC
    does not know are reported apart and left out of the scores. A query with errors is
    refused; see `validate_query`.
    """
    result = qm.lint(query)
    if result.errors:
        raise ToolError(f"Fix the query first: {_problems(result.issues)}")
    included = _pmid_list(included_pmids, "included_pmids")
    excluded = _pmid_list(excluded_pmids or [], "excluded_pmids")
    try:
        inc_known, inc_matched = await _seed_hits(query, included)
        exc_known, exc_matched = await _seed_hits(query, excluded) if excluded else (set(), set())
        total = await _run_blocking(_get_client().get_hit_count, query)
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc

    recall = len(inc_matched) / len(inc_known) if inc_known else None
    found_any = len(inc_matched) + len(exc_matched)
    precision = len(inc_matched) / found_any if found_any else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return {
        "total_hits": total,
        "included": {
            "known": len(inc_known),
            "matched": len(inc_matched),
            "recall": recall,
            "missed": sorted(inc_known - inc_matched),
            "unknown_to_europepmc": sorted(set(included) - inc_known),
        },
        "excluded": {
            "known": len(exc_known),
            "matched": len(exc_matched),
            "matched_pmids": sorted(exc_matched),
            "unknown_to_europepmc": sorted(set(excluded) - exc_known),
        },
        "precision_on_seeds": precision,
        "f1_on_seeds": f1,
        "warnings": [i.to_dict() for i in result.warnings],
    }


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

_EXPORT_FORMATS = ("bibtex", "ris", "csl-json", "csv", "json", "markdown")


def _export_units(
    fmt: str, records: list[dict[str, Any]], fields: tuple[str, ...], abstract: bool
) -> tuple[str, list[str], str, str, list[ex.Paper]]:
    """``(header, one text per record, separator, footer, papers)`` for a format.

    Every record becomes one unit so that an export can be cut at a record boundary and still
    be valid: a BibTeX or RIS file stays parseable, a JSON array stays closed.
    """
    papers: list[ex.Paper] = []
    if fmt in ("bibtex", "ris", "csl-json"):
        papers = [ex.to_paper(r) for r in records]
        if not abstract:
            for paper in papers:
                paper.abstract = ""
        ex.assign_keys(papers)
    if fmt == "bibtex":
        return "", [ex.bibtex_entry(p) for p in papers], "\n\n", "", papers
    if fmt == "ris":
        return "", [ex.ris_entry(p) for p in papers], "\n\n", "", papers
    if fmt == "csl-json":
        return "[", [ex.csl_text(ex.csl_item(p)) for p in papers], ",\n", "]", papers
    rows = ex.table_rows(records, fields)
    if fmt == "json":
        return "[", [json.dumps(r, ensure_ascii=False) for r in rows], ",\n", "]", papers
    values = [[r[f] for f in fields] for r in rows]
    if fmt == "csv":
        return ex.csv_row(list(fields)), [ex.csv_row(v) for v in values], "\n", "", papers
    return ex.markdown_header(fields), [ex.markdown_row(v) for v in values], "\n", "", papers


def _fit_units(
    header: str, units: list[str], sep: str, footer: str, max_chars: int
) -> tuple[str, int]:
    """The header, as many whole units as fit ``max_chars``, and the footer.

    The first unit is always kept, so one very long record cannot leave the export empty.
    """
    kept: list[str] = []
    size = len(header) + len(footer)
    for unit in units:
        cost = len(unit) + len(sep)
        if kept and size + cost > max_chars:
            break
        kept.append(unit)
        size += cost
    body = sep.join(kept)
    if header == "[":  # a JSON array: the bracket opens it, the footer closes it
        return f"[{body}{footer}", len(kept)
    if header:  # CSV and Markdown: header lines, then one row per record
        return f"{header}\n{body}", len(kept)
    return body, len(kept)


async def _export_records(
    query: str, ids: list[str] | None, limit: int, skip: int, result_type: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]], int | None]:
    """The records to export, what was left out of an identifier list and why, and, for a
    query, how many records match in all."""
    skipped: list[dict[str, str]] = []
    if ids is not None:
        entries = [bm.classify(i) for i in ids[:limit]]
        index, errors = await _fetch_batch_records(entries, result_type)
        records: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for entry in entries:
            record = bm.lookup(index, entry)
            if entry.kind == "invalid":
                skipped.append({"id": entry.raw, "status": "invalid"})
            elif record is None:
                failed = errors.get((entry.kind, entry.value.lower()))
                skipped.append({"id": entry.raw, "status": "error" if failed else "not_found"})
            elif (str(record.get("source")), str(record.get("id"))) in seen:
                skipped.append({"id": entry.raw, "status": "duplicate"})
            else:
                seen.add((str(record.get("source")), str(record.get("id"))))
                records.append(record)
        return records, skipped, None
    wanted = skip + limit
    found = await _run_blocking(
        _get_client().search_all,
        query,
        page_size=wanted,
        max_results=wanted,
        resultType=result_type,
    )
    total = await _run_blocking(_get_client().get_hit_count, query)
    return [_as_dict(r) for r in found][skip:], skipped, total


@mcp.tool(annotations=_ro("Export papers"))
async def export_papers(
    format: Annotated[
        Literal["bibtex", "ris", "csl-json", "csv", "json", "markdown"],
        Field(description="Output format"),
    ] = "bibtex",
    query: Annotated[
        str, Field(description="A Europe PMC search query; give this or ids, not both")
    ] = "",
    ids: Annotated[
        list[str] | None,
        Field(
            description="PMIDs, PMCIDs and DOIs (mixed) to export, in this order; give this or "
            "query, not both",
            max_length=200,
        ),
    ] = None,
    limit: Annotated[int, Field(description="Most records to export", ge=1, le=1000)] = 100,
    skip: Annotated[
        int, Field(description="Query only: results to skip, for the next part", ge=0, le=999)
    ] = 0,
    fields: Annotated[
        list[str] | None,
        Field(
            description="csv, json and markdown only: columns, from "
            + ", ".join(bm.FIELDS)
            + ". Default: "
            + ", ".join(bm.DEFAULT_FIELDS)
        ),
    ] = None,
    include_abstract: Annotated[
        bool, Field(description="bibtex, ris and csl-json only: include the abstract")
    ] = False,
    max_chars: Annotated[
        int,
        Field(
            description="Cut the export at a record boundary after this many characters",
            ge=1000,
            le=500000,
        ),
    ] = 60000,
) -> dict[str, Any]:
    """Export papers as a file's worth of text to hand to a reference manager or a spreadsheet:
    BibTeX, RIS or CSL-JSON (Zotero, Mendeley, EndNote, Pandoc) or CSV, JSON or Markdown.
    Give a search `query` or a list of `ids`. BibTeX keys look like `vasiliou2005analysis`,
    are unique within the export and do not change when it is cut to size; text that LaTeX
    reads as syntax (& % # _ $) is escaped. A paper with more than 100 authors lists the first
    100 (BibTeX adds `and others`). The export is never cut in the middle of a record:
    `truncated` says that records were left out; `next_skip` (query) or `remaining` (ids) say
    where to continue. Nothing is written to disk.
    """
    if bool(query.strip()) == bool(ids):
        raise ToolError("Give either query or ids, not both and not neither")
    try:
        wanted = bm.validate_fields(fields)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    if query.strip():
        problems = qm.lint(query).errors
        if problems:
            raise ToolError(f"Fix the query first: {_problems(problems)}")
        if skip + limit > 1000:
            raise ToolError("skip + limit must not exceed 1000; narrow the query instead")
    wants_core = format in ("bibtex", "ris", "csl-json") or "abstract" in wanted
    try:
        records, skipped, total = await _export_records(
            query.strip(), ids, limit, skip, "core" if wants_core else "lite"
        )
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc

    header, units, sep, footer, papers = _export_units(format, records, wanted, include_abstract)
    content, kept = _fit_units(header, units, sep, footer, max_chars)
    left_out = len(units) - kept
    notes = []
    omitted = sum(1 for p in papers if p.authors_omitted)
    if omitted:
        tail = " and BibTeX ends them with 'and others'" if format == "bibtex" else ""
        notes.append(
            f"{omitted} paper(s) have more than {ex.MAX_AUTHORS} authors; the first "
            f"{ex.MAX_AUTHORS} are listed{tail}"
        )
    result: dict[str, Any] = {
        "format": format,
        "content": content,
        "exported": kept,
        "found": len(units),
        "truncated": left_out > 0,
        "returned_chars": len(content),
        "skipped": skipped,
        "notes": notes,
    }
    if ids is not None:
        result["remaining"] = [r.get("pmid") or r.get("id") for r in records[kept:]]
    else:
        result["total_hits"] = total
        more = (skip + kept) < (total or 0) and skip + kept <= 999
        result["next_skip"] = skip + kept if more else None
    return result


# ---------------------------------------------------------------------------
# Batch lookups
# ---------------------------------------------------------------------------

_FULLTEXT_CONCURRENCY = 4


async def _fetch_batch_records(
    entries: list[bm.Entry], result_type: str
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], str]]:
    """Look all valid entries up in as few Europe PMC requests as possible.

    Returns the records indexed by identifier and, for every entry whose request failed, the
    error text: one failing chunk must not take the other chunks down with it.
    """
    index: dict[tuple[str, str], dict[str, Any]] = {}
    errors: dict[tuple[str, str], str] = {}
    client = _get_client()
    for chunk in bm.chunks(entries):
        size = min(1000, 3 * len(chunk))  # a DOI can name a preprint and its published version
        try:
            results = await _run_blocking(
                client.search_all,
                bm.build_query(chunk),
                page_size=size,
                max_results=size,
                resultType=result_type,
            )
        except EuropePMCError as exc:
            for entry in chunk:
                errors[(entry.kind, entry.value.lower())] = str(exc)
            continue
        for key, record in bm.index_records([_as_dict(r) for r in results]).items():
            index.setdefault(key, record)
    return index, errors


@mcp.tool(annotations=_ro("Get papers in batch"))
async def get_papers_batch(
    ids: Annotated[
        list[str],
        Field(
            description="PMIDs, PMCIDs and DOIs, mixed allowed (bare digits are a PMID; "
            "'doi:' and https://doi.org/ prefixes are accepted)",
            min_length=1,
            max_length=100,
        ),
    ],
    fields: Annotated[
        list[str] | None,
        Field(
            description="Fields to return per paper, from: "
            + ", ".join(bm.FIELDS)
            + ". Default: "
            + ", ".join(bm.DEFAULT_FIELDS)
            + ". 'abstract' makes the lookup slower and the answer larger."
        ),
    ] = None,
) -> dict[str, Any]:
    """Look up many papers at once: one combined Europe PMC query per 50 identifiers instead of
    one call per paper. Every input gets a result in the order given, with a status: ok,
    not_found, invalid (malformed identifier) or error (that request failed). One bad
    identifier never fails the batch; a repeated identifier repeats its result."""
    try:
        wanted = bm.validate_fields(fields)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    entries = [bm.classify(i) for i in ids]
    index, errors = await _fetch_batch_records(entries, "core" if "abstract" in wanted else "lite")

    results = []
    for entry in entries:
        item: dict[str, Any] = {
            "id": entry.raw,
            "id_type": entry.kind,
            "status": "ok",
            "record": None,
            "error": None,
        }
        error = errors.get((entry.kind, entry.value.lower()))
        record = bm.lookup(index, entry)
        if entry.kind == "invalid":
            item.update(status="invalid", error=entry.problem)
        elif error and record is None:
            item.update(status="error", error=error)
        elif record is None:
            item.update(status="not_found")
        else:
            item["record"] = bm.project(record, wanted)
        results.append(item)
    return {
        "requested": len(ids),
        "distinct": len(bm.distinct_valid(entries)),
        "by_status": dict(Counter(r["status"] for r in results)),
        "results": results,
    }


def _render_fulltext_markdown(
    xml: str, sections: list[str] | None, max_chars: int
) -> dict[str, Any]:
    """Markdown of the (filtered) sections of one article, cut at a block boundary."""
    parser = FullTextXMLParser(xml)
    all_sections = parser.get_full_text_sections_structured()
    chosen = ft.select_sections(all_sections, sections)
    units = ft.render_units(chosen, "markdown")
    kept, total, truncated = ft.take_within(units, max_chars)
    return {
        "title": parser.extract_metadata().get("title") or "",
        "content": ft.units_to_markdown(kept),
        "total_chars": total,
        "returned_chars": sum(len(u[2]) + 2 for u in kept),
        "truncated": truncated,
        "matched": bool(chosen),
        "sections_available": ft.section_titles(all_sections),
    }


async def _xml_or_error(pmcid: str) -> tuple[str | None, str | None]:
    try:
        return await _fulltext_xml(pmcid), None
    except ToolError as exc:
        return None, str(exc)


def _fulltext_status(
    entry: bm.Entry, record: dict[str, Any] | None, error: str | None
) -> dict[str, Any]:
    """Status and identifying fields of one input before any full text is fetched."""
    item: dict[str, Any] = {"id": entry.raw, "id_type": entry.kind, "status": "ok"}
    pmcid = str((record or {}).get("pmcid") or "")
    if entry.kind == "invalid":
        item.update(status="invalid", error=entry.problem)
    elif error and record is None:
        item.update(status="error", error=error)
    elif record is None:
        item["status"] = "not_found"
    elif not pmcid:
        item["status"] = "not_in_pmc"
    elif record.get("isOpenAccess") != "Y":
        item.update(status="not_open_access", pmcid=pmcid)
    else:
        item["pmcid"] = pmcid
    return item


async def _render_into(
    item: dict[str, Any],
    xml: str | None,
    error: str | None,
    sections: list[str] | None,
    allowance: int,
) -> int:
    """Fill ``item`` with the rendered text of one paper; returns the characters used."""
    if xml is None:
        item.update(status="error", error=error)
        return 0
    try:
        data = await _run_blocking(_render_fulltext_markdown, xml, sections, allowance)
    except ParsingError as exc:
        item.update(status="error", error=str(exc))
        return 0
    item["title"] = data["title"]
    if not data["matched"]:
        item.update(status="no_matching_section", sections_available=data["sections_available"])
        return 0
    item.update(
        content=data["content"],
        total_chars=data["total_chars"],
        returned_chars=data["returned_chars"],
        truncated=data["truncated"],
    )
    return int(data["returned_chars"])


@mcp.tool(annotations=_ro("Get full text of several papers"))
async def get_papers_fulltext_batch(
    ids: Annotated[
        list[str],
        Field(
            description="PMIDs, PMCIDs and DOIs, mixed allowed. Only open-access papers "
            "have full text",
            min_length=1,
            max_length=20,
        ),
    ],
    sections: Annotated[
        list[str] | None,
        Field(
            description="Only these sections of every paper: case-insensitive substrings of "
            "a title, e.g. ['methods', 'results']. Default: all sections."
        ),
    ] = None,
    max_chars_per_paper: Annotated[
        int, Field(description="Cap on the content of one paper", ge=1000, le=100000)
    ] = 8000,
    max_total_chars: Annotated[
        int, Field(description="Cap on the content of the whole response", ge=1000, le=300000)
    ] = 60000,
) -> dict[str, Any]:
    """Markdown full text of several open-access papers in one call, within a size budget.

    The identifiers are resolved with one query, papers that are not open access are reported
    without being downloaded, and the rest are fetched four at a time. The total budget is
    handed out in the order given: once it is used up, the remaining papers are reported as
    skipped_budget and not downloaded. Each result has a status: ok, not_found, invalid,
    not_in_pmc, not_open_access, no_matching_section, duplicate, error or skipped_budget.
    Use `get_paper_fulltext` for one paper at a larger size.
    """
    _require_available(FULLTEXT_AVAILABLE, "FullTextXMLParser")
    entries = [bm.classify(i) for i in ids]
    index, errors = await _fetch_batch_records(entries, "lite")

    results: list[dict[str, Any]] = []
    candidates: list[int] = []
    first_by_pmcid: dict[str, int] = {}
    for pos, entry in enumerate(entries):
        item = _fulltext_status(
            entry,
            bm.lookup(index, entry),
            errors.get((entry.kind, entry.value.lower())),
        )
        if item["status"] == "ok":
            if item["pmcid"] in first_by_pmcid:
                item.update(status="duplicate", duplicate_of=first_by_pmcid[item["pmcid"]])
            else:
                first_by_pmcid[item["pmcid"]] = pos
                candidates.append(pos)
        results.append(item)

    remaining = max_total_chars
    for start in range(0, len(candidates), _FULLTEXT_CONCURRENCY):
        window = candidates[start : start + _FULLTEXT_CONCURRENCY]
        if remaining <= 0:
            for pos in candidates[start:]:
                results[pos]["status"] = "skipped_budget"
            break
        fetched = await asyncio.gather(*(_xml_or_error(results[p]["pmcid"]) for p in window))
        for pos, (xml, error) in zip(window, fetched, strict=True):
            if remaining <= 0:
                results[pos]["status"] = "skipped_budget"
                continue
            allowance = min(max_chars_per_paper, remaining)
            remaining -= await _render_into(results[pos], xml, error, sections, allowance)
    return {
        "requested": len(ids),
        "by_status": dict(Counter(r["status"] for r in results)),
        "total_chars_returned": max_total_chars - remaining,
        "budget_exhausted": remaining <= 0,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Open-access locations
# ---------------------------------------------------------------------------


async def _europepmc_record(query: str, *, required: bool) -> dict[str, Any] | None:
    """The lite Europe PMC record for ``query``; ``None`` when absent or, if not required,
    when the lookup itself fails."""
    try:
        results = await _run_blocking(
            _get_client().search_all, query, page_size=1, max_results=1, resultType="lite"
        )
    except EuropePMCError as exc:
        if required:
            raise ToolError(str(exc)) from exc
        return None
    return _as_dict(results[0]) if results else None


@mcp.tool(annotations=_ro("Find open-access copies"))
async def find_open_access(
    doi: Annotated[str, Field(description="DOI, e.g. 10.1038/s41586-020-2649-2")] = "",
    pmid: Annotated[str, Field(description="PubMed ID (alternative to doi)")] = "",
    pmcid: Annotated[str, Field(description="PMC ID (alternative to doi)")] = "",
) -> dict[str, Any]:
    """Where can this paper be read for free? Looks the DOI up in Unpaywall and returns the
    open-access status (gold, green, hybrid, bronze, closed), the best copy with its PDF
    link and licence, and a few alternatives. ``europepmc_fulltext`` says whether
    `get_paper_fulltext` will work for it. Needs UNPAYWALL_EMAIL in the server's environment.
    """
    # Validate locally, then fetch the client (it fails fast when no e-mail is configured),
    # and only then touch the network.
    if doi.strip():
        clean = oa.clean_doi(doi)
        if not clean:
            raise ToolError(f"doi must look like 10.1234/abc, got {doi!r}")
        query = f'DOI:"{clean}"'
    else:
        query = _fulltext_query(pmcid, pmid, "")
    client = _unpaywall_client_cache.get()

    if doi.strip():
        record = await _europepmc_record(query, required=False)
    else:
        record = await _europepmc_record(query, required=True)
        if record is None:
            raise ToolError(f"No Europe PMC record found for {pmcid or pmid!r}")
        clean = oa.clean_doi(str(record.get("doi") or ""))
        if not clean:
            raise ToolError(
                f"{pmcid or pmid!r} has no DOI in Europe PMC, and Unpaywall looks papers up by DOI"
            )

    try:
        found = await _run_blocking(client.lookup_by_doi, clean)
    except UnpaywallError as exc:
        message = (
            str(exc.context.get("message", exc)) if isinstance(exc.context, dict) else str(exc)
        )
        if "429" in message:
            message = "Unpaywall is rate limiting this server (HTTP 429); retry later"
        raise ToolError(message) from exc

    has_pmc = bool(record and record.get("pmcid"))
    result: dict[str, Any] = {
        "doi": clean,
        "pmcid": (record or {}).get("pmcid") or None,
        "europepmc_fulltext": None
        if record is None
        else has_pmc and record.get("isOpenAccess") == "Y",
        "found": found is not None,
    }
    if found is None:
        result.update(
            is_oa=False,
            oa_status=None,
            best_location=None,
            alternatives=[],
            location_count=0,
            note="Unpaywall does not know this DOI",
        )
        return result
    result.update(oa.summarize(found))
    return result


# ---------------------------------------------------------------------------
# Text-mined annotations
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_ro("Get paper annotations"))
async def get_paper_annotations(
    pmcid: Annotated[str, Field(description="PMC ID of the article, e.g. PMC1234567")] = "",
    pmid: Annotated[str, Field(description="PubMed ID (alternative to pmcid)")] = "",
    doi: Annotated[str, Field(description="DOI (alternative to pmcid)")] = "",
    annotation_type: Annotated[
        str,
        Field(
            description="Only this entity type, e.g. Gene_Proteins, Chemicals, Diseases, "
            "Organisms, 'Gene Ontology'. Case-insensitive; the result lists "
            "available_types when nothing matches."
        ),
    ] = "",
    section: Annotated[
        str, Field(description="Only mentions in this section, e.g. Abstract, Results, Methods")
    ] = "",
    provider: Annotated[
        str, Field(description="Only this annotation provider, e.g. 'Europe PMC'")
    ] = "",
    limit: Annotated[
        int, Field(description="Max entities to return, most mentioned first", ge=1, le=1000)
    ] = 50,
) -> dict[str, Any]:
    """Genes, proteins, chemicals, diseases, organisms and other entities that Europe PMC
    text-mined from a paper, grouped by entity with mention counts, sections and example
    mentions. A review with hundreds of mentions comes back as a short entity list."""
    article_id = await _annotation_article_id(pmcid, pmid, doi)
    client = _annotations_client_cache.get()
    try:
        result = await _run_blocking(
            client.get_annotations_by_article_ids, [article_id], format="JSON"
        )
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc
    raw = result.get("raw")
    records = raw if isinstance(raw, list) else []
    record = records[0] if records and isinstance(records[0], dict) else {}
    found = ann.collect(
        record.get("annotations") or [],
        annotation_type=annotation_type,
        section=section,
        provider=provider,
    )
    entities = found["entities"]
    return {
        "article": {
            "id": article_id,
            "source": record.get("source", ""),
            "pmcid": record.get("pmcid", ""),
        },
        "found": bool(record),
        "annotation_count": found["annotation_count"],
        "entity_count": len(entities),
        "by_type": dict(Counter(e["type"] for e in entities).most_common()),
        "available_types": found["available_types"],
        "entities": entities[:limit],
        "truncated": len(entities) > limit,
    }


@mcp.tool(annotations=_ro("Find papers by entity"))
async def find_papers_by_entity(
    entity: Annotated[
        str,
        Field(description="Entity identifier or name, e.g. 'CHEBI:16236', 'ethanol', 'BRCA1'"),
    ],
    annotation_type: Annotated[
        str,
        Field(description="Only count mentions of this type, e.g. Chemicals, Diseases"),
    ] = "",
    section: Annotated[
        str, Field(description="Only count mentions in this section, e.g. Abstract, Results")
    ] = "",
    provider: Annotated[str, Field(description="Only count mentions from this provider")] = "",
    limit: Annotated[
        int, Field(description="Articles per page (Europe PMC allows 1 to 8)", ge=1, le=8)
    ] = 5,
    cursor: Annotated[
        str, Field(description="next_cursor of the previous page; empty for the first page")
    ] = "",
) -> dict[str, Any]:
    """Articles in which Europe PMC found a given entity, with how often and where it is
    mentioned. One page per call: pass ``next_cursor`` back as ``cursor`` for the next.

    Europe PMC's entity search ignores type, section and provider, so the three filters
    here apply to the mentions it returns: an article without a matching mention is left
    out and counted in ``articles_filtered_out``.
    """
    if not entity.strip():
        raise ToolError("entity must not be empty")
    client = _annotations_client_cache.get()
    try:
        result = await _run_blocking(
            client.get_annotations_by_entity,
            entity.strip(),
            page_size=limit,
            format="JSON",
            cursor_mark=cursor or None,
        )
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc
    raw = result.get("raw")
    page = raw if isinstance(raw, dict) else {}
    articles = []
    filtered_out = 0
    for item in page.get("articles") or []:
        if not isinstance(item, dict):
            continue
        summary = ann.summarize_article(
            item.get("annotations") or [],
            annotation_type=annotation_type,
            section=section,
            provider=provider,
        )
        if not summary["mentions"]:
            filtered_out += 1
            continue
        articles.append(
            {
                "source": item.get("source", ""),
                "id": item.get("extId", ""),
                "pmcid": item.get("pmcid", ""),
                **summary,
            }
        )
    return {
        "entity": entity.strip(),
        "article_count": len(articles),
        "articles_filtered_out": filtered_out,
        "articles": articles,
        "next_cursor": ann.next_cursor(page.get("nextCursorMark")),
    }


# ---------------------------------------------------------------------------
# Data and lab links
# ---------------------------------------------------------------------------


async def _link_target(pmcid: str, pmid: str, doi: str) -> tuple[str, str]:
    """``(source, id)`` for the link services, which take ``PMC/PMC123`` or ``MED/123``."""
    source, _, ext_id = (await _annotation_article_id(pmcid, pmid, doi)).partition(":")
    return source, ext_id


@mcp.tool(annotations=_ro("Get paper data links"))
async def get_paper_data_links(
    pmcid: Annotated[str, Field(description="PMC ID of the article, e.g. PMC1234567")] = "",
    pmid: Annotated[str, Field(description="PubMed ID (alternative to pmcid)")] = "",
    doi: Annotated[str, Field(description="DOI (alternative to pmcid)")] = "",
    category: Annotated[
        str,
        Field(
            description="Only this category, e.g. 'Data Citations', SNPs, RefSeq, "
            "'Clinical Trials', Diseases, Altmetric. Case-insensitive; "
            "`categories` in the result lists what exists."
        ),
    ] = "",
    scheme: Annotated[
        str, Field(description="Only this identifier scheme, e.g. dbSNP, RefSeq, DOI, OMIM")
    ] = "",
    limit: Annotated[int, Field(description="Max links to return", ge=1, le=1000)] = 100,
) -> dict[str, Any]:
    """Where is the data of this paper? Accession numbers Europe PMC text-mined from the full
    text (dbSNP, RefSeq, OMIM, ClinicalTrials.gov, cited DOIs) and records that providers link
    to the paper (BioStudies supplementary data, model-organism databases, Altmetric), as one
    flat list. `kind` separates supporting_data and related_data from altmetrics and
    recommended_reviews; `origin` says whether a link was text_mined or supplied by a
    provider. A paper without links gives an empty list, which is a valid answer."""
    source, ext_id = await _link_target(pmcid, pmid, doi)
    try:
        response = await _run_blocking(_get_article_client().get_data_links, source, ext_id)
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc
    everything = lk.flatten_data_links(response)
    chosen = lk.select(everything, category=category, scheme=scheme)
    return {
        "article": {"source": source, "id": ext_id},
        "total": len(everything),
        "matching": len(chosen),
        "categories": lk.count_by(everything, "category"),
        "schemes": lk.count_by(everything, "scheme"),
        "links": chosen[:limit],
        "truncated": len(chosen) > limit,
    }


@mcp.tool(annotations=_ro("Get paper lab links"))
async def get_paper_lab_links(
    pmcid: Annotated[str, Field(description="PMC ID of the article, e.g. PMC1234567")] = "",
    pmid: Annotated[str, Field(description="PubMed ID (alternative to pmcid)")] = "",
    doi: Annotated[str, Field(description="DOI (alternative to pmcid)")] = "",
    provider: Annotated[
        str,
        Field(
            description="Only this provider: part of its name (e.g. biostudies) or its "
            "numeric id. Europe PMC ignores a provider filter, so this is applied here."
        ),
    ] = "",
) -> dict[str, Any]:
    """Links that third parties publish for a paper, grouped by provider with the provider's
    description: BioStudies supplementary material, model-organism databases, GO annotations,
    Faculty Opinions recommendations, Altmetric. Use get_paper_data_links for the data
    accessions mentioned in the text."""
    source, ext_id = await _link_target(pmcid, pmid, doi)
    try:
        response = await _run_blocking(_get_article_client().get_lab_links, source, ext_id)
    except EuropePMCError as exc:
        raise ToolError(str(exc)) from exc
    everything = lk.flatten_lab_links(response)
    providers = lk.flatten_lab_links(response, provider=provider)
    return {
        "article": {"source": source, "id": ext_id},
        "available_providers": [p["provider"] for p in everything],
        "link_count": sum(len(p["links"]) for p in providers),
        "providers": providers,
    }


# ---------------------------------------------------------------------------
# LLM-powered tools
# ---------------------------------------------------------------------------

_LLM_ANNOTATIONS_KW = {"readOnlyHint": True, "openWorldHint": True}


def _require_llm() -> Any:
    if not LLM_AVAILABLE:
        raise ToolError(
            "LLM tools not available. Install with: pip install pyeuropepmc[agentic] "
            "and configure an LLM provider (see pyeuropepmc.agentic.llm_client)."
        )
    try:
        return _llm_agent_cache.get()
    except Exception as e:
        raise ToolError(f"Failed to initialise LLM client: {e}") from e


@mcp.tool(annotations=ToolAnnotations(title="Analyze citation context", **_LLM_ANNOTATIONS_KW))
async def analyze_citations(
    pmid: Annotated[str, Field(description="PubMed ID")],
    context: Annotated[str, Field(description="Citation context description")] = "general",
    task: Annotated[
        str, Field(description="Analysis task description")
    ] = "Provide a comprehensive analysis of the citation context for this paper.",
) -> dict[str, Any]:
    """Analyze citation context for a paper using an LLM (requires an LLM provider)."""
    agent = _require_llm()
    client = _get_client()
    paper = await _fetch_paper_summary(pmid, client)
    if paper is None:
        raise ToolError(f"Paper PMID {pmid} not found")
    result = await _run_blocking(
        agent.analyze_citation_context, paper=paper, context=context, task=task
    )
    if not result:
        raise ToolError("Failed to analyze citations")
    return _as_dict(result)


@mcp.tool(
    annotations=ToolAnnotations(title="Compare two papers' citations", **_LLM_ANNOTATIONS_KW)
)
async def compare_citations(
    pmid1: Annotated[str, Field(description="PubMed ID of first paper")],
    pmid2: Annotated[str, Field(description="PubMed ID of second paper")],
    task: Annotated[
        str, Field(description="Comparison task description")
    ] = "Compare these two papers and their citations.",
) -> dict[str, Any]:
    """Compare citations between two papers using an LLM (requires an LLM provider)."""
    agent = _require_llm()
    client = _get_client()
    p1 = await _fetch_paper_summary(pmid1, client)
    p2 = await _fetch_paper_summary(pmid2, client)
    if p1 is None or p2 is None:
        raise ToolError("One or both papers not found")
    result = await _run_blocking(agent.compare_citations, paper1=p1, paper2=p2, task=task)
    if not result:
        raise ToolError("Failed to compare citations")
    return _as_dict(result)


@mcp.tool(annotations=ToolAnnotations(title="Summarize citation activity", **_LLM_ANNOTATIONS_KW))
async def summarize_citations(
    pmid: Annotated[str, Field(description="PubMed ID")],
    citation_count: Annotated[int, Field(description="Number of citations", ge=0)] = 0,
) -> dict[str, Any]:
    """Summarize citation activity for a paper using an LLM (requires an LLM provider)."""
    agent = _require_llm()
    client = _get_client()
    paper = await _fetch_paper_summary(pmid, client)
    if paper is None:
        raise ToolError(f"Paper PMID {pmid} not found")
    result = await _run_blocking(
        agent.summarize_citations, paper=paper, citation_count=citation_count
    )
    if not result:
        raise ToolError("Failed to summarize citations")
    return _as_dict(result)


@mcp.tool(annotations=ToolAnnotations(title="PRISMA paper screening", **_LLM_ANNOTATIONS_KW))
async def paper_screening(
    query: Annotated[str, Field(description="Search query")],
    inclusion_criteria: Annotated[list[str], Field(description="Inclusion criteria")],
    exclusion_criteria: Annotated[list[str], Field(description="Exclusion criteria")],
    limit: Annotated[int, Field(description="Papers to screen", ge=1, le=500)] = 25,
    ctx: Context[Any, Any, Any] | None = None,
) -> dict[str, Any]:
    """Automated paper screening with PRISMA-compliant criteria, using an LLM (requires
    an LLM provider)."""
    agent = _require_llm()
    client = _get_client()
    if ctx:
        await ctx.info(f"Fetching up to {limit} candidates for {query!r}")
    raw = await _run_blocking(client.search_all, query, page_size=limit, max_results=limit)
    papers = [_paper_summary_from_raw(p) for p in raw]
    if ctx:
        await ctx.info(f"Screening {len(papers)} papers against inclusion/exclusion criteria")
    result = await _run_blocking(
        agent.screen_papers,
        papers=papers,
        inclusion_criteria=inclusion_criteria,
        exclusion_criteria=exclusion_criteria,
    )
    if not result:
        raise ToolError("Failed to screen papers")
    return _as_dict(result)


@mcp.tool(annotations=ToolAnnotations(title="Analyze a research question", **_LLM_ANNOTATIONS_KW))
async def research_question_analysis(
    research_question: Annotated[str, Field(description="Research question")],
    time_frame: Annotated[str, Field(description="Time frame for literature search")] = "all",
) -> dict[str, Any]:
    """Expand and analyze a research question using an LLM (requires an LLM provider)."""
    agent = _require_llm()
    result = await _run_blocking(
        agent.analyze_research_question, research_question=research_question, time_frame=time_frame
    )
    if not result:
        raise ToolError("Failed to analyze research question")
    return _as_dict(result)


@mcp.tool(annotations=ToolAnnotations(title="Preprint quality assessment", **_LLM_ANNOTATIONS_KW))
async def preprint_analysis(
    pmid: Annotated[str, Field(description="PubMed ID")],
    preprint_server: Annotated[
        str, Field(description="Preprint server, e.g. bioRxiv, medRxiv")
    ] = "",
) -> dict[str, Any]:
    """Preprint-specific quality assessment using an LLM (requires an LLM provider)."""
    agent = _require_llm()
    client = _get_client()
    paper = await _fetch_paper_summary(pmid, client)
    if paper is None:
        raise ToolError(f"Paper PMID {pmid} not found")
    paper["preprint_server"] = preprint_server
    paper["date_posted"] = ""
    result = await _run_blocking(agent.analyze_preprint, paper=paper)
    if not result:
        raise ToolError("Failed to analyze preprint")
    return _as_dict(result)


@mcp.tool(annotations=ToolAnnotations(title="Generate a literature review", **_LLM_ANNOTATIONS_KW))
async def literature_review(
    research_topic: Annotated[str, Field(description="Research topic")],
    key_concepts: Annotated[list[str], Field(description="Key concepts to cover")],
    time_frame: Annotated[str, Field(description="Time frame")] = "all",
    excluded_topics: Annotated[
        list[str] | None, Field(description="Topics to exclude from the review")
    ] = None,
    ctx: Context[Any, Any, Any] | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive literature review using an LLM (requires an LLM
    provider)."""
    agent = _require_llm()
    client = _get_client()
    if ctx:
        await ctx.info(f"Gathering source papers for {research_topic!r}")
    raw = await _run_blocking(client.search_all, research_topic, page_size=25, max_results=25)
    papers = [_paper_summary_from_raw(p) for p in raw]
    result = await _run_blocking(
        agent.generate_literature_review,
        research_topic=research_topic,
        papers=papers,
        time_frame=time_frame,
        key_concepts=key_concepts,
        excluded_topics=excluded_topics or [],
    )
    if not result:
        raise ToolError("Failed to generate literature review")
    return _as_dict(result)


@mcp.tool(annotations=ToolAnnotations(title="Build a knowledge graph", **_LLM_ANNOTATIONS_KW))
async def knowledge_graph(
    research_domain: Annotated[str, Field(description="Research domain")],
    entities: Annotated[list[str] | None, Field(description="Key entities")] = None,
    relationships: Annotated[list[str] | None, Field(description="Known relationships")] = None,
) -> dict[str, Any]:
    """Build a knowledge graph from research literature using an LLM (requires an LLM
    provider)."""
    agent = _require_llm()
    result = await _run_blocking(
        agent.build_knowledge_graph,
        research_domain=research_domain,
        entities=entities or [],
        relationships=relationships or [],
    )
    if not result:
        raise ToolError("Failed to build knowledge graph")
    return _as_dict(result)


# ---------------------------------------------------------------------------
# Bibliography tools
# ---------------------------------------------------------------------------


def _require_bibliography() -> tuple[Any, Any, Any]:
    """The BibTeX tools' dependencies; bibtexparser comes with the `bibliography` extra."""
    _require_available(
        BIBLIOGRAPHY_AVAILABLE and BIBTEXPARSER_AVAILABLE, "BibTeX tools", "bibliography"
    )
    return _bib_manager_cache.get(), _bib_converter_cache.get(), _bib_resolver_cache.get()


def _require_resolver() -> Any:
    """The identifier resolver, which needs no extra."""
    _require_available(BIBLIOGRAPHY_AVAILABLE, "ReferenceResolver")
    return _bib_resolver_cache.get()


@mcp.tool(annotations=_ro("Parse BibTeX", local=True))
async def bib_parse_string(
    content: Annotated[str, Field(description="BibTeX-formatted string")],
) -> dict[str, Any]:
    """Parse a BibTeX string into structured entries."""
    mgr, _, _ = _require_bibliography()
    lib = await _run_blocking(mgr.parse_string, content)
    return {
        "entries_count": len(lib),
        "keys": [e.citation_key for e in lib.entries],
        "entries": [
            {"key": e.citation_key, "type": e.entry_type, "fields": e.fields} for e in lib.entries
        ],
    }


@mcp.tool(annotations=_ro("Validate BibTeX", local=True))
async def bib_validate(
    content: Annotated[str, Field(description="BibTeX string to validate")],
) -> dict[str, Any]:
    """Validate BibTeX entries for completeness and correctness."""
    mgr, _, _ = _require_bibliography()
    lib = await _run_blocking(mgr.parse_string, content)
    issues = mgr.validate(lib)
    return {"entries": len(lib), "issues_count": len(issues), "issues": issues}


@mcp.tool(annotations=_ro("Convert BibTeX to RIS", local=True))
async def bib_to_ris(
    content: Annotated[str, Field(description="BibTeX-formatted string")],
) -> str:
    """Convert BibTeX entries to RIS format."""
    mgr, converter, _ = _require_bibliography()
    lib = await _run_blocking(mgr.parse_string, content)
    return "\n\n".join(converter.to_ris(e) for e in lib.entries)


@mcp.tool(annotations=_ro("Convert BibTeX to CSL-JSON", local=True))
async def bib_to_csl(
    content: Annotated[str, Field(description="BibTeX-formatted string")],
) -> list[dict[str, Any]]:
    """Convert BibTeX entries to CSL-JSON format."""
    mgr, converter, _ = _require_bibliography()
    lib = await _run_blocking(mgr.parse_string, content)
    return [converter.to_csl_json(e) for e in lib.entries]


@mcp.tool(annotations=_ro("Resolve a DOI"))
async def ref_resolve_doi(
    doi: Annotated[str, Field(description="DOI to resolve")],
) -> dict[str, Any]:
    """Resolve a DOI to bibliographic metadata."""
    resolver = _require_resolver()
    ref = await _run_blocking(resolver.resolve_doi, doi)
    if ref is None:
        raise ToolError(f"No metadata found for DOI: {doi}")
    return cast(dict[str, Any], ref.to_dict())


@mcp.tool(annotations=_ro("Resolve a PMID"))
async def ref_resolve_pmid(
    pmid: Annotated[str, Field(description="PubMed ID")],
) -> dict[str, Any]:
    """Resolve a PubMed ID to bibliographic metadata."""
    resolver = _require_resolver()
    ref = await _run_blocking(resolver.resolve_pmid, pmid)
    if ref is None:
        raise ToolError(f"No metadata found for PMID: {pmid}")
    return cast(dict[str, Any], ref.to_dict())


@mcp.tool(annotations=_ro("Merge BibTeX libraries", local=True))
async def bib_merge(
    libraries: Annotated[list[str], Field(description="BibTeX-formatted strings to merge")],
) -> dict[str, Any]:
    """Merge multiple BibTeX libraries, deduplicating by DOI."""
    mgr, _, _ = _require_bibliography()

    def _merge() -> dict[str, Any]:
        libs = [mgr.parse_string(s) for s in libraries]
        merged = mgr.merge(libs)
        return {
            "input_libraries": len(libs),
            "total_entries_before": sum(len(lib) for lib in libs),
            "merged_entries": len(merged),
            "deduplicated": sum(len(lib) for lib in libs) - len(merged),
            "keys": [e.citation_key for e in merged.entries],
        }

    return await _run_blocking(_merge)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyeuropepmc-mcp",
        description="MCP server for the pyeuropepmc literature-search toolkit.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.environ.get("PYEUROPEPMC_MCP_TRANSPORT", "stdio"),
        help="MCP transport to serve (default: stdio, for Claude Desktop and similar "
        "process-managed clients; use streamable-http or sse to expose the server to "
        "remote/networked agents)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("PYEUROPEPMC_MCP_HOST", "127.0.0.1"),
        help="Bind host for the sse/streamable-http transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PYEUROPEPMC_MCP_PORT", "8000")),
        help="Bind port for the sse/streamable-http transports (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("PYEUROPEPMC_MCP_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity, written to stderr (default: INFO)",
    )
    return parser


def _main_entry(argv: list[str] | None = None) -> None:
    args = _build_arg_parser().parse_args(argv)
    _configure_logging(args.log_level)
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    logger.info("pyeuropepmc-mcp v%s starting (transport=%s)", _server_version(), args.transport)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    _main_entry()
