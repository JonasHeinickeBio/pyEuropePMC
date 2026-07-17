"""
Typed state definitions for LangGraph-based claim workflows.

Defines the state schemas used by the graph nodes to pass data
between stages of the claim verification pipeline.

Uses LangGraph's ``Annotated`` type with reducers for fields that
accumulate across nodes (errors, warnings), so each node only
returns the *new* items and LangGraph merges them automatically.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ClaimState(TypedDict):
    """
    Shared state for the claim verification workflow graph.

    Passed through all nodes in the graph, with each node reading
    from and writing to this state.  The supervisor node coordinates
    subagents and handles retries.

    List fields annotated with ``operator.add`` use LangGraph's reducer
    mechanism: each node returns only the *new* items and the framework
    concatenates them with the existing list.
    """

    # Input
    source_text: str

    # Extraction stage
    claims_raw: list[dict[str, Any]]
    extraction_complete: bool

    # Verification stage
    verified_claims: list[dict[str, Any]]
    verification_summary: dict[str, int]
    verification_complete: bool

    # Review stage
    review: dict[str, Any]
    review_complete: bool

    # User decisions
    user_decisions: dict[str, bool]
    decisions_complete: bool

    # Output
    improved_text: str
    bibliography: list[dict[str, Any]]
    output_complete: bool

    # Error tracking — reducer auto-concatenates new items
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]

    # Supervisor / multi-agent fields
    agent_messages: Annotated[list[dict[str, Any]], operator.add]
    """Inter-agent communication log: each entry has agent, target, action, payload, timestamp."""

    supervisor_phase: str
    """Current phase tracked by the supervisor (init, extracting, verifying, reviewing,
       deciding, writing, done, failed)."""

    workflow_progress: float
    """Progress indicator 0.0–1.0 reported to UI."""

    retry_count: int
    """How many retries the supervisor has performed across all subagents."""

    max_retries: int
    """Maximum number of sub-agent retries before the supervisor gives up (default 2)."""

    # Metadata
    llm_enabled: bool
    auto_accept: bool
    bibliography_format: str
    workflow_id: str
    current_node: str


def create_initial_state(
    source_text: str,
    llm_enabled: bool = True,
    auto_accept: bool = False,
    bibliography_format: str = "bibtex",
    workflow_id: str = "",
    max_retries: int = 2,
) -> ClaimState:
    """
    Create the initial state for a claim workflow.

    Parameters
    ----------
    source_text : str
        The text to analyze
    llm_enabled : bool, optional
        Whether LLM is available
    auto_accept : bool, optional
        Auto-accept claims without user interaction
    bibliography_format : str, optional
        Output format for bibliography
    workflow_id : str, optional
        Unique workflow identifier
    max_retries : int, optional
        Maximum sub-agent retries before supervisor gives up (default 2)

    Returns
    -------
    ClaimState
        Initialized state
    """
    return ClaimState(
        source_text=source_text,
        claims_raw=[],
        extraction_complete=False,
        verified_claims=[],
        verification_summary={},
        verification_complete=False,
        review={},
        review_complete=False,
        user_decisions={},
        decisions_complete=False,
        improved_text="",
        bibliography=[],
        output_complete=False,
        errors=[],
        warnings=[],
        agent_messages=[],
        supervisor_phase="init",
        workflow_progress=0.0,
        retry_count=0,
        max_retries=max_retries,
        llm_enabled=llm_enabled,
        auto_accept=auto_accept,
        bibliography_format=bibliography_format,
        workflow_id=workflow_id or "",
        current_node="__start__",
    )


__all__ = ["ClaimState", "create_initial_state"]
