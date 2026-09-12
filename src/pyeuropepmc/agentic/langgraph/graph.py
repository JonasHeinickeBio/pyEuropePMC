"""
LangGraph-based multi-agent workflow orchestration for claim verification.

Provides the full claim verification graph with a supervisor agent
that coordinates sub-agents for:

1. **Extract** — find atomic claims in source text
2. **Verify** — check claims against Europe PMC literature
3. **Review** — assess evidence quality
4. **Decisions** — auto or human-in-the-loop accept/reject
5. **Write** — improve text with citations and export bibliography

Architecture
------------
The ``SupervisorClaimWorkflow`` uses a **supervisor-orchestrated** pattern:

    START → supervisor → [extract → supervisor → verify → supervisor
            → review → supervisor → decisions → supervisor → write
            → supervisor →] END

The supervisor node (``_supervisor_node``) tracks progress, routes to
the next needed subagent, and automatically retries failed subagents
(up to ``max_retries`` times) before giving up.

Key features
------------
- Supervisor-driven retry / fallback for failed subagents
- Inter-agent message log (``agent_messages``)
- Progress tracking (``workflow_progress``) consumable by a UI
- Streaming of intermediate node results
- Human-in-the-loop via ``interrupt()`` for user claim confirmation
- ``MemorySaver`` checkpointer for state persistence
"""

from __future__ import annotations

from collections.abc import Callable, Generator
import logging
from typing import Any, Literal
import uuid

from pyeuropepmc.agentic.langgraph.state import ClaimState, create_initial_state

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    LANGGRAPH_AVAILABLE = True
except ImportError:
    END = "__end__"
    START = "__start__"
    StateGraph = None  # type: ignore[assignment]
    Command = None
    interrupt = None
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not available. Install with: pip install langgraph")


# Phase progression for the supervisor
# Phase names match sub-agent node names so error detection works.
SUPERVISOR_PHASES = [
    "extract",
    "verify",
    "review",
    "decisions",
    "write",
]
SUPERVISOR_PHASE_TO_FLAG = {
    "extract": "extraction_complete",
    "verify": "verification_complete",
    "review": "review_complete",
    "decisions": "decisions_complete",
    "write": "output_complete",
}
SUPERVISOR_PHASE_PROGRESS = {
    "init": 0.0,
    "extract": 0.15,
    "verify": 0.35,
    "review": 0.55,
    "decisions": 0.70,
    "write": 0.85,
    "done": 1.0,
    "failed": -1.0,
}


class SupervisorClaimWorkflow:
    """
    Multi-agent claim verification workflow built on LangGraph's ``StateGraph``.

    A **supervisor agent** orchestrates sub-agents (extract, verify, review,
    decisions, write) and handles retries on failure.

    The graph structure::

        START → supervisor → [sub-agent cycles → ...] → END

    The supervisor routes to the next undone sub-agent, checks for retries,
    and updates ``workflow_progress`` for UI consumption.

    Parameters
    ----------
    extract_claims_fn : Callable[[ClaimState], dict]
        Node function for the *extract* sub-agent
    verify_claims_fn : Callable[[ClaimState], dict]
        Node function for the *verify* sub-agent
    review_claims_fn : Callable[[ClaimState], dict]
        Node function for the *review* sub-agent
    write_report_fn : Callable[[ClaimState], dict]
        Node function for the *write* sub-agent
    checkpointer : Any, optional
        LangGraph checkpointer (e.g. ``MemorySaver``) for persistence

    Examples
    --------
    >>> from pyeuropepmc.agentic.langgraph.claims_graph import build_supervisor_graph
    >>> graph = build_supervisor_graph(llm_enabled=True)
    >>> result = graph.invoke("Some text to analyze ...", auto_accept=True)
    """

    def __init__(
        self,
        extract_claims_fn: Callable[[ClaimState], dict[str, Any]],
        verify_claims_fn: Callable[[ClaimState], dict[str, Any]],
        review_claims_fn: Callable[[ClaimState], dict[str, Any]],
        write_report_fn: Callable[[ClaimState], dict[str, Any]],
        checkpointer: Any = None,
    ):
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph is required. Install with: pip install langgraph")

        self.extract_claims_fn = extract_claims_fn
        self.verify_claims_fn = verify_claims_fn
        self.review_claims_fn = review_claims_fn
        self.write_report_fn = write_report_fn
        self.checkpointer = checkpointer

        self._graph: StateGraph = self._build_graph()
        self._compiled = None

    # ------------------------------------------------------------------ #
    # Graph construction
    # ------------------------------------------------------------------ #

    def _build_graph(self) -> StateGraph:
        """Build the ``StateGraph`` with supervisor node and sub-agents."""
        builder: StateGraph = StateGraph(ClaimState)

        # Supervisor — central coordinator
        builder.add_node("supervisor", self._supervisor_node)

        # Sub-agents (injected at construction time)
        builder.add_node("extract", self.extract_claims_fn)
        builder.add_node("verify", self.verify_claims_fn)
        builder.add_node("review", self.review_claims_fn)
        builder.add_node("decisions", self._decisions_node)
        builder.add_node("write", self.write_report_fn)

        # START always goes to supervisor
        builder.add_edge(START, "supervisor")

        # Supervisor routes to sub-agents conditionally
        builder.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            {
                "extract": "extract",
                "verify": "verify",
                "review": "review",
                "decisions": "decisions",
                "write": "write",
                END: END,
            },
        )

        # Every sub-agent returns to the supervisor
        for subagent in ("extract", "verify", "review", "decisions", "write"):
            builder.add_edge(subagent, "supervisor")

        return builder

    def compile(self) -> Any:
        """Compile the graph for execution."""
        if self._compiled is None:
            kwargs: dict[str, Any] = {}
            if self.checkpointer:
                kwargs["checkpointer"] = self.checkpointer
            self._compiled = self._graph.compile(**kwargs)
        return self._compiled

    # ------------------------------------------------------------------ #
    # invoke() — run-to-completion
    # ------------------------------------------------------------------ #

    def invoke(
        self,
        source_text: str,
        llm_enabled: bool = True,
        auto_accept: bool = False,
        bibliography_format: str = "bibtex",
        max_retries: int = 2,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run the full multi-agent claim workflow to completion.

        Parameters
        ----------
        source_text : str
            Text to analyze
        llm_enabled : bool, optional
            Whether to use LLM (default ``True``)
        auto_accept : bool, optional
            Auto-accept all claims without user interaction (default ``False``)
        bibliography_format : str, optional
            Output format for bibliography (default ``"bibtex"``)
        max_retries : int, optional
            Maximum retries per sub-agent (default 2)
        config : dict, optional
            LangGraph runtime config (for checkpointer thread, etc.)

        Returns
        -------
        dict[str, Any]
            Final state with improved text and bibliography
        """
        initial_state = create_initial_state(
            source_text=source_text,
            llm_enabled=llm_enabled,
            auto_accept=auto_accept,
            bibliography_format=bibliography_format,
            workflow_id=uuid.uuid4().hex[:12],
            max_retries=max_retries,
        )

        graph = self.compile()
        final_state = graph.invoke(
            initial_state,
            config=config or {"configurable": {"thread_id": initial_state["workflow_id"]}},
        )
        return final_state

    # ------------------------------------------------------------------ #
    # stream() — step-by-step node outputs
    # ------------------------------------------------------------------ #

    def stream(
        self,
        source_text: str,
        llm_enabled: bool = True,
        auto_accept: bool = False,
        bibliography_format: str = "bibtex",
        max_retries: int = 2,
        config: dict[str, Any] | None = None,
    ) -> Generator[dict[str, Any], None, dict[str, Any]]:
        """
        Run the multi-agent workflow and **yield** outputs node-by-node.

        Each yielded dict maps node names to their state updates::

            {"supervisor": {"supervisor_phase": "extract", ...}}
            {"extract": {"claims_raw": [...], ...}}
            {"supervisor": {"supervisor_phase": "verify", ...}}
            ...

        The final value returned from the generator is the complete
        final state (same format as ``invoke()``).

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
        max_retries : int, optional
            Maximum retries per sub-agent (default 2)
        config : dict, optional
            LangGraph runtime config

        Yields
        ------
        dict[str, Any]
            Per-node state update

        Returns
        -------
        dict[str, Any]
            Aggregated final state
        """
        initial_state = create_initial_state(
            source_text=source_text,
            llm_enabled=llm_enabled,
            auto_accept=auto_accept,
            bibliography_format=bibliography_format,
            workflow_id=uuid.uuid4().hex[:12],
            max_retries=max_retries,
        )

        graph = self.compile()
        final_state: dict[str, Any] = {}
        for step in graph.stream(
            initial_state,
            config=config or {"configurable": {"thread_id": initial_state["workflow_id"]}},
        ):
            yield step
            for _node_name, update in step.items():
                if isinstance(update, dict):
                    final_state.update(update)

        return final_state

    # ------------------------------------------------------------------ #
    # Supervisor node
    # ------------------------------------------------------------------ #

    def _supervisor_node(self, state: ClaimState) -> dict[str, Any]:
        """
        Supervisor agent — decide what to do next and update progress.

        The supervisor:
        1. Checks the current phase and completion flags
        2. Routes to the next uncompleted sub-agent
        3. Handles retries (increments ``retry_count``)
        4. Updates ``workflow_progress`` for UI consumption
        """
        phase = state.get("supervisor_phase", "init")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        # If a sub-agent just failed, handle retry
        errors = state.get("errors", [])
        recent_errors = [e for e in errors if self._is_recent_subagent_error(e, phase)]

        if recent_errors and retry_count < max_retries:
            logger.warning(
                "[supervisor] Retrying phase '%s' (attempt %d/%d)",
                phase,
                retry_count + 1,
                max_retries,
            )
            return {
                "retry_count": retry_count + 1,
                "supervisor_phase": phase,
                "workflow_progress": SUPERVISOR_PHASE_PROGRESS.get(phase, 0.0),
                "current_node": "supervisor",
            }

        # If too many retries, mark as failed
        if recent_errors and retry_count >= max_retries:
            logger.error("[supervisor] Max retries reached for phase '%s'", phase)
            return {
                "supervisor_phase": "failed",
                "workflow_progress": -1.0,
                "errors": [f"supervisor: max retries reached for {phase}"],
                "current_node": "supervisor",
            }

        # Normal progression: find next uncompleted phase
        # Determine current phase from state flags
        next_phase = self._next_phase(state)
        progress = SUPERVISOR_PHASE_PROGRESS.get(next_phase, 0.0)

        logger.info("[supervisor] Phase: %s (progress: %.0f%%)", next_phase, progress * 100)

        update: dict[str, Any] = {
            "supervisor_phase": next_phase,
            "workflow_progress": progress,
            "current_node": "supervisor",
        }

        if next_phase == "done":
            update["workflow_progress"] = 1.0
        elif next_phase == "failed":
            update["workflow_progress"] = -1.0

        return update

    @staticmethod
    def _is_recent_subagent_error(error: str, current_phase: str) -> bool:
        """Check if an error string is from the current phase's subagent."""
        return error.startswith(f"{current_phase}:")

    @staticmethod
    def _next_phase(state: ClaimState) -> str:
        """Determine the next phase to execute based on completion flags.

        Phase names match the sub-agent node names so that
        ``_route_from_supervisor`` can route to the same name.
        """
        if not state.get("extraction_complete"):
            return "extract"
        if not state.get("verification_complete"):
            return "verify"
        if not state.get("review_complete"):
            return "review"
        if not state.get("decisions_complete"):
            return "decisions"
        if not state.get("output_complete"):
            return "write"

        # Check if anything failed permanently
        errors = state.get("errors", [])
        if errors and any("supervisor: max retries" in e for e in errors):
            return "failed"

        return "done"

    # ------------------------------------------------------------------ #
    # Supervisor routing
    # ------------------------------------------------------------------ #

    def _route_from_supervisor(
        self,
        state: ClaimState,
    ) -> Literal["extract", "verify", "review", "decisions", "write", "__end__"]:
        """Route from supervisor to the next sub-agent based on phase.

        Phase names now match node names directly, so we can route
        to the same name unless it's a terminal phase.
        """
        phase = state.get("supervisor_phase", "init")

        if phase == "failed" or phase == "done":
            return END  # type: ignore[return-value]

        # Phase names match node names: extract, verify, review, decisions, write
        if phase in SUPERVISOR_PHASES:
            return phase  # type: ignore[return-value]

        return END  # type: ignore[return-value]

    # ------------------------------------------------------------------ #
    # Decisions node (internal — human-in-the-loop)
    # ------------------------------------------------------------------ #

    def _decisions_node(self, state: ClaimState) -> dict[str, Any]:
        """Handle user decisions (auto or human-in-the-loop)."""
        logger.info("[decisions] Processing user decisions")
        try:
            if state.get("auto_accept"):
                return self._auto_decisions(state)
            return self._human_decisions(state)
        except Exception as e:
            logger.error("[decisions] Failed: %s", e)
            return {"errors": [f"decisions: {e}"]}

    # ------------------------------------------------------------------ #
    # Decision helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _auto_decisions(state: ClaimState) -> dict[str, Any]:
        """Auto-generate decisions without user interaction."""
        from pyeuropepmc.claims.models import Verdict

        verified = state.get("verified_claims", [])
        decisions: dict[str, bool] = {}
        for claim in verified:
            verdict = claim.get("verdict", Verdict.NOT_CHECKED.value)
            if verdict in (
                Verdict.SUPPORTED.value,
                Verdict.PARTIALLY_SUPPORTED.value,
            ):
                decisions[claim["id"]] = True
            else:
                decisions[claim["id"]] = False

        return {
            "user_decisions": decisions,
            "decisions_complete": True,
        }

    @staticmethod
    def _human_decisions(state: ClaimState) -> dict[str, Any]:
        """Use ``interrupt()`` for human-in-the-loop decisions."""
        from pyeuropepmc.claims.models import Verdict

        claims_for_review = state.get("verified_claims", [])

        review_payload = [
            {
                "id": c["id"],
                "text": c["text"],
                "verdict": c.get("verdict", Verdict.NOT_CHECKED.value),
                "confidence": c.get("confidence", 0.0),
                "evidence_count": len(c.get("evidence", [])),
            }
            for c in claims_for_review
        ]

        # Pause execution and yield control to the caller
        user_input = interrupt(
            {
                "type": "claim_review",
                "claims": review_payload,
                "message": "Please review each claim and decide whether to include it.",
            }
        )

        decisions: dict[str, bool] = {}
        if isinstance(user_input, dict):
            for claim_id, accepted in user_input.items():
                decisions[claim_id] = accepted
        else:
            # Fallback: accept supported / partially-supported
            for c in claims_for_review:
                verdict = c.get("verdict", Verdict.NOT_CHECKED.value)
                decisions[c["id"]] = verdict in (
                    Verdict.SUPPORTED.value,
                    Verdict.PARTIALLY_SUPPORTED.value,
                )

        return {
            "user_decisions": decisions,
            "decisions_complete": True,
        }


__all__ = ["SupervisorClaimWorkflow", "LANGGRAPH_AVAILABLE"]
