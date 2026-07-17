"""
Claim review and evidence quality assessment.

ClaimReviewer evaluates the quality of evidence gathered for each claim,
identifies gaps, suggests additional searches, and provides an overall
quality assessment of the verification.

Acts as the "review agent" in the full workflow pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.agentic.llm_client import LLMClient, create_llm_client
from pyeuropepmc.claims.models import (
    ClaimSet,
    EvidenceQuality,
    Verdict,
)

logger = logging.getLogger(__name__)


class ClaimReviewer:
    """
    Review and assess the quality of claim verification results.

    Evaluates:
    - Evidence quality and relevance
    - Coverage across claims
    - Strength of support/refutation
    - Suggestions for improvement

    Parameters
    ----------
    llm_client : LLMClient, optional
        LLM client for review generation
    llm_enabled : bool, optional
        Whether LLM is enabled (default: True)
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        llm_enabled: bool = True,
    ):
        self.llm_client = llm_client or create_llm_client(enabled=llm_enabled)
        self.llm_enabled = llm_enabled

    def review_claim_set(self, claim_set: ClaimSet) -> dict[str, Any]:
        """
        Perform a comprehensive review of a verified claim set.

        Parameters
        ----------
        claim_set : ClaimSet
            The verified claims to review

        Returns
        -------
        dict
            Review results with evidence quality scores, gap analysis,
            and improvement suggestions
        """
        if not claim_set.claims:
            return {
                "overall_quality": "empty",
                "total_claims": 0,
                "message": "No claims to review.",
            }

        evidence_quality = self._assess_evidence_quality(claim_set)
        coverage = self._assess_coverage(claim_set)
        gaps = self._identify_gaps(claim_set)
        suggestions = self._generate_suggestions(claim_set, gaps)

        review = {
            "overall_quality": self._compute_overall_quality(evidence_quality, coverage),
            "total_claims": len(claim_set.claims),
            "evidence_quality": evidence_quality,
            "coverage": coverage,
            "gaps": gaps,
            "suggestions": suggestions,
            "verification_summary": claim_set.verification_summary,
        }

        # LLM-enhanced review
        if self.llm_enabled and self.llm_client.enabled:
            try:
                llm_review = self._llm_review(claim_set, review)
                review["llm_review"] = llm_review
            except Exception as e:
                logger.warning(f"LLM review failed: {e}")
                review["llm_review"] = None

        return review

    def _assess_evidence_quality(self, claim_set: ClaimSet) -> dict[str, Any]:
        """Assess the quality of evidence across all claims."""
        verified = [c for c in claim_set.claims if c.evidence]

        if not verified:
            return {
                "average_relevance": 0.0,
                "quality_distribution": {},
                "with_evidence": 0,
                "total": len(claim_set.claims),
            }

        quality_counts: dict[str, int] = {}
        relevance_scores = []

        for claim in verified:
            for ev in claim.evidence:
                quality_counts[ev.quality.value] = quality_counts.get(ev.quality.value, 0) + 1
                relevance_scores.append(ev.relevance_score)

        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

        return {
            "average_relevance": round(avg_relevance, 3),
            "quality_distribution": quality_counts,
            "with_evidence": len(verified),
            "total": len(claim_set.claims),
        }

    def _assess_coverage(self, claim_set: ClaimSet) -> dict[str, Any]:
        """Assess how well claims are covered by evidence."""
        total = len(claim_set.claims)
        if total == 0:
            return {"coverage_pct": 0.0, "verdict_distribution": {}}

        verdict_counts: dict[str, int] = {}
        for c in claim_set.claims:
            verdict_counts[c.verdict.value] = verdict_counts.get(c.verdict.value, 0) + 1

        with_evidence = sum(
            1
            for c in claim_set.claims
            if c.verdict in (Verdict.SUPPORTED, Verdict.REFUTED, Verdict.PARTIALLY_SUPPORTED)
        )

        return {
            "coverage_pct": round(with_evidence / total * 100, 1) if total else 0.0,
            "verdict_distribution": verdict_counts,
            "claims_with_evidence": with_evidence,
            "total": total,
        }

    def _identify_gaps(self, claim_set: ClaimSet) -> list[dict[str, Any]]:
        """Identify gaps in evidence coverage."""
        gaps = []

        for claim in claim_set.claims:
            if claim.verdict == Verdict.INSUFFICIENT_EVIDENCE:
                gaps.append(
                    {
                        "claim_id": claim.id,
                        "claim_text": claim.text[:100],
                        "gap_type": "insufficient_evidence",
                        "suggestion": "Try alternative search terms or broader query.",
                    }
                )
            elif claim.verdict == Verdict.NOT_CHECKED:
                gaps.append(
                    {
                        "claim_id": claim.id,
                        "claim_text": claim.text[:100],
                        "gap_type": "not_verified",
                        "suggestion": "Claim was not verified.",
                    }
                )
            elif claim.verdict == Verdict.REFUTED:
                gaps.append(
                    {
                        "claim_id": claim.id,
                        "claim_text": claim.text[:100],
                        "gap_type": "contradictory_evidence",
                        "suggestion": "Claim contradicts found evidence. Consider revising.",
                    }
                )

        return gaps

    def _generate_suggestions(
        self,
        claim_set: ClaimSet,
        gaps: list[dict[str, Any]],
    ) -> list[str]:
        """Generate actionable suggestions."""
        suggestions = []
        summary = claim_set.verification_summary

        if summary["refuted"] > 0:
            suggestions.append(
                f"Review {summary['refuted']} refuted claim(s) carefully "
                "and consider correcting the source text."
            )

        if summary["insufficient_evidence"] > 0:
            suggestions.append(
                f"Perform additional searches for {summary['insufficient_evidence']} "
                "claim(s) with insufficient evidence."
            )

        if summary["not_checked"] > 0:
            suggestions.append(f"Verify {summary['not_checked']} unchecked claim(s).")

        # Check evidence quality
        low_quality = sum(
            1
            for c in claim_set.claims
            for e in c.evidence
            if e.quality in (EvidenceQuality.LOW, EvidenceQuality.UNCERTAIN)
        )
        if low_quality > 0:
            suggestions.append(
                f"{low_quality} evidence item(s) have low quality. "
                "Consider finding stronger sources."
            )

        if not suggestions:
            suggestions.append("All claims have supporting evidence. Good quality review.")

        return suggestions

    def _compute_overall_quality(
        self,
        evidence_quality: dict[str, Any],
        coverage: dict[str, Any],
    ) -> str:
        """Compute overall quality rating."""
        if evidence_quality.get("total", 0) == 0:
            return "no_evidence"

        coverage_pct = coverage.get("coverage_pct", 0)
        avg_relevance = evidence_quality.get("average_relevance", 0)

        if coverage_pct >= 80 and avg_relevance >= 0.6:
            return "excellent"
        elif coverage_pct >= 60 and avg_relevance >= 0.4:
            return "good"
        elif coverage_pct >= 40:
            return "fair"
        else:
            return "poor"

    def _llm_review(
        self,
        claim_set: ClaimSet,
        review_data: dict[str, Any],
    ) -> str:
        """Generate an LLM-enhanced review narrative."""
        summary = claim_set.verification_summary

        claims_summary = []
        for c in claim_set.claims:
            evidence_texts = [e.text[:100] for e in c.evidence[:2]]
            claims_summary.append(
                f"Claim: {c.text[:100]}\n"
                f"  Verdict: {c.verdict.value}\n"
                f"  Evidence: {'; '.join(evidence_texts) if evidence_texts else 'None'}"
            )

        prompt = f"""You are a scientific claim review expert. Review the following claim verification results and provide a concise assessment.

Summary:
- Total claims: {summary["total"]}
- Supported: {summary["supported"]}
- Refuted: {summary["refuted"]}
- Insufficient evidence: {summary["insufficient_evidence"]}
- Partially supported: {summary["partially_supported"]}

Overall quality: {review_data.get("overall_quality", "unknown")}

Claims details:
{chr(10).join(claims_summary)}

Provide a brief review (2-3 paragraphs) covering:
1. Overall assessment of the evidence quality
2. Any concerning findings (refuted claims, gaps)
3. Recommendations for the writer agent
"""

        try:
            result = self.llm_client.generate(prompt)
            return result or "LLM review not available."
        except Exception as e:
            logger.warning(f"LLM review generation failed: {e}")
            return "LLM review not available."


__all__ = ["ClaimReviewer"]
