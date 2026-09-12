"""
Claim verification against the scientific literature.

ClaimVerifier searches Europe PMC for evidence relevant to each claim,
then uses an LLM to determine whether the evidence supports or refutes
the claim.

Inspired by Graphite (minjun1/graphite-core) and ExecutableClaims
(aayambansal/ExecutableClaims) for evidence retrieval and verification
patterns.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pyeuropepmc.agentic.llm_client import LLMClient, create_llm_client
from pyeuropepmc.claims.models import (
    Claim,
    ClaimEvidence,
    ClaimSet,
    EvidenceQuality,
    Verdict,
)
from pyeuropepmc.features.bibliography.reference import ReferenceResolver
from pyeuropepmc.features.literature.search import SearchClient

logger = logging.getLogger(__name__)


class ClaimVerificationError(Exception):
    """Raised when claim verification fails."""


class ClaimVerifier:
    """
    Verify claims against evidence from the scientific literature.

    For each claim, the verifier:
    1. Searches Europe PMC for relevant papers
    2. Extracts evidence snippets from top results
    3. Uses LLM to determine support/refute/insufficient verdict
    4. Returns structured evidence with provenance

    Parameters
    ----------
    llm_client : LLMClient, optional
        LLM client for verification reasoning
    llm_enabled : bool, optional
        Whether LLM is enabled (default: True)
    search_limit : int, optional
        Max papers to search per claim (default: 5)
    max_evidence_per_claim : int, optional
        Max evidence snippets per claim (default: 3)

    Examples
    --------
    >>> verifier = ClaimVerifier()
    >>> claim = Claim(id="c1", text="CRISPR treats beta-thalassemia",
    ...               original_text="CRISPR treats beta-thalassemia")
    >>> verified = verifier.verify_claim(claim)
    >>> verified.verdict == Verdict.SUPPORTED
    True
    """

    _VERIFICATION_PROMPT = """You are a scientific claim verification expert. Given a claim and relevant evidence from the literature, determine whether the evidence SUPPORTS, REFUTES, or is INSUFFICIENT to evaluate the claim.

Claim: {claim_text}

Evidence:
{evidence_text}

Task:
1. Carefully read the claim and each piece of evidence
2. Determine if the evidence supports the claim, refutes it, or is insufficient
3. Provide clear reasoning for your verdict

Return ONLY valid JSON:
{{"verdict": "supported" | "refuted" | "insufficient_evidence" | "partially_supported",
 "reasoning": "Detailed explanation of your verdict...",
 "supporting_evidence_indices": [0, 2],
 "refuting_evidence_indices": [1],
 "confidence": 0.85}}
"""

    _QUERY_GENERATION_PROMPT = """You are a search query optimizer for biomedical literature. Given a factual claim, generate 1-3 concise PubMed/Europe PMC search queries that would find evidence FOR or AGAINST the claim.

Rules:
- Each query must be 3-8 key terms (no full sentences, no punctuation except hyphens)
- Use MeSH-like terms and synonyms where appropriate
- Cover different angles of the claim
- Do NOT include the claim statement itself verbatim

Claim: {claim_text}

Respond ONLY with a valid JSON object of this exact form:
{{"queries": ["term1 term2 term3", "term4 term5 term6"]}}
"""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        llm_enabled: bool = True,
        search_limit: int = 5,
        max_evidence_per_claim: int = 3,
    ):
        self.llm_client = llm_client or create_llm_client(enabled=llm_enabled)
        self.llm_enabled = llm_enabled
        self.search_limit = search_limit
        self.max_evidence_per_claim = max_evidence_per_claim
        self._search_client = SearchClient()
        self._article_client: Any = None  # lazy import to avoid circular dependency
        self._ref_resolver = ReferenceResolver()
        self._verification_cache: dict[str, tuple[Verdict, str, list[ClaimEvidence]]] = {}

    def verify_claim(self, claim: Claim) -> Claim:
        """
        Verify a single claim against the literature.

        Searches Europe PMC, retrieves evidence, and produces a verdict.

        Parameters
        ----------
        claim : Claim
            The claim to verify

        Returns
        -------
        Claim
            Updated claim with verdict and evidence
        """
        # Check cache
        cache_key = claim.text.lower().strip()
        if cache_key in self._verification_cache:
            verdict, reasoning, evidence = self._verification_cache[cache_key]
            claim.verdict = verdict
            claim.verification_reasoning = reasoning
            claim.evidence = evidence
            return claim

        # Search for evidence
        papers = self._search_evidence(claim.text)

        if not papers:
            claim.verdict = Verdict.INSUFFICIENT_EVIDENCE
            claim.verification_reasoning = "No relevant papers found in Europe PMC."
            self._verification_cache[cache_key] = (
                claim.verdict,
                claim.verification_reasoning,
                [],
            )
            return claim

        # Extract evidence snippets
        evidence_list = self._extract_evidence(papers, claim.text)

        if not evidence_list:
            claim.verdict = Verdict.INSUFFICIENT_EVIDENCE
            claim.verification_reasoning = (
                "Papers found but no specific evidence snippets extracted."
            )
            self._verification_cache[cache_key] = (
                claim.verdict,
                claim.verification_reasoning,
                [],
            )
            return claim

        claim.evidence = evidence_list[: self.max_evidence_per_claim]

        # LLM-based verification
        if self.llm_enabled and self.llm_client.enabled:
            verdict, reasoning = self._llm_verify(claim.text, claim.evidence)
            claim.verdict = verdict
            claim.verification_reasoning = reasoning
        else:
            # Default: mark as supported if we found any evidence
            claim.verdict = Verdict.SUPPORTED
            claim.verification_reasoning = (
                f"Found {len(claim.evidence)} relevant evidence items in literature."
            )

        # Cache
        self._verification_cache[cache_key] = (
            claim.verdict,
            claim.verification_reasoning,
            claim.evidence,
        )

        return claim

    def verify_claim_set(self, claim_set: ClaimSet) -> ClaimSet:
        """
        Verify all claims in a ClaimSet.

        Parameters
        ----------
        claim_set : ClaimSet
            Claims to verify

        Returns
        -------
        ClaimSet
            Updated claims with verdicts and evidence
        """
        for i, claim in enumerate(claim_set.claims):
            logger.info(f"Verifying claim {i + 1}/{len(claim_set.claims)}: {claim.text[:60]}...")
            self.verify_claim(claim)

        claim_set.metadata["verification_complete"] = True
        claim_set.metadata["verification_counts"] = claim_set.verification_summary
        return claim_set

    def _search_evidence(self, claim_text: str) -> list[dict[str, Any]]:
        """Search Europe PMC for evidence relevant to the claim.

        When LLM is enabled, generates targeted search queries from the
        claim text instead of using the raw text verbatim.

        The Europe PMC search API returns ``lite`` results (no abstracts).
        Papers with PMIDs/PMCIDs are then enriched with full details
        (including abstract text) via the article details endpoint.
        """
        queries = [claim_text]

        # Generate targeted queries via LLM
        if self.llm_enabled and self.llm_client.enabled:
            llm_queries = self._llm_generate_queries(claim_text)
            if llm_queries:
                logger.info(f"Using LLM-generated queries: {llm_queries}")
                queries = llm_queries

        # Try each query in order, collecting up to search_limit * 2 candidates
        seen_pmids: set[str] = set()
        all_papers: list[dict[str, Any]] = []
        # Fetch more candidates so we can filter out conference abstracts
        fetch_limit = self.search_limit * 3

        for query in queries:
            try:
                results = self._search_client.search(
                    query=query,
                    page_size=fetch_limit,
                    # Default sort (relevance) — NOT CITED desc, which surfaces
                    # high-citation papers unrelated to the topic.
                )
                if results and isinstance(results, dict):
                    result_list = results.get("resultList", {})
                    papers = result_list.get("result", []) if isinstance(result_list, dict) else []
                else:
                    papers = []

                # Deduplicate by PMID
                for p in papers:
                    pmid = p.get("pmid", "") or ""
                    if pmid and pmid not in seen_pmids:
                        seen_pmids.add(pmid)
                        all_papers.append(p)
                    elif not pmid:
                        all_papers.append(p)

                if len(all_papers) >= fetch_limit:
                    break

            except Exception as e:
                logger.warning(f"Search error for query '{query[:60]}': {e}")
                continue

        # Enrich lite results with full details (abstracts), then filter
        enriched = self._enrich_papers(all_papers[:fetch_limit])
        return self._filter_relevant_papers(enriched, claim_text)

    def _enrich_papers(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fetch full article details for papers that lack abstracts."""
        enriched = []
        for p in papers:
            # Skip if already has abstract
            if p.get("abstractText"):
                enriched.append(p)
                continue

            pmid = p.get("pmid", "")
            pmcid = p.get("pmcid", "")
            source = "MED" if pmid else "PMC" if pmcid else None
            article_id = pmid or pmcid or ""

            if source and article_id:
                try:
                    details = self._get_article_details(source, article_id)
                    if details:
                        # Merge full details into lite result
                        p["abstractText"] = (
                            details.get("abstractText") or details.get("fullText") or ""
                        )
                        p["title"] = p.get("title") or details.get("title", "")
                except Exception as e:
                    logger.debug(f"Could not enrich {source}:{article_id}: {e}")

            enriched.append(p)
        return enriched

    # Patterns that indicate a paper is a conference abstract, not research
    _CONFERENCE_KEYWORDS = (
        "abstract",
        "congress",
        "symposium",
        "conference",
        "meeting",
        "proceedings",
        "annual meeting",
    )

    @classmethod
    def _is_conference_abstract(cls, paper: dict[str, Any]) -> bool:
        """Check if a paper is a conference abstract (no real abstract body)."""
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstractText") or "").lower()

        # No real abstract text at all
        if not abstract.strip() or len(abstract.strip()) < 50:
            return True

        # Title contains conference keywords AND abstract is very short
        if len(abstract.strip()) < 150:
            for kw in cls._CONFERENCE_KEYWORDS:
                if kw in title:
                    return True

        return False

    @classmethod
    def _filter_relevant_papers(
        cls,
        papers: list[dict[str, Any]],
        claim_text: str,
        max_papers: int = 5,
    ) -> list[dict[str, Any]]:
        """Filter out conference abstracts and score for relevance.

        1. Remove conference abstracts (no real research content).
        2. Compute a quick text-overlap relevance score.
        3. Return top ``max_papers`` most relevant, skipping low-quality entries.
        """
        claim_lower = claim_text.lower()
        claim_words = set(re.findall(r"\b[a-z]{3,}\b", claim_lower))

        scored: list[tuple[float, dict[str, Any]]] = []
        for p in papers:
            # Skip conference abstracts
            if cls._is_conference_abstract(p):
                continue

            title = (p.get("title") or "").lower()
            abstract = (p.get("abstractText") or "").lower()
            combined = f"{title} {abstract}"

            if not combined.strip():
                continue

            # Simple word-overlap score
            text_words = set(re.findall(r"\b[a-z]{3,}\b", combined))
            if not claim_words or not text_words:
                score = 0.0
            else:
                overlap = claim_words & text_words
                score = len(overlap) / len(claim_words | text_words) * 2  # DSC

            # Bonus for exact phrase match
            phrases = [s.strip() for s in claim_text.lower().split(".") if len(s.strip()) > 10]
            for phrase in phrases:
                if phrase in combined:
                    score += 0.2

            scored.append((score, p))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [p for _, p in scored[:max_papers]]

    def _get_article_details(self, source: str, article_id: str) -> dict[str, Any] | None:
        """Fetch full article details from Europe PMC."""
        if self._article_client is None:
            from pyeuropepmc.features.literature.article import ArticleClient

            self._article_client = ArticleClient()

        try:
            response = self._article_client.get_article_details(
                source=source, article_id=article_id
            )
            return response.get("result") if isinstance(response, dict) else None
        except Exception as e:
            logger.debug(f"Article details error for {source}:{article_id}: {e}")
            return None

    def _llm_generate_queries(self, claim_text: str) -> list[str] | None:
        """Use LLM to generate targeted search queries from a claim."""
        try:
            result = self.llm_client.generate(
                self._QUERY_GENERATION_PROMPT.format(claim_text=claim_text),
            )
            if not result:
                return None

            # Parse JSON response
            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", result, re.DOTALL)
            if json_match:
                result = json_match.group(1)

            data = json.loads(result.strip())
            queries = data.get("queries", [])
            if queries and isinstance(queries, list):
                # Clean and validate queries
                cleaned = [q.strip() for q in queries if q.strip() and len(q.strip().split()) >= 2]
                return cleaned[:3] if cleaned else None
            return None

        except Exception as e:
            logger.warning(f"Query generation error: {e}")
            return None

    def _extract_evidence(
        self,
        papers: list[dict[str, Any]],
        claim_text: str,
    ) -> list[ClaimEvidence]:
        """Extract evidence snippets from search results."""
        evidence = []
        for paper in papers:
            try:
                title = paper.get("title", "Unknown Title") or "Unknown Title"
                abstract = paper.get("abstractText", "") or ""
                authors = paper.get("authorString", "") or ""
                pmid = paper.get("pmid", "") or ""
                doi = paper.get("doi", "") or ""
                year = paper.get("pubYear", None)
                journal = paper.get("journalTitle", None)
                cited_by = paper.get("citedByCount", None)

                # Use abstract as evidence text
                evidence_text = abstract[:500] if abstract else title

                if not evidence_text:
                    continue

                # Estimate relevance
                relevance = self._estimate_relevance(claim_text, evidence_text)

                evidence.append(
                    ClaimEvidence(
                        text=evidence_text,
                        paper_title=title,
                        authors=authors,
                        source=pmid or doi,
                        source_type="pmid" if pmid else "doi",
                        year=int(year) if year else None,
                        journal=journal,
                        relevance_score=relevance,
                        quality=EvidenceQuality.MEDIUM,
                        url=f"https://europepmc.org/article/med/{pmid}" if pmid else None,
                        citation_count=int(cited_by) if cited_by else None,
                    )
                )
            except Exception as e:
                logger.warning(f"Error extracting evidence from paper: {e}")
                continue

        # Sort by relevance
        evidence.sort(key=lambda e: e.relevance_score, reverse=True)
        return evidence

    def _estimate_relevance(self, claim_text: str, evidence_text: str) -> float:
        """Estimate relevance between claim and evidence text."""
        claim_lower = claim_text.lower()
        evidence_lower = evidence_text.lower()

        # Count overlapping significant words
        claim_words = set(re.findall(r"\b[a-z]{4,}\b", claim_lower))
        evidence_words = set(re.findall(r"\b[a-z]{4,}\b", evidence_lower))

        if not claim_words:
            return 0.3

        overlap = claim_words & evidence_words
        score = len(overlap) / len(claim_words)

        # Bonus for exact phrase match
        if claim_lower[:50] in evidence_lower:
            score = min(1.0, score + 0.3)

        return min(1.0, max(0.0, score))

    def _llm_verify(
        self,
        claim_text: str,
        evidence_list: list[ClaimEvidence],
    ) -> tuple[Verdict, str]:
        """
        Use LLM to verify a claim against evidence.

        Returns
        -------
        tuple[Verdict, str]
            The verdict and reasoning
        """
        evidence_text_parts = []
        for i, ev in enumerate(evidence_list):
            evidence_text_parts.append(
                f"[{i}] From: {ev.paper_title} ({ev.authors}, {ev.year})\n"
                f"    Evidence: {ev.text[:300]}"
            )

        evidence_text = "\n\n".join(evidence_text_parts)

        try:
            result = self.llm_client.generate(
                self._VERIFICATION_PROMPT.format(
                    claim_text=claim_text,
                    evidence_text=evidence_text,
                ),
            )

            if not result:
                return Verdict.INSUFFICIENT_EVIDENCE, "LLM returned empty result."

            return self._parse_verdict(result)

        except Exception as e:
            logger.error(f"LLM verification error: {e}")
            return Verdict.INSUFFICIENT_EVIDENCE, f"Verification error: {e}"

    def _parse_verdict(self, llm_output: str) -> tuple[Verdict, str]:
        """Parse LLM output to extract verdict and reasoning."""
        # Try JSON extraction
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", llm_output, re.DOTALL)
        if json_match:
            llm_output = json_match.group(1)

        try:
            data = json.loads(llm_output)
            verdict_str = data.get("verdict", "insufficient_evidence")
            reasoning = data.get("reasoning", "")
            return Verdict(verdict_str), reasoning
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: scan for verdict keywords
        lower = llm_output.lower()
        if "supported" in lower and "refuted" not in lower:
            return Verdict.SUPPORTED, llm_output[:200]
        elif "refuted" in lower or "contradict" in lower:
            return Verdict.REFUTED, llm_output[:200]
        elif "insufficient" in lower or "not enough" in lower:
            return Verdict.INSUFFICIENT_EVIDENCE, llm_output[:200]
        elif "partially" in lower:
            return Verdict.PARTIALLY_SUPPORTED, llm_output[:200]
        else:
            return Verdict.INSUFFICIENT_EVIDENCE, llm_output[:200]

    def clear_cache(self) -> None:
        """Clear the verification cache."""
        self._verification_cache.clear()


__all__ = ["ClaimVerifier", "ClaimVerificationError"]
