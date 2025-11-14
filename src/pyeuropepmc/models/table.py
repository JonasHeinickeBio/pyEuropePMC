"""
Table entity models for representing tables and their rows.
"""

from dataclasses import dataclass, field

from pyeuropepmc.models.base import BaseEntity

__all__ = ["TableEntity", "TableRowEntity"]


@dataclass
class TableEntity(BaseEntity):
    """
    Entity representing a table with BIBO alignment.

    Attributes
    ----------
    caption : Optional[str]
        Table caption/description
    table_label : Optional[str]
        Table label (e.g., "Table 1")

    Examples
    --------
    >>> table = TableEntity(
    ...     table_label="Table 1",
    ...     caption="Sample data table"
    ... )
    >>> table.validate()
    """

    caption: str | None = None
    table_label: str | None = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:Table"]
        if not self.label:
            self.label = self.table_label or "Untitled Table"

    def validate(self) -> None:
        """Validate table data."""
        # Tables can exist with minimal information
        pass

    def normalize(self) -> None:
        """Normalize table data (trim whitespace)."""
        if self.caption:
            self.caption = self.caption.strip()
        if self.table_label:
            self.table_label = self.table_label.strip()


@dataclass
class TableRowEntity(BaseEntity):
    """
    Entity representing a table row.

    Attributes
    ----------
    headers : list[str]
        Column headers for this row
    cells : list[str]
        Cell values for this row

    Examples
    --------
    >>> row = TableRowEntity(
    ...     headers=["Column 1", "Column 2"],
    ...     cells=["Value 1", "Value 2"]
    ... )
    >>> row.validate()
    """

    headers: list[str] = field(default_factory=list)
    cells: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:Row"]
        if not self.label:
            self.label = f"Row with {len(self.cells)} cells"

    def validate(self) -> None:
        """
        Validate table row data.

        Raises
        ------
        ValueError
            If both headers and cells are empty
        """
        if not self.headers and not self.cells:
            raise ValueError("TableRowEntity must have headers or cells")

    def normalize(self) -> None:
        """Normalize table row data (trim whitespace)."""
        self.headers = [h.strip() for h in self.headers if h]
        self.cells = [c.strip() for c in self.cells if c]
