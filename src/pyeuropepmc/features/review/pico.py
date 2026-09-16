"""
PICO (Population, Intervention, Comparison, Outcome) decomposition utility.

Decomposes clinical research questions into PICO elements to facilitate
structured literature search. Supports PICO, PICOS (with Study design),
PICOT (with Time), and SPIDER variants.

References:
    - Centre for Reviews and Dissemination (CRD) guidelines
    - Cochrane Handbook for Systematic Reviews
    - PubMed Clinical Queries framework
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "PICOElements",
    "PICOParser",
    "pico_decompose",
    "pico_to_query",
    "pico_to_pubmed_query",
    "SPIDERDecomposer",
    "PICOSDecomposer",
    "PICOTDecomposer",
]

# Pattern templates for detecting PICO elements in text
_PATTERNS = {
    "population": re.compile(
        r"\b(patients?|subjects?|participants?|population|adults?|children|"
        r"infants?|women|men|people|individuals?|cohort|group)\s+(?:with|of|having|"
        r"diagnosed|suffering|presenting)?\s+([^.]+)",
        re.IGNORECASE,
    ),
    "intervention": re.compile(
        r"\b(treated?|intervention|therapy|treatment|administered|exposed|"
        r"received|given|management|care|program|strategy|approach|technique)\s+"
        r"(?:with|to|by|using)?\s+([^.]+)",
        re.IGNORECASE,
    ),
    "comparison": re.compile(
        r"\b(compared?\s+(?:with|to|against)|vs\.?|versus|"
        r"versus|control|placebo|standard|usual\s+care|alternative|"
        r"sham|baseline)\s+([^.]+)",
        re.IGNORECASE,
    ),
    "outcome": re.compile(
        r"\b(outcome|endpoint|result|efficacy|effectiveness|safety|survival|"
        r"mortality|morbidity|response|remission|recurrence|improvement|"
        r"reduction|increase|decrease|change|rate|score|index)\s+"
        r"(?:of|in|at|to|was|were)?\s+([^.]+)",
        re.IGNORECASE,
    ),
    "study_design": re.compile(
        r"\b(RCT|randomized|randomised|systematic\s+review|meta-analysis|"
        r"cohort|case-control|cross-sectional|longitudinal|prospective|"
        r"retrospective|observational|clinical\s+trial|controlled\s+trial)",
        re.IGNORECASE,
    ),
    "time_frame": re.compile(
        r"\b(over|within|during|at|after|before|following)\s+(\d+\s*(?:days?|weeks?|months?|years?)|"
        r"short-term|long-term|immediate|acute|chronic|follow-up)",
        re.IGNORECASE,
    ),
    "setting": re.compile(
        r"\b(in|at|within)\s+([^.]*(?:hospital|clinic|community|primary\s+care|"
        r"outpatient|inpatient|urban|rural|tertiary|nursing\s+home))",
        re.IGNORECASE,
    ),
}

# Pattern names that differ from the PICOElements field they fill.  "time" was
# the default key before it was renamed to match the field; custom pattern
# dicts written against that name still fill ``time_frame``.
_ELEMENT_ALIASES = {"time": "time_frame"}

# Common PICO question starters
_QUESTION_STARTERS = re.compile(
    r"^(?:in|among|for|does|do|is|are|what|how|whether|compare|evaluat|assess|"
    r"determine|investigate)\s+",
    re.IGNORECASE,
)


@dataclass
class PICOElements:
    """
    Structured PICO elements from a clinical question.

    Attributes
    ----------
    population : str
        Population / Patient / Problem.
    intervention : str
        Intervention / Exposure.
    comparison : str, optional
        Comparison / Control (if applicable).
    outcome : str
        Outcome measured.
    study_design : str, optional
        Study design type (for PICOS).
    time_frame : str, optional
        Time frame (for PICOT).
    original_question : str
        The original query text.

    Notes
    -----
    Empty elements indicate the parser could not identify that component.
    """

    population: str = ""
    intervention: str = ""
    comparison: str = ""
    outcome: str = ""
    study_design: str = ""
    time_frame: str = ""
    setting: str = ""
    original_question: str = ""
    confidence: float = 0.0  # 0.0 - 1.0
    identifiers_used: dict[str, list[str]] = field(default_factory=dict)

    def is_complete(self) -> bool:
        """Check if Population, Intervention, and Outcome are all present."""
        return bool(self.population and self.intervention and self.outcome)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dictionary."""
        return {
            "population": self.population,
            "intervention": self.intervention,
            "comparison": self.comparison,
            "outcome": self.outcome,
            "study_design": self.study_design,
            "time_frame": self.time_frame,
            "setting": self.setting,
            "original_question": self.original_question,
            "confidence": self.confidence,
        }

    def __repr__(self) -> str:
        parts = [
            f"P: {self.population}" if self.population else "",
            f"I: {self.intervention}" if self.intervention else "",
            f"C: {self.comparison}" if self.comparison else "",
            f"O: {self.outcome}" if self.outcome else "",
            f"S: {self.study_design}" if self.study_design else "",
            f"T: {self.time_frame}" if self.time_frame else "",
        ]
        present = [p for p in parts if p]
        return f"PICOElements({', '.join(present)})"


class PICOParser:
    """
    Parses clinical research questions into PICO elements.

    Uses pattern matching and heuristics to decompose natural-language
    clinical questions into structured Population, Intervention,
    Comparison, and Outcome components.

    Examples
    --------
    >>> parser = PICOParser()
    >>> pico = parser.parse(
    ...     "In patients with diabetes, does metformin reduce cardiovascular risk vs placebo?"
    ... )
    >>> print(pico.population)
    >>> print(pico.intervention)
    """

    def __init__(
        self,
        patterns: dict[str, re.Pattern[str]] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        patterns : dict, optional
            Custom regex patterns for PICO elements, keyed by the
            :class:`PICOElements` field each one fills (``"time"`` is accepted
            for ``time_frame``). Uses defaults if None.
        """
        self.patterns = patterns or _PATTERNS

    def parse(self, question: str) -> PICOElements:
        """
        Decompose a clinical question into PICO elements.

        Parameters
        ----------
        question : str
            Clinical research question in natural language.

        Returns
        -------
        PICOElements
            Parsed PICO components.
        """
        cleaned = self._clean_question(question)
        elements = PICOElements(original_question=question)
        identifiers: dict[str, list[str]] = {}

        # Attempt pattern matches for each element
        for name, pattern in self.patterns.items():
            element = _ELEMENT_ALIASES.get(name, name)
            matches = pattern.findall(cleaned)
            if matches:
                # For patterns with groups, take the last group as the value
                values = []
                for match in matches:
                    if isinstance(match, tuple):
                        values.append(match[-1].strip().rstrip(".,;:"))
                    else:
                        values.append(match.strip().rstrip(".,;:"))
                if values:
                    setattr(elements, element, values[0])
                    identifiers[element] = values

        elements.identifiers_used = identifiers

        # Post-processing and fallbacks
        if not elements.population:
            elements.population = self._infer_population(cleaned)
        if not elements.outcome:
            elements.outcome = self._infer_outcome(cleaned)

        # Calculate confidence
        elements.confidence = self._calculate_confidence(elements)

        return elements

    def _clean_question(self, question: str) -> str:
        """Normalize and clean the input question."""
        # Remove leading question words
        cleaned = _QUESTION_STARTERS.sub("", question.strip())
        # Remove trailing question marks
        cleaned = cleaned.rstrip("?.")
        return cleaned

    def _infer_population(self, text: str) -> str:
        """Fallback: try to infer the population from the question."""
        # Look for common population markers
        pop_match = re.search(
            r"\b(?:patients?|subjects?|participants?)\s+(?:with|of|having|diagnosed)\s+([^,;.]+)",
            text,
            re.IGNORECASE,
        )
        if pop_match:
            return pop_match.group(1).strip()
        # Look for disease/condition names
        disease_match = re.search(
            r"\b(?:with|of|having|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
            text,
        )
        if disease_match:
            return disease_match.group(1).strip()
        return ""

    def _infer_outcome(self, text: str) -> str:
        """Fallback: try to infer the outcome."""
        outcome_match = re.search(
            r"\b(reduce|increase|improve|prevent|decrease)\s+([^,.;]+)",
            text,
            re.IGNORECASE,
        )
        if outcome_match:
            return f"{outcome_match.group(1)} {outcome_match.group(2)}".strip()
        return ""

    def _calculate_confidence(self, elements: PICOElements) -> float:
        """Calculate parsing confidence score (0.0 - 1.0)."""
        score = 0.0
        if elements.population:
            score += 0.3
        if elements.intervention:
            score += 0.3
        if elements.outcome:
            score += 0.25
        if elements.comparison:
            score += 0.15
        return min(score, 1.0)


# ------------------------------------------------------------------
# Variant parsers
# ------------------------------------------------------------------


class PICOSDecomposer(PICOParser):
    """PICOS: PICO + Study design."""

    def parse(self, question: str) -> PICOElements:
        elements = super().parse(question)
        # Study design is already extracted by parse() via patterns
        return elements


class PICOTDecomposer(PICOParser):
    """PICOT: PICO + Time frame."""

    def parse(self, question: str) -> PICOElements:
        elements = super().parse(question)
        # Time frame is already extracted by parse() via patterns
        return elements


class SPIDERDecomposer:
    """
    SPIDER framework for qualitative/mixed-methods research.

    SPIDER = Sample, Phenomenon of Interest, Design, Evaluation, Research type.
    Suitable for qualitative and mixed-methods questions.

    Reference: Cooke, A., Smith, D., & Booth, A. (2012).
    """

    _SPIDER_PATTERNS = {
        "sample": re.compile(
            r"\b(sample|participants?|group|population|informants?)\s+(?:of|with|is|are)?\s+([^.]+)",
            re.IGNORECASE,
        ),
        "phenomenon_of_interest": re.compile(
            r"\b(experience|perception|attitude|belief|view|opinion|feeling|"
            r"understanding|perspective|barrier|facilitator)\s+(?:of|about|on|towards?)?\s+([^.]+)",
            re.IGNORECASE,
        ),
        "design": re.compile(
            r"\b(qualitative|mixed-methods|interview|focus\s+group|"
            r"survey|ethnography|phenomenology|grounded\s+theory|case\s+study)",
            re.IGNORECASE,
        ),
        "evaluation": re.compile(
            r"\b(evaluat|outcome|impact|effect|result|change|"
            r"effectiveness|satisfaction|benefit|challenge)\s+(?:of|on)?\s+([^.]+)",
            re.IGNORECASE,
        ),
        "research_type": re.compile(
            r"\b(qualitative|quantitative|mixed\s*(?:method|approach)|"
            r"cross-sectional|longitudinal|observational)",
            re.IGNORECASE,
        ),
    }

    def parse(self, question: str) -> dict[str, str]:
        """Parse a question into SPIDER elements."""
        result: dict[str, str] = {}
        for element, pattern in self._SPIDER_PATTERNS.items():
            match = pattern.search(question)
            if match:
                if match.groups():
                    result[element] = match.group(match.lastindex or 1).strip().rstrip(".,;:")
                else:
                    result[element] = match.group(0).strip()
        result["original_question"] = question
        return result


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------


def pico_decompose(question: str) -> PICOElements:
    """
    Decompose a clinical question into PICO elements.

    Parameters
    ----------
    question : str
        Clinical research question.

    Returns
    -------
    PICOElements
    """
    parser = PICOParser()
    return parser.parse(question)


def pico_to_query(pico: PICOElements, use_boolean: bool = True) -> str:
    """
    Convert PICO elements into a structured search query.

    Parameters
    ----------
    pico : PICOElements
        Parsed PICO elements.
    use_boolean : bool, optional
        If True, format as boolean query with AND/OR operators.

    Returns
    -------
    str
        Search query string.
    """
    parts = []
    if pico.population:
        terms = pico.population.split()
        parts.append(f"({' OR '.join(terms[:5])})" if use_boolean else pico.population)
    if pico.intervention:
        terms = pico.intervention.split()
        parts.append(f"({' OR '.join(terms[:5])})" if use_boolean else pico.intervention)
    if pico.outcome:
        terms = pico.outcome.split()
        parts.append(f"({' OR '.join(terms[:5])})" if use_boolean else pico.outcome)
    if pico.comparison:
        terms = pico.comparison.split()
        parts.append(f"({' OR '.join(terms[:3])})" if use_boolean else pico.comparison)
    if pico.study_design:
        parts.append(pico.study_design)
    if pico.time_frame:
        parts.append(pico.time_frame)
    return " AND ".join(parts)


def pico_to_pubmed_query(pico: PICOElements, use_mesh: bool = True) -> str:
    """
    Convert PICO elements into a PubMed-optimized search query using
    Clinical Queries filters.

    Parameters
    ----------
    pico : PICOElements
        Parsed PICO elements.
    use_mesh : bool, optional
        Whether to add [MeSH] tagging to terms.

    Returns
    -------
    str
        PubMed-formatted query string.
    """
    tag = "[MeSH]" if use_mesh else "[tiab]"
    parts = []
    if pico.population:
        parts.append(f"({pico.population}{tag})")
    if pico.intervention:
        parts.append(f"({pico.intervention}{tag})")
    if pico.outcome:
        parts.append(f"({pico.outcome}{tag})")
    if pico.comparison:
        parts.append(f"({pico.comparison}{tag})")
    return " AND ".join(parts)
