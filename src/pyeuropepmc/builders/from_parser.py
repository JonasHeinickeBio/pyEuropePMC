"""
Builder functions to convert FullTextXMLParser outputs to entity models.
"""

from typing import TYPE_CHECKING, Any

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


def _build_author_entity(
    author_data: str | dict[str, Any], affiliations: list[dict[str, Any]]
) -> AuthorEntity:
    """Build a single AuthorEntity from author data and affiliations."""
    from pyeuropepmc.models.institution import InstitutionEntity

    if isinstance(author_data, str):
        # Backward compatibility: handle string names
        return AuthorEntity(full_name=author_data)

    # New format: detailed author data
    full_name = author_data.get("full_name", "")
    if not full_name:
        raise ValueError("Author data must contain full_name")

    # Get affiliation text from referenced affiliations
    affiliation_text = None
    institution_entities = []
    affiliation_refs = author_data.get("affiliation_refs", [])

    if affiliation_refs:
        # Create a lookup dict for affiliations by ID
        aff_lookup = {aff["id"]: aff for aff in affiliations if aff.get("id")}

        # Combine text from all referenced affiliations
        aff_texts = []
        for ref_id in affiliation_refs:
            if ref_id in aff_lookup:
                aff_data = aff_lookup[ref_id]
                # Prefer clean institution text, fallback to full text
                text = aff_data.get("institution_text") or aff_data.get("text") or ""
                if text:
                    aff_texts.append(text.strip())

                # Create InstitutionEntity from affiliation data
                institution = InstitutionEntity(
                    display_name=aff_data.get("institution")
                    or aff_data.get("institution_text")
                    or aff_data.get("text", ""),
                    city=aff_data.get("city"),
                    country=aff_data.get("country"),
                    source_uri=f"urn:pmc-affiliation:{ref_id}",
                )
                institution_entities.append(institution)

        if aff_texts:
            affiliation_text = "; ".join(aff_texts)

    return AuthorEntity(
        full_name=full_name,
        first_name=author_data.get("given_names", ""),
        last_name=author_data.get("surname", ""),
        orcid=author_data.get("orcid"),
        affiliation_text=affiliation_text,
        institutions=institution_entities if institution_entities else None,
    )


def build_paper_entities(
    parser: "FullTextXMLParser",
    search_data: dict[str, Any] | None = None,
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

    # Merge search API data if provided
    if search_data:
        search_paper_data = {
            "pmid": search_data.get("pmid"),
            "cited_by_count": search_data.get("citedByCount"),
            "pub_type": search_data.get("pubType"),
            "issn": search_data.get("journalIssn"),  # Map journalIssn to issn field
            "page_info": search_data.get("pageInfo"),
            "is_oa": search_data.get("isOpenAccess") == "Y",
            "in_epmc": search_data.get("inEPMC") == "Y",
            "in_pmc": search_data.get("inPMC") == "Y",
            "has_pdf": search_data.get("hasPDF") == "Y",
            "has_supplementary": search_data.get("hasSuppl") == "Y",
            "has_references": search_data.get("hasReferences") == "Y",
            "has_text_mined_terms": search_data.get("hasTextMinedTerms") == "Y",
            "has_db_cross_references": (
                search_data.get("hasDbCrossReferences") == "N"
            ),  # API uses "N" for no
            "has_labs_links": search_data.get("hasLabsLinks") == "Y",
            "has_tm_accession_numbers": search_data.get("hasTMAccessionNumbers") == "Y",
            "first_index_date": search_data.get("firstIndexDate"),
            "first_publication_date": search_data.get("firstPublicationDate"),
            "publication_year": int(search_data["pubYear"]) if "pubYear" in search_data else None,
        }
        paper.merge_from_source(search_paper_data, "europe_pmc_search")

    # Build AuthorEntity list
    authors = []
    author_details = parser.extract_authors_detailed()
    affiliations = parser.extract_affiliations()

    for author_data in author_details:
        try:
            author = _build_author_entity(author_data, affiliations)
            authors.append(author)
        except ValueError:
            # Skip invalid author data
            continue

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
        year = ref_data.get("year")
        reference = ReferenceEntity(
            title=ref_data.get("title"),
            journal=ref_data.get("source"),
            publication_year=int(year) if year is not None else None,
            volume=ref_data.get("volume"),
            pages=ref_data.get("pages"),
            doi=ref_data.get("doi"),
            pmid=ref_data.get("pmid"),
            authors=ref_data.get("authors"),
        )
        references.append(reference)

    return paper, authors, sections, tables, figures, references
