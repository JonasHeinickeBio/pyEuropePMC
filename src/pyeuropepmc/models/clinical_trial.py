"""
Clinical trial Pydantic model.

Standardizes clinical trial data from ClinicalTrials.gov and other
trial registries into a consistent format for downstream analysis.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pyeuropepmc.models.literature import Author, LiteratureResult

__all__ = ["ClinicalTrial", "TrialStatus", "TrialPhase", "TrialDesign"]


class TrialStatus:
    """Clinical trial status constants."""

    RECRUITING = "RECRUITING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    WITHDRAWN = "WITHDRAWN"
    UNKNOWN = "UNKNOWN"


class TrialPhase:
    """Clinical trial phase constants."""

    PHASE1 = "PHASE1"
    PHASE2 = "PHASE2"
    PHASE3 = "PHASE3"
    PHASE4 = "PHASE4"
    EARLY_PHASE1 = "EARLY_PHASE1"
    NA = "NA"


class TrialDesign:
    """Clinical trial design type constants."""

    INTERVENTIONAL = "INTERVENTIONAL"
    OBSERVATIONAL = "OBSERVATIONAL"
    EXPANDED_ACCESS = "EXPANDED_ACCESS"


class ClinicalTrial(BaseModel):
    """
    Normalized clinical trial record.

    Attributes
    ----------
    nct_id : str
        ClinicalTrials.gov identifier (NCT number).
    title : str
        Official trial title.
    status : str
        Recruitment status.
    phase : str
        Trial phase.
    conditions : list[str]
        Medical conditions studied.
    interventions : list[dict]
        Interventions evaluated.
    sponsors : list[dict]
        Sponsors and collaborators.
    enrollment : int or None
        Target enrollment number.
    design : str or None
        Study design type.
    start_date : str or None
        Study start date.
    completion_date : str or None
        Primary completion date.
    brief_summary : str or None
        Brief summary of the trial.
    detailed_description : str or None
        Detailed description.
    eligibility_criteria : str or None
        Eligibility criteria text.
    locations : list[dict]
        Facility locations.
    references : list[dict]
        Associated publications (PMIDs/DOIs).
    mesh_conditions : list[str]
        MeSH terms for conditions.
    mesh_interventions : list[str]
        MeSH terms for interventions.
    """

    model_config = ConfigDict(extra="allow")

    nct_id: str = Field(..., description="ClinicalTrials.gov identifier")
    title: str = Field("", description="Official trial title")
    status: str = Field(TrialStatus.UNKNOWN, description="Recruitment status")
    phase: str = Field(TrialPhase.NA, description="Trial phase")
    conditions: list[str] = Field(default_factory=list, description="Medical conditions studied")
    interventions: list[dict[str, Any]] = Field(
        default_factory=list, description="Interventions evaluated"
    )
    sponsors: list[dict[str, str]] = Field(
        default_factory=list, description="Sponsors and collaborators"
    )
    enrollment: int | None = Field(None, description="Target enrollment number")
    design: str | None = Field(None, description="Study design type")
    start_date: str | None = Field(None, description="Study start date")
    completion_date: str | None = Field(None, description="Primary completion date")
    brief_summary: str | None = Field(None, description="Brief summary of the trial")
    detailed_description: str | None = Field(None, description="Detailed description")
    eligibility_criteria: str | None = Field(None, description="Eligibility criteria text")
    locations: list[dict[str, str]] = Field(default_factory=list, description="Facility locations")
    references: list[dict[str, str]] = Field(
        default_factory=list, description="Associated publications"
    )
    mesh_conditions: list[str] = Field(
        default_factory=list, description="MeSH terms for conditions"
    )
    mesh_interventions: list[str] = Field(
        default_factory=list, description="MeSH terms for interventions"
    )

    @classmethod
    def from_literature_result(cls, result: LiteratureResult) -> ClinicalTrial:
        """Construct a ClinicalTrial from a LiteratureResult (round-trip)."""
        meta = result.extra_metadata or {}
        nct_id = meta.get("nct_id") or (
            result.source_id if result.source == "clinicaltrials" else ""
        )
        title = result.title or meta.get("official_title") or meta.get("brief_title") or ""
        return cls(
            nct_id=nct_id,
            title=title,
            status=meta.get("status", TrialStatus.UNKNOWN),
            phase=meta.get("phase", TrialPhase.NA),
            conditions=meta.get("conditions", []) if meta else [],
        )

    def to_literature_result(self) -> LiteratureResult:
        """Convert to LiteratureResult for dedup pipeline."""
        authors = None
        if self.sponsors:
            authors = [Author(name=s.get("name", "")) for s in self.sponsors if s.get("name")]
        year = None
        if self.start_date:
            try:
                year = int(self.start_date[:4])
            except (ValueError, IndexError):
                pass

        return LiteratureResult(
            doi=None,
            pmid=None,
            pmcid=None,
            title=self.title,
            authors=authors or None,
            publication_year=year,
            journal=f"Clinical Trial {self.phase}"
            if self.phase != TrialPhase.NA
            else "Clinical Trial",
            abstract=self.brief_summary,
            citation_count=0,
            source="clinicaltrials",
            source_id=self.nct_id,
            extra_metadata={
                "nct_id": self.nct_id,
                "status": self.status,
                "phase": self.phase,
                "conditions": self.conditions[:5] if self.conditions else [],
                "interventions": [i.get("name", "") for i in self.interventions[:5]]
                if self.interventions
                else [],
                "enrollment": self.enrollment,
                "sponsors": [s.get("name", "") for s in self.sponsors] if self.sponsors else [],
            },
        )


class ICiteMetrics(BaseModel):
    """
    NIH iCite citation metrics for a paper.

    Attributes
    ----------
    pmid : str
        PubMed ID.
    rcr : float
        Relative Citation Ratio (field-normalized impact).
    percentile : float
        Citation percentile (0-100).
    citation_count : int
        Total citation count.
    expected_citations : float
        Expected citations based on field average.
    field_citation_ratio : float
        Observed / expected citations ratio.
    nih_percentile : float
        NIH-specific percentile.
    is_controversial : bool
        Whether the paper is flagged as controversial.
    """

    model_config = ConfigDict(extra="allow")

    pmid: str = Field(..., description="PubMed ID")
    rcr: float = Field(0.0, description="Relative Citation Ratio")
    percentile: float = Field(0.0, description="Citation percentile (0-100)")
    citation_count: int = Field(0, description="Total citation count")
    expected_citations: float = Field(0.0, description="Expected citations based on field average")
    field_citation_ratio: float = Field(0.0, description="Observed/expected citations ratio")
    nih_percentile: float = Field(0.0, description="NIH-specific percentile")
    is_controversial: bool = Field(False, description="Flagged as controversial")
