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
        get_paper_details    — Paper metadata by ID (via Europe PMC)
        search_authors       — Author search (via Europe PMC)

    Citation:
        get_paper_citations  — Forward citations (cited-by)
        citation_snowball    — Recursive citation graph walking (forward/backward/both)
        analyze_citations    — LLM-powered citation context analysis
        compare_citations    — LLM-powered paper comparison
        summarize_citations  — LLM-powered citation summary

    Clinical trials:
        clinical_trial_search — Search ClinicalTrials.gov by condition, intervention, or keyword

    Full-text & figures:
        fulltext_index_query  — Search local SQLite FTS5 full-text index
        paper_figures         — Extract figures from PMC Open Access articles

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
from collections.abc import Callable
from functools import partial
from importlib.metadata import PackageNotFoundError, version as _pkg_version
import logging
import os
import sys
import threading
from typing import Annotated, Any, Generic, Literal, TypeVar, cast

import anyio
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from pyeuropepmc import SearchClient
from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.exceptions import ParsingError

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

    def set(self, value: _T) -> None:
        """Inject a pre-built value (tests: bypass the factory with a mock)."""
        with self._lock:
            self._value = value


_client_cache: _Lazy[SearchClient] = _Lazy(
    lambda: SearchClient(cache_config=CacheConfig(enabled=True))
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
    results = await _run_blocking(client.search_all, f"ext_id:{pmid}", pageSize=1)
    if not results:
        return None
    return _paper_summary_from_raw(results[0])


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
) -> list[dict[str, Any]]:
    """Search Europe PMC for papers (single source — prefer `unified_search` for
    multi-source coverage)."""
    client = _get_client()
    kwargs: dict[str, Any] = {"pageSize": limit, "resultType": result_type}
    if sort:
        kwargs["sort"] = sort
    results = await _run_blocking(client.search_all, query, **kwargs)
    return [_to_serializable(r) for r in results]


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
    results = await _run_blocking(client.search_all, query, pageSize=1)
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
    results = await _run_blocking(client.search_all, f'AUTH:"{query}"', pageSize=limit)
    return [_to_serializable(r) for r in results]


# ---------------------------------------------------------------------------
# Citation tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_ro("Get paper citations"))
async def get_paper_citations(
    pmid: Annotated[str, Field(description="PubMed ID")],
    limit: Annotated[int, Field(description="Max citing papers to return", ge=1, le=1000)] = 100,
) -> list[dict[str, Any]]:
    """Get papers that cite a given paper (Europe PMC)."""
    client = _get_client()
    results = await _run_blocking(client.search_all, f"CITED:{pmid}", pageSize=limit)
    return [_to_serializable(r) for r in results]


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
        identifier=identifier,
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


@mcp.tool(annotations=_ro("Extract paper figures"))
async def paper_figures(
    pmcid: Annotated[str, Field(description="PMC ID of the article, e.g. PMC1234567")] = "",
    pmid: Annotated[str, Field(description="PubMed ID (alternative to pmcid)")] = "",
    doi: Annotated[str, Field(description="DOI (alternative to pmcid)")] = "",
) -> dict[str, Any]:
    """Extract figures from PMC Open Access articles (labels, captions, and image URLs)."""
    _require_available(FIGURE_EXTRACTOR_AVAILABLE, "FigureExtractor")
    if not any([pmcid, pmid, doi]):
        raise ToolError("One of pmcid, pmid, or doi is required")

    extractor = _figure_extractor_cache.get()
    try:
        if pmcid:
            figures = await _run_blocking(extractor.extract, pmcid=pmcid)
        elif pmid:
            figures = await _run_blocking(extractor.extract, pmid=pmid)
        else:
            figures = await _run_blocking(extractor.extract, doi=doi)
    except ParsingError as exc:
        # A refused document is not "no figures": say so instead of reporting 0.
        raise ToolError(str(exc)) from exc

    return {"figure_count": len(figures), "figures": [_to_serializable(f) for f in figures]}


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
    raw = await _run_blocking(client.search_all, query, pageSize=limit)
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
    raw = await _run_blocking(client.search_all, research_topic, pageSize=25)
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
