"""
Concrete LangGraph workflow for the multi-agent claim verification pipeline.

Builds and compiles a LangGraph ``StateGraph`` that orchestrates the full
claim pipeline using a **supervisor agent** pattern::

    supervisor → extract → supervisor → verify → supervisor
        → review → supervisor → decisions → supervisor
        → write → supervisor → done

Supports:

- Supervisor-driven multi-agent orchestration
- Conditional branching with automatic retries (up to ``max_retries``)
- Automatic or human-in-the-loop decisions (``interrupt()``)
- Sequential or **parallel** claim verification (``ThreadPoolExecutor``)
- State persistence via ``MemorySaver`` checkpointer
- Streaming of intermediate node results
- Progress tracking (``workflow_progress``) consumable by a web UI
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Generator
import logging
from typing import Any

from pyeuropepmc.agentic.langgraph.graph import SupervisorClaimWorkflow
from pyeuropepmc.agentic.langgraph.nodes import (
    make_extract_node,
    make_parallel_verify_node,
    make_review_node,
    make_verify_node,
    make_write_node,
)
from pyeuropepmc.agentic.langgraph.state import ClaimState, create_initial_state

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.memory import MemorySaver

    HAS_CHECKPOINTER = True
except ImportError:
    MemorySaver = None
    HAS_CHECKPOINTER = False


def build_supervisor_graph(
    llm_enabled: bool = True,
    use_checkpointer: bool = True,
    parallel_workers: int = 0,
) -> SupervisorClaimWorkflow:
    """
    Build the multi-agent claim verification workflow graph.

    Creates all sub-agent functions from existing component instances
    and wires them into a LangGraph ``StateGraph`` with a supervisor
    orchestrator node.

    Parameters
    ----------
    llm_enabled : bool, optional
        Whether to enable LLM-dependent features (default ``True``)
    use_checkpointer : bool, optional
        Whether to enable state persistence (default ``True``)
    parallel_workers : int, optional
        Number of parallel threads for claim verification.
        ``0`` (default) uses sequential verification.
        ``>0`` uses a ``ThreadPoolExecutor`` with that many workers.

    Returns
    -------
    SupervisorClaimWorkflow
        The compiled workflow graph

    Examples
    --------
    >>> graph = build_supervisor_graph()
    >>> result = graph.invoke(
    ...     "CRISPR-Cas9 corrects 75% of mutations.",
    ...     auto_accept=True,
    ... )
    >>> result["output_complete"]
    True

    >>> # Parallel verification (faster for many claims)
    >>> graph = build_supervisor_graph(parallel_workers=4)
    """
    from pyeuropepmc.claims.extractor import ClaimExtractor
    from pyeuropepmc.claims.reviewer import ClaimReviewer
    from pyeuropepmc.claims.verifier import ClaimVerifier
    from pyeuropepmc.claims.writer import ClaimWriter

    extractor = ClaimExtractor(llm_enabled=llm_enabled)
    verifier = ClaimVerifier(llm_enabled=llm_enabled)
    reviewer = ClaimReviewer(llm_enabled=llm_enabled)
    writer = ClaimWriter(llm_enabled=llm_enabled)

    checkpointer = MemorySaver() if use_checkpointer and HAS_CHECKPOINTER else None

    # Choose sequential or parallel verification
    if parallel_workers > 0:
        verify_fn = make_parallel_verify_node(verifier, max_workers=parallel_workers)
    else:
        verify_fn = make_verify_node(verifier)

    graph = SupervisorClaimWorkflow(
        extract_claims_fn=make_extract_node(extractor),
        verify_claims_fn=verify_fn,
        review_claims_fn=make_review_node(reviewer),
        write_report_fn=make_write_node(writer),
        checkpointer=checkpointer,
    )

    return graph


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

build_claim_graph = build_supervisor_graph
"""Alias for ``build_supervisor_graph`` — preserves backward compatibility."""


# ---------------------------------------------------------------------------
# Convenience: build + invoke
# ---------------------------------------------------------------------------


def run_supervisor_graph(
    source_text: str,
    llm_enabled: bool = True,
    auto_accept: bool = False,
    bibliography_format: str = "bibtex",
    use_checkpointer: bool = False,
    parallel_workers: int = 0,
    max_retries: int = 2,
    progress_callback: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """
    Convenience function: **build + invoke** the supervisor graph in one call.

    Parameters
    ----------
    source_text : str
        Text to analyze
    llm_enabled : bool, optional
        Whether to use LLM (default ``True``)
    auto_accept : bool, optional
        Auto-accept all claims (default ``False``)
    bibliography_format : str, optional
        Output format (default ``"bibtex"``)
    use_checkpointer : bool, optional
        Enable state persistence (default ``False``)
    parallel_workers : int, optional
        Parallel verification threads (``0`` = sequential, default ``0``)
    max_retries : int, optional
        Maximum sub-agent retries (default ``2``)
    progress_callback : Callable[[float], None], optional
        Optional callback invoked with ``workflow_progress`` (0.0–1.0)
        after each node completes.  Useful for UI progress bars.

    Returns
    -------
    dict[str, Any]
        Final workflow state
    """
    graph = build_supervisor_graph(
        llm_enabled=llm_enabled,
        use_checkpointer=use_checkpointer,
        parallel_workers=parallel_workers,
    )

    if progress_callback is not None:
        # Use streaming to report progress, then aggregate the final state
        gen = graph.stream(
            source_text=source_text,
            llm_enabled=llm_enabled,
            auto_accept=auto_accept,
            bibliography_format=bibliography_format,
            max_retries=max_retries,
        )
        final_state: dict[str, Any] = {}
        for step in gen:
            for _node_name, update in step.items():
                if isinstance(update, dict):
                    final_state.update(update)
                    pct = update.get("workflow_progress")
                    if pct is not None:
                        progress_callback(pct)
        return final_state

    return graph.invoke(
        source_text=source_text,
        llm_enabled=llm_enabled,
        auto_accept=auto_accept,
        bibliography_format=bibliography_format,
        max_retries=max_retries,
    )


# ---------------------------------------------------------------------------
# Backward-compatible alias for run_supervisor_graph
# ---------------------------------------------------------------------------

run_claim_graph = run_supervisor_graph
"""Alias for ``run_supervisor_graph`` — preserves backward compatibility."""


# ---------------------------------------------------------------------------
# Streaming convenience
# ---------------------------------------------------------------------------


def stream_supervisor_graph(
    source_text: str,
    llm_enabled: bool = True,
    auto_accept: bool = False,
    bibliography_format: str = "bibtex",
    parallel_workers: int = 0,
    max_retries: int = 2,
) -> Generator[dict[str, Any], None, dict[str, Any]]:
    """
    Convenience generator: **build + stream** the supervisor graph node-by-node.

    Each yielded dict maps a node name to its state update::

        {"supervisor": {"supervisor_phase": "extract", ...}}
        {"extract": {"claims_raw": [...], "extraction_complete": True}}
        {"supervisor": {"supervisor_phase": "verify", ...}}
        ...

    The final (returned) value is the complete aggregated state.

    Parameters
    ----------
    source_text : str
        Text to analyze
    llm_enabled : bool, optional
        Whether to use LLM (default ``True``)
    auto_accept : bool, optional
        Auto-accept all claims (default ``False``)
    bibliography_format : str, optional
        Output format (default ``"bibtex"``)
    parallel_workers : int, optional
        Parallel verification threads (``0`` = sequential, default ``0``)
    max_retries : int, optional
        Maximum sub-agent retries (default ``2``)

    Yields
    ------
    dict[str, Any]
        Per-node state update

    Returns
    -------
    dict[str, Any]
        Final state
    """
    graph = build_supervisor_graph(
        llm_enabled=llm_enabled,
        use_checkpointer=False,
        parallel_workers=parallel_workers,
    )
    return graph.stream(
        source_text=source_text,
        llm_enabled=llm_enabled,
        auto_accept=auto_accept,
        bibliography_format=bibliography_format,
        max_retries=max_retries,
    )


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

stream_claim_graph = stream_supervisor_graph
"""Alias for ``stream_supervisor_graph`` — preserves backward compatibility."""


# ---------------------------------------------------------------------------
# Async streaming convenience
# ---------------------------------------------------------------------------


async def astream_supervisor_graph(
    source_text: str,
    llm_enabled: bool = True,
    auto_accept: bool = False,
    bibliography_format: str = "bibtex",
    parallel_workers: int = 0,
    max_retries: int = 2,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Async convenience: **build + astream** the supervisor graph node-by-node.

    Same as ``stream_supervisor_graph`` but returns an async generator.
    Requires LangGraph's async runtime support.

    Each yielded dict maps a node name to its state update::

        {"supervisor": {"supervisor_phase": "extract", ...}}
        {"extract": {"claims_raw": [...], "extraction_complete": True}}
        ...

    Parameters are identical to ``stream_supervisor_graph``.
    """
    graph = build_supervisor_graph(
        llm_enabled=llm_enabled,
        use_checkpointer=False,
        parallel_workers=parallel_workers,
    )

    initial_state = create_initial_state(
        source_text=source_text,
        llm_enabled=llm_enabled,
        auto_accept=auto_accept,
        bibliography_format=bibliography_format,
        workflow_id="",
        max_retries=max_retries,
    )

    compiled = graph.compile()

    async for step in compiled.astream(
        initial_state,
        config={"configurable": {"thread_id": initial_state["workflow_id"]}},
    ):
        yield step


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

astream_claim_graph = astream_supervisor_graph
"""Alias for ``astream_supervisor_graph`` — preserves backward compatibility."""


__all__ = [
    "build_supervisor_graph",
    "build_claim_graph",
    "run_supervisor_graph",
    "run_claim_graph",
    "stream_supervisor_graph",
    "stream_claim_graph",
    "astream_supervisor_graph",
    "astream_claim_graph",
    "ClaimState",
    "create_initial_state",
]
