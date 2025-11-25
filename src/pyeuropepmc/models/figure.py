"""
Figure entity model for representing figures and images.
"""

from dataclasses import dataclass

from pyeuropepmc.models.base import BaseEntity

__all__ = ["FigureEntity"]


@dataclass
class FigureEntity(BaseEntity):
    """
    Entity representing a figure with BIBO alignment.

    Attributes
    ----------
    caption : Optional[str]
        Figure caption/description
    figure_label : Optional[str]
        Figure label (e.g., "Figure 1")
    graphic_uri : Optional[str]
        URI to the figure graphic/image file

    Examples
    --------
    >>> figure = FigureEntity(
    ...     figure_label="Figure 1",
    ...     caption="Sample scatter plot",
    ...     graphic_uri="https://example.com/figure1.png"
    ... )
    >>> figure.validate()
    """

    caption: str | None = None
    figure_label: str | None = None
    graphic_uri: str | None = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:Image"]
        if not self.label:
            self.label = self.figure_label or "Untitled Figure"

    def validate(self) -> None:
        """Validate figure data."""
        from pyeuropepmc.models.utils import validate_and_normalize_uri

        # Validate URI if provided
        if self.graphic_uri:
            self.graphic_uri = validate_and_normalize_uri(self.graphic_uri)

        super().validate()

    def normalize(self) -> None:
        """Normalize figure data (trim whitespace, validate URIs)."""
        from pyeuropepmc.models.utils import (
            normalize_string_field,
            validate_and_normalize_uri,
        )

        self.caption = normalize_string_field(self.caption)
        self.figure_label = normalize_string_field(self.figure_label)
        if self.graphic_uri:
            self.graphic_uri = validate_and_normalize_uri(self.graphic_uri)

        super().normalize()
