"""Tests for claim extraction."""

from unittest.mock import MagicMock

from pyeuropepmc.claims.extractor import ClaimExtractor


class TestClaimExtractor:
    def test_extract_empty_text(self):
        extractor = ClaimExtractor(llm_enabled=False)
        result = extractor.extract("")
        assert len(result.claims) == 0

        result = extractor.extract("   ")
        assert len(result.claims) == 0

    def test_extract_fallback_splits_sentences(self):
        extractor = ClaimExtractor(llm_enabled=False)
        result = extractor.extract("First sentence. Second sentence. Third one here.")
        assert len(result.claims) == 3
        assert result.claims[0].text == "First sentence."
        assert result.metadata.get("fallback") is True

    def test_extract_fallback_single_sentence(self):
        extractor = ClaimExtractor(llm_enabled=False)
        result = extractor.extract("Just one sentence here.")
        assert len(result.claims) == 1

    def test_min_confidence_filter(self):
        # Fallback gives 0.3 confidence to each claim
        extractor = ClaimExtractor(llm_enabled=False, min_confidence=0.5)
        result = extractor.extract("Sentence A. Sentence B.")
        # Fallback claims have 0.3 confidence, filtered by min_confidence=0.5
        assert len(result.claims) == 0

    def test_extract_with_llm_parses_json(self):
        """Test _parse_llm_output handles JSON response."""
        extractor = ClaimExtractor(llm_enabled=False)
        result = extractor._parse_llm_output(
            '```json\n{"claims": [{"text": "CRISPR corrects", '
            '"claim_type": "existence", "confidence": 0.95}]}\n```',
            "original text",
        )
        assert len(result) == 1
        assert result[0]["text"] == "CRISPR corrects"

    def test_extract_with_llm_line_fallback(self):
        """Test _parse_llm_output handles line-based fallback."""
        extractor = ClaimExtractor(llm_enabled=False)
        result = extractor._parse_llm_output(
            "- Claim one\n- Claim two\n- Claim three",
            "original text",
        )
        assert len(result) == 3
        assert result[0]["text"] == "Claim one"

    def test_extract_llm_empty_falls_back(self):
        """LLM returns None, falls back to sentence splitting."""
        mock_llm = MagicMock()
        mock_llm.enabled = True
        mock_llm.generate.return_value = None
        extractor = ClaimExtractor(llm_enabled=True)
        extractor.llm_client = mock_llm

        result = extractor.extract("Hello world. How are you.")
        assert len(result.claims) == 2
        assert result.metadata.get("fallback") is True

    def test_find_original_span_exact_match(self):
        extractor = ClaimExtractor()
        result = extractor._find_original_span(
            "CRISPR corrects 75% of mutations in vitro.",
            "CRISPR corrects 75% of mutations",
        )
        assert result == "CRISPR corrects 75% of mutations"

    def test_find_original_span_partial_match(self):
        extractor = ClaimExtractor()
        result = extractor._find_original_span(
            "The study found that CRISPR corrects 75% of mutations.",
            "CRISPR corrects 80% of mutations",
        )
        assert "CRISPR corrects" in result

    def test_extract_with_metadata(self):
        extractor = ClaimExtractor(llm_enabled=False)
        result = extractor.extract("Hello world.", metadata={"source": "test"})
        assert result.metadata.get("source") == "test"

    def test_extract_error_handling(self):
        """When LLM raises, fall back gracefully."""
        mock_llm = MagicMock()
        mock_llm.enabled = True
        mock_llm.generate.side_effect = Exception("API error")
        extractor = ClaimExtractor(llm_enabled=True)
        extractor.llm_client = mock_llm

        result = extractor.extract("Some text here.")
        assert len(result.claims) > 0  # falls back
        assert result.metadata.get("fallback") is True

    def test_parse_json_with_llm_output(self):
        """Direct test of JSON parsing logic."""
        extractor = ClaimExtractor(llm_enabled=False)
        result = extractor._parse_llm_output(
            '{"claims": [{"text": "Test claim", "claim_type": "causal", "confidence": 0.8}]}',
            "original text",
        )
        assert len(result) == 1
        assert result[0]["text"] == "Test claim"
