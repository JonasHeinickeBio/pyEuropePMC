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
        URI of the figure graphic/image file. May be a relative reference such
        as the file name in JATS ``<graphic xlink:href="pone.0012345.g001"/>``;
        an absolute URI must be well formed.

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
        # Validate URI if provided
        if self.graphic_uri:
            self.graphic_uri = _normalize_graphic_uri(self.graphic_uri)

        super().validate()

    def normalize(self) -> None:
        """Normalize figure data (trim whitespace, validate URIs)."""
        from pyeuropepmc.models.utils import normalize_string_field

        self.caption = normalize_string_field(self.caption)
        self.figure_label = normalize_string_field(self.figure_label)
        if self.graphic_uri:
            self.graphic_uri = _normalize_graphic_uri(self.graphic_uri)

        super().normalize()


def _normalize_graphic_uri(value: str) -> str | None:
    """Trim a graphic reference; check it as a URI only when it is absolute.

    JATS points at figure files with relative references (the ``xlink:href``
    of ``<graphic>``), which have no scheme and are left as they are.
    """
    from urllib.parse import urlparse

    from pyeuropepmc.models.utils import normalize_string_field, validate_and_normalize_uri

    trimmed = normalize_string_field(value)
    if trimmed and urlparse(trimmed).scheme:
        return validate_and_normalize_uri(trimmed)
    return trimmed
