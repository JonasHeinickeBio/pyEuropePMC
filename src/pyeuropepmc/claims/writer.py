"""
Writer agent for improving text with verified claims and citations.

ClaimWriter takes user-confirmed claims, integrates them into the
original text with proper citations, and exports a formatted bibliography.

Inspired by SourceCheck (Eliot-2006/SourceCheck) for conservative
text rewriting and ExecutableClaims for evidence integration.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pyeuropepmc.agentic.llm_client import LLMClient, create_llm_client
from pyeuropepmc.claims.models import (
    Claim,
    ClaimReport,
    ClaimSet,
    Verdict,
)
from pyeuropepmc.features.bibliography.bibtex import BibtexManager
from pyeuropepmc.features.bibliography.conversion import CitationConverter
from pyeuropepmc.features.bibliography.models import BibEntry, BibLibrary

logger = logging.getLogger(__name__)


class ClaimWriterError(Exception):
    """Raised when the writer agent fails."""


class ClaimWriter:
    """
    Improve text with verified claims, citations, and bibliography.

    Workflow:
    1. Accept user-confirmed claims with verified evidence
    2. Rewrite original text inserting inline citations
    3. Append formatted bibliography (BibTeX/RIS/CSL)
    4. Provide diff of changes

    Parameters
    ----------
    llm_client : LLMClient, optional
        LLM client for text improvement
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
        self._bibtex_manager = BibtexManager()
        self._converter = CitationConverter()

    def write_report(
        self,
        original_text: str,
        claim_set: ClaimSet,
        user_decisions: dict[str, bool] | None = None,
        bibliography_format: str = "bibtex",
    ) -> ClaimReport:
        """
        Generate a complete improved text with citations and bibliography.

        Parameters
        ----------
        original_text : str
            The original text to improve
        claim_set : ClaimSet
            Claims with verification results
        user_decisions : dict, optional
            User decisions on which claims to include (claim_id -> accepted)
        bibliography_format : str, optional
            Output format: "bibtex", "ris", or "csl" (default: "bibtex")

        Returns
        -------
        ClaimReport
            Improved text, bibliography, and audit trail
        """
        user_decisions = user_decisions or {}

        # Filter to accepted claims with evidence
        accepted_claims = self._filter_accepted(claim_set.claims, user_decisions)

        if not accepted_claims:
            return ClaimReport(
                original_text=original_text,
                improved_text=original_text,
                claim_set=claim_set,
                bibliography=[],
                review_notes="No accepted claims to integrate.",
                user_decisions=user_decisions,
            )

        # Build bibliography from evidence
        bibliography = self._build_bibliography(accepted_claims)

        # Generate improved text with citations
        if self.llm_enabled and self.llm_client.enabled:
            improved_text = self._llm_improve_text(original_text, accepted_claims, bibliography)
        else:
            improved_text = self._simple_improve_text(original_text, accepted_claims, bibliography)

        # Export bibliography
        if bibliography_format != "bibtex":
            bibliography = self._convert_bibliography(bibliography, bibliography_format)

        report = ClaimReport(
            original_text=original_text,
            improved_text=improved_text,
            claim_set=claim_set,
            bibliography=bibliography,
            user_decisions=user_decisions,
        )

        return report

    def _filter_accepted(
        self,
        claims: list[Claim],
        user_decisions: dict[str, bool],
    ) -> list[Claim]:
        """Filter to claims that are user-accepted."""
        accepted = []

        for claim in claims:
            # Check user decision
            if claim.id in user_decisions:
                if user_decisions[claim.id]:
                    accepted.append(claim)
                continue

            # No explicit user decision: auto-filter based on verdict + evidence
            if claim.verdict in (Verdict.REFUTED, Verdict.UNVERIFIABLE):
                continue
            if claim.verdict == Verdict.SUPPORTED and not claim.evidence:
                continue

            accepted.append(claim)

        return accepted

    def _build_bibliography(self, claims: list[Claim]) -> list[dict[str, Any]]:
        """Build a bibliography from claim evidence."""
        seen_sources: set[str] = set()
        bibliography = []

        for i, claim in enumerate(claims):
            for ev in claim.evidence:
                source_key = ev.source or f"{ev.paper_title}_{ev.authors}"
                if source_key in seen_sources:
                    continue
                seen_sources.add(source_key)

                entry = {
                    "id": f"ref{i + 1}",
                    "type": "article",
                    "title": ev.paper_title,
                    "author": ev.authors,
                    "year": str(ev.year) if ev.year else "",
                    "journal": ev.journal or "",
                    "source": ev.source,
                    "source_type": ev.source_type,
                    "url": ev.url or "",
                    "citation_count": ev.citation_count,
                    "claims": [claim.id for claim in claims if ev in claim.evidence],
                }
                bibliography.append(entry)

        return bibliography

    def _llm_improve_text(
        self,
        original_text: str,
        claims: list[Claim],
        bibliography: list[dict[str, Any]],
    ) -> str:
        """
        Use LLM to improve text with citations.

        The LLM inserts citation markers like [ref1] that are later
        resolved to the bibliography.
        """
        claims_text = []
        for i, claim in enumerate(claims):
            evidence_refs = []
            for _j, ev in enumerate(claim.evidence[:2]):
                bib_idx = next(
                    (
                        k
                        for k, b in enumerate(bibliography)
                        if b["source"] == ev.source or b["id"] == f"ref{k + 1}"
                    ),
                    None,
                )
                if bib_idx is not None:
                    evidence_refs.append(f"ref{bib_idx + 1}")

            claims_text.append(
                f"[Claim {i + 1}] {claim.text}\n"
                f"  Verdict: {claim.verdict.value}\n"
                f"  Evidence: {', '.join(f'[{r}]' for r in evidence_refs) if evidence_refs else 'No direct citation'}\n"
                f"  Supporting papers: {ev.paper_title[:80] if claim.evidence else 'N/A'}"
            )

        bib_text = "\n".join(
            f"[{b['id']}] {b['author']} ({b['year']}). {b['title']}. {b['journal']}."
            for b in bibliography
        )

        prompt = f"""You are a scientific writing expert. Improve the following text by integrating verified claims with proper inline citations.

Original text:
---
{original_text}
---

Verified claims with evidence:
{chr(10).join(claims_text)}

Available references:
{bib_text}

Instructions:
1. Improve the text by incorporating the verified claims
2. Add inline citations using [ref1], [ref2], etc. markers
3. Correct any claims that were refuted
4. Preserve the original meaning and style
5. Only change what is supported by evidence
6. Return the improved text ONLY (no additional commentary)

Improved text:
"""

        try:
            result = self.llm_client.generate(prompt)
            if result:
                # Clean up any markdown code blocks the LLM might add
                result = re.sub(r"^```\w*\n?|```$", "", result.strip(), flags=re.MULTILINE)
                return result.strip()
        except Exception as e:
            logger.warning(f"LLM text improvement failed: {e}")

        return self._simple_improve_text(original_text, claims, bibliography)

    def _simple_improve_text(
        self,
        original_text: str,
        claims: list[Claim],
        bibliography: list[dict[str, Any]],
    ) -> str:
        """
        Simple rule-based text improvement without LLM.

        Appends evidence citations after relevant sentences.
        """
        improved = original_text

        # For each claim, try to find its original text span and append citation
        for claim in claims:
            if not claim.evidence:
                continue

            bib_refs = []
            for ev in claim.evidence[:1]:  # Use top evidence
                bib_idx = next(
                    (k for k, b in enumerate(bibliography) if b["source"] == ev.source),
                    None,
                )
                if bib_idx is not None:
                    bib_refs.append(f"ref{bib_idx + 1}")

            if not bib_refs:
                continue

            citation = f" [{', '.join(bib_refs)}]"

            # Try to find original span and append citation
            orig = claim.original_text
            if orig and orig in improved:
                # Append citation after the claim's original text
                improved = improved.replace(orig, orig + citation, 1)
            else:
                # Append at the end of the text
                improved += citation

        return improved

    def _convert_bibliography(
        self,
        bibliography: list[dict[str, Any]],
        output_format: str,
    ) -> list[dict[str, Any]]:
        """Convert bibliography to requested format."""
        if output_format == "bibtex":
            return bibliography  # already bibtex-style dicts

        # Build BibLibrary for conversion
        lib = BibLibrary()
        for entry in bibliography:
            bib_entry = BibEntry(
                citation_key=entry["id"],
                entry_type=entry.get("type", "article"),
                fields={
                    "title": entry.get("title", ""),
                    "author": entry.get("author", ""),
                    "year": entry.get("year", ""),
                    "journal": entry.get("journal", ""),
                },
            )
            lib.add_entry(bib_entry)

        if output_format == "ris":
            ris_text = self._converter.to_ris(lib)
            return [{"format": "ris", "content": ris_text}]
        elif output_format == "csl":
            csl_data = self._converter.to_csl_json(lib)
            return csl_data if isinstance(csl_data, list) else [csl_data]

        return bibliography


__all__ = ["ClaimWriter", "ClaimWriterError"]
