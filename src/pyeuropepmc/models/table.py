"""
Table entity models for representing tables and their rows.
"""

from dataclasses import dataclass, field

from pyeuropepmc.models.base import BaseEntity

__all__ = ["TableEntity", "TableRowEntity"]


@dataclass
class TableRowEntity(BaseEntity):
    """
    Entity representing a table row.

    Attributes
    ----------
    cells : list[str]
        Cell values for this row

    Examples
    --------
    >>> row = TableRowEntity(cells=["Value 1", "Value 2"])
    >>> row.validate()
    """

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
            If cells are empty
        """
        if not self.cells:
            raise ValueError("TableRowEntity must have cells")

    def normalize(self) -> None:
        """Normalize table row data (trim whitespace)."""
        self.cells = [c.strip() for c in self.cells if c]


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
    headers : list[str]
        Column headers for the table
    rows : list[TableRowEntity]
        Table rows as structured entities

    Examples
    --------
    >>> table = TableEntity(
    ...     table_label="Table 1",
    ...     caption="Sample data table",
    ...     headers=["Name", "Age", "City"],
    ...     rows=[
    ...         TableRowEntity(cells=["Alice", "25", "NYC"]),
    ...         TableRowEntity(cells=["Bob", "30", "LA"])
    ...     ]
    ... )
    >>> table.validate()
    """

    caption: str | None = None
    table_label: str | None = None
    headers: list[str] = field(default_factory=list)
    rows: list[TableRowEntity] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:Table"]
        if not self.label:
            self.label = self.table_label or "Untitled Table"

    def validate(self) -> None:
        """Validate table data."""
        # Tables can exist with minimal information
        # But if rows exist, they should be consistent
        if self.rows:
            row_lengths = [len(row.cells) for row in self.rows]
            if len(set(row_lengths)) > 1:
                raise ValueError("All table rows must have the same number of columns")
            if self.headers and len(self.headers) != row_lengths[0]:
                raise ValueError("Number of headers must match number of columns in rows")

    def normalize(self) -> None:
        """Normalize table data (trim whitespace)."""
        if self.caption:
            self.caption = self.caption.strip()
        if self.table_label:
            self.table_label = self.table_label.strip()
        # Normalize headers
        self.headers = [h.strip() for h in self.headers if h]
        # Normalize rows
        for row in self.rows:
            row.normalize()
