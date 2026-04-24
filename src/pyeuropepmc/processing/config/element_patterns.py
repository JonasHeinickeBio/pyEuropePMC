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
    ...     citation_types={"types": ["element-citation", "mixed-citation", "nlm-citation"]}
    ... )
    """

    # Bibliographic citation patterns (ordered by preference)
    citation_types: dict[str, list[str]] = field(
        default_factory=lambda: {
            "types": ["element-citation", "mixed-citation", "nlm-citation", "citation"]
        }
    )

    # Author element patterns (XPath to author containers)
    author_element_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "patterns": [
                ".//contrib[@contrib-type='author']",  # Full contrib element
                ".//contrib[@contrib-type='author']/name",  # Name element (fallback)
                ".//author-group/author",
                ".//author",
                ".//name",
            ]
        }
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
            "volume": [".//volume", ".//vol"],
            "issue": [".//issue"],
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
            "pmcid": [
                ".//pub-id[@pub-id-type='pmc']",
                ".//pub-id[@pub-id-type='pmcid']",
                ".//pmcid",
            ],
            "person_group": [".//person-group"],
            "etal": [".//etal"],
        }
    )

    # Inline element patterns (elements to extract or filter out)
    inline_element_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "patterns": [".//sup", ".//sub", ".//italic", ".//bold", ".//underline"]
        }
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
    object_id_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {"patterns": [".//object-id", ".//article-id"]}
    )

    # Mathematical notation patterns (MathML support)
    math_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "math": [".//math", ".//mml:math"],
            "mfenced": [".//mfenced", ".//mml:mfenced"],
            "mfrac": [".//mfrac", ".//mml:mfrac"],
            "mi": [".//mi", ".//mml:mi"],
            "mn": [".//mn", ".//mml:mn"],
            "mo": [".//mo", ".//mml:mo"],
            "mover": [".//mover", ".//mml:mover"],
            "mrow": [".//mrow", ".//mml:mrow"],
            "mspace": [".//mspace", ".//mml:mspace"],
            "msqrt": [".//msqrt", ".//mml:msqrt"],
            "mstyle": [".//mstyle", ".//mml:mstyle"],
            "msub": [".//msub", ".//mml:msub"],
            "msubsup": [".//msubsup", ".//mml:msubsup"],
            "msup": [".//msup", ".//mml:msup"],
            "mtable": [".//mtable", ".//mml:mtable"],
            "mtd": [".//mtd", ".//mml:mtd"],
            "mtext": [".//mtext", ".//mml:mtext"],
            "mtr": [".//mtr", ".//mml:mtr"],
            "munder": [".//munder", ".//mml:munder"],
            "munderover": [".//munderover", ".//mml:munderover"],
        }
    )

    # Formatting and layout patterns
    formatting_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "break": [".//break"],
            "hr": [".//hr"],
            "strike": [".//strike"],
            "string_date": [".//string-date"],
            "string_name": [".//string-name"],
            "styled_content": [".//styled-content"],
            "tex_math": [".//tex-math"],
            "word_count": [".//word-count"],
            "equation_count": [".//equation-count"],
            "figure_count": [".//figure-count"],
            "table_count": [".//table-count"],
        }
    )

    # Extended metadata patterns
    extended_metadata_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "alt_text": [".//alt-text"],
            "alt_title": [".//alt-title"],
            "anonymous": [".//anonymous"],
            "article_version": [".//article-version"],
            "conf_date": [".//conf-date"],
            "conf_loc": [".//conf-loc"],
            "conf_name": [".//conf-name"],
            "conf_sponsor": [".//conf-sponsor"],
            "edition": [".//edition"],
            "elocation_id": [".//elocation-id"],
            "event": [".//event"],
            "event_desc": [".//event-desc"],
            "free_to_read": [".//free_to_read"],
            "issue_id": [".//issue-id"],
            "issue_title": [".//issue-title"],
            "journal_id": [".//journal-id"],
            "named_content": [".//named-content"],
            "on_behalf_of": [".//on-behalf-of"],
            "part_title": [".//part-title"],
            "restricted_by": [".//restricted-by"],
            "season": [".//season"],
            "series": [".//series"],
            "subj_group": [".//subj-group"],
            "subject": [".//subject"],
            "subtitle": [".//subtitle"],
            "version": [".//version"],
        }
    )

    # Content structure patterns
    content_structure_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "address": [".//address"],
            "alternatives": [".//alternatives"],
            "article": [".//article"],
            "author_notes": [".//author-notes"],
            "back": [".//back"],
            "body": [".//body"],
            "citation_alternatives": [".//citation-alternatives"],
            "col": [".//col"],
            "colgroup": [".//colgroup"],
            "collab": [".//collab"],
            "comment": [".//comment"],
            "compound_subject": [".//compound-subject"],
            "compound_subject_part": [".//compound-subject-part"],
            "custom_meta": [".//custom-meta"],
            "def": [".//def"],
            "disp_formula": [".//disp-formula"],
            "disp_quote": [".//disp-quote"],
            "fig": [".//fig"],
            "fig_group": [".//fig-group"],
            "floats_group": [".//floats-group"],
            "glossary": [".//glossary"],
            "inline_supplementary_material": [".//inline-supplementary-material"],
            "label": [".//label"],
            "permissions": [".//permissions"],
            "processing_meta": [".//processing-meta"],
            "related_article": [".//related-article"],
            "related_object": [".//related-object"],
            "role": [".//role"],
            "sc": [".//sc"],
            "statement": [".//statement"],
            "support_group": [".//support-group"],
        }
    )

    # Award and grant patterns
    award_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "award_group": [".//award-group"],
            "award_id": [".//award-id"],
            "principal_award_recipient": [".//principal-award-recipient"],
        }
    )

    # Appendix patterns
    appendix_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "app": [".//app"],
            "article_categories": [".//article-categories"],
        }
    )
