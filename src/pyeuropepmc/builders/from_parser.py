"""
Builder functions to convert FullTextXMLParser outputs to entity models.
"""

from typing import TYPE_CHECKING

from pyeuropepmc.models import (
    AuthorEntity,
    FigureEntity,
    PaperEntity,
    ReferenceEntity,
    SectionEntity,
    TableEntity,
    TableRowEntity,
)

if TYPE_CHECKING:
    from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

__all__ = ["build_paper_entities"]


def build_paper_entities(
    parser: "FullTextXMLParser",
) -> tuple[
    PaperEntity,
    list[AuthorEntity],
    list[SectionEntity],
    list[TableEntity],
    list[FigureEntity],
    list[ReferenceEntity],
]:
    """
    Build entity models from a FullTextXMLParser instance.

    This function extracts data from the parser and constructs typed entity models
    for the paper, authors, sections, tables, and references.

    Parameters
    ----------
    parser : FullTextXMLParser
        Parser instance with loaded XML content

    Returns
    -------
    tuple
        A tuple containing:
        - PaperEntity: The main paper entity
        - list[AuthorEntity]: List of author entities
        - list[SectionEntity]: List of section entities
        - list[TableEntity]: List of table entities
        - list[ReferenceEntity]: List of reference entities

    Examples
    --------
    >>> from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
    >>> parser = FullTextXMLParser(xml_content)
    >>> paper, authors, sections, tables, refs = build_paper_entities(parser)
    >>> print(paper.title)
    Sample Article Title
    """
    # Extract metadata
    meta = parser.extract_metadata()

    # Build PaperEntity
    paper = PaperEntity(
        id=meta.get("pmcid") or meta.get("doi"),
        label=meta.get("title"),
        source_uri=f"urn:pmc:{meta.get('pmcid', '')}" if meta.get("pmcid") else None,
        pmcid=meta.get("pmcid"),
        doi=meta.get("doi"),
        title=meta.get("title"),
        journal=meta.get("journal"),
        volume=meta.get("volume"),
        issue=meta.get("issue"),
        pages=meta.get("pages"),
        pub_date=meta.get("pub_date"),
        keywords=meta.get("keywords") or [],
    )

    # Build AuthorEntity list
    authors = []
    for author_name in meta.get("authors") or []:
        author = AuthorEntity(full_name=author_name)
        authors.append(author)

    # Build SectionEntity list
    sections = []
    for sec_data in parser.get_full_text_sections():
        section = SectionEntity(
            label=sec_data.get("title"),
            title=sec_data.get("title"),
            content=sec_data.get("content"),
        )
        sections.append(section)

    # Build TableEntity list
    tables = []
    for table_data in parser.extract_tables():
        # Convert raw row data to TableRowEntity instances
        rows = [TableRowEntity(cells=row_data) for row_data in (table_data.get("rows") or [])]
        table = TableEntity(
            label=table_data.get("label"),
            caption=table_data.get("caption"),
            table_label=table_data.get("label"),
            headers=table_data.get("headers") or [],
            rows=rows,
        )
        tables.append(table)

    # Build FigureEntity list (placeholder - figure extraction not yet implemented)
    figures: list[FigureEntity] = []
    # TODO: Implement figure extraction in parser and add here
    # for figure_data in parser.extract_figures():
    #     figure = FigureEntity(
    #         label=figure_data.get("label"),
    #         caption=figure_data.get("caption"),
    #         figure_label=figure_data.get("label"),
    #         graphic_uri=figure_data.get("graphic_uri"),
    #     )
    #     figures.append(figure)

    # Build ReferenceEntity list
    references = []
    for ref_data in parser.extract_references():
        reference = ReferenceEntity(
            title=ref_data.get("title"),
            source=ref_data.get("source"),
            year=ref_data.get("year"),
            volume=ref_data.get("volume"),
            pages=ref_data.get("pages"),
            doi=ref_data.get("doi"),
            authors=ref_data.get("authors"),
        )
        references.append(reference)

    return paper, authors, sections, tables, figures, references
