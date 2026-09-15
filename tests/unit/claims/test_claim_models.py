"""Tests for claims models."""

from pyeuropepmc.claims.models import (
    Claim,
    ClaimEvidence,
    ClaimReport,
    ClaimSet,
    ClaimType,
    EvidenceQuality,
    Verdict,
)


class TestClaimModels:
    def test_claim_creation(self):
        c = Claim(
            id="c1",
            text="CRISPR-Cas9 corrects mutations",
            original_text="CRISPR-Cas9 corrects 75% of beta-thalassemia mutations in vitro.",
            claim_type=ClaimType.EXISTENCE,
            confidence=0.9,
        )
        assert c.id == "c1"
        assert c.verdict == Verdict.NOT_CHECKED
        assert c.claim_type == ClaimType.EXISTENCE

    def test_claim_to_dict_roundtrip(self):
        c = Claim(
            id="c1",
            text="test claim",
            original_text="original text",
            claim_type=ClaimType.NUMERICAL,
            confidence=0.8,
            verdict=Verdict.SUPPORTED,
        )
        d = c.to_dict()
        assert d["id"] == "c1"
        assert d["verdict"] == "supported"

        c2 = Claim.from_dict(d)
        assert c2.id == c.id
        assert c2.verdict == c.verdict
        assert c2.claim_type == ClaimType.NUMERICAL

    def test_claim_with_evidence(self):
        ev = ClaimEvidence(
            text="CRISPR corrects mutations efficiently",
            paper_title="CRISPR Study",
            authors="Smith J",
            source="12345",
            source_type="pmid",
            relevance_score=0.85,
            quality=EvidenceQuality.HIGH,
        )
        c = Claim(
            id="c1",
            text="test",
            original_text="test",
            evidence=[ev],
        )
        assert len(c.evidence) == 1
        assert c.evidence[0].quality == EvidenceQuality.HIGH

    def test_claim_evidence_roundtrip(self):
        ev = ClaimEvidence(
            text="evidence text",
            paper_title="Paper",
            authors="Author A",
            source="doi:10.1234/test",
            source_type="doi",
            year=2023,
        )
        d = ev.to_dict()
        assert d["year"] == 2023
        assert d["quality"] == "medium"

        ev2 = ClaimEvidence.from_dict(d)
        assert ev2.year == 2023
        assert ev2.quality == EvidenceQuality.MEDIUM

    def test_claim_set_summary(self):
        cs = ClaimSet(source_text="test text")
        cs.claims = [
            Claim(id="c1", text="supported", original_text="s", verdict=Verdict.SUPPORTED),
            Claim(id="c2", text="refuted", original_text="r", verdict=Verdict.REFUTED),
            Claim(
                id="c3",
                text="insufficient",
                original_text="i",
                verdict=Verdict.INSUFFICIENT_EVIDENCE,
            ),
            Claim(id="c4", text="unchecked", original_text="u"),
        ]
        summary = cs.verification_summary
        assert summary["total"] == 4
        assert summary["supported"] == 1
        assert summary["refuted"] == 1
        assert summary["not_checked"] == 1

    def test_claim_set_properties(self):
        cs = ClaimSet(source_text="test")
        cs.claims = [
            Claim(id="c1", text="a", original_text="a", verdict=Verdict.SUPPORTED),
            Claim(id="c2", text="b", original_text="b", verdict=Verdict.REFUTED),
        ]
        assert len(cs.supported) == 1
        assert len(cs.refuted) == 1
        assert len(cs.insufficient) == 0

    def test_claim_set_roundtrip(self):
        cs = ClaimSet(source_text="test")
        cs.claims = [
            Claim(id="c1", text="a", original_text="a", verdict=Verdict.SUPPORTED),
        ]
        d = cs.to_dict()
        assert d["summary"]["supported"] == 1

        cs2 = ClaimSet.from_dict(d)
        assert cs2.source_text == "test"
        assert len(cs2.claims) == 1

    def test_claim_report_creation(self):
        report = ClaimReport(
            original_text="original",
            improved_text="improved",
            bibliography=[{"id": "ref1", "title": "Paper"}],
        )
        assert report.original_text == "original"
        assert len(report.bibliography) == 1

    def test_claim_types(self):
        assert ClaimType.NUMERICAL.value == "numerical"
        assert ClaimType.CAUSAL.value == "causal"
        assert ClaimType.COMPARATIVE.value == "comparative"

    def test_evidence_quality_values(self):
        assert EvidenceQuality.HIGH.value == "high"
        assert EvidenceQuality.LOW.value == "low"

    def test_verdict_values(self):
        assert Verdict.SUPPORTED.value == "supported"
        assert Verdict.REFUTED.value == "refuted"
