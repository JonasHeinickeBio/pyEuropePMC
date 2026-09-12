"""
Agentic ToolRegistry tools for the claim verification workflow.

Registers tools that wrap the claims module for use with
the AgentOrchestrator and ResearchPipeline systems.
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.agentic.registry import ToolRegistry, ToolType
from pyeuropepmc.claims.extractor import ClaimExtractor
from pyeuropepmc.claims.models import ClaimSet, Verdict
from pyeuropepmc.claims.reviewer import ClaimReviewer
from pyeuropepmc.claims.verifier import ClaimVerifier
from pyeuropepmc.claims.writer import ClaimWriter

logger = logging.getLogger(__name__)

# Create the claims tool registry
claims_registry = ToolRegistry(name="claims")

# Store workflow state for multi-step interaction
_workflow_state: dict[str, Any] = {}
_extractor_cache: ClaimExtractor | None = None
_verifier_cache: ClaimVerifier | None = None
_reviewer_cache: ClaimReviewer | None = None
_writer_cache: ClaimWriter | None = None


def _get_extractor() -> ClaimExtractor:
    global _extractor_cache
    if _extractor_cache is None:
        _extractor_cache = ClaimExtractor()
    return _extractor_cache


def _get_verifier() -> ClaimVerifier:
    global _verifier_cache
    if _verifier_cache is None:
        _verifier_cache = ClaimVerifier()
    return _verifier_cache


def _get_reviewer() -> ClaimReviewer:
    global _reviewer_cache
    if _reviewer_cache is None:
        _reviewer_cache = ClaimReviewer()
    return _reviewer_cache


def _get_writer() -> ClaimWriter:
    global _writer_cache
    if _writer_cache is None:
        _writer_cache = ClaimWriter()
    return _writer_cache


# ---------------------------------------------------------------------------
# Tool: Extract claims from text
# ---------------------------------------------------------------------------


@claims_registry.register(
    name="claim_extract",
    description="Extract atomic verifiable claims from a text paragraph/sentence",
    tool_type=ToolType.ANALYSIS,
)
def claim_extract(text: str) -> dict[str, Any]:
    """
    Extract atomic claims from source text.

    Parameters
    ----------
    text : str
        The text to analyze

    Returns
    -------
    dict
        Extracted claims with types and confidence
    """
    try:
        extractor = _get_extractor()
        claim_set = extractor.extract(text)

        # Store in workflow state
        _workflow_state["claim_set"] = claim_set
        _workflow_state["source_text"] = text

        return {
            "success": True,
            "claims": [c.to_dict() for c in claim_set.claims],
            "count": len(claim_set.claims),
            "source_text": text,
        }
    except Exception as e:
        logger.error(f"Claim extraction error: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tool: Verify claims
# ---------------------------------------------------------------------------


@claims_registry.register(
    name="claim_verify",
    description="Verify extracted claims against Europe PMC literature",
    tool_type=ToolType.ANALYSIS,
)
def claim_verify(claim_ids: list[str] | None = None) -> dict[str, Any]:
    """
    Verify claims against scientific literature.

    Parameters
    ----------
    claim_ids : list of str, optional
        Specific claim IDs to verify (default: all)

    Returns
    -------
    dict
        Verification results with evidence and verdicts
    """
    try:
        claim_set: ClaimSet | None = _workflow_state.get("claim_set")
        if not claim_set:
            return {"success": False, "error": "No claims to verify. Run claim_extract first."}

        verifier = _get_verifier()

        if claim_ids:
            for claim in claim_set.claims:
                if claim.id in claim_ids:
                    verifier.verify_claim(claim)
        else:
            claim_set = verifier.verify_claim_set(claim_set)
            _workflow_state["claim_set"] = claim_set

        return {
            "success": True,
            "summary": claim_set.verification_summary,
            "claims": [c.to_dict() for c in claim_set.claims],
        }
    except Exception as e:
        logger.error(f"Claim verification error: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tool: Review claims
# ---------------------------------------------------------------------------


@claims_registry.register(
    name="claim_review",
    description="Review evidence quality and provide assessment",
    tool_type=ToolType.ANALYSIS,
)
def claim_review() -> dict[str, Any]:
    """
    Review the quality of claim verification results.

    Returns
    -------
    dict
        Review with evidence quality, gaps, and suggestions
    """
    try:
        claim_set: ClaimSet | None = _workflow_state.get("claim_set")
        if not claim_set:
            return {"success": False, "error": "No claims to review. Run claim_extract first."}

        reviewer = _get_reviewer()
        review = reviewer.review_claim_set(claim_set)

        _workflow_state["review"] = review

        return {
            "success": True,
            "overall_quality": review.get("overall_quality", "unknown"),
            "gaps": review.get("gaps", []),
            "suggestions": review.get("suggestions", []),
            "coverage": review.get("coverage", {}),
            "evidence_quality": review.get("evidence_quality", {}),
            "llm_review": review.get("llm_review"),
        }
    except Exception as e:
        logger.error(f"Claim review error: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tool: Accept / reject a claim
# ---------------------------------------------------------------------------


@claims_registry.register(
    name="claim_accept",
    description="Accept or reject a specific claim for inclusion in output",
    tool_type=ToolType.UTILITY,
)
def claim_accept(claim_id: str, accepted: bool) -> dict[str, Any]:
    """
    Accept or reject a specific claim.

    Parameters
    ----------
    claim_id : str
        ID of the claim
    accepted : bool
        True to accept, False to reject

    Returns
    -------
    dict
        Confirmation of decision
    """
    decisions = _workflow_state.setdefault("user_decisions", {})
    decisions[claim_id] = accepted
    return {"success": True, "claim_id": claim_id, "accepted": accepted}


# ---------------------------------------------------------------------------
# Tool: Write improved text
# ---------------------------------------------------------------------------


@claims_registry.register(
    name="claim_write",
    description="Generate improved text with citations and bibliography",
    tool_type=ToolType.ANALYSIS,
)
def claim_write(bib_format: str = "bibtex") -> dict[str, Any]:
    """
    Generate improved text with citations.

    Parameters
    ----------
    bib_format : str, optional
        Bibliography format (bibtex, ris, csl)

    Returns
    -------
    dict
        Improved text and bibliography
    """
    try:
        claim_set: ClaimSet | None = _workflow_state.get("claim_set")
        source_text: str | None = _workflow_state.get("source_text")

        if not claim_set or not source_text:
            return {
                "success": False,
                "error": "No claims or source text. Run claim_extract first.",
            }

        user_decisions = _workflow_state.get("user_decisions", {})

        writer = _get_writer()
        report = writer.write_report(
            original_text=source_text,
            claim_set=claim_set,
            user_decisions=user_decisions,
            bibliography_format=bib_format,
        )

        _workflow_state["report"] = report

        return {
            "success": True,
            "improved_text": report.improved_text,
            "bibliography": report.bibliography,
            "bibliography_count": len(report.bibliography),
        }
    except Exception as e:
        logger.error(f"Claim write error: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tool: Get claim summary
# ---------------------------------------------------------------------------


@claims_registry.register(
    name="claim_summary",
    description="Get summary of claim verification results",
    tool_type=ToolType.UTILITY,
)
def claim_summary() -> dict[str, Any]:
    """Get a summary of current claim verification status."""
    claim_set: ClaimSet | None = _workflow_state.get("claim_set")
    if not claim_set:
        return {"success": True, "status": "no_claims"}

    return {
        "success": True,
        "total_claims": len(claim_set.claims),
        "summary": claim_set.verification_summary,
        "has_evidence": sum(1 for c in claim_set.claims if c.evidence),
    }


# ---------------------------------------------------------------------------
# Tool: Get evidence for a claim
# ---------------------------------------------------------------------------


@claims_registry.register(
    name="claim_get_evidence",
    description="Get evidence details for a specific claim",
    tool_type=ToolType.UTILITY,
)
def claim_get_evidence(claim_id: str) -> dict[str, Any]:
    """Get evidence details for a specific claim."""
    claim_set: ClaimSet | None = _workflow_state.get("claim_set")
    if not claim_set:
        return {"success": False, "error": "No claims."}

    for claim in claim_set.claims:
        if claim.id == claim_id:
            return {
                "success": True,
                "claim": claim.to_dict(),
            }

    return {"success": False, "error": f"Claim '{claim_id}' not found."}


# ---------------------------------------------------------------------------
# Tool: Run full workflow
# ---------------------------------------------------------------------------


@claims_registry.register(
    name="claim_run_workflow",
    description="Run the full claim workflow: extract, verify, review, write",
    tool_type=ToolType.AGENT,
)
def claim_run_workflow(
    text: str,
    bib_format: str = "bibtex",
    accept_supported: bool = True,
) -> dict[str, Any]:
    """
    Run the complete claim verification workflow.

    Parameters
    ----------
    text : str
        Source text to analyze
    bib_format : str, optional
        Bibliography format
    accept_supported : bool, optional
        Whether to auto-accept supported claims

    Returns
    -------
    dict
        Full workflow results
    """
    try:
        # 1. Extract
        extractor = _get_extractor()
        claim_set = extractor.extract(text)

        _workflow_state["claim_set"] = claim_set
        _workflow_state["source_text"] = text

        # 2. Verify
        verifier = _get_verifier()
        claim_set = verifier.verify_claim_set(claim_set)
        _workflow_state["claim_set"] = claim_set

        # 3. Review
        reviewer = _get_reviewer()
        review = reviewer.review_claim_set(claim_set)
        _workflow_state["review"] = review

        # 4. Auto-decisions
        user_decisions = {}
        for claim in claim_set.claims:
            if accept_supported and claim.verdict in (
                Verdict.SUPPORTED,
                Verdict.PARTIALLY_SUPPORTED,
            ):
                user_decisions[claim.id] = True
            elif claim.verdict == Verdict.REFUTED:
                user_decisions[claim.id] = False
            else:
                user_decisions[claim.id] = False
        _workflow_state["user_decisions"] = user_decisions

        # 5. Write
        writer = _get_writer()
        report = writer.write_report(
            original_text=text,
            claim_set=claim_set,
            user_decisions=user_decisions,
            bibliography_format=bib_format,
        )
        report.review_notes = review.get("llm_review")

        _workflow_state["report"] = report

        return {
            "success": True,
            "summary": claim_set.verification_summary,
            "overall_quality": review.get("overall_quality", "unknown"),
            "improved_text": report.improved_text,
            "bibliography": report.bibliography,
            "bibliography_count": len(report.bibliography),
            "claims": [c.to_dict() for c in claim_set.claims],
            "suggestions": review.get("suggestions", []),
            "gaps": review.get("gaps", []),
        }
    except Exception as e:
        logger.error(f"Claim workflow error: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_all_claims_tools(target_registry: ToolRegistry | None = None) -> ToolRegistry:
    """
    Register all claims tools into a target registry.

    Parameters
    ----------
    target_registry : ToolRegistry, optional
        Target registry to copy tools into

    Returns
    -------
    ToolRegistry
        The registry with claims tools
    """
    if target_registry is not None:
        for info in claims_registry.list_all():
            fn = info.func
            if fn:
                target_registry.register(
                    name=info.name,
                    description=info.description,
                    tool_type=info.tool_type,
                )(fn)
        return target_registry
    return claims_registry


__all__ = [
    "claims_registry",
    "register_all_claims_tools",
    "claim_extract",
    "claim_verify",
    "claim_review",
    "claim_accept",
    "claim_write",
    "claim_summary",
    "claim_get_evidence",
    "claim_run_workflow",
]
