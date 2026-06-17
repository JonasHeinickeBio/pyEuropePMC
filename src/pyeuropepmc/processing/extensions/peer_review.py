"""
Peer Review Material Extraction from JATS XML.

Extracts peer review materials from JATS articles that contain ``<sub-article>``
elements with peer review article types (eLife, bioRxiv, etc.).

Supports extraction of:
- Decision letters
- Referee reports (reviewer comments)
- Editor reports
- Author responses/replies
- Revision rounds

Based on patterns from the OpenEvalProject/jats parser and JATS4R recommendations
for peer review materials (NISO RP-48-2024).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.extensions.content_blocks import (
    ContentBlock,
    ContentBlockExtractor,
    StructuredSection,
)
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class PeerReviewType(str, Enum):
    """Types of peer review materials defined in JATS."""

    DECISION_LETTER = "decision-letter"
    REFEREE_REPORT = "referee-report"
    EDITOR_REPORT = "editor-report"
    REVIEWER_REPORT = "reviewer-report"
    AUTHOR_COMMENT = "author-comment"
    REPLY = "reply"
    UNKNOWN = "unknown"


# Mapping of JATS article-type attribute values to PeerReviewType
JATS_REVIEW_TYPE_MAP: dict[str, PeerReviewType] = {
    "decision-letter": PeerReviewType.DECISION_LETTER,
    "referee-report": PeerReviewType.REFEREE_REPORT,
    "editor-report": PeerReviewType.EDITOR_REPORT,
    "reviewer-report": PeerReviewType.REVIEWER_REPORT,
    "author-comment": PeerReviewType.AUTHOR_COMMENT,
    "reply": PeerReviewType.REPLY,
}


@dataclass
class PeerReviewMaterial:
    """
    A single peer review item (one sub-article).

    Parameters
    ----------
    review_type : PeerReviewType
        The type of review material.
    title : str
        Title of the review item.
    contributors : list[dict[str, str]]
        Persons involved (reviewers, editors).
    sections : list[StructuredSection]
        Structured content of the review.
    revision_round : int, optional
        Which revision round this belongs to (1-indexed).
    metadata : dict
        Additional metadata extracted from the sub-article.
    """

    review_type: PeerReviewType
    title: str = ""
    contributors: list[dict[str, str]] = field(default_factory=list)
    sections: list[StructuredSection] = field(default_factory=list)
    revision_round: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "review_type": self.review_type.value,
            "title": self.title,
            "contributors": self.contributors,
            "sections": [s.to_dict() for s in self.sections],
            "revision_round": self.revision_round,
            "metadata": self.metadata,
        }


@dataclass
class PeerReviewSet:
    """
    Collection of peer review materials for an article, organized by revision round.

    Parameters
    ----------
    article_id : str
        PMID or DOI of the parent article.
    reviews : list[PeerReviewMaterial]
        All review materials across all rounds.
    revision_rounds : dict[int, list[PeerReviewMaterial]]
        Reviews grouped by revision round number.
    """

    article_id: str = ""
    reviews: list[PeerReviewMaterial] = field(default_factory=list)
    revision_rounds: dict[int, list[PeerReviewMaterial]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "article_id": self.article_id,
            "reviews": [r.to_dict() for r in self.reviews],
            "revision_rounds": {
                str(round_num): [r.to_dict() for r in items]
                for round_num, items in self.revision_rounds.items()
            },
        }


class PeerReviewExtractor(BaseParser):
    """
    Extracts peer review materials from JATS XML sub-articles.

    Parameters
    ----------
    root : ET.Element, optional
        Root element of the parsed XML.
    config : ElementPatterns, optional
        Configuration for element pattern matching.
    """

    def __init__(
        self,
        root: ET.Element | None = None,
        config: ElementPatterns | None = None,
    ):
        """Initialize the peer review extractor."""
        super().__init__(root, config)
        self._block_extractor: ContentBlockExtractor | None = None

    @property
    def block_extractor(self) -> ContentBlockExtractor:
        """Lazy-loaded content block extractor."""
        if self._block_extractor is None:
            self._block_extractor = ContentBlockExtractor(self.root, self.config)
        return self._block_extractor

    def extract_peer_reviews(self) -> PeerReviewSet:
        """
        Extract all peer review materials from the XML.

        Returns
        -------
        PeerReviewSet
            All review materials grouped by revision round.

        Examples
        --------
        >>> reviews = extractor.extract_peer_reviews()
        >>> for round_num, items in reviews.revision_rounds.items():
        ...     for item in items:
        ...         print(f"[Round {round_num}] {item.review_type.value}: {item.title}")
        """
        self._require_root()

        review_set = PeerReviewSet()

        # Extract article ID from parent article
        review_set.article_id = self._extract_article_id()

        # Find all sub-articles with review types
        if self.root is None:
            return review_set

        for sub_article in self.root.findall(".//sub-article"):
            article_type = sub_article.get("article-type", "")
            review_type = JATS_REVIEW_TYPE_MAP.get(article_type)

            if review_type is None:
                continue

            review = self._extract_single_review(sub_article, review_type)
            review_set.reviews.append(review)
            review_set.revision_rounds.setdefault(review.revision_round, []).append(review)

        # Sort rounds for deterministic output
        review_set.revision_rounds = dict(sorted(review_set.revision_rounds.items()))

        logger.info(
            f"Extracted {len(review_set.reviews)} peer review items "
            f"across {len(review_set.revision_rounds)} revision rounds"
        )
        return review_set

    def _extract_article_id(self) -> str:
        """Extract the parent article ID."""
        if self.root is None:
            return ""
        # Try PMID first, then DOI, then PMCID
        for id_type in ("pmid", "doi", "pmcid"):
            for elem in self.root.findall(f".//article-id[@pub-id-type='{id_type}']"):
                text = elem.text
                if text and text.strip():
                    return text.strip()
        return ""

    def _extract_single_review(
        self,
        sub_article: ET.Element,
        review_type: PeerReviewType,
    ) -> PeerReviewMaterial:
        """Extract a single peer review from a sub-article element."""
        title = ""
        title_group = sub_article.find(".//article-meta/title-group/article-title")
        if title_group is not None:
            title = XMLHelper.get_text_content(title_group)

        # Detect revision round from metadata
        revision_round = self._detect_revision_round(sub_article)

        # Extract contributors (reviewers, editors)
        contributors = self._extract_contributors(sub_article)

        # Extract structured content sections
        sections = self._extract_review_sections(sub_article)

        # Extract additional metadata
        metadata = self._extract_review_metadata(sub_article)

        return PeerReviewMaterial(
            review_type=review_type,
            title=title,
            contributors=contributors,
            sections=sections,
            revision_round=revision_round,
            metadata=metadata,
        )

    def _detect_revision_round(self, sub_article: ET.Element) -> int:
        """Detect the revision round from sub-article metadata."""
        # Try version number
        version = sub_article.find(".//version")
        if version is not None and version.text:
            try:
                return int(version.text.strip())
            except ValueError:
                pass

        # Try fn-group with revision history
        fn = sub_article.find(".//fn[@fn-type='rev-received']")
        if fn is not None:
            # Derive round from the fn label if present
            label = fn.find("label")
            if label is not None and "R" in (label.text or ""):
                import re

                match = re.search(r"R(\d+)", label.text or "")
                if match:
                    return int(match.group(1))

        return 1  # Default to round 1

    def _extract_contributors(self, sub_article: ET.Element) -> list[dict[str, str]]:
        """Extract contributors from the sub-article."""
        contributors: list[dict[str, str]] = []

        for contrib in sub_article.findall(".//contrib"):
            contrib_type = contrib.get("contrib-type", "")
            name = contrib.find("name")
            if name is not None:
                surname = name.findtext("surname", "")
                given_names = name.findtext("given-names", "")
                full_name = f"{given_names} {surname}".strip() if surname else given_names
                if full_name:
                    contributors.append(
                        {
                            "name": full_name,
                            "type": contrib_type,
                        }
                    )

        return contributors

    def _extract_review_sections(self, sub_article: ET.Element) -> list[StructuredSection]:
        """Extract structured content from review sub-article body."""
        sections: list[StructuredSection] = []

        body = sub_article.find(".//body")
        if body is None:
            return sections

        for sec in body.findall("sec"):
            structured_sec = self.block_extractor._extract_structured_section(sec)  # noqa: SLF001
            if structured_sec.content:
                sections.append(structured_sec)

        # If no sec elements, treat body paragraphs as a single section
        if not sections:
            content_blocks: list[ContentBlock] = []
            for child in body:
                tag = self._get_local_tag(child.tag)
                if tag == "p":
                    text = XMLHelper.get_text_content(child)
                    if text.strip():
                        content_blocks.append(ContentBlock.paragraph(text.strip()))

            if content_blocks:
                sections.append(
                    StructuredSection(
                        title="",
                        content=content_blocks,
                        section_type="body",
                    )
                )

        return sections

    def _extract_review_metadata(self, sub_article: ET.Element) -> dict[str, Any]:
        """Extract additional metadata from the review sub-article."""
        metadata: dict[str, Any] = {}

        # Dates
        for date_type in ("received", "rev-received", "accepted"):
            date_elem = sub_article.find(f".//date[@date-type='{date_type}']")
            if date_elem is not None:
                year = date_elem.findtext("year", "")
                month = date_elem.findtext("month", "")
                day = date_elem.findtext("day", "")
                metadata[f"{date_type}_date"] = (
                    f"{year}-{month.zfill(2) if month else ''}"
                    f"-{day.zfill(2) if day else ''}".strip("-")
                )

        # Object ID (DOI for the review)
        for obj_id in sub_article.findall(".//object-id"):
            id_type = obj_id.get("pub-id-type", "")
            if obj_id.text:
                metadata[f"object_id_{id_type}"] = obj_id.text.strip()

        return metadata

    @staticmethod
    def _get_local_tag(tag: str) -> str:
        """Strip namespace from a tag name."""
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag
