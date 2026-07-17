"""
Document schema configuration for fulltext parser.

This module contains the DocumentSchema dataclass that stores information about
the XML document structure to enable adaptive parsing strategies.

"""

from dataclasses import dataclass, field


@dataclass
class DocumentSchema:
    """
    Detected document schema information.

    This class stores information about the XML document structure to enable
    adaptive parsing strategies.

    Attributes
    ----------
    has_tables : bool
        Whether document contains tables
    has_figures : bool
        Whether document contains figures
    has_supplementary : bool
        Whether document contains supplementary materials
    citation_types : list[str]
        Types of citation elements found
    table_structure : str
        Table structure type: "jats", "html", "cals"
    has_acknowledgments : bool
        Whether document has acknowledgments section
    has_funding : bool
        Whether document has funding information
    """

    has_tables: bool = False
    has_figures: bool = False
    has_supplementary: bool = False
    has_acknowledgments: bool = False
    has_funding: bool = False
    citation_types: list[str] = field(default_factory=list)
    table_structure: str = "jats"  # "jats", "html", "cals"
