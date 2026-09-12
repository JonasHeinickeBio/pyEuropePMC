"""Tests for claim reviewer."""

import pytest
from pyeuropepmc.claims.models import Claim, ClaimEvidence, ClaimSet, EvidenceQuality, Verdict
from pyeuropepmc.claims.reviewer import ClaimReviewer


class TestClaimReviewer:
    def test_review_empty_claim_set(self):
        reviewer = ClaimReviewer(llm_enabled=False)
        cs = ClaimSet(source_text="test")
        review = reviewer.review_claim_set(cs)
        assert review["overall_quality"] == "empty"
        assert review["total_claims"] == 0

    def test_review_all_supported(self):
        reviewer = ClaimReviewer(llm_enabled=False)
        cs = ClaimSet(source_text="test")
        cs.claims = [
            Claim(
                id="c1", text="test1", original_text="t1",
                verdict=Verdict.SUPPORTED,
                evidence=[
                    ClaimEvidence(
                        text="evidence text",
                        paper_title="Paper",
                        authors="Author",
                        source="1",
                        relevance_score=0.9,
                        quality=EvidenceQuality.HIGH,
                    )
                ],
            ),
        ]
        review = reviewer.review_claim_set(cs)
        assert review["overall_quality"] in ("good", "excellent")
        assert review["total_claims"] == 1

    def test_review_generates_suggestions(self):
        reviewer = ClaimReviewer(llm_enabled=False)
        cs = ClaimSet(source_text="test")
        cs.claims = [
            Claim(id="c1", text="refuted claim", original_text="r",
                  verdict=Verdict.REFUTED),
            Claim(id="c2", text="insufficient", original_text="i",
                  verdict=Verdict.INSUFFICIENT_EVIDENCE),
            Claim(id="c3", text="unchecked", original_text="u",
                  verdict=Verdict.NOT_CHECKED),
        ]
        review = reviewer.review_claim_set(cs)
        assert len(review["suggestions"]) >= 2
        assert len(review["gaps"]) >= 2

    def test_assess_evidence_quality(self):
        reviewer = ClaimReviewer(llm_enabled=False)
        cs = ClaimSet(source_text="test")
        cs.claims = [
            Claim(
                id="c1", text="t", original_text="t",
                verdict=Verdict.SUPPORTED,
                evidence=[
                    ClaimEvidence(
                        text="e", paper_title="P", authors="A", source="1",
                        relevance_score=0.8, quality=EvidenceQuality.HIGH,
                    ),
                    ClaimEvidence(
                        text="e2", paper_title="P2", authors="A2", source="2",
                        relevance_score=0.4, quality=EvidenceQuality.LOW,
                    ),
                ],
            ),
        ]
        quality = reviewer._assess_evidence_quality(cs)
        assert quality["average_relevance"] == 0.6
        assert quality["quality_distribution"].get("high") == 1
        assert quality["quality_distribution"].get("low") == 1

    def test_assess_coverage(self):
        reviewer = ClaimReviewer(llm_enabled=False)
        cs = ClaimSet(source_text="test")
        cs.claims = [
            Claim(id="c1", text="a", original_text="a", verdict=Verdict.SUPPORTED),
            Claim(id="c2", text="b", original_text="b", verdict=Verdict.REFUTED),
            Claim(id="c3", text="c", original_text="c", verdict=Verdict.NOT_CHECKED),
        ]
        coverage = reviewer._assess_coverage(cs)
        assert coverage["claims_with_evidence"] == 2
        assert coverage["coverage_pct"] == pytest.approx(66.7, rel=0.1)

    def test_identify_gaps(self):
        reviewer = ClaimReviewer(llm_enabled=False)
        cs = ClaimSet(source_text="test")
        cs.claims = [
            Claim(id="c1", text="supported", original_text="s", verdict=Verdict.SUPPORTED),
            Claim(id="c2", text="refuted", original_text="r", verdict=Verdict.REFUTED),
            Claim(id="c3", text="insufficient", original_text="i", verdict=Verdict.INSUFFICIENT_EVIDENCE),
        ]
        gaps = reviewer._identify_gaps(cs)
        assert len(gaps) == 2
        gap_types = {g["gap_type"] for g in gaps}
        assert "contradictory_evidence" in gap_types
        assert "insufficient_evidence" in gap_types
