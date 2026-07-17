"""
Data models for the claim extraction and verification system.

Defines the core dataclasses used throughout the pipeline:
- Claim: An atomic verifiable claim extracted from text
- ClaimEvidence: Evidence retrieved from literature
- ClaimVerdict: The result of verifying a claim against evidence
- ClaimSet: A collection of claims with their verification results
- ClaimReport: The final output of the full workflow
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ClaimType(str, Enum):
    """Type of claim based on its semantic nature."""

    NUMERICAL = "numerical"  # "75% of patients..."
    CAUSAL = "causal"  # "X leads to Y..."
    COMPARATIVE = "comparative"  # "X outperforms Y by..."
    DEFINITIONAL = "definitional"  # "X is defined as..."
    EXISTENCE = "existence"  # "There is a method called..."
    RELATIONAL = "relational"  # "X is associated with Y..."
    TEMPORAL = "temporal"  # "In 2023, X was found to..."
    METHODOLOGICAL = "methodological"  # "Using X method, they achieved..."
    ATTRIBUTIONAL = "attributional"  # "According to Smith et al..."
    OTHER = "other"  # Catch-all


class Verdict(str, Enum):
    """Verdict of a claim against evidence."""

    SUPPORTED = "supported"  # Evidence supports the claim
    REFUTED = "refuted"  # Evidence contradicts the claim
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # Not enough evidence found
    PARTIALLY_SUPPORTED = "partially_supported"  # Some evidence supports, some contradicts
    UNVERIFIABLE = "unverifiable"  # Claim cannot be verified (e.g. opinion)
    NOT_CHECKED = "not_checked"  # Verification not yet performed


class EvidenceQuality(str, Enum):
    """Quality assessment of retrieved evidence."""

    HIGH = "high"  # Direct, recent, peer-reviewed
    MEDIUM = "medium"  # Relevant but indirect or older
    LOW = "low"  # Weak relevance or non-peer-reviewed
    UNCERTAIN = "uncertain"  # Cannot determine quality


@dataclass
class ClaimEvidence:
    """
    A piece of evidence retrieved from the literature.

    Attributes
    ----------
    text : str
        Evidence text snippet
    paper_title : str
        Title of the source paper
    authors : str
        Authors of the source paper
    source : str
        Source identifier (PMID, DOI, etc.)
    source_type : str
        Type of source (pmid, doi, pmcid)
    year : int | None
        Publication year
    journal : str | None
        Journal name
    relevance_score : float
        Relevance score 0.0-1.0
    quality : EvidenceQuality
        Quality assessment of this evidence
    url : str | None
        URL to the paper
    citation_count : int | None
        Number of citations the paper has received
    """

    text: str
    paper_title: str
    authors: str
    source: str
    source_type: str = "pmid"
    year: int | None = None
    journal: str | None = None
    relevance_score: float = 0.5
    quality: EvidenceQuality = EvidenceQuality.MEDIUM
    url: str | None = None
    citation_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "text": self.text,
            "paper_title": self.paper_title,
            "authors": self.authors,
            "source": self.source,
            "source_type": self.source_type,
            "year": self.year,
            "journal": self.journal,
            "relevance_score": self.relevance_score,
            "quality": self.quality.value,
            "url": self.url,
            "citation_count": self.citation_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaimEvidence:
        """Deserialize from dictionary."""
        data = dict(data)
        if "quality" in data and isinstance(data["quality"], str):
            data["quality"] = EvidenceQuality(data["quality"])
        return cls(**data)


@dataclass
class Claim:
    """
    An atomic verifiable claim extracted from source text.

    Each claim represents a single factual assertion that can be
    independently verified against the scientific literature.

    Attributes
    ----------
    id : str
        Unique identifier for the claim
    text : str
        The claim text (self-contained, decontextualized)
    original_text : str
        The original span in the source text
    claim_type : ClaimType
        Semantic type of the claim
    confidence : float
        Confidence in extraction (0.0-1.0)
    source_start : int | None
        Character offset in source text
    source_end : int | None
        Character offset in source text
    verdict : Verdict
        Current verification verdict
    evidence : list[ClaimEvidence]
        Retrieved evidence for this claim
    verification_reasoning : str | None
        LLM reasoning for the verdict
    """

    id: str
    text: str
    original_text: str
    claim_type: ClaimType = ClaimType.OTHER
    confidence: float = 0.5
    source_start: int | None = None
    source_end: int | None = None
    verdict: Verdict = Verdict.NOT_CHECKED
    evidence: list[ClaimEvidence] = field(default_factory=list)
    verification_reasoning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "original_text": self.original_text,
            "claim_type": self.claim_type.value,
            "confidence": self.confidence,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "verdict": self.verdict.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "verification_reasoning": self.verification_reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Claim:
        """Deserialize from dictionary."""
        data = dict(data)
        if "claim_type" in data and isinstance(data["claim_type"], str):
            data["claim_type"] = ClaimType(data["claim_type"])
        if "verdict" in data and isinstance(data["verdict"], str):
            data["verdict"] = Verdict(data["verdict"])
        if "evidence" in data:
            data["evidence"] = [
                ClaimEvidence.from_dict(e) if isinstance(e, dict) else e for e in data["evidence"]
            ]
        return cls(**data)


@dataclass
class ClaimSet:
    """
    A collection of claims with their verification results.

    Represents the full output of analyzing a source text.

    Attributes
    ----------
    source_text : str
        The original text that was analyzed
    claims : list[Claim]
        Extracted claims
    metadata : dict[str, Any]
        Additional metadata about the analysis
    """

    source_text: str
    claims: list[Claim] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def supported(self) -> list[Claim]:
        """Claims that are supported by evidence."""
        return [c for c in self.claims if c.verdict == Verdict.SUPPORTED]

    @property
    def refuted(self) -> list[Claim]:
        """Claims that are refuted by evidence."""
        return [c for c in self.claims if c.verdict == Verdict.REFUTED]

    @property
    def insufficient(self) -> list[Claim]:
        """Claims with insufficient evidence."""
        return [c for c in self.claims if c.verdict == Verdict.INSUFFICIENT_EVIDENCE]

    @property
    def unverified(self) -> list[Claim]:
        """Claims not yet verified."""
        return [c for c in self.claims if c.verdict == Verdict.NOT_CHECKED]

    @property
    def verification_summary(self) -> dict[str, int]:
        """Summary statistics of verification results."""
        return {
            "total": len(self.claims),
            "supported": len(self.supported),
            "refuted": len(self.refuted),
            "insufficient_evidence": len(self.insufficient),
            "partially_supported": len(
                [c for c in self.claims if c.verdict == Verdict.PARTIALLY_SUPPORTED]
            ),
            "unverifiable": len([c for c in self.claims if c.verdict == Verdict.UNVERIFIABLE]),
            "not_checked": len(self.unverified),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_text": self.source_text,
            "claims": [c.to_dict() for c in self.claims],
            "summary": self.verification_summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaimSet:
        """Deserialize from dictionary."""
        data = dict(data)
        if "claims" in data:
            data["claims"] = [
                Claim.from_dict(c) if isinstance(c, dict) else c for c in data["claims"]
            ]
        data.pop("summary", None)  # computed property
        return cls(**data)


@dataclass
class ClaimReport:
    """
    Final output of the full claim verification workflow.

    Contains the improved text, bibliography, and full audit trail.

    Attributes
    ----------
    original_text : str
        The original input text
    improved_text : str
        Text improved with citations and verified claims
    claim_set : ClaimSet
        All claims with their verification results
    bibliography : list[dict[str, Any]]
        Bibliography entries in BibTeX format
    review_notes : str | None
        Notes from the reviewer agent
    user_decisions : dict[str, bool]
        User confirmation decisions (claim_id -> accepted)
    """

    original_text: str
    improved_text: str = ""
    claim_set: ClaimSet | None = None
    bibliography: list[dict[str, Any]] = field(default_factory=list)
    review_notes: str | None = None
    user_decisions: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "original_text": self.original_text,
            "improved_text": self.improved_text,
            "claim_set": self.claim_set.to_dict() if self.claim_set else None,
            "bibliography": self.bibliography,
            "review_notes": self.review_notes,
            "user_decisions": self.user_decisions,
        }


__all__ = [
    "ClaimType",
    "Verdict",
    "EvidenceQuality",
    "ClaimEvidence",
    "Claim",
    "ClaimSet",
    "ClaimReport",
]
