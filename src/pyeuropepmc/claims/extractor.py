"""
Claim extraction from natural language text.

ClaimExtractor uses an LLM to decompose paragraphs/sentences into
atomic, verifiable claims. Each claim is self-contained (decontextualized)
and classified by type.

Inspired by ReClaim (stat-ml/reclaim) and Graphite (minjun1/graphite-core)
for atomic claim extraction patterns.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
import uuid

from pyeuropepmc.agentic.llm_client import LLMClient, create_llm_client
from pyeuropepmc.claims.models import Claim, ClaimSet, ClaimType

logger = logging.getLogger(__name__)


class ClaimExtractionError(Exception):
    """Raised when claim extraction fails."""


class ClaimExtractor:
    """
    Extract atomic verifiable claims from natural language text.

    Uses an LLM to decompose text into individual factual assertions
    that can be independently verified against the scientific literature.

    Parameters
    ----------
    llm_client : LLMClient, optional
        LLM client for extraction. If None, creates a new one.
    llm_enabled : bool, optional
        Whether LLM is enabled (default: True)
    min_confidence : float, optional
        Minimum confidence for returned claims (default: 0.0)

    Examples
    --------
    >>> extractor = ClaimExtractor()
    >>> claim_set = extractor.extract(
    ...     "CRISPR-Cas9 corrects 75% of beta-thalassemia mutations in vitro."
    ... )
    >>> len(claim_set.claims)
    2  # "CRISPR-Cas9 corrects mutations" + "75% correction rate"
    """

    _EXTRACTION_PROMPT = """You are a scientific claim extraction expert. Extract atomic, verifiable factual claims from the given text. Each claim must be:

1. **Atomic** — A single assertion that can be verified independently
2. **Verifiable** — Checkable against scientific literature
3. **Decontextualized** — Self-contained, understandable without the original text
4. **Faithful** — Accurately reflects what the text says (no additions)

For each claim, provide:
- text: The claim statement (decontextualized)
- claim_type: One of: numerical, causal, comparative, definitional, existence, relational, temporal, methodological, attributional, other
- confidence: Your confidence this is a valid extractable claim (0.0-1.0)

Respond ONLY with a valid JSON object. Do NOT include any markdown formatting, code fences, or extra text:
{{"claims": [
  {{"text": "CRISPR-Cas9 can correct beta-thalassemia mutations in vitro", "claim_type": "existence", "confidence": 0.95}},
  {{"text": "The correction rate is 75%", "claim_type": "numerical", "confidence": 0.9}}
]}}

Text to analyze:
---
{text}
---
"""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        llm_enabled: bool = True,
        min_confidence: float = 0.0,
    ):
        self.llm_client = llm_client or create_llm_client(enabled=llm_enabled)
        self.llm_enabled = llm_enabled
        self.min_confidence = min_confidence

    def extract(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> ClaimSet:
        """
        Extract atomic claims from a text passage.

        Parameters
        ----------
        text : str
            The source text to analyze
        metadata : dict, optional
            Additional metadata to attach to the ClaimSet

        Returns
        -------
        ClaimSet
            Extracted claims with their types and confidence scores

        Raises
        ------
        ClaimExtractionError
            If extraction fails
        """
        if not text or not text.strip():
            return ClaimSet(source_text=text, claims=[], metadata=metadata or {})

        if not self.llm_enabled or not self.llm_client.enabled:
            return self._extract_fallback(text, metadata=metadata)

        try:
            result_text = self.llm_client.generate(
                self._EXTRACTION_PROMPT.format(text=text),
            )
            if not result_text:
                return self._extract_fallback(text, metadata=metadata)

            claims_data = self._parse_llm_output(result_text, text)
            claims = [
                Claim(
                    id=f"claim-{uuid.uuid4().hex[:8]}",
                    text=c["text"],
                    original_text=self._find_original_span(text, c["text"]),
                    claim_type=ClaimType(c.get("claim_type", "other")),
                    confidence=float(c.get("confidence", 0.5)),
                )
                for c in claims_data
                if float(c.get("confidence", 0)) >= self.min_confidence
            ]

            return ClaimSet(
                source_text=text,
                claims=claims,
                metadata=metadata or {},
            )

        except Exception as e:
            logger.error(f"Claim extraction error: {e}")
            return self._extract_fallback(text, metadata=metadata)

    def _parse_llm_output(self, result_text: str, original: str) -> list[dict[str, Any]]:
        """Parse LLM response to extract claim data.

        Uses multiple strategies in order of preference:
        1. Extract JSON block from markdown code fences
        2. Parse as plain JSON (with optional repair for truncation)
        3. Extract JSON fragment from text with regex
        4. Extract lines with claim-like content from text
        5. Fallback: return original text as a single claim
        """
        raw = result_text  # Keep original for fallback parsing

        # Strategy 1: Extract JSON block from ```json ... ``` fences
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(1)

        # Strategy 2: Try to parse as JSON directly, with repair
        parsed = self._try_parse_json(result_text)
        if parsed is not None:
            return parsed

        # Strategy 3: Search for JSON-like object anywhere in the text
        # (handles cases where LLM adds commentary around the JSON)
        obj_match = re.search(r'\{\s*"[^"]+"\s*:', raw, re.DOTALL)
        if obj_match:
            # Try to find the full object by brace matching
            depth = 0
            full_obj = ""
            for ch in raw[obj_match.start() :]:
                full_obj += ch
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
            if depth == 0 and full_obj.endswith("}"):
                parsed = self._try_parse_json(full_obj)
                if parsed:
                    return parsed
            # If we couldn't close the brace, try with artificially closed
            if depth > 0:
                repaired = full_obj + "}" * depth
                parsed = self._try_parse_json(repaired)
                if parsed:
                    return parsed

        # Strategy 4: Extract lines with claim-like content patterns
        claims = self._extract_claim_lines(raw, original)
        if claims:
            return claims

        # Strategy 5: Extract any quoted text or substantive lines
        claims = self._extract_any_content(raw, original)
        if claims:
            return claims

        # Final fallback: return original text as a single claim
        return [{"text": original, "claim_type": "other", "confidence": 1.0}]

    def _try_parse_json(self, text: str) -> list[dict[str, Any]] | None:
        """Try to parse text as JSON, with progressive repair for truncation."""
        text = text.strip()

        # Direct parse attempt
        try:
            data = json.loads(text)
            claims = data.get("claims", [])
            if claims:
                return claims
            return None
        except (json.JSONDecodeError, ValueError):
            pass

        # Repair attempt 1: If it starts with { but is truncated, try closing all open braces
        if text.startswith("{") and not text.endswith("}"):
            # Count open vs close braces
            opens = text.count("{")
            closes = text.count("}")
            missing = opens - closes
            if missing > 0:
                repaired = text + "}" * missing
                try:
                    data = json.loads(repaired)
                    claims = data.get("claims", [])
                    if claims:
                        return claims
                except (json.JSONDecodeError, ValueError):
                    pass

        # Repair attempt 2: If it's just an array or partial array
        if "[" in text and "]" not in text:
            idx = text.find("[")
            candidate = text[:idx] + "[]"
            try:
                data = json.loads(candidate)
                return data.get("claims", [])
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def _extract_claim_lines(self, text: str, original: str) -> list[dict[str, Any]] | None:
        """Extract claims from line-oriented text (dash/bullet/numbered lists)."""
        claims = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip().strip('"').strip(",")
            if not line or len(line) < 5:
                continue
            # Match dash, asterisk, numbered, or "text": key patterns
            if re.match(r"^[-*\d+.]+\s+", line) or line.startswith('"text"'):
                claim_text = re.sub(r"^[-*\d+.]+\s+", "", line)
                claim_text = re.sub(r'^"text":\s*"?(.*?)"?\s*,?\s*$', r"\1", claim_text)
                claim_text = claim_text.strip().strip('"')
                if claim_text and len(claim_text) > 5:
                    claims.append(
                        {
                            "text": claim_text,
                            "claim_type": "other",
                            "confidence": 0.3,
                        }
                    )
            # Also catch lines that look like claim statements (substantive content)
            elif len(line) > 20 and not line.startswith("{") and not line.startswith("}"):
                # Could be a raw claim string
                pass  # handled in _extract_any_content

        return claims if claims else None

    def _extract_any_content(self, text: str, original: str) -> list[dict[str, Any]] | None:
        """Last-resort: extract any substantive lines from the text."""
        lines = []
        for line in text.split("\n"):
            line = line.strip().strip('"').strip(",").strip()
            # Skip JSON structural characters, short lines, empty
            if not line or len(line) < 10:
                continue
            if line in ("{", "}", "[", "]", "claims:", '"claims":'):
                continue
            if re.match(r"^[\s{}\[\],]+$", line):
                continue
            # Remove JSON field labels
            cleaned = re.sub(r'^"[^"]+":\s*"?', "", line)
            cleaned = re.sub(r'"?\s*,?\s*$', "", cleaned)
            cleaned = cleaned.strip()
            if len(cleaned) >= 10:
                lines.append(cleaned)

        if lines:
            return [{"text": ln, "claim_type": "other", "confidence": 0.3} for ln in lines[:10]]
        return None

    def _find_original_span(self, text: str, claim_text: str) -> str:
        """Find the closest matching span in the original text."""
        # Try exact match first
        if claim_text in text:
            return claim_text
        # Try finding the longest common subsequence-ish
        words = claim_text.split()
        for i in range(len(words), 0, -1):
            for j in range(len(words) - i + 1):
                candidate = " ".join(words[j : j + i])
                if candidate in text:
                    return candidate
        # Fallback: return the whole text
        return text[:200]

    def _extract_fallback(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> ClaimSet:
        """
        Fallback extraction using sentence splitting when LLM is unavailable.

        Splits text into sentences and creates simple claims.
        """
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        claims = []
        for i, sentence in enumerate(sentences):
            claim = Claim(
                id=f"claim-fallback-{i}",
                text=sentence,
                original_text=sentence,
                claim_type=ClaimType.OTHER,
                confidence=0.3,
            )
            if claim.confidence >= self.min_confidence:
                claims.append(claim)

        return ClaimSet(
            source_text=text,
            claims=claims,
            metadata={"fallback": True, **(metadata or {})},
        )


__all__ = ["ClaimExtractor", "ClaimExtractionError"]
