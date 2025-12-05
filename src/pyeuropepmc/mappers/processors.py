"""
Data processing utilities for PyEuropePMC RDF conversion.

This module provides functions for processing different data sources
into entity data format for RDF conversion.
"""

from typing import Any

from pyeuropepmc.models import (
    AuthorEntity,
    FigureEntity,
    GrantEntity,
    InstitutionEntity,
    JournalEntity,
    PaperEntity,
    ReferenceEntity,
)
from pyeuropepmc.models.section import SectionEntity
from pyeuropepmc.models.table import TableEntity


def _convert_search_author_to_entity(author_dict: dict[str, Any]) -> AuthorEntity:
    """Convert a search result author dictionary to an AuthorEntity."""
    from pyeuropepmc.processing.search_parser import EuropePMCParser

    # Extract affiliation text from the nested structure
    affiliation_text = None
    institutions = []
    affiliation_details = author_dict.get("authorAffiliationDetailsList", {})
    if isinstance(affiliation_details, dict):
        affiliations = affiliation_details.get("authorAffiliation", [])
        if isinstance(affiliations, list) and affiliations:
            # Parse each affiliation into InstitutionEntity objects
            for aff in affiliations:
                affiliation_str = aff.get("affiliation")
                if affiliation_str:
                    institution_entity = EuropePMCParser.parse_affiliation_string(affiliation_str)
                    if institution_entity.display_name:  # Only add if we have a valid institution
                        institutions.append(institution_entity)
            # Use the first affiliation as the primary affiliation text
            if affiliations:
                affiliation_text = affiliations[0].get("affiliation")

    # Extract ORCID if available
    orcid = None
    author_id = author_dict.get("authorId")
    if isinstance(author_id, dict) and author_id.get("type") == "ORCID":
        orcid = author_id.get("value")

    return AuthorEntity(
        full_name=author_dict.get("fullName", ""),
        first_name=author_dict.get("firstName"),
        last_name=author_dict.get("lastName"),
        initials=author_dict.get("initials"),
        affiliation_text=affiliation_text,
        institutions=institutions if institutions else None,
        orcid=orcid,
    )


def _convert_search_author_simple(author_dict: dict[str, Any]) -> AuthorEntity:
    """Convert search author dict to AuthorEntity (simple, no institution parsing)."""
    # Extract ORCID if available
    orcid = None
    author_id = author_dict.get("authorId")
    if isinstance(author_id, dict) and author_id.get("type") == "ORCID":
        orcid = author_id.get("value")

    return AuthorEntity(
        full_name=author_dict.get("fullName", ""),
        first_name=author_dict.get("firstName"),
        last_name=author_dict.get("lastName"),
        initials=author_dict.get("initials"),
        affiliation_text=None,  # Skip affiliation parsing for search results
        institutions=None,  # Skip institution parsing for search results
        orcid=orcid,
    )


def _parse_author_string_to_authors(author_string: str) -> list[str]:
    """Parse an authorString into individual author names."""
    if not author_string:
        return []

    # Split by common separators: commas, semicolons, "and"
    # Handle patterns like "Smith J, Johnson A, Brown K" or "Smith J; Johnson A; Brown K"
    authors = []
    import re

    # Replace "and" with comma for consistent splitting
    cleaned = re.sub(r"\s+and\s+", ", ", author_string, flags=re.IGNORECASE)

    # Split by commas or semicolons
    parts = re.split(r"[;,]", cleaned)

    for part in parts:
        part = part.strip()
        if part:
            # Clean up extra whitespace and remove trailing periods
            part = re.sub(r"\s+", " ", part).strip(".").strip()
            if part:
                authors.append(part)

    return authors


def _extract_mesh_terms(result: dict[str, Any]) -> list[str]:
    """
    Extract MeSH terms from search result (simple string list for backward compatibility).

    For structured MeSH parsing with qualifiers, use _extract_mesh_headings instead.
    """
    mesh_terms = []
    mesh_heading_list = result.get("meshHeadingList", {}).get("meshHeading", [])
    for mesh_heading in mesh_heading_list:
        descriptor_name = mesh_heading.get("descriptorName")
        if descriptor_name:
            mesh_terms.append(descriptor_name)
    return mesh_terms


def _extract_mesh_headings(result: dict[str, Any]) -> list[Any]:
    """
    Extract structured MeSH headings with qualifiers from search result.

    Parameters
    ----------
    result : dict
        Search result dictionary from Europe PMC API

    Returns
    -------
    list[MeSHHeadingEntity]
        List of structured MeSH heading entities with qualifiers
    """
    from pyeuropepmc.models.mesh import MeSHHeadingEntity

    mesh_headings = []
    mesh_heading_list = result.get("meshHeadingList", {}).get("meshHeading", [])

    if isinstance(mesh_heading_list, list):
        for mesh_data in mesh_heading_list:
            try:
                heading = MeSHHeadingEntity.from_dict(mesh_data)
                mesh_headings.append(heading)
            except (KeyError, ValueError):
                # Silently skip malformed headings
                pass

    return mesh_headings


def _extract_authors_from_search_result(result: dict[str, Any]) -> list[AuthorEntity]:
    """Extract and convert authors from search result."""
    author_entities = []
    author_list = result.get("authorList") or result.get("authors", [])

    if isinstance(author_list, dict) and "author" in author_list:
        authors = author_list["author"]
    elif isinstance(author_list, list):
        authors = author_list
    else:
        authors = []

    # If no structured author data, try to parse authorString
    if not authors and result.get("authorString"):
        authors = _parse_author_string_to_authors(result["authorString"])

    for author_dict in authors:
        if isinstance(author_dict, dict):
            author_entity = _convert_search_author_simple(author_dict)
            author_entities.append(author_entity)
        elif isinstance(author_dict, str):
            author_entity = AuthorEntity(full_name=author_dict.strip())
            author_entities.append(author_entity)

    return author_entities


def _create_paper_entity_from_search_result(
    result: dict[str, Any],
    journal_entity: JournalEntity | None,
    author_entities: list[AuthorEntity],
    mesh_terms: list[str],
) -> PaperEntity:
    """Create PaperEntity from search result data."""
    return PaperEntity(
        doi=result.get("doi"),
        pmcid=result.get("pmcid"),
        pmid=result.get("pmid"),
        title=result.get("title"),
        abstract=result.get("abstractText"),
        journal=journal_entity,
        publication_year=result.get("pubYear"),
        authors=[],  # AuthorEntity objects go in related_entities
        keywords=result.get("keywordList", []),
        mesh_terms=mesh_terms,
    )


def _process_single_search_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Process a single search result into entities_data format."""
    entities_data = []

    # Create JournalEntity if journal information is available
    journal_entity = None
    journal_title = result.get("journalTitle")
    if journal_title:
        journal_entity = JournalEntity(title=journal_title)

    # Extract MeSH terms and authors
    mesh_terms = _extract_mesh_terms(result)
    author_entities = _extract_authors_from_search_result(result)

    # Create paper entity
    paper_entity = _create_paper_entity_from_search_result(
        result, journal_entity, author_entities, mesh_terms
    )

    # Add the paper entity
    entities_data.append(
        {
            "entity": paper_entity,
            "related_entities": {
                "authors": author_entities,
                "institutions": [],  # Simplified for search results
            },
        }
    )

    # Add each author entity as a separate main entity
    for author_entity in author_entities:
        entities_data.append(
            {
                "entity": author_entity,
                "related_entities": {
                    "institutions": author_entity.institutions or [],
                },
            }
        )

    return entities_data


def process_search_results(
    search_results: list[dict[str, Any]] | dict[str, Any],
) -> list[dict[str, Any]]:
    """Process search results into entities_data format."""
    entities_data = []

    # Handle both single result and list of results
    results_list = [search_results] if isinstance(search_results, dict) else search_results

    for result in results_list:
        try:
            entities_data.extend(_process_single_search_result(result))
        except Exception as e:
            print(f"Error processing search result: {e}")
            continue

    return entities_data


def process_xml_data(
    xml_data: dict[str, Any], include_content: bool = True
) -> list[dict[str, Any]]:
    """Process XML data into entities_data format."""
    return _extract_entities_from_xml(xml_data, include_content)


def process_enrichment_data(enrichment_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Process enrichment data into entities_data format."""
    return _extract_entities_from_enrichment(enrichment_data)


def _create_journal_entity(journal_info: dict[str, Any] | str) -> JournalEntity | None:
    """Create a JournalEntity from journal information."""
    if isinstance(journal_info, dict):
        # Look for title in multiple possible keys
        title = (
            journal_info.get("title")
            or journal_info.get("name")
            or journal_info.get("journal_title")
            or ""
        )
        return JournalEntity(
            title=title,
            issn=journal_info.get("issn") or journal_info.get("issn_print"),
            essn=journal_info.get("issn_electronic"),
            medline_abbreviation=journal_info.get("nlm_ta"),
            iso_abbreviation=journal_info.get("iso_abbrev"),
            publisher=journal_info.get("publisher"),
            country=journal_info.get("country"),
        )
    elif isinstance(journal_info, str):
        return JournalEntity(title=journal_info)
    return None


def _create_paper_entity(
    paper_data: dict[str, Any], journal_entity: JournalEntity | None
) -> PaperEntity:
    """Create a PaperEntity from paper data."""
    # Extract identifiers if available
    identifiers = paper_data.get("identifiers", {})

    return PaperEntity(
        doi=paper_data.get("doi") or identifiers.get("doi"),
        pmcid=paper_data.get("pmcid") or identifiers.get("pmcid"),
        pmid=paper_data.get("pmid") or identifiers.get("pmid"),
        title=paper_data.get("title"),
        abstract=paper_data.get("abstract"),
        journal=journal_entity,
        publication_year=paper_data.get("publication_year"),
        authors=paper_data.get("authors", []),
        keywords=paper_data.get("keywords", []),
        mesh_terms=paper_data.get("mesh_terms", []),
        grants=_create_grant_entities(paper_data.get("funding")),
        license=paper_data.get("license"),
        publisher=paper_data.get("publisher", {}).get("name"),
        external_ids=identifiers if identifiers else None,
    )


def _extract_author_full_name(author_item: dict[str, Any]) -> str:
    """Extract full name from author item."""
    return (
        author_item.get("full_name")
        or author_item.get("name")
        or f"{author_item.get('given_names', '')} {author_item.get('surname', '')}".strip()
        or ""
    )


def _resolve_affiliation_text(
    author_item: dict[str, Any], affiliations_lookup: dict[str, str] | None
) -> str | None:
    """Resolve affiliation text from author item and lookup."""
    affiliation_text = author_item.get("affiliation")
    affiliation_refs = author_item.get("affiliation_refs", [])

    if affiliation_text or not affiliation_refs:
        return affiliation_text

    if affiliations_lookup:
        resolved = [
            affiliations_lookup[ref] for ref in affiliation_refs if ref in affiliations_lookup
        ]
        return "; ".join(resolved) if resolved else None

    return ", ".join(affiliation_refs)


def _resolve_author_institutions(
    author_item: dict[str, Any],
    affiliations_id_to_entity: dict[str, InstitutionEntity] | None,
) -> list[InstitutionEntity]:
    """Resolve institution entities for author from affiliation refs."""
    if not affiliations_id_to_entity:
        return []

    affiliation_refs = author_item.get("affiliation_refs", [])
    return [
        affiliations_id_to_entity[ref]
        for ref in affiliation_refs
        if ref in affiliations_id_to_entity
    ]


def _create_author_entities(
    authors_data: list[Any],
    affiliations_lookup: dict[str, str] | None = None,
    affiliations_id_to_entity: dict[str, InstitutionEntity] | None = None,
) -> list[AuthorEntity]:
    """Create AuthorEntity objects from author data."""
    author_entities = []
    for author_item in authors_data:
        try:
            if isinstance(author_item, dict):
                full_name = _extract_author_full_name(author_item)
                affiliation_text = _resolve_affiliation_text(author_item, affiliations_lookup)
                author_institutions = _resolve_author_institutions(
                    author_item, affiliations_id_to_entity
                )

                author_entity = AuthorEntity(
                    full_name=full_name,
                    orcid=author_item.get("orcid"),
                    affiliation_text=affiliation_text,
                    institutions=author_institutions if author_institutions else None,
                )
            elif isinstance(author_item, str):
                author_entity = AuthorEntity(full_name=author_item)
            else:
                continue
            author_entities.append(author_entity)
        except Exception as e:
            print(f"Error creating author entity: {e}")
            continue
    return author_entities


def _create_reference_entities(references_data: list[Any]) -> list[ReferenceEntity]:
    """Create ReferenceEntity objects from reference data."""
    reference_entities = []
    for ref_data in references_data:
        try:
            if isinstance(ref_data, dict):
                year = ref_data.get("year")
                reference_entity = ReferenceEntity(
                    title=ref_data.get("title"),
                    journal=ref_data.get("source"),
                    publication_year=int(year) if year is not None else None,
                    volume=ref_data.get("volume"),
                    pages=ref_data.get("pages"),
                    doi=ref_data.get("doi"),
                    pmid=ref_data.get("pmid"),
                    authors=ref_data.get("authors"),
                )
            else:
                # Skip invalid reference data
                continue
            reference_entities.append(reference_entity)
        except Exception as e:
            print(f"Error creating reference entity: {e}")
            continue
    return reference_entities


def _create_institution_entities(affiliations_data: list[Any]) -> list[InstitutionEntity]:
    """Create InstitutionEntity objects from affiliation data with institution IDs."""
    institution_entities = []
    seen_institutions = set()  # Track by unique identifier to avoid duplicates

    for aff in affiliations_data:
        try:
            if not isinstance(aff, dict):
                continue

            institution_ids = aff.get("institution_ids", {})
            institution_name = aff.get("institution") or aff.get("text", "")

            # Skip if no institution identifiers and no name
            if not institution_ids and not institution_name:
                continue

            # Create unique key for deduplication
            unique_key = (
                institution_ids.get("ROR")
                or institution_ids.get("GRID")
                or institution_ids.get("ISNI")
                or institution_name
            )

            if unique_key in seen_institutions:
                continue
            seen_institutions.add(unique_key)

            # Extract country from affiliation data if available
            country = aff.get("country")
            city = aff.get("city")

            # Create institution entity with identifiers
            institution_entity = InstitutionEntity(
                display_name=institution_name,
                ror_id=institution_ids.get("ROR"),
                grid_id=institution_ids.get("GRID"),
                isni=institution_ids.get("ISNI"),
                country=country,
                city=city,
            )
            institution_entities.append(institution_entity)

        except Exception as e:
            print(f"Error creating institution entity: {e}")
            continue

    return institution_entities


def _create_grant_entities(funding_data: list[dict[str, Any]] | None) -> list[GrantEntity] | None:
    """Create GrantEntity objects from funding data."""
    if not funding_data:
        return None

    grant_entities = []
    for funder in funding_data:
        if isinstance(funder, dict):
            try:
                # Handle recipients list (new format with AuthorEntity objects)
                recipients_list = []
                if "recipients" in funder and isinstance(funder["recipients"], list):
                    from ..models.author import AuthorEntity

                    for recip_data in funder["recipients"]:
                        if isinstance(recip_data, dict):
                            full_name = recip_data.get("full_name")
                            if full_name:
                                recipient_entity = AuthorEntity(
                                    full_name=full_name,
                                    first_name=recip_data.get("given_names"),
                                    last_name=recip_data.get("surname"),
                                )
                                recipients_list.append(recipient_entity)

                grant_entity = GrantEntity(
                    fundref_doi=funder.get("fundref_doi"),
                    award_id=funder.get("award_id"),
                    funding_source=funder.get("funding_source"),
                    recipients=recipients_list if recipients_list else None,
                    # Keep deprecated recipient field for backward compatibility
                    recipient=funder.get("recipient_full") or funder.get("recipient_name"),
                )
                grant_entities.append(grant_entity)
            except Exception as e:
                print(f"Error creating grant entity: {e}")
                continue

    return grant_entities if grant_entities else None


def _create_section_entities(sections_data: list[Any]) -> list[SectionEntity]:
    """Create SectionEntity objects from section data."""
    section_entities = []

    for section_data in sections_data:
        try:
            if isinstance(section_data, dict):
                # Extract section title and content
                title = section_data.get("title") or section_data.get("heading", "")
                content = section_data.get("content") or section_data.get("text", "")

                # Skip sections with no content
                if not content:
                    continue

                section_entity = SectionEntity(
                    title=title,
                    content=content,
                )
                section_entities.append(section_entity)
            elif isinstance(section_data, SectionEntity):
                # Already a SectionEntity
                section_entities.append(section_data)
        except Exception as e:
            print(f"Error creating section entity: {e}")
            continue

    return section_entities


def _create_table_entities(tables_data: list[Any]) -> list[TableEntity]:
    """Create TableEntity objects from table data."""
    table_entities = []

    for table_data in tables_data:
        try:
            if isinstance(table_data, dict):
                # Extract table label and caption
                table_label = table_data.get("label") or table_data.get("table_label")
                caption = table_data.get("caption") or table_data.get("title")

                table_entity = TableEntity(
                    table_label=table_label,
                    caption=caption,
                )
                table_entities.append(table_entity)
            elif isinstance(table_data, TableEntity):
                # Already a TableEntity
                table_entities.append(table_data)
        except Exception as e:
            print(f"Error creating table entity: {e}")
            continue

    return table_entities


def _create_figure_entities(figures_data: list[dict[str, Any]]) -> list[FigureEntity]:
    """Create FigureEntity objects from figure data."""
    figure_entities = []
    for figure_data in figures_data:
        try:
            if isinstance(figure_data, dict):
                figure_entity = FigureEntity(
                    figure_label=figure_data.get("label"),
                    caption=figure_data.get("caption"),
                )
                figure_entities.append(figure_entity)
        except Exception as e:
            print(f"Error creating figure entity: {e}")
            continue
    return figure_entities


def _extract_entities_from_xml(
    xml_data: dict[str, Any], include_content: bool
) -> list[dict[str, Any]]:
    """Extract entities from parsed XML data."""
    entities_data = []

    if "paper" in xml_data:
        paper_data = xml_data["paper"]

        # Create JournalEntity if journal information is available
        journal_entity = _create_journal_entity(paper_data.get("journal", {}))

        # Create a proper PaperEntity from the XML data
        paper_entity = _create_paper_entity(paper_data, journal_entity)

        # Convert author dicts/strings to AuthorEntity objects
        # Try multiple possible author keys for flexibility
        authors_data = (
            xml_data.get("authors")
            or xml_data.get("authors_detailed")
            or xml_data.get("authors_simple")
            or []
        )

        # Build affiliations lookup from xml_data if available
        affiliations_lookup = None
        affiliations_id_to_entity: dict[str, InstitutionEntity] = {}
        if xml_data.get("affiliations"):
            affiliations_lookup = {
                aff.get("id"): aff.get("text") or aff.get("institution", "")
                for aff in xml_data.get("affiliations", [])
                if aff.get("id")
            }

            # Create a mapping from affiliation ID to InstitutionEntity
            for aff in xml_data.get("affiliations", []):
                if not isinstance(aff, dict):
                    continue
                aff_id = aff.get("id")
                if not aff_id:
                    continue

                institution_ids = aff.get("institution_ids", {})
                institution_name = aff.get("institution") or aff.get("text", "")

                # Skip if no institution identifiers and no name
                if not institution_ids and not institution_name:
                    continue

                # Create institution entity
                institution_entity = InstitutionEntity(
                    display_name=institution_name,
                    ror_id=institution_ids.get("ROR"),
                    grid_id=institution_ids.get("GRID"),
                    isni=institution_ids.get("ISNI"),
                    country=aff.get("country"),
                    city=aff.get("city"),
                )
                affiliations_id_to_entity[aff_id] = institution_entity

        author_entities = _create_author_entities(
            authors_data, affiliations_lookup, affiliations_id_to_entity
        )

        # Create institution entities from affiliations with IDs
        institution_entities = _create_institution_entities(xml_data.get("affiliations", []))

        # Convert reference dicts to ReferenceEntity objects
        reference_entities = _create_reference_entities(xml_data.get("references", []))

        # Convert section dicts to SectionEntity objects
        section_entities = (
            _create_section_entities(xml_data.get("sections", [])) if include_content else []
        )

        # Convert table dicts to TableEntity objects
        table_entities = (
            _create_table_entities(xml_data.get("tables", [])) if include_content else []
        )

        # Convert figure dicts to FigureEntity objects
        figure_entities = _create_figure_entities(
            xml_data.get("figures", []) if include_content else []
        )

        entities_data.append(
            {
                "entity": paper_entity,
                "related_entities": {
                    "authors": author_entities,
                    "institutions": institution_entities,
                    "sections": section_entities,
                    "tables": table_entities,
                    "figures": figure_entities,
                    "references": reference_entities if include_content else [],
                },
            }
        )

    return entities_data


def _determine_enrichment_data_structure(
    enrichment_data: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[Any]]:
    """Determine the structure of enrichment data and extract paper and authors data."""
    # Check for merged data first (preferred)
    merged_data = enrichment_data.get("merged", {})

    # If no merged data, try semantic_scholar
    if not merged_data:
        semantic_scholar = enrichment_data.get("semantic_scholar", {})
        if semantic_scholar:
            merged_data = semantic_scholar

    # Check for direct paper key (for test compatibility)
    paper_data = enrichment_data.get("paper")

    # Determine what type of data we have
    if paper_data:
        # Direct paper structure (test compatibility)
        return paper_data, enrichment_data.get("authors", [])
    elif merged_data and isinstance(merged_data, dict) and "authors" not in merged_data:
        # Merged data is paper data
        return merged_data, merged_data.get("authors", [])
    else:
        return None, []


def _create_enrichment_paper_entity(
    paper_data: dict[str, Any], enrichment_data: dict[str, Any]
) -> PaperEntity:
    """Create a PaperEntity from enrichment data."""
    # Create JournalEntity if journal information is available
    journal_entity = None
    journal_info = paper_data.get("journal") or paper_data.get("biblio", {})
    if isinstance(journal_info, dict):
        journal_entity = JournalEntity(
            title=journal_info.get("name") or "",
            issn=journal_info.get("issn"),
            publisher=journal_info.get("publisher"),
        )
    elif isinstance(journal_info, str):
        journal_entity = JournalEntity(title=journal_info)

    return PaperEntity(
        doi=paper_data.get("doi") or enrichment_data.get("doi"),
        pmcid=paper_data.get("pmcid"),
        pmid=(paper_data.get("pmid") or paper_data.get("external_ids", {}).get("pmid")),
        title=paper_data.get("title"),
        abstract=paper_data.get("abstract"),
        journal=journal_entity,
        publication_year=paper_data.get("year"),
        authors=[],  # Will be populated below
        keywords=paper_data.get("keywords", []),
        mesh_terms=paper_data.get("mesh_terms", []),
        topics=paper_data.get("topics", []),  # OpenAlex topics
    )


def _create_enrichment_author_entities(authors_data: list[Any]) -> list[AuthorEntity]:
    """Create AuthorEntity objects from enrichment author data."""
    author_entities = []
    for author_dict in authors_data:
        try:
            if isinstance(author_dict, dict):
                full_name = author_dict.get("name") or author_dict.get("full_name") or ""
                author_entity = AuthorEntity(
                    full_name=full_name,
                    orcid=author_dict.get("orcid"),
                    affiliation_text=author_dict.get("affiliation"),
                )
            elif isinstance(author_dict, str):
                author_entity = AuthorEntity(
                    full_name=author_dict,
                    orcid=None,
                    affiliation_text=None,
                )
            else:
                continue
            author_entities.append(author_entity)
        except Exception as e:
            print(f"Error creating author entity: {e}")
            continue
    return author_entities


def _extract_entities_from_enrichment(enrichment_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract entities from enrichment data."""
    entities_data = []

    # Determine data structure
    actual_paper_data, authors_data = _determine_enrichment_data_structure(enrichment_data)

    # If we have paper data, process it
    if actual_paper_data:
        paper_entity = _create_enrichment_paper_entity(actual_paper_data, enrichment_data)
        author_entities = _create_enrichment_author_entities(authors_data)

        entities_data.append(
            {
                "entity": paper_entity,
                "related_entities": {
                    "authors": author_entities,
                },
            }
        )

    # If enrichment data contains author-level information directly
    elif (
        "authors" in enrichment_data
        and enrichment_data["authors"] is not None
        and not actual_paper_data
    ):
        # Create entities for enriched authors
        for author_data in enrichment_data["authors"]:
            try:
                author_entity = AuthorEntity(
                    full_name=author_data.get("full_name"),
                    orcid=author_data.get("orcid"),
                    affiliation_text=author_data.get("affiliation"),
                )
                entities_data.append(
                    {
                        "entity": author_entity,
                        "related_entities": {},
                    }
                )
            except Exception as e:
                print(f"Error creating author entity from enrichment: {e}")
                continue

    return entities_data
