"""
Rhetorical PDF highlighting service.

Analyzes sentences in a PDF or text document and labels them by their
rhetorical role (Claim, Method, Result, Limitation, Conclusion, etc.)
using an LLM (OpenAI by default). Produces a structured output that can
be used for PDF annotation overlays.

Reference:
    - ScholarPhi / Semantic Scholar's SPECTER approach
    - CL-X (Claim Extraction) methodology
    - scite.ai Smart Citations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "RhetoricalRole",
    "SentenceAnnotation",
    "HighlightedDocument",
    "RhetoricalHighlighter",
    "highlight_pdf_text",
    "highlight_text",
]


class RhetoricalRole(str, Enum):
    """Rhetorical roles for sentence-level annotations."""

    CLAIM = "claim"
    """A central claim or contribution of the paper."""

    METHOD = "method"
    """Description of methods, experiments, or procedures."""

    RESULT = "result"
    """Reported results, findings, or observations."""

    LIMITATION = "limitation"
    """Limitations, weaknesses, or caveats."""

    CONCLUSION = "conclusion"
    """Conclusions, implications, or future work."""

    BACKGROUND = "background"
    """Background information or related work."""

    MOTIVATION = "motivation"
    """Motivation for the work or problem statement."""

    SUPPORTING_CITATION = "supporting_citation"
    """A citation that supports the paper's claims."""

    CONTRADICTING_CITATION = "contradicting_citation"
    """A citation that contradicts or challenges the paper's claims."""

    SUPPLEMENTARY = "supplementary"
    """Supplementary or additional information."""

    UNKNOWN = "unknown"
    """Role could not be determined."""

    @classmethod
    def display_labels(cls) -> dict[str, str]:
        """Get human-readable display labels for each role."""
        return {
            cls.CLAIM: "🔵 Claim",
            cls.METHOD: "🟢 Method",
            cls.RESULT: "🟡 Result",
            cls.LIMITATION: "🔴 Limitation",
            cls.CONCLUSION: "🟣 Conclusion",
            cls.BACKGROUND: "⚪ Background",
            cls.MOTIVATION: "🟠 Motivation",
            cls.SUPPORTING_CITATION: "✅ Supporting Citation",
            cls.CONTRADICTING_CITATION: "❌ Contradicting Citation",
            cls.SUPPLEMENTARY: "📎 Supplementary",
            cls.UNKNOWN: "⬜ Unknown",
        }

    @classmethod
    def hex_colors(cls) -> dict[str, str]:
        """Get hex colors for annotation overlays."""
        return {
            cls.CLAIM: "#1f77b4",
            cls.METHOD: "#2ca02c",
            cls.RESULT: "#ffbb78",
            cls.LIMITATION: "#d62728",
            cls.CONCLUSION: "#9467bd",
            cls.BACKGROUND: "#7f7f7f",
            cls.MOTIVATION: "#ff7f0e",
            cls.SUPPORTING_CITATION: "#98df8a",
            cls.CONTRADICTING_CITATION: "#c49c94",
            cls.SUPPLEMENTARY: "#bcbd22",
            cls.UNKNOWN: "#cccccc",
        }


@dataclass
class SentenceAnnotation:
    """
    Annotation for a single sentence in a document.

    Attributes
    ----------
    text : str
        The sentence text.
    role : RhetoricalRole
        Predicted rhetorical role.
    confidence : float
        Confidence score (0.0–1.0).
    start_char : int, optional
        Character offset (start) in the original text.
    end_char : int, optional
        Character offset (end) in the original text.
    explanation : str, optional
        Brief explanation of why this role was assigned.
    metadata : dict
        Additional metadata (e.g., cited papers, entities).
    """

    text: str
    role: RhetoricalRole = RhetoricalRole.UNKNOWN
    confidence: float = 0.0
    start_char: int = 0
    end_char: int = 0
    explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "role": self.role.value,
            "confidence": self.confidence,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "explanation": self.explanation,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"<SentenceAnnotation role={self.role.value} conf={self.confidence:.2f}>"


@dataclass
class HighlightedDocument:
    """
    A fully annotated document with sentence-level rhetorical roles.

    Attributes
    ----------
    sentences : list[SentenceAnnotation]
        Annotated sentences.
    title : str, optional
        Document title.
    authors : str, optional
        Document authors.
    source : str, optional
        Source identifier (PMID, DOI, etc.).
    statistics : dict
        Aggregated stats (count per role, mean confidence, etc.).
    """

    sentences: list[SentenceAnnotation] = field(default_factory=list)
    title: str = ""
    authors: str = ""
    source: str = ""
    statistics: dict[str, Any] = field(default_factory=dict)

    def group_by_role(self) -> dict[str, list[SentenceAnnotation]]:
        """Group sentences by their rhetorical role."""
        grouped: dict[str, list[SentenceAnnotation]] = {}
        for sent in self.sentences:
            role = sent.role.value
            if role not in grouped:
                grouped[role] = []
            grouped[role].append(sent)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "title": self.title,
            "authors": self.authors,
            "source": self.source,
            "sentences": [s.to_dict() for s in self.sentences],
            "statistics": self.statistics,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def compute_statistics(self) -> dict[str, Any]:
        """Compute aggregate statistics."""
        total = len(self.sentences)
        role_counts: dict[str, int] = {}
        confidences: dict[str, list[float]] = {}
        for sent in self.sentences:
            role = sent.role.value
            role_counts[role] = role_counts.get(role, 0) + 1
            if role not in confidences:
                confidences[role] = []
            confidences[role].append(sent.confidence)

        role_pcts = {
            role: (count / total * 100) if total > 0 else 0 for role, count in role_counts.items()
        }
        mean_conf = {role: (sum(cf) / len(cf)) if cf else 0.0 for role, cf in confidences.items()}

        self.statistics = {
            "total_sentences": total,
            "role_counts": role_counts,
            "role_percentages": role_pcts,
            "mean_confidence_per_role": mean_conf,
            "overall_mean_confidence": (
                sum(s.confidence for s in self.sentences) / total if total > 0 else 0.0
            ),
        }
        return self.statistics

    def summary(self) -> str:
        """Human-readable summary."""
        if not self.statistics:
            self.compute_statistics()
        lines = [f"Title: {self.title or 'N/A'}"]
        lines.append(f"Sentences: {self.statistics['total_sentences']}")
        for role, count in sorted(self.statistics["role_counts"].items(), key=lambda x: -x[1]):
            pct = self.statistics["role_percentages"][role]
            label = RhetoricalRole.display_labels().get(RhetoricalRole(role), role)
            lines.append(f"  {label}: {count} ({pct:.1f}%)")
        return "\n".join(lines)


# ------------------------------------------------------------------
# Heuristic classifier (no LLM required)
# ------------------------------------------------------------------

_RULE_PATTERNS: list[tuple[re.Pattern[str], RhetoricalRole, float]] = [
    # Claims (words suggesting a strong statement)
    (
        re.compile(
            r"\b(we show|we demonstrate|we prove|we establish|we find|we argue|our results indicate|these findings suggest|this work demonstrates|the key insight|the main contribution|importantly|notably|critically)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.CLAIM,
        0.6,
    ),
    # Method (procedural language)
    (
        re.compile(
            r"\b(we used|we applied|we employed|we conducted|we performed|we implemented|we developed|we trained|we collected|we analyzed|we measured|we computed|we designed|using|method|approach|algorithm|dataset|experiment|protocol|procedure|model was trained|architecture|framework)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.METHOD,
        0.5,
    ),
    # Results (reporting outcomes)
    (
        re.compile(
            r"\b(we observed|we obtained|the result|our results|the outcome|the effect|achieved|reached|yielded|produced|resulted in|led to|showed that|demonstrated that|found that|achieved an?|improved by|decreased by|increased by)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.RESULT,
        0.5,
    ),
    # Limitations
    (
        re.compile(
            r"\b(limitation|caveat|drawback|weakness|shortcoming|not generaliz|limited to|not consider|does not account|may not apply|potential bias|confound|constraint|restrict)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.LIMITATION,
        0.6,
    ),
    # Conclusion / Future work
    (
        re.compile(
            r"\b(in conclusion|to conclude|we conclude|in summary|to summarize|taken together|taken together,|future work|future research|open problem|remains to be|further investigation|further study|ongoing work|we plan to)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.CONCLUSION,
        0.5,
    ),
    # Background
    (
        re.compile(
            r"\b(previous work|prior work|related work|earlier studies|previous studies|has been studied|it is well known|it has been shown|background|motivated by|prior research|state of the art)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.BACKGROUND,
        0.5,
    ),
    # Motivation
    (
        re.compile(
            r"\b(motivat|aim of this|goal of this|objective|we aim to|we seek to|this paper addresses|we address the|the challenge of|despite|however|although|while there is|limited research|gap in|need for)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.MOTIVATION,
        0.5,
    ),
    # Supporting citation
    (
        re.compile(
            r"\b(as shown by|consistent with|in agreement with|support|confirm|citing|reported by|according to|following|similar to|in line with)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.SUPPORTING_CITATION,
        0.4,
    ),
    # Contradicting citation
    (
        re.compile(
            r"\b(in contrast|contrary to|contradict|conflict with|unlike|inconsistent|disagree|challenge|refute|rebut|argument against)\b",
            re.IGNORECASE,
        ),
        RhetoricalRole.CONTRADICTING_CITATION,
        0.4,
    ),
]

_SENTENCE_SPLITTER = re.compile(r"(?<=[.!?])\s+")


class RhetoricalHighlighter:
    """
    Analyzes sentences in a document and labels their rhetorical roles.

    Uses a two-stage approach:
    1. Rule-based heuristic classification (fast, no API needed)
    2. Optional LLM refinement (requires LLMClient and API key)

    Examples
    --------
    >>> rl = RhetoricalHighlighter()
    >>> text = "We show that our method achieves 95% accuracy. The model was trained on ImageNet."
    >>> doc = rl.highlight(text)
    >>> for s in doc.sentences:
    ...     print(f"[{s.role.value}] {s.text}")
    """

    def __init__(
        self,
        use_llm: bool = False,
        llm_client: Any = None,
        llm_model: str = "gpt-4o-mini",
        confidence_threshold: float = 0.3,
    ) -> None:
        """
        Parameters
        ----------
        use_llm : bool, optional
            Whether to use LLM-based classification for ambiguous sentences.
        llm_client : LLMClient, optional
            LLM client instance. If None, uses rule-based only.
        llm_model : str, optional
            Model name for LLM refinement.
        confidence_threshold : float, optional
            Minimum confidence to keep a classification (0.0–1.0).
            Sentences below this are labeled UNKNOWN.
        """
        self.use_llm = use_llm
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.confidence_threshold = confidence_threshold

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def highlight(
        self,
        text: str,
        title: str = "",
        authors: str = "",
        source: str = "",
    ) -> HighlightedDocument:
        """
        Analyze text and annotate sentences with rhetorical roles.

        Parameters
        ----------
        text : str
            Full document text to analyze.
        title : str, optional
            Document title.
        authors : str, optional
            Document authors.
        source : str, optional
            Source identifier.

        Returns
        -------
        HighlightedDocument
        """
        # Split into sentences
        raw_sentences = _SENTENCE_SPLITTER.split(text.strip())
        raw_sentences = [s.strip() for s in raw_sentences if s.strip()]

        annotations: list[SentenceAnnotation] = []
        char_pos = 0

        for sent_text in raw_sentences:
            role, confidence = self._classify_sentence(sent_text)
            annotation = SentenceAnnotation(
                text=sent_text,
                role=role,
                confidence=confidence,
                start_char=char_pos,
                end_char=char_pos + len(sent_text),
            )
            annotations.append(annotation)
            char_pos += len(sent_text) + 1  # +1 for space

        doc = HighlightedDocument(
            sentences=annotations,
            title=title,
            authors=authors,
            source=source,
        )
        doc.compute_statistics()
        return doc

    # ------------------------------------------------------------------
    # Sentence classification
    # ------------------------------------------------------------------

    def _classify_sentence(
        self,
        sentence: str,
    ) -> tuple[RhetoricalRole, float]:
        """Classify a single sentence using rules, optionally LLM."""
        best_role = RhetoricalRole.UNKNOWN
        best_confidence = 0.0

        # Rule-based matching
        for pattern, role, conf in _RULE_PATTERNS:
            if pattern.search(sentence) and conf > best_confidence:
                best_role = role
                best_confidence = conf

        # LLM refinement for uncertain sentences
        if self.use_llm and self.llm_client and best_confidence < 0.4:
            try:
                llm_role, llm_conf = self._classify_with_llm(sentence)
                if llm_conf > best_confidence:
                    best_role = llm_role
                    best_confidence = llm_conf
            except Exception as e:
                logger.warning("LLM classification failed: %s", e)

        if best_confidence < self.confidence_threshold:
            return RhetoricalRole.UNKNOWN, best_confidence

        return best_role, best_confidence

    def _classify_with_llm(
        self,
        sentence: str,
    ) -> tuple[RhetoricalRole, float]:
        """Use LLM to classify a sentence's rhetorical role."""
        roles_list = ", ".join(f'"{r.value}"' for r in RhetoricalRole)
        prompt = (
            f"Classify the following sentence into exactly one of these "
            f"rhetorical roles: {roles_list}.\n\n"
            f'Respond with a JSON object: {{"role": "<role>", "confidence": 0.0-1.0, "explanation": "<brief reason>"}}\n\n'
            f'Sentence: "{sentence}"'
        )

        response = self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.llm_model,
            temperature=0.0,
        )

        try:
            result = json.loads(response)
            role_str = result.get("role", "unknown")
            confidence = float(result.get("confidence", 0.0))

            # Validate role
            try:
                role = RhetoricalRole(role_str)
            except ValueError:
                role = RhetoricalRole.UNKNOWN

            return role, confidence
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("LLM response parsing failed: %s", e)
            return RhetoricalRole.UNKNOWN, 0.0


# ------------------------------------------------------------------
# PDF text extraction helper
# ------------------------------------------------------------------


def extract_text_from_pdf(pdf_path: str) -> str | None:
    """
    Extract text from a PDF file using available backends.

    Tries PyMuPDF (fitz), then pdfplumber, then pdfminer.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    str or None
        Extracted text, or None if no backend is available.
    """
    for lib_name, _module_path, extract_fn in [
        ("fitz", "fitz", "_extract_pymupdf"),
        ("pdfplumber", "pdfplumber", "_extract_pdfplumber"),
        ("pdfminer", "pdfminer.high_level", "_extract_pdfminer"),
    ]:
        try:
            text: str = globals()[extract_fn](pdf_path)
            return text
        except ImportError:
            continue
        except Exception as e:
            logger.debug("PDF extraction with %s failed: %s", lib_name, e)
            continue

    logger.error("No PDF extraction library available (try: pip install pymupdf pdfplumber)")
    return None


def _extract_pymupdf(pdf_path: str) -> str:
    """Extract text using PyMuPDF."""
    import fitz

    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def _extract_pdfplumber(pdf_path: str) -> str:
    """Extract text using pdfplumber."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return text


def _extract_pdfminer(pdf_path: str) -> str:
    """Extract text using pdfminer.six."""
    from pdfminer.high_level import extract_text as pm_extract

    text: str = pm_extract(pdf_path)
    return text


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------


def highlight_pdf_text(
    pdf_path: str,
    use_llm: bool = False,
    llm_client: Any = None,
    title: str = "",
    authors: str = "",
) -> HighlightedDocument | None:
    """
    Extract text from a PDF and annotate with rhetorical roles.

    Parameters
    ----------
    pdf_path : str
        Path to PDF file.
    use_llm : bool, optional
        Whether to use LLM for refinement.
    llm_client : LLMClient, optional
        LLM client for refinement.
    title : str, optional
        Document title.
    authors : str, optional
        Document authors.

    Returns
    -------
    HighlightedDocument or None
        Annotated document, or None if PDF could not be read.
    """
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return None

    highlighter = RhetoricalHighlighter(use_llm=use_llm, llm_client=llm_client)
    return highlighter.highlight(text, title=title, authors=authors, source=pdf_path)


def highlight_text(
    text: str,
    use_llm: bool = False,
    llm_client: Any = None,
    title: str = "",
    authors: str = "",
) -> HighlightedDocument:
    """
    Annotate plain text with rhetorical roles.

    Parameters
    ----------
    text : str
        Text to analyze.
    use_llm : bool, optional
        Whether to use LLM for refinement.
    llm_client : LLMClient, optional
        LLM client for refinement.
    title, authors : str, optional
        Metadata.

    Returns
    -------
    HighlightedDocument
    """
    highlighter = RhetoricalHighlighter(use_llm=use_llm, llm_client=llm_client)
    return highlighter.highlight(text, title=title, authors=authors)
