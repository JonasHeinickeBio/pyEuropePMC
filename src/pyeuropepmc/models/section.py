"""
Section entity model for representing article sections.
"""

from dataclasses import dataclass

from pyeuropepmc.models.base import BaseEntity

__all__ = ["SectionEntity"]


@dataclass
class SectionEntity(BaseEntity):
    """
    Entity representing a document section with BIBO and NIF alignment.

    Attributes
    ----------
    title : Optional[str]
        Section title/heading
    content : Optional[str]
        Section text content
    begin_index : Optional[int]
        NIF begin offset (for sentence/token alignment)
    end_index : Optional[int]
        NIF end offset (for sentence/token alignment)

    Examples
    --------
    >>> section = SectionEntity(
    ...     title="Introduction",
    ...     content="This is the introduction text..."
    ... )
    >>> section.validate()
    """

    title: str | None = None
    content: str | None = None
    begin_index: int | None = None
    end_index: int | None = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:DocumentPart", "nif:Context"]
        if not self.label:
            self.label = self.title or "Untitled Section"

    def validate(self) -> None:
        """
        Validate section data.

        Raises
        ------
        ValueError
            If content is missing
        """
        if self.content is None:
            raise ValueError("SectionEntity must have content")

    def normalize(self) -> None:
        """Normalize section data (trim whitespace)."""
        if self.title:
            self.title = self.title.strip()
        if self.content:
            self.content = self.content.strip()
