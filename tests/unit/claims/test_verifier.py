"""Tests for claim verifier."""

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.claims.models import Claim, ClaimEvidence, ClaimSet, Verdict
from pyeuropepmc.claims.verifier import ClaimVerifier


class TestClaimVerifier:
    def test_verify_no_evidence(self):
        verifier = ClaimVerifier(llm_enabled=False)
        claim = Claim(id="c1", text="Obscure ultra-specific claim", original_text="test")
        with patch.object(verifier, "_search_evidence", return_value=[]):
            result = verifier.verify_claim(claim)

        assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert len(result.evidence) == 0

    def test_verify_with_evidence(self):
        verifier = ClaimVerifier(llm_enabled=False)
        claim = Claim(id="c1", text="CRISPR treats disease", original_text="test")
        mock_papers = [
            {
                "title": "CRISPR Study",
                "authorString": "Smith J",
                "pmid": "12345",
                "abstractText": "CRISPR-Cas9 can efficiently treat genetic diseases in vitro.",
                "pubYear": "2023",
                "journalTitle": "Nature",
                "citedByCount": 50,
            }
        ]
        with patch.object(verifier, "_search_evidence", return_value=mock_papers):
            result = verifier.verify_claim(claim)

        assert result.verdict == Verdict.SUPPORTED
        assert len(result.evidence) == 1
        assert result.evidence[0].source == "12345"

    def test_verify_caching(self):
        verifier = ClaimVerifier(llm_enabled=False)
        claim = Claim(id="c1", text="Same claim text", original_text="test")
        mock_papers = [
            {
                "title": "Paper",
                "authorString": "Author",
                "pmid": "999",
                "abstractText": "Some text.",
            }
        ]

        with patch.object(verifier, "_search_evidence", return_value=mock_papers) as mock_search:
            verifier.verify_claim(claim)
            verifier.verify_claim(claim)  # cache hit

        assert mock_search.call_count == 1

    def test_verify_llm_verdict(self):
        """LLM returns supported verdict."""
        verifier = ClaimVerifier(llm_enabled=True)
        claim = Claim(id="c1", text="CRISPR effective", original_text="test")
        mock_papers = [
            {
                "title": "Paper",
                "authorString": "Author",
                "pmid": "1",
                "abstractText": "CRISPR effective.",
            }
        ]

        with patch.object(verifier, "_search_evidence", return_value=mock_papers):
            with patch.object(
                verifier, "_llm_verify", return_value=(Verdict.SUPPORTED, "Evidence supports.")
            ):
                verifier.llm_client = MagicMock()
                verifier.llm_client.enabled = True
                result = verifier.verify_claim(claim)

        assert result.verdict == Verdict.SUPPORTED

    def test_verify_llm_refuted(self):
        """LLM returns refuted verdict."""
        verifier = ClaimVerifier(llm_enabled=True)
        claim = Claim(id="c1", text="CRISPR dangerous", original_text="test")
        with patch.object(
            verifier,
            "_search_evidence",
            return_value=[
                {"title": "P", "authorString": "A", "pmid": "1", "abstractText": "CRISPR safe."}
            ],
        ):
            with patch.object(
                verifier, "_llm_verify", return_value=(Verdict.REFUTED, "Contradicts.")
            ):
                verifier.llm_client = MagicMock()
                verifier.llm_client.enabled = True
                result = verifier.verify_claim(claim)

        assert result.verdict == Verdict.REFUTED

    def test_verify_claim_set(self):
        verifier = ClaimVerifier(llm_enabled=False)
        cs = ClaimSet(source_text="test")
        cs.claims = [
            Claim(id="c1", text="One", original_text="o"),
            Claim(id="c2", text="Two", original_text="t"),
        ]

        with patch.object(verifier, "verify_claim", side_effect=lambda c: c):
            result = verifier.verify_claim_set(cs)

        assert result.metadata.get("verification_complete") is True

    def test_estimate_relevance_match(self):
        verifier = ClaimVerifier()
        score = verifier._estimate_relevance(
            "CRISPR corrects mutations", "We found that CRISPR corrects mutations in mice"
        )
        assert score >= 0.5

    def test_estimate_relevance_no_match(self):
        verifier = ClaimVerifier()
        score = verifier._estimate_relevance("Quantum computing", "Climate change affects bears")
        assert score < 0.5

    def test_parse_verdict_json(self):
        verifier = ClaimVerifier()
        v, r = verifier._parse_verdict('{"verdict": "supported", "reasoning": "Good."}')
        assert v == Verdict.SUPPORTED
        assert r == "Good."

    def test_parse_verdict_refuted(self):
        verifier = ClaimVerifier()
        v, r = verifier._parse_verdict('{"verdict": "refuted", "reasoning": "Bad."}')
        assert v == Verdict.REFUTED

    def test_parse_verdict_keyword(self):
        verifier = ClaimVerifier()
        v, r = verifier._parse_verdict("The evidence strongly supported the claim")
        assert v == Verdict.SUPPORTED

    def test_clear_cache(self):
        verifier = ClaimVerifier()
        verifier._verification_cache["test"] = (Verdict.SUPPORTED, "", [])
        verifier.clear_cache()
        assert len(verifier._verification_cache) == 0
