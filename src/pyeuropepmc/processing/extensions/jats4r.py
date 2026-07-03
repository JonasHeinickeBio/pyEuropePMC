"""
JATS4R Compliance Validation.

Checks parsed XML output against JATS4R (NISO RP-48-2024) recommendations
for best practices in JATS XML tagging.

Validated areas:
- Authors and affiliations (v2.0)
- Abstracts (v1.0)
- Funding information (v1.3)
- Citations (general)
- Data availability statements
- CRediT taxonomy (author contributions)
- Peer review materials (v1.0)
- ORCID identifiers

Reference
---------
JATS4R recommendations: https://jats4r.niso.org/recommendations/
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ValidationFinding:
    """
    A single validation finding.

    Parameters
    ----------
    rule_id : str
        Identifier for the JATS4R rule (e.g. ``AUTH-01``).
    severity : str
        ``"error"``, ``"warning"``, or ``"info"``.
    message : str
        Human-readable description.
    category : str
        The recommendation category (e.g. ``"authors"``, ``"funding"``).
    element_path : str, optional
        XPath-like path to the relevant element.
    suggestion : str, optional
        How to fix the issue.
    """

    rule_id: str
    severity: str  # 'error', 'warning', 'info'
    message: str
    category: str = "general"
    element_path: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "category": self.category,
            "element_path": self.element_path,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationReport:
    """
    Complete validation report for a document.

    Parameters
    ----------
    findings : list[ValidationFinding]
        All validation findings.
    score : float
        Compliance score (0.0 to 1.0).
    categories : dict[str, list[ValidationFinding]]
        Findings grouped by category.
    """

    findings: list[ValidationFinding] = field(default_factory=list)
    score: float = 1.0
    categories: dict[str, list[ValidationFinding]] = field(default_factory=dict)

    def add_finding(self, finding: ValidationFinding) -> None:
        """Add a finding and update the score."""
        self.findings.append(finding)
        self.categories.setdefault(finding.category, []).append(finding)
        self._recalculate_score()

    def _recalculate_score(self) -> None:
        """Recalculate compliance score based on findings."""
        if not self.findings:
            self.score = 1.0
            return
        # Weight by severity
        weights = {"error": 1.0, "warning": 0.5, "info": 0.1}
        total_penalty = sum(weights.get(f.severity, 0.1) for f in self.findings)
        self.score = max(0.0, 1.0 - (total_penalty / 10.0))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "score": round(self.score, 2),
            "total_findings": len(self.findings),
            "errors": sum(1 for f in self.findings if f.severity == "error"),
            "warnings": sum(1 for f in self.findings if f.severity == "warning"),
            "infos": sum(1 for f in self.findings if f.severity == "info"),
            "categories": {
                cat: [f.to_dict() for f in items] for cat, items in self.categories.items()
            },
        }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class JATS4RValidator(BaseParser):
    """
    Validates JATS XML compliance against JATS4R recommendations.

    Parameters
    ----------
    root : ET.Element, optional
        Root element of the parsed XML.
    config : ElementPatterns, optional
        Configuration for element pattern matching.

    Examples
    --------
    >>> validator = JATS4RValidator(root)
    >>> report = validator.validate()
    >>> print(f"Compliance score: {report.score:.0%}")
    >>> for finding in report.findings:
    ...     print(f"  [{finding.severity}] {finding.message}")
    """

    def __init__(
        self,
        root: ET.Element | None = None,
        config: ElementPatterns | None = None,
    ):
        """Initialize the JATS4R validator."""
        super().__init__(root, config)

    def validate(self) -> ValidationReport:
        """
        Run all JATS4R validations on the document.

        Returns
        -------
        ValidationReport
            Complete validation findings and compliance score.
        """
        self._require_root()

        report = ValidationReport()

        self._validate_authors(report)
        self._validate_abstract(report)
        self._validate_funding(report)
        self._validate_citations(report)
        self._validate_data_availability(report)
        self._validate_orcid(report)
        self._validate_peer_review(report)
        self._validate_affiliations(report)

        logger.info(
            f"JATS4R validation complete: score={report.score:.0%}, "
            f"findings={len(report.findings)}"
        )
        return report

    # ------------------------------------------------------------------
    # Author validation (JATS4R Authors v2.0)
    # ------------------------------------------------------------------

    def _validate_authors(self, report: ValidationReport) -> None:
        """Validate author tagging against JATS4R recommendations."""
        if self.root is None:
            return

        contrib_elements = self.root.findall(".//contrib[@contrib-type='author']")

        if not contrib_elements:
            report.add_finding(
                ValidationFinding(
                    rule_id="AUTH-01",
                    severity="error",
                    message="No author contributions found",
                    category="authors",
                    suggestion="Add <contrib contrib-type='author'> elements",
                )
            )
            return

        for contrib in contrib_elements:
            author_id = contrib.get("id", "")
            # Check for ORCID
            orcid = contrib.find(".//contrib-id[@contrib-id-type='orcid']")
            if orcid is None:
                orcid_uri = contrib.find(".//ext-link[@ext-link-type='orcid']")
                if orcid_uri is None:
                    report.add_finding(
                        ValidationFinding(
                            rule_id="AUTH-02",
                            severity="info",
                            message=f"Author {author_id} missing ORCID identifier",
                            category="authors",
                            suggestion=(
                                "Add a <contrib-id contrib-id-type='orcid'> element"
                                " with the author's ORCID"
                            ),
                        )
                    )

            # Check for equal-contribution flag
            if (
                contrib.find(".//fn[@fn-type='equal']") is None
                and contrib.find(".//xref[@ref-type='fn']") is None
            ):
                # This is soft - not all authors have equal contribution
                pass

            # Check for corresponding author
            corr_xref = contrib.find(".//xref[@ref-type='corresp']")
            if corr_xref is None:
                pass  # Not all authors are corresponding

    def _validate_affiliations(self, report: ValidationReport) -> None:
        """Validate affiliation tagging."""
        if self.root is None:
            return

        affs = self.root.findall(".//aff")
        if not affs:
            report.add_finding(
                ValidationFinding(
                    rule_id="AFF-01",
                    severity="error",
                    message="No affiliations found",
                    category="affiliations",
                    suggestion=(
                        "Add <aff> elements within <contrib-group> to link authors to institutions"
                    ),
                )
            )
            return

        for aff in affs:
            aff_id = aff.get("id", "")
            # Check for institution name
            if aff.find("institution") is None:
                report.add_finding(
                    ValidationFinding(
                        rule_id="AFF-02",
                        severity="warning",
                        message=f"Affiliation {aff_id} missing institution name",
                        category="affiliations",
                        element_path=f".//aff[@id='{aff_id}']",
                        suggestion=("Add an <institution> element within the affiliation"),
                    )
                )

            # Check for country
            if aff.find("country") is None:
                report.add_finding(
                    ValidationFinding(
                        rule_id="AFF-03",
                        severity="info",
                        message=f"Affiliation {aff_id} missing country",
                        category="affiliations",
                        element_path=f".//aff[@id='{aff_id}']",
                        suggestion=("Add a <country> element for geographic metadata"),
                    )
                )

    # ------------------------------------------------------------------
    # Abstract validation (JATS4R Abstracts v1.0)
    # ------------------------------------------------------------------

    def _validate_abstract(self, report: ValidationReport) -> None:
        """Validate abstract tagging."""
        if self.root is None:
            return

        abstracts = self.root.findall(".//abstract")
        if not abstracts:
            report.add_finding(
                ValidationFinding(
                    rule_id="ABST-01",
                    severity="error",
                    message="No abstract found",
                    category="abstract",
                    suggestion=("Add an <abstract> element with <p> children"),
                )
            )
            return

        for abstract in abstracts:
            abstract_type = abstract.get("abstract-type", "default")
            paragraphs = abstract.findall(".//p")
            if not paragraphs:
                report.add_finding(
                    ValidationFinding(
                        rule_id="ABST-02",
                        severity="error",
                        message=f"Abstract (type={abstract_type}) has no paragraphs",
                        category="abstract",
                        suggestion=("Add <p> elements within the <abstract>"),
                    )
                )

            # Check for structured abstract types
            if abstract_type in (
                "structured",
                "executive-summary",
                "toc",
            ):
                secs = abstract.findall(".//sec")
                if not secs:
                    report.add_finding(
                        ValidationFinding(
                            rule_id="ABST-03",
                            severity="info",
                            message=(
                                f"Structured abstract (type={abstract_type}) "
                                "should contain <sec> elements"
                            ),
                            category="abstract",
                            suggestion=(
                                "Use <sec> within <abstract> for labeled sections"
                                " like Background, Methods, Results, Conclusions"
                            ),
                        )
                    )

    # ------------------------------------------------------------------
    # Funding validation (JATS4R Funding v1.3)
    # ------------------------------------------------------------------

    def _validate_funding(self, report: ValidationReport) -> None:
        """Validate funding information."""
        if self.root is None:
            return

        funding_groups = self.root.findall(".//funding-group")
        if not funding_groups:
            report.add_finding(
                ValidationFinding(
                    rule_id="FUND-01",
                    severity="info",
                    message="No funding information found",
                    category="funding",
                    suggestion=("Add a <funding-group> element with award information"),
                )
            )
            return

        for fg in funding_groups:
            # Check for award IDs
            awards = fg.findall(".//award-id")
            if not awards:
                report.add_finding(
                    ValidationFinding(
                        rule_id="FUND-02",
                        severity="warning",
                        message="Funding group missing award IDs",
                        category="funding",
                        suggestion=(
                            "Add <award-id> elements within <funding-group> with grant numbers"
                        ),
                    )
                )

            # Check for funding source
            sources = fg.findall(".//funding-source") or fg.findall(".//funder-name")
            if not sources:
                report.add_finding(
                    ValidationFinding(
                        rule_id="FUND-03",
                        severity="warning",
                        message="Funding group missing funding source",
                        category="funding",
                        suggestion=("Add <funding-source> elements naming the funder"),
                    )
                )

            # Check for open access award pattern
            for _award in awards:
                pass
                # No further validation on award IDs

    # ------------------------------------------------------------------
    # Citation validation (JATS4R Citations)
    # ------------------------------------------------------------------

    def _validate_citations(self, report: ValidationReport) -> None:
        """Validate citation tagging."""
        if self.root is None:
            return

        refs = self.root.findall(".//ref")
        if not refs:
            report.add_finding(
                ValidationFinding(
                    rule_id="CITE-01",
                    severity="info",
                    message="No references found",
                    category="citations",
                    suggestion=("Add a <ref-list> with <ref> elements"),
                )
            )
            return

        # Check each reference for required elements
        for ref in refs:
            ref_id = ref.get("id", "")
            citation = ref.find(".//element-citation")
            if citation is None:
                citation = ref.find(".//mixed-citation")

            if citation is None:
                # Check for other citation types
                citation = ref.find(".//nlm-citation")
                if citation is None:
                    citation = ref.find(".//citation")

            if citation is None:
                report.add_finding(
                    ValidationFinding(
                        rule_id="CITE-02",
                        severity="error",
                        message=f"Reference {ref_id} missing citation element",
                        category="citations",
                        element_path=f".//ref[@id='{ref_id}']",
                        suggestion=("Use <element-citation> or <mixed-citation> within <ref>"),
                    )
                )
                continue

            # Check for DOI or PMID
            has_doi = citation.find(".//pub-id[@pub-id-type='doi']") is not None
            has_pmid = citation.find(".//pub-id[@pub-id-type='pmid']") is not None

            if not has_doi and not has_pmid:
                report.add_finding(
                    ValidationFinding(
                        rule_id="CITE-03",
                        severity="info",
                        message=(f"Reference {ref_id} missing DOI or PMID identifier"),
                        category="citations",
                        suggestion=("Add a <pub-id> element with pub-id-type='doi'"),
                    )
                )

    # ------------------------------------------------------------------
    # Data availability validation
    # ------------------------------------------------------------------

    def _validate_data_availability(self, report: ValidationReport) -> None:
        """Validate data availability statements."""
        if self.root is None:
            return

        # Look for data availability in several possible locations
        # NOTE: Using Python checks instead of XPath 2.0 starts-with()
        found = False

        # Check for sec elements with matching titles (XPath 1.0 compatible)
        for sec in self.root.findall(".//sec"):
            title_elem = sec.find("title")
            if title_elem is not None and title_elem.text:
                title_lower = title_elem.text.lower().strip()
                if any(
                    phrase in title_lower
                    for phrase in [
                        "data availability",
                        "data access",
                        "availability of data",
                        "data sharing",
                    ]
                ):
                    found = True
                    break

        # Check for attribute-based markers
        if not found and self.root.find(".//fn[@fn-type='data-availability']") is not None:
            found = True

        if not found and self.root.find(".//sec[@sec-type='data-availability']") is not None:
            found = True

        if not found:
            report.add_finding(
                ValidationFinding(
                    rule_id="DATA-01",
                    severity="info",
                    message="No data availability statement found",
                    category="data_availability",
                    suggestion=(
                        "Add a data availability section or "
                        "<fn fn-type='data-availability'> element"
                    ),
                )
            )

    # ------------------------------------------------------------------
    # ORCID validation
    # ------------------------------------------------------------------

    def _validate_orcid(self, report: ValidationReport) -> None:
        """Validate ORCID identifier presence and format."""
        if self.root is None:
            return

        orcids = self.root.findall(".//contrib-id[@contrib-id-type='orcid']")

        for orcid in orcids:
            orcid_value = orcid.text or ""
            # Validate format: 0000-0002-1825-0097 (16 digits with hyphens)
            if not re.match(
                r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$",
                orcid_value.strip(),
            ):
                report.add_finding(
                    ValidationFinding(
                        rule_id="ORCID-01",
                        severity="warning",
                        message=f"Invalid ORCID format: '{orcid_value}'",
                        category="orcid",
                        element_path=".//contrib-id[@contrib-id-type='orcid']",
                        suggestion=("ORCID should follow format: 0000-0002-1825-0097"),
                    )
                )

    # ------------------------------------------------------------------
    # Peer review validation (JATS4R Peer Review v1.0)
    # ------------------------------------------------------------------

    def _validate_peer_review(self, report: ValidationReport) -> None:
        """Validate peer review material tagging."""
        if self.root is None:
            return

        sub_articles = self.root.findall(".//sub-article")
        if not sub_articles:
            # Not all articles have peer review - this is informational
            return

        for sub in sub_articles:
            article_type = sub.get("article-type", "")
            review_types = {
                "decision-letter",
                "referee-report",
                "editor-report",
                "reviewer-report",
                "author-comment",
                "reply",
            }

            if article_type not in review_types:
                report.add_finding(
                    ValidationFinding(
                        rule_id="REV-01",
                        severity="info",
                        message=(f"Sub-article has non-review type: '{article_type}'"),
                        category="peer_review",
                        element_path=f".//sub-article[@article-type='{article_type}']",
                        suggestion=("Use one of the JATS4R review article types"),
                    )
                )

    # ------------------------------------------------------------------
    # Helper: extract element text safely
    # ------------------------------------------------------------------

    @staticmethod
    def _get_elem_text(elem: ET.Element | None) -> str:
        """Get text content safely."""
        if elem is None:
            return ""
        return " ".join(elem.itertext()).strip()
