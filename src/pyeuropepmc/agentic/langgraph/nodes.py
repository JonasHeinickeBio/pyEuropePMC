"""
Node functions for the LangGraph claim verification graph.

Each node wraps an existing pyEuropePMC component (ClaimExtractor,
ClaimVerifier, ClaimReviewer, ClaimWriter) into a subagent function
that reads from and writes to the shared ClaimState.

Subagents are coordinated by a supervisor node in ``graph.py``.
They communicate via ``agent_messages`` in the shared state and
support automatic retry (the supervisor checks ``retry_count``).

Error/warning lists use LangGraph's ``Annotated`` reducer mechanism
(see ``state.py``), so nodes return only *new* items; the framework
auto-concatenates them.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import logging
from typing import Any

from pyeuropepmc.agentic.langgraph.state import ClaimState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent_msg(
    agent: str,
    target: str,
    action: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an inter-agent message entry."""
    return {
        "agent": agent,
        "target": target,
        "action": action,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Extract subagent
# ---------------------------------------------------------------------------


def make_extract_node(
    extractor: Any,
    agent_name: str = "extract",
) -> Callable[[ClaimState], dict[str, Any]]:
    """
    Create a LangGraph subagent that extracts claims from source text.

    Parameters
    ----------
    extractor : ClaimExtractor
        The claim extractor instance
    agent_name : str, optional
        Name for inter-agent messages (default ``"extract"``)

    Returns
    -------
    Callable[[ClaimState], dict[str, Any]]
        Subagent node function
    """

    def extract_node(state: ClaimState) -> dict[str, Any]:
        """Extract atomic claims from source text (subagent)."""
        text = state["source_text"]
        if not text:
            msg = _agent_msg(agent_name, "supervisor", "failed", {"reason": "empty text"})
            return {
                "errors": [f"{agent_name}: No source text provided"],
                "extraction_complete": False,
                "agent_messages": [msg],
            }

        logger.info("[%s] Extracting claims...", agent_name)
        try:
            claim_set = extractor.extract(text)
            claims_raw = [c.to_dict() for c in claim_set.claims]
            msg = _agent_msg(
                agent_name,
                "supervisor",
                "complete",
                {"claims_count": len(claims_raw)},
            )
            return {
                "claims_raw": claims_raw,
                "extraction_complete": True,
                "current_node": agent_name,
                "agent_messages": [msg],
            }
        except Exception as e:
            logger.error("[%s] Extraction failed: %s", agent_name, e)
            msg = _agent_msg(agent_name, "supervisor", "failed", {"error": str(e)})
            return {
                "errors": [f"{agent_name}: {e}"],
                "extraction_complete": False,
                "agent_messages": [msg],
            }

    return extract_node


# ---------------------------------------------------------------------------
# Verify subagent (sequential)
# ---------------------------------------------------------------------------


def make_verify_node(
    verifier: Any,
    agent_name: str = "verify",
) -> Callable[[ClaimState], dict[str, Any]]:
    """
    Create a LangGraph subagent that verifies claims **sequentially**.

    Parameters
    ----------
    verifier : ClaimVerifier
        The claim verifier instance
    agent_name : str, optional
        Name for inter-agent messages (default ``"verify"``)

    Returns
    -------
    Callable[[ClaimState], dict[str, Any]]
        Subagent node function
    """

    def verify_node(state: ClaimState) -> dict[str, Any]:
        """Verify extracted claims against literature (subagent)."""
        from pyeuropepmc.claims.models import Claim, ClaimSet

        claims_raw = state["claims_raw"]
        if not claims_raw:
            msg = _agent_msg(agent_name, "supervisor", "skipped", {"reason": "no claims"})
            return {
                "warnings": ["No claims to verify"],
                "verification_complete": False,
                "agent_messages": [msg],
            }

        logger.info("[%s] Verifying %d claims (sequential)...", agent_name, len(claims_raw))
        try:
            claims = [Claim.from_dict(c) for c in claims_raw]
            claim_set = ClaimSet(source_text=state["source_text"], claims=claims)

            claim_set = verifier.verify_claim_set(claim_set)

            msg = _agent_msg(
                agent_name,
                "supervisor",
                "complete",
                {"verified_count": len(claim_set.claims)},
            )
            return {
                "verified_claims": [c.to_dict() for c in claim_set.claims],
                "verification_summary": claim_set.verification_summary,
                "verification_complete": True,
                "current_node": agent_name,
                "agent_messages": [msg],
            }
        except Exception as e:
            logger.error("[%s] Verification failed: %s", agent_name, e)
            msg = _agent_msg(agent_name, "supervisor", "failed", {"error": str(e)})
            return {
                "errors": [f"{agent_name}: {e}"],
                "verification_complete": False,
                "agent_messages": [msg],
            }

    return verify_node


# ---------------------------------------------------------------------------
# Verify subagent (parallel — uses ThreadPoolExecutor for I/O-bound API calls)
# ---------------------------------------------------------------------------


def make_parallel_verify_node(
    verifier: Any,
    max_workers: int = 4,
    agent_name: str = "verify",
) -> Callable[[ClaimState], dict[str, Any]]:
    """
    Create a LangGraph subagent that verifies claims **in parallel**
    using a thread pool.

    Useful when each claim requires independent API calls to Europe PMC;
    the thread pool lets I/O overlap and reduces wall-clock time.

    Parameters
    ----------
    verifier : ClaimVerifier
        The claim verifier instance
    max_workers : int, optional
        Maximum number of parallel verification threads (default 4)
    agent_name : str, optional
        Name for inter-agent messages (default ``"verify"``)

    Returns
    -------
    Callable[[ClaimState], dict[str, Any]]
        Subagent node function
    """

    def parallel_verify_node(state: ClaimState) -> dict[str, Any]:
        """Verify extracted claims in parallel (subagent)."""
        from pyeuropepmc.claims.models import Claim, ClaimSet

        claims_raw = state["claims_raw"]
        if not claims_raw:
            msg = _agent_msg(agent_name, "supervisor", "skipped", {"reason": "no claims"})
            return {
                "warnings": ["No claims to verify"],
                "verification_complete": False,
                "agent_messages": [msg],
            }

        logger.info(
            "[%s] Verifying %d claims (parallel, %d workers)...",
            agent_name,
            len(claims_raw),
            max_workers,
        )
        try:
            claims = [Claim.from_dict(c) for c in claims_raw]

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(verifier.verify_claim, c): i for i, c in enumerate(claims)}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        future.result()
                    except Exception as exc:
                        logger.warning(
                            "[%s] Claim %d verification failed: %s", agent_name, idx, exc
                        )

            claim_set = ClaimSet(source_text=state["source_text"], claims=claims)

            msg = _agent_msg(
                agent_name,
                "supervisor",
                "complete",
                {"verified_count": len(claims)},
            )
            return {
                "verified_claims": [c.to_dict() for c in claims],
                "verification_summary": claim_set.verification_summary,
                "verification_complete": True,
                "current_node": agent_name,
                "agent_messages": [msg],
            }
        except Exception as e:
            logger.error("[%s] Parallel verification failed: %s", agent_name, e)
            msg = _agent_msg(agent_name, "supervisor", "failed", {"error": str(e)})
            return {
                "errors": [f"{agent_name}: {e}"],
                "verification_complete": False,
                "agent_messages": [msg],
            }

    return parallel_verify_node


# ---------------------------------------------------------------------------
# Review subagent
# ---------------------------------------------------------------------------


def make_review_node(
    reviewer: Any,
    agent_name: str = "review",
) -> Callable[[ClaimState], dict[str, Any]]:
    """
    Create a LangGraph subagent that reviews verification results.

    Parameters
    ----------
    reviewer : ClaimReviewer
        The claim reviewer instance
    agent_name : str, optional
        Name for inter-agent messages (default ``"review"``)

    Returns
    -------
    Callable[[ClaimState], dict[str, Any]]
        Subagent node function
    """

    def review_node(state: ClaimState) -> dict[str, Any]:
        """Review evidence quality (subagent)."""
        from pyeuropepmc.claims.models import Claim, ClaimSet

        verified = state["verified_claims"]
        if not verified:
            msg = _agent_msg(agent_name, "supervisor", "skipped", {"reason": "no verified claims"})
            return {
                "warnings": ["No verified claims to review"],
                "review_complete": False,
                "agent_messages": [msg],
            }

        logger.info("[%s] Reviewing evidence quality...", agent_name)
        try:
            claims = [Claim.from_dict(c) for c in verified]
            claim_set = ClaimSet(source_text=state["source_text"], claims=claims)

            review = reviewer.review_claim_set(claim_set)

            msg = _agent_msg(
                agent_name, "supervisor", "complete", {"quality": review.get("overall_quality")}
            )
            return {
                "review": review,
                "review_complete": True,
                "current_node": agent_name,
                "agent_messages": [msg],
            }
        except Exception as e:
            logger.error("[%s] Review failed: %s", agent_name, e)
            msg = _agent_msg(agent_name, "supervisor", "failed", {"error": str(e)})
            return {
                "errors": [f"{agent_name}: {e}"],
                "review_complete": False,
                "agent_messages": [msg],
            }

    return review_node


# ---------------------------------------------------------------------------
# Write subagent
# ---------------------------------------------------------------------------


def make_write_node(
    writer: Any,
    agent_name: str = "write",
) -> Callable[[ClaimState], dict[str, Any]]:
    """
    Create a LangGraph subagent that generates the final report.

    Parameters
    ----------
    writer : ClaimWriter
        The claim writer instance
    agent_name : str, optional
        Name for inter-agent messages (default ``"write"``)

    Returns
    -------
    Callable[[ClaimState], dict[str, Any]]
        Subagent node function
    """

    def write_node(state: ClaimState) -> dict[str, Any]:
        """Generate improved text with citations and bibliography (subagent)."""
        from pyeuropepmc.claims.models import Claim, ClaimSet

        source_text = state["source_text"]
        verified = state["verified_claims"]
        user_decisions = state["user_decisions"]
        bib_format = state["bibliography_format"]

        if not verified:
            msg = _agent_msg(agent_name, "supervisor", "skipped", {"reason": "no claims"})
            return {
                "improved_text": source_text,
                "bibliography": [],
                "output_complete": False,
                "warnings": ["No claims to write"],
                "agent_messages": [msg],
            }

        logger.info("[%s] Generating report...", agent_name)
        try:
            claims = [Claim.from_dict(c) for c in verified]
            claim_set = ClaimSet(source_text=source_text, claims=claims)

            report = writer.write_report(
                original_text=source_text,
                claim_set=claim_set,
                user_decisions=user_decisions,
                bibliography_format=bib_format,
            )

            review = state.get("review", {})
            report.review_notes = review.get("llm_review")

            msg = _agent_msg(
                agent_name,
                "supervisor",
                "complete",
                {"bib_entries": len(report.bibliography)},
            )
            return {
                "improved_text": report.improved_text,
                "bibliography": report.bibliography,
                "output_complete": True,
                "current_node": agent_name,
                "agent_messages": [msg],
            }
        except Exception as e:
            logger.error("[%s] Write failed: %s", agent_name, e)
            msg = _agent_msg(agent_name, "supervisor", "failed", {"error": str(e)})
            return {
                "errors": [f"{agent_name}: {e}"],
                "output_complete": False,
                "agent_messages": [msg],
            }

    return write_node


__all__ = [
    "make_extract_node",
    "make_verify_node",
    "make_parallel_verify_node",
    "make_review_node",
    "make_write_node",
]
