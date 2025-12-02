"""
Element patterns configuration for XML parsing.

This module contains the ElementPatterns dataclass that defines flexible patterns
for extracting various elements from different XML schema variations (JATS, NLM, custom).
"""

from dataclasses import dataclass, field


@dataclass
class ElementPatterns:
    """
    Configuration for XML element patterns with fallbacks.

    This class defines flexible patterns for extracting various elements from
    different XML schema variations (JATS, NLM, custom).

    Examples
    --------
    >>> # Use default patterns
    >>> config = ElementPatterns()
    >>>
    >>> # Customize citation patterns
    >>> config = ElementPatterns(
    ...     citation_types=["element-citation", "mixed-citation", "nlm-citation"]
    ... )
    """

    # Bibliographic citation patterns (ordered by preference)
    citation_types: list[str] = field(
        default_factory=lambda: ["element-citation", "mixed-citation", "nlm-citation", "citation"]
    )

    # Author element patterns (XPath to author containers)
    author_element_patterns: list[str] = field(
        default_factory=lambda: [
            ".//contrib[@contrib-type='author']",  # Full contrib element
            ".//contrib[@contrib-type='author']/name",  # Name element (fallback)
            ".//author-group/author",
            ".//author",
            ".//name",
        ]
    )

    # Author name field patterns with fallbacks
    author_field_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "surname": [".//surname", ".//family", ".//last-name", ".//lname"],
            "given_names": [
                ".//given-names",
                ".//given-name",
                ".//given",
                ".//forename",
                ".//first-name",
                ".//fname",
            ],
            "suffix": [".//suffix"],
            "prefix": [".//prefix"],
            "role": [".//role"],
        }
    )

    # Journal metadata patterns
    journal_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "title": [".//journal-title", ".//source", ".//journal"],
            "issn": [".//issn"],
            "publisher": [".//publisher-name", ".//publisher"],
            "publisher_loc": [".//publisher-loc", ".//publisher-location"],
            "volume": [".//volume", ".//vol"],
            "issue": [".//issue"],
        }
    )

    # Article metadata patterns
    article_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "title": [".//article-title", ".//title"],
            "abstract": [".//abstract"],
            "keywords": [".//kwd", ".//keyword"],
            "doi": [".//article-id[@pub-id-type='doi']", ".//doi"],
            "pmid": [".//article-id[@pub-id-type='pmid']", ".//pmid"],
            "pmcid": [".//article-id[@pub-id-type='pmcid']", ".//pmcid"],
        }
    )

    # Table structure patterns
    table_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "wrapper": ["table-wrap", "table-wrapper", "tbl-wrap"],
            "table": ["table"],
            "caption": ["caption", "title", "table-title"],
            "label": ["label"],
            "header": ["thead", "th"],
            "body": ["tbody"],
            "row": ["tr"],
            "cell": ["td", "th"],
        }
    )

    # Reference/citation field patterns
    reference_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "title": [".//article-title", ".//source", ".//title"],
            "source": [".//source", ".//journal", ".//publication"],
            "year": [".//year", ".//date"],
            "month": [".//month"],
            "day": [".//day"],
            "volume": [".//volume", ".//vol"],
            "issue": [".//issue"],
            "fpage": [".//fpage", ".//first-page"],
            "lpage": [".//lpage", ".//last-page"],
            "doi": [
                ".//pub-id[@pub-id-type='doi']",
                ".//doi",
                ".//ext-link[@ext-link-type='doi']",
            ],
            "pmid": [
                ".//pub-id[@pub-id-type='pmid']",
                ".//pmid",
            ],
            "person_group": [".//person-group"],
            "etal": [".//etal"],
        }
    )

    # Inline element patterns (elements to extract or filter out)
    inline_element_patterns: list[str] = field(
        default_factory=lambda: [".//sup", ".//sub", ".//italic", ".//bold", ".//underline"]
    )

    # Cross-reference patterns (for linking to figures, tables, citations)
    xref_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "bibr": [".//xref[@ref-type='bibr']"],  # Bibliography references
            "fig": [".//xref[@ref-type='fig']"],  # Figure references
            "table": [".//xref[@ref-type='table']"],  # Table references
            "supplementary": [".//xref[@ref-type='supplementary-material']"],
        }
    )

    # Media and supplementary material patterns
    media_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "supplementary": [".//supplementary-material", ".//media"],
            "graphic": [".//graphic"],
            "inline_graphic": [".//inline-graphic"],
        }
    )

    # Object identifier patterns
    object_id_patterns: list[str] = field(
        default_factory=lambda: [".//object-id", ".//article-id"]
    )
