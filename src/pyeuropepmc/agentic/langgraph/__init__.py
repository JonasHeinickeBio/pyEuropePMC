"""
LangGraph integration for multi-agent orchestration.

Provides graph-based workflow orchestration using LangGraph's ``StateGraph``,
with typed state management, a supervisor agent, conditional branching,
automatic retries, and human-in-the-loop.

Components
----------
- ``state.py`` — Typed state definitions (``ClaimState``)
- ``graph.py`` — ``SupervisorClaimWorkflow`` multi-agent orchestrator
- ``nodes.py`` — Sub-agent node factories wrapping existing components
- ``claims_graph.py`` — ``build_supervisor_graph()``, ``run_supervisor_graph()``,
  ``stream_supervisor_graph()``, and ``astream_supervisor_graph()`` convenience API
  (with backward-compatible aliases ``build_claim_graph``, ``run_claim_graph``, etc.)
"""

from pyeuropepmc.agentic.langgraph.claims_graph import (
    astream_claim_graph,
    astream_supervisor_graph,
    build_claim_graph,
    build_supervisor_graph,
    run_claim_graph,
    run_supervisor_graph,
    stream_claim_graph,
    stream_supervisor_graph,
)
from pyeuropepmc.agentic.langgraph.graph import LANGGRAPH_AVAILABLE, SupervisorClaimWorkflow
from pyeuropepmc.agentic.langgraph.nodes import make_parallel_verify_node
from pyeuropepmc.agentic.langgraph.state import ClaimState, create_initial_state

__all__ = [
    "build_supervisor_graph",
    "build_claim_graph",
    "run_supervisor_graph",
    "run_claim_graph",
    "stream_supervisor_graph",
    "stream_claim_graph",
    "astream_supervisor_graph",
    "astream_claim_graph",
    "SupervisorClaimWorkflow",
    "ClaimState",
    "create_initial_state",
    "make_parallel_verify_node",
    "LANGGRAPH_AVAILABLE",
]
