"""
MCP Server for pyeuropepmc — unified literature search, citation graph traversal,
clinical trials, full-text indexing, and figure extraction.

Usage:
    pyeuropepmc-mcp

Tools:
    Core:
        unifed_search       — Search across PubMed, arXiv, Semantic Scholar, OpenAlex,
                              ClinicalTrials.gov (auto-deduped)
        get_paper_details   — Paper metadata by ID (via Europe PMC)
        search_authors      — Author search (via Europe PMC)

    Citation:
        get_paper_citations — Forward citations (cited-by)
        citation_snowball   — Recursive citation graph walking (forward/backward/both)
        analyze_citations   — LLM-powered citation context analysis
        compare_citations   — LLM-powered paper comparison
        summarize_citations — LLM-powered citation summary

    Clinical trials:
        clinical_trial_search — Search ClinicalTrials.gov by condition, intervention, or keyword

    Full-text & figures:
        fulltext_index_query  — Search local SQLite FTS5 full-text index
        paper_figures         — Extract figures from PMC Open Access articles

    Screening & review:
        paper_screening       — PRISMA-compliant automated screening
        literature_review     — LLM-generated literature reviews
        research_question     — Expand & analyze research questions (LLM)
        preprint_analysis     — Preprint quality assessment (LLM)
        knowledge_graph       — Build knowledge graphs (LLM)

    Bibliography:
        bib_parse_string  ref_resolve_doi   ref_resolve_pmid
        bib_validate      bib_to_ris         bib_to_csl
        bib_merge
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from pyeuropepmc import SearchClient
from pyeuropepmc.cache.cache import CacheConfig

# Optional: new literature modules
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

# Optional: processing modules
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

# Optional: LLM tools
try:
    from pyeuropepmc.agentic.agents import SmartCitationAnalysis
    from pyeuropepmc.agentic.llm_client import create_llm_client

    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# Optional: bibliography tools
try:
    from pyeuropepmc.features.bibliography import (
        BIBTEXPARSER_AVAILABLE,  # noqa: F401  (availability flag)
        BibtexManager,
        CitationConverter,
        ReferenceResolver,
    )

    BIBLIOGRAPHY_AVAILABLE = True
except ImportError:
    BIBLIOGRAPHY_AVAILABLE = False


_SINGLE_CLIENT: SearchClient | None = None
_SINGLE_UNIFIED: UnifiedSearch | None = None


def _get_client() -> SearchClient:
    """Get (or create) a cached SearchClient instance."""
    global _SINGLE_CLIENT
    if _SINGLE_CLIENT is None:
        _SINGLE_CLIENT = SearchClient(cache_config=CacheConfig(enabled=True))
    return _SINGLE_CLIENT


def _get_unified() -> UnifiedSearch | None:
    """Get (or create) a cached UnifiedSearch instance."""
    global _SINGLE_UNIFIED
    if _SINGLE_UNIFIED is None and UNIFIED_AVAILABLE:
        _SINGLE_UNIFIED = UnifiedSearch()
    return _SINGLE_UNIFIED


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


def _err(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Error: {msg}"}]}


def _ok(data: Any) -> dict[str, Any]:
    return {
        "content": [
            {"type": "text", "text": json.dumps(_to_serializable(data), indent=2, default=str)}
        ]
    }


# ---------------------------------------------------------------------------
# JSON-RPC handlers
# ---------------------------------------------------------------------------


def parse_mcp_request(line: str) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(line.strip())
    return parsed


def create_response(
    request_id: int,
    result: Any = None,
    error: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error:
        if isinstance(error, dict):
            response["error"] = error
        else:
            response["error"] = {"code": -32603, "message": error}
    else:
        response["result"] = result
    return response


def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "pyeuropepmc-mcp", "version": "2.0.0"},
    }


def handle_list_tools(params: dict[str, Any]) -> dict[str, Any]:
    """Return the full tool registry."""
    tools: list[dict[str, Any]] = [
        # ── Unifed search ──────────────────────────────────────────
        {
            "name": "unified_search",
            "description": "Search across multiple literature sources (PubMed, arXiv, Semantic Scholar, OpenAlex, ClinicalTrials.gov) with automatic deduplication",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sources to query (default: pubmed, arxiv, semantic_scholar)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results per source (default: 25)",
                    },
                },
                "required": ["query"],
            },
        },
        # ── Citation snowball ──────────────────────────────────────
        {
            "name": "citation_snowball",
            "description": "Walk the citation graph forward (cited-by), backward (references), or both, with configurable depth and minimum citation filter",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Paper ID (PMID, DOI, or Semantic Scholar ID)",
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["forward", "backward", "both"],
                        "description": "Snowball direction (default: forward)",
                    },
                    "max_papers": {
                        "type": "integer",
                        "description": "Max papers to return per level (default: 50)",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Recursion depth (default: 1, 0 = no limit)",
                    },
                    "min_citations": {
                        "type": "integer",
                        "description": "Minimum citation count filter (default: 0)",
                    },
                },
                "required": ["identifier"],
            },
        },
        # ── Clinical trial search ──────────────────────────────────
        {
            "name": "clinical_trial_search",
            "description": "Search ClinicalTrials.gov for studies by condition, intervention, or keyword",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "condition": {"type": "string", "description": "Medical condition filter"},
                    "intervention": {
                        "type": "string",
                        "description": "Intervention/treatment filter",
                    },
                    "limit": {"type": "integer", "description": "Max results (default: 25)"},
                    "status": {
                        "type": "string",
                        "description": "Recruitment status filter: ACTIVE, COMPLETED, RECRUITING, etc.",
                    },
                },
            },
        },
        # ── Full-text index query ──────────────────────────────────
        {
            "name": "fulltext_index_query",
            "description": "Search the local SQLite FTS5 full-text index for papers whose full text matches a query",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Full-text search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 25)",
                    },
                    "index_path": {
                        "type": "string",
                        "description": "Path to the SQLite index file (optional)",
                    },
                },
                "required": ["query"],
            },
        },
        # ── Paper figures ──────────────────────────────────────────
        {
            "name": "paper_figures",
            "description": "Extract figures from PMC Open Access articles (returns figure labels, captions, and image URLs)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pmcid": {
                        "type": "string",
                        "description": "PMC ID of the article (e.g. PMC1234567)",
                    },
                    "pmid": {"type": "string", "description": "PubMed ID (alternative to PMCID)"},
                    "doi": {"type": "string", "description": "DOI (alternative to PMCID)"},
                },
            },
        },
        # ── Existing tools (preserved) ─────────────────────────────
        {
            "name": "search_papers",
            "description": "[Legacy] Search Europe PMC for papers (use unifed_search for multi-source)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Number of results (default: 25)"},
                    "sort": {"type": "string", "description": "Sort order (cited, date)"},
                    "result_type": {
                        "type": "string",
                        "description": "Result type (default: core)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_paper_details",
            "description": "Get detailed paper information by PMID, PMCID, or DOI",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pmid": {"type": "string", "description": "PubMed ID"},
                    "pmcid": {"type": "string", "description": "PMCID"},
                    "doi": {"type": "string", "description": "DOI"},
                },
            },
        },
        {
            "name": "search_authors",
            "description": "Search for authors in Europe PMC",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Author name or affiliation"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_paper_citations",
            "description": "Get papers that cite a given paper",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pmid": {"type": "string", "description": "PubMed ID"},
                    "source": {
                        "type": "string",
                        "description": "Source identifier (MED, PMC, etc.)",
                        "default": "MED",
                    },
                },
                "required": ["pmid"],
            },
        },
        # ── LLM tools ──────────────────────────────────────────────
        {
            "name": "analyze_citations",
            "description": "Analyze citation context for a paper using LLM (requires OpenAI API key)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pmid": {"type": "string", "description": "PubMed ID"},
                    "context": {
                        "type": "string",
                        "description": "Citation context description",
                        "default": "general",
                    },
                    "task": {
                        "type": "string",
                        "description": "Analysis task description",
                        "default": "Provide a comprehensive analysis of the citation context for this paper.",
                    },
                },
                "required": ["pmid"],
            },
        },
        {
            "name": "compare_citations",
            "description": "Compare citations between two papers using LLM (requires OpenAI API key)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pmid1": {"type": "string", "description": "PubMed ID of first paper"},
                    "pmid2": {"type": "string", "description": "PubMed ID of second paper"},
                    "task": {
                        "type": "string",
                        "description": "Comparison task description",
                        "default": "Compare these two papers and their citations.",
                    },
                },
                "required": ["pmid1", "pmid2"],
            },
        },
        {
            "name": "summarize_citations",
            "description": "Summarize citation activity for a paper using LLM (requires OpenAI API key)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pmid": {"type": "string", "description": "PubMed ID"},
                    "citation_count": {
                        "type": "integer",
                        "description": "Number of citations",
                        "default": 0,
                    },
                },
                "required": ["pmid"],
            },
        },
        {
            "name": "paper_screening",
            "description": "Automated paper screening with PRISMA-compliant criteria using LLM (requires OpenAI API key)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "inclusion_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Inclusion criteria",
                    },
                    "exclusion_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exclusion criteria",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Papers to screen (default: 25)",
                    },
                },
                "required": ["query", "inclusion_criteria", "exclusion_criteria"],
            },
        },
        {
            "name": "research_question_analysis",
            "description": "Expand and analyze research questions using LLM (requires OpenAI API key)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "research_question": {"type": "string", "description": "Research question"},
                    "time_frame": {
                        "type": "string",
                        "description": "Time frame for literature search",
                        "default": "all",
                    },
                },
                "required": ["research_question"],
            },
        },
        {
            "name": "preprint_analysis",
            "description": "Preprint-specific quality assessment using LLM (requires OpenAI API key)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pmid": {"type": "string", "description": "PubMed ID"},
                    "preprint_server": {
                        "type": "string",
                        "description": "Preprint server (bioRxiv, medRxiv, etc.)",
                    },
                },
                "required": ["pmid"],
            },
        },
        {
            "name": "literature_review",
            "description": "Generate comprehensive literature reviews using LLM (requires OpenAI API key)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "research_topic": {"type": "string", "description": "Research topic"},
                    "time_frame": {
                        "type": "string",
                        "description": "Time frame",
                        "default": "all",
                    },
                    "key_concepts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key concepts to cover",
                    },
                },
                "required": ["research_topic", "key_concepts"],
            },
        },
        {
            "name": "knowledge_graph",
            "description": "Build knowledge graphs from research literature using LLM (requires OpenAI API key)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "research_domain": {"type": "string", "description": "Research domain"},
                    "entities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key entities",
                    },
                    "relationships": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Known relationships",
                    },
                },
                "required": ["research_domain"],
            },
        },
        # ── Bibliography tools ─────────────────────────────────────
        {
            "name": "bib_parse_string",
            "description": "Parse BibTeX string into structured entries",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "BibTeX-formatted string"},
                },
                "required": ["content"],
            },
        },
        {
            "name": "bib_validate",
            "description": "Validate BibTeX entries for completeness and correctness",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "BibTeX string to validate"},
                },
                "required": ["content"],
            },
        },
        {
            "name": "bib_to_ris",
            "description": "Convert BibTeX entries to RIS format",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "BibTeX-formatted string"},
                },
                "required": ["content"],
            },
        },
        {
            "name": "bib_to_csl",
            "description": "Convert BibTeX entries to CSL-JSON format",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "BibTeX-formatted string"},
                },
                "required": ["content"],
            },
        },
        {
            "name": "ref_resolve_doi",
            "description": "Resolve a DOI to bibliographic metadata",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "doi": {"type": "string", "description": "DOI to resolve"},
                },
                "required": ["doi"],
            },
        },
        {
            "name": "ref_resolve_pmid",
            "description": "Resolve a PubMed ID to bibliographic metadata",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pmid": {"type": "string", "description": "PubMed ID"},
                },
                "required": ["pmid"],
            },
        },
        {
            "name": "bib_merge",
            "description": "Merge multiple BibTeX libraries, deduplicating by DOI",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "libraries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "BibTeX-formatted strings to merge",
                    },
                },
                "required": ["libraries"],
            },
        },
    ]
    return {"tools": tools}


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def handle_call_tool(params: dict[str, Any]) -> dict[str, Any]:
    """Route tool calls to their handler."""
    tool_name = params.get("name", "")
    args = params.get("arguments", {})

    try:
        client = _get_client()

        # ── New tools ──────────────────────────────────────────────

        if tool_name == "unified_search":
            return _handle_unified_search(args)

        if tool_name == "citation_snowball":
            return _handle_citation_snowball(args)

        if tool_name == "clinical_trial_search":
            return _handle_clinical_trial_search(args)

        if tool_name == "fulltext_index_query":
            return _handle_fulltext_index_query(args)

        if tool_name == "paper_figures":
            return _handle_paper_figures(args)

        # ── Existing tools (preserved) ─────────────────────────────

        if tool_name == "search_papers":
            query = args.get("query", "")
            limit = args.get("limit", 25)
            sort = args.get("sort", "")
            result_type = args.get("result_type", "core")
            kwargs: dict[str, Any] = {"pageSize": limit, "resultType": result_type}
            if sort:
                kwargs["sort"] = sort
            results = client.search_all(query, **kwargs)
            return _ok(results)

        if tool_name == "get_paper_details":
            return _handle_get_paper_details(args, client)

        if tool_name == "search_authors":
            query = f'AUTH:"{args.get("query", "")}"'
            results = client.search_all(query, pageSize=args.get("limit", 25))
            return _ok(results)

        if tool_name == "get_paper_citations":
            pmid = args.get("pmid", "")
            results = client.search_all(f"CITED:{pmid}", pageSize=args.get("limit", 100))
            return _ok(results)

        # ── LLM tools ──────────────────────────────────────────────

        if tool_name in (
            "analyze_citations",
            "compare_citations",
            "summarize_citations",
            "paper_screening",
            "research_question_analysis",
            "preprint_analysis",
            "literature_review",
            "knowledge_graph",
        ):
            return _handle_llm_tool(tool_name, args, client)

        # ── Bibliography tools ─────────────────────────────────────

        if tool_name in (
            "bib_parse_string",
            "bib_validate",
            "bib_to_ris",
            "bib_to_csl",
            "ref_resolve_doi",
            "ref_resolve_pmid",
            "bib_merge",
        ):
            return _handle_bibliography_tool(tool_name, args)

        return _err(f"Unknown tool: {tool_name}")

    except Exception as e:
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        return _err(str(e))


# ---------------------------------------------------------------------------
# New tool handlers
# ---------------------------------------------------------------------------


def _handle_unified_search(args: dict[str, Any]) -> dict[str, Any]:
    if not UNIFIED_AVAILABLE:
        return _err("UnifiedSearch not available. Install with: pip install pyeuropepmc[all]")

    unified = _get_unified()
    if unified is None:
        return _err("Failed to initialise UnifiedSearch")

    query = args.get("query", "")
    if not query:
        return _err("query is required")

    sources = args.get("sources")
    limit = args.get("limit", 25)

    try:
        if sources:
            results, report = unified.search(query, sources=sources, limit=limit)
        else:
            results, report = unified.search(query, limit=limit)

        return _ok(
            {
                "results": [_to_serializable(r) for r in results],
                "dedup": {
                    "total_input": report.total_input,
                    "total_output": report.total_output,
                    "duplicates_removed": report.duplicates_removed,
                },
            }
        )
    except Exception as e:
        return _err(f"Unified search failed: {e}")


def _handle_citation_snowball(args: dict[str, Any]) -> dict[str, Any]:
    if not CITATION_WALKER_AVAILABLE:
        return _err("CitationWalker not available. Install with: pip install pyeuropepmc[all]")

    identifier = args.get("identifier", "")
    if not identifier:
        return _err("identifier is required")

    strategy_str = args.get("strategy", "forward")
    strategy_map = {
        "forward": SnowballingStrategy.FORWARD,
        "backward": SnowballingStrategy.BACKWARD,
        "both": SnowballingStrategy.BOTH,
    }
    strategy = strategy_map.get(strategy_str, SnowballingStrategy.FORWARD)
    max_papers = args.get("max_papers", 50)
    max_depth = args.get("max_depth", 1)
    min_citations = args.get("min_citations", 0)

    walker = CitationWalker()
    try:
        results, report = walker.snowball(
            identifier=identifier,
            strategy=strategy,
            max_papers=max_papers,
            max_depth=max_depth,
            min_citations=min_citations,
        )
        return _ok(
            {
                "paper_count": len(results),
                "dedup": {
                    "total_input": report.total_input,
                    "total_output": report.total_output,
                    "duplicates_removed": report.duplicates_removed,
                },
                "papers": [_to_serializable(r) for r in results],
            }
        )
    except Exception as e:
        return _err(f"Snowball failed: {e}")


def _handle_clinical_trial_search(args: dict[str, Any]) -> dict[str, Any]:
    if not CLINICAL_TRIALS_AVAILABLE:
        return _err(
            "ClinicalTrialsClient not available. Install with: pip install pyeuropepmc[all]"
        )

    client_ = ClinicalTrialsClient()
    query = args.get("query", "")
    condition = args.get("condition")
    intervention = args.get("intervention")
    limit = args.get("limit", 25)
    status = args.get("status")

    try:
        if condition and intervention:
            # Search by condition, then filter by intervention keyword
            results = client_.search_by_condition(condition, limit=limit * 2)
            intervention_lower = intervention.lower()
            results = [
                r
                for r in results
                if intervention_lower
                in ((r.extra_metadata or {}).get("interventions") or "").lower()
            ][:limit]
        elif condition:
            results = client_.search_by_condition(condition, limit=limit)
        elif intervention:
            results = client_.search_by_intervention(intervention, limit=limit)
        else:
            results = client_.search(query, limit=limit)

        if status:
            results = [
                r
                for r in results
                if (r.extra_metadata or {}).get("status", "").upper() == status.upper()
            ]

        return _ok(
            {
                "trial_count": len(results),
                "trials": [_to_serializable(r) for r in results],
            }
        )
    except Exception as e:
        return _err(f"Clinical trial search failed: {e}")


def _handle_fulltext_index_query(args: dict[str, Any]) -> dict[str, Any]:
    if not FTS_AVAILABLE:
        return _err("FullTextIndex not available. Install with: pip install pyeuropepmc[all]")

    query = args.get("query", "")
    limit = args.get("limit", 25)
    index_path = args.get("index_path")

    try:
        idx = FullTextIndex(db_path=index_path) if index_path else FullTextIndex()
        # Use search method — returns list of dicts with snippet
        results = idx.search(query, limit=limit)
        stats = idx.stats() if hasattr(idx, "stats") else {}

        return _ok(
            {
                "results": results,
                "stats": stats,
            }
        )
    except Exception as e:
        return _err(f"Full-text index query failed: {e}")


def _handle_paper_figures(args: dict[str, Any]) -> dict[str, Any]:
    if not FIGURE_EXTRACTOR_AVAILABLE:
        return _err("FigureExtractor not available. Install with: pip install pyeuropepmc[all]")

    pmcid = args.get("pmcid", "")
    pmid = args.get("pmid", "")
    doi = args.get("doi", "")

    if not any([pmcid, pmid, doi]):
        return _err("One of pmcid, pmid, or doi is required")

    try:
        extractor = FigureExtractor()
        if pmcid:
            figures = extractor.extract(pmcid=pmcid)
        elif pmid:
            figures = extractor.extract(pmid=pmid)
        else:
            figures = extractor.extract(doi=doi)

        return _ok(
            {
                "figure_count": len(figures),
                "figures": figures,
            }
        )
    except Exception as e:
        return _err(f"Figure extraction failed: {e}")


# ---------------------------------------------------------------------------
# Existing handler helpers
# ---------------------------------------------------------------------------


def _handle_get_paper_details(args: dict[str, Any], client: SearchClient) -> dict[str, Any]:
    pmid = args.get("pmid")
    pmcid = args.get("pmcid")
    doi = args.get("doi")

    if pmid:
        query = f"ext_id:{pmid}"
    elif pmcid:
        query = f"ext_id:{pmcid}"
    elif doi:
        query = f"doi:{doi}"
    else:
        return _err("At least one ID (pmid, pmcid, doi) is required")

    results = client.search_all(query, pageSize=1)
    if results:
        return _ok(results[0])
    return _err("No results found")


def _handle_llm_tool(tool_name: str, args: dict[str, Any], client: SearchClient) -> dict[str, Any]:
    if not LLM_AVAILABLE:
        return _err(
            "LLM tools not available. Install with: pip install langchain langchain-openai openai"
        )

    try:
        llm_client = create_llm_client()
        agent = SmartCitationAnalysis(
            llm_client=llm_client,
            literature_client=client,  # type: ignore[arg-type]
        )
    except Exception as e:
        return _err(f"Failed to initialise LLM: {e}")

    try:
        if tool_name == "analyze_citations":
            pmid = args.get("pmid", "")
            paper = _fetch_paper_summary(pmid, client)
            if paper is None:
                return _err(f"Paper PMID {pmid} not found")
            result = agent.analyze_citation_context(
                paper=paper,
                context=args.get("context", "general"),
                task=args.get(
                    "task",
                    "Provide a comprehensive analysis of the citation context for this paper.",
                ),
            )
            return _ok(result) if result else _err("Failed to analyze citations")

        if tool_name == "compare_citations":
            pmid1, pmid2 = args.get("pmid1", ""), args.get("pmid2", "")
            p1 = _fetch_paper_summary(pmid1, client)
            p2 = _fetch_paper_summary(pmid2, client)
            if p1 is None or p2 is None:
                return _err("One or both papers not found")
            result = agent.compare_citations(
                paper1=p1,
                paper2=p2,
                task=args.get("task", "Compare these two papers and their citations."),
            )
            return _ok(result) if result else _err("Failed to compare citations")

        if tool_name == "summarize_citations":
            pmid = args.get("pmid", "")
            paper = _fetch_paper_summary(pmid, client)
            if paper is None:
                return _err(f"Paper PMID {pmid} not found")
            result = agent.summarize_citations(
                paper=paper,
                citation_count=args.get("citation_count", 0),
            )
            return _ok(result) if result else _err("Failed to summarize citations")

        if tool_name == "paper_screening":
            query = args.get("query", "")
            raw = client.search_all(query, pageSize=args.get("limit", 25))
            papers = [_build_paper_dict(p) for p in raw]
            result = agent.screen_papers(
                papers=papers,
                inclusion_criteria=args.get("inclusion_criteria", []),
                exclusion_criteria=args.get("exclusion_criteria", []),
            )
            return _ok(result) if result else _err("Failed to screen papers")

        if tool_name == "research_question_analysis":
            result = agent.analyze_research_question(
                research_question=args.get("research_question", ""),
                time_frame=args.get("time_frame", "all"),
            )
            return _ok(result) if result else _err("Failed to analyze research question")

        if tool_name == "preprint_analysis":
            pmid = args.get("pmid", "")
            paper = _fetch_paper_summary(pmid, client)
            if paper is None:
                return _err(f"Paper PMID {pmid} not found")
            paper["preprint_server"] = args.get("preprint_server", "")
            paper["date_posted"] = ""
            result = agent.analyze_preprint(paper=paper)
            return _ok(result) if result else _err("Failed to analyze preprint")

        if tool_name == "literature_review":
            query = args.get("research_topic", "")
            raw = client.search_all(query, pageSize=25)
            papers = [_build_paper_dict(p) for p in raw]
            result = agent.generate_literature_review(
                research_topic=query,
                papers=papers,
                time_frame=args.get("time_frame", "all"),
                key_concepts=args.get("key_concepts", []),
                excluded_topics=args.get("excluded_topics", []),
            )
            return _ok(result) if result else _err("Failed to generate literature review")

        if tool_name == "knowledge_graph":
            result = agent.build_knowledge_graph(
                research_domain=args.get("research_domain", ""),
                entities=args.get("entities", []),
                relationships=args.get("relationships", []),
            )
            return _ok(result) if result else _err("Failed to build knowledge graph")

        return _err(f"Unknown LLM tool: {tool_name}")

    except Exception as e:
        return _err(f"LLM tool error: {e}")


def _handle_bibliography_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if not BIBLIOGRAPHY_AVAILABLE:
        return _err(
            "Bibliography tools not available. Install with: pip install pyeuropepmc[bibliography]"
        )

    try:
        mgr = BibtexManager()
        converter = CitationConverter()
        resolver = ReferenceResolver()

        if tool_name == "bib_parse_string":
            lib = mgr.parse_string(args.get("content", ""))
            return _ok(
                {
                    "entries_count": len(lib),
                    "keys": [e.citation_key for e in lib.entries],
                    "entries": [
                        {"key": e.citation_key, "type": e.entry_type, "fields": e.fields}
                        for e in lib.entries
                    ],
                }
            )

        if tool_name == "bib_validate":
            lib = mgr.parse_string(args.get("content", ""))
            issues = mgr.validate(lib)
            return _ok({"entries": len(lib), "issues_count": len(issues), "issues": issues})

        if tool_name == "bib_to_ris":
            lib = mgr.parse_string(args.get("content", ""))
            ris = "\n\n".join(converter.to_ris(e) for e in lib.entries)
            return {"content": [{"type": "text", "text": ris}]}

        if tool_name == "bib_to_csl":
            lib = mgr.parse_string(args.get("content", ""))
            return _ok([converter.to_csl_json(e) for e in lib.entries])

        if tool_name == "ref_resolve_doi":
            ref = resolver.resolve_doi(args.get("doi", ""))
            if ref:
                return _ok(ref.to_dict())
            return _err(f"No metadata found for DOI: {args.get('doi', '')}")

        if tool_name == "ref_resolve_pmid":
            ref = resolver.resolve_pmid(args.get("pmid", ""))
            if ref:
                return _ok(ref.to_dict())
            return _err(f"No metadata found for PMID: {args.get('pmid', '')}")

        if tool_name == "bib_merge":
            libs = [mgr.parse_string(s) for s in args.get("libraries", [])]
            merged = mgr.merge(libs)
            return _ok(
                {
                    "input_libraries": len(libs),
                    "total_entries_before": sum(len(lib) for lib in libs),
                    "merged_entries": len(merged),
                    "deduplicated": sum(len(lib) for lib in libs) - len(merged),
                    "keys": [e.citation_key for e in merged.entries],
                }
            )

        return _err(f"Unknown bibliography tool: {tool_name}")

    except Exception as e:
        return _err(f"Bibliography error: {e}")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _fetch_paper_summary(pmid: str, client: SearchClient) -> dict[str, Any] | None:
    """Fetch a minimal paper dict for LLM tools."""
    results = client.search_all(f"ext_id:{pmid}", pageSize=1)
    if not results:
        return None
    r = results[0]
    return {
        "pmid": r.get("pmid", ""),
        "pmcid": r.get("pmcid", ""),
        "doi": r.get("doi", ""),
        "title": r.get("title", ""),
        "authors": [{"name": a.get("author", "")} for a in r.get("authorInfo", [])],
        "publication_year": r.get("firstPublicationYear", ""),
        "journal": r.get("journalTitle", ""),
        "abstract": r.get("abstract", ""),
    }


def _build_paper_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Build enriched paper dict from Europe PMC raw result."""
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


# ---------------------------------------------------------------------------
# Async main loop
# ---------------------------------------------------------------------------


def _main_entry() -> None:
    asyncio.run(main())


async def main() -> None:
    """Read JSON-RPC requests from stdin, write responses to stdout."""
    print("pyeuropepmc-mcp server starting...", file=sys.stderr)
    sys.stderr.flush()

    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break

            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}", file=sys.stderr)
                sys.stderr.flush()
                continue

            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            is_notification = request_id is None

            if method == "initialize":
                response_json = json.dumps(
                    create_response(request_id, result=handle_initialize(params))
                )
            elif method == "tools/list":
                response_json = json.dumps(
                    create_response(request_id, result=handle_list_tools(params))
                )
            elif method == "tools/call":
                response_json = json.dumps(
                    create_response(request_id, result=handle_call_tool(params))
                )
            else:
                response_json = json.dumps(
                    create_response(
                        request_id,
                        error={"code": -32601, "message": f"Method not found: {method}"},
                    )
                )

            if not is_notification:
                print(response_json, flush=True)

        except Exception as e:
            import traceback

            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            if request_id is not None:
                error_response = json.dumps(
                    create_response(
                        request_id,
                        error={"code": -32603, "message": f"Internal error: {e}"},
                    )
                )
                print(error_response, flush=True)


if __name__ == "__main__":
    _main_entry()
