"""
Reference entity model for representing bibliographic references.
"""

from dataclasses import dataclass

from pyeuropepmc.models.scholarly_work import ScholarlyWorkEntity

__all__ = ["ReferenceEntity"]


@dataclass
class ReferenceEntity(ScholarlyWorkEntity):
    """
    Entity representing a bibliographic reference with BIBO alignment.

    Attributes
    ----------
    authors : Optional[str]
        Author list (comma-separated)
    raw_citation : Optional[str]
        Raw citation text when parsing fails to extract structured metadata

    Examples
    --------
    >>> ref = ReferenceEntity(
    ...     title="Sample Article",
    ...     journal="Nature",
    ...     publication_year=2021,
    ...     doi="10.1038/nature12345"
    ... )
    >>> ref.validate()
    """

    raw_citation: str | None = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:Document"]
        if not self.label:
            self.label = self.title or self.doi or "Untitled Reference"

    def validate(self) -> None:
        """Validate reference data."""
        # References can exist with minimal information, but validate what we have
        from pyeuropepmc.models.utils import validate_and_normalize_year

        if self.publication_year is not None:
            self.publication_year = validate_and_normalize_year(self.publication_year)

        super().validate()

    def normalize(self) -> None:
        """Normalize reference data (trim whitespace, validate types)."""
        from pyeuropepmc.models.utils import normalize_string_field

        if isinstance(self.authors, str):
            self.authors = normalize_string_field(self.authors)
        self.raw_citation = normalize_string_field(self.raw_citation)
        super().normalize()
