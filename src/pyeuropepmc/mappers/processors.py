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
    JournalEntity,
    Organization,
    PaperEntity,
    ReferenceEntity,
    SectionEntity,
    SectionType,
    TableEntity,
)


# Helper functions for data formatting
def _format_pmcid(pmcid: str | None) -> str | None:
    """Format PMCID to ensure it has PMC prefix."""
    if not pmcid:
        return None
    pmcid_str = str(pmcid).strip()
    if pmcid_str.startswith("PMC"):
        return pmcid_str
    return f"PMC{pmcid_str}"


def _format_external_ids(external_ids: dict | None) -> str | None:
    """Format external IDs dict as JSON string."""
    if not external_ids:
        return None
    import json

    return json.dumps(external_ids)


def _format_license(license_data: dict | str | None) -> str | None:
    """Format license data as string."""
    if not license_data:
        return None
    if isinstance(license_data, str):
        return license_data
    if isinstance(license_data, dict):
        # Extract license text if available
        license_text = license_data.get("text") or license_data.get("license")
        if license_text:
            return str(license_text)
        # Fallback to JSON representation
        import json

        return json.dumps(license_data)
    return str(license_data)


def _format_orcid(orcid: str | None) -> str | None:
    """Format ORCID to extract ID from URL if needed."""
    if not orcid:
        return None
    orcid_str = str(orcid).strip()
    # Extract ORCID ID from URL
    if orcid_str.startswith("https://orcid.org/"):
        return orcid_str.replace("https://orcid.org/", "")
    elif orcid_str.startswith("http://orcid.org/"):
        return orcid_str.replace("http://orcid.org/", "")
    return orcid_str


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
            # Parse each affiliation into Organization objects
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
        orcid = _format_orcid(author_id.get("value"))

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
        orcid = _format_orcid(author_id.get("value"))

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
    # TODO: Implement MeSHHeadingEntity class in schema
    # from pyeuropepmc.models.mesh import MeSHHeadingEntity

    mesh_headings = []
    mesh_heading_list = result.get("meshHeadingList", {}).get("meshHeading", [])

    if isinstance(mesh_heading_list, list):
        for mesh_data in mesh_heading_list:
            try:
                # heading = MeSHHeadingEntity.from_dict(mesh_data)
                # mesh_headings.append(heading)
                # For now, just return the raw data
                mesh_headings.append(mesh_data)
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
            # Check if the author entity has meaningful name information
            # If not, and we have an authorString, use that as fallback
            if not author_entity.full_name and result.get("authorString"):
                # For collective authorship, use the authorString as the name
                author_entity.full_name = result["authorString"].strip()
            author_entities.append(author_entity)
        elif isinstance(author_dict, str):
            author_entity = AuthorEntity(full_name=author_dict.strip())
            author_entities.append(author_entity)

    return author_entities


def _extract_keywords_from_search_result(result: dict[str, Any]) -> list[str]:
    """Extract keywords from search result keywordList structure."""
    keyword_list = result.get("keywordList", {})
    if isinstance(keyword_list, dict):
        keywords = keyword_list.get("keyword", [])
    elif isinstance(keyword_list, list):
        keywords = keyword_list
    else:
        keywords = []

    # Ensure we return a list of strings
    if isinstance(keywords, list):
        return [str(k) for k in keywords if k]
    elif isinstance(keywords, str):
        return [keywords]
    else:
        return []


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
        keywords=_extract_keywords_from_search_result(result),
        mesh_terms=mesh_terms,
    )


def _process_single_search_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Process a single search result into entities_data format."""
    entities_data = []

    # Create JournalEntity if journal information is available
    journal_entity = None
    journal_title = result.get("journalTitle")
    if not journal_title and result.get("journalInfo"):
        journal_info = result["journalInfo"]
        if isinstance(journal_info, dict):
            journal_title = journal_info.get("title") or journal_info.get("journalTitle")
    if journal_title:
        journal_entity = JournalEntity(title=journal_title)

    # Extract MeSH terms and authors
    mesh_terms = _extract_mesh_terms(result)
    author_entities = _extract_authors_from_search_result(result)

    # Create Organization from affiliation if available
    if result.get("affiliation"):
        institution = Organization(display_name=result["affiliation"])
        for author in author_entities:
            if author.institutions is None:
                author.institutions = []
            author.institutions.append(institution)

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


def _pad_partial_date(date_str: str | None) -> str | None:
    """Pad partial dates to full dates for parsing."""
    if not date_str:
        return None
    parts = date_str.split("-")
    if len(parts) == 1:  # year
        return f"{parts[0]}-01-01"
    elif len(parts) == 2:  # year-month
        return f"{parts[0]}-{parts[1]}-01"
    else:
        return date_str


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
        pmcid=_format_pmcid(paper_data.get("pmcid") or identifiers.get("pmcid")),
        pmid=paper_data.get("pmid") or identifiers.get("pmid"),
        title=paper_data.get("title"),
        abstract=paper_data.get("abstract"),
        journal=journal_entity,
        publication_year=paper_data.get("publication_year"),
        pub_date=_pad_partial_date(paper_data.get("pub_date")),
        authors=[],  # AuthorEntity objects go in related_entities
        keywords=paper_data.get("keywords", []),
        mesh_terms=paper_data.get("mesh_terms", []),
        grants=_create_grant_entities(paper_data.get("funding")),
        license=_format_license(paper_data.get("license")),
        publisher=paper_data.get("publisher", {}).get("name"),
        pii=identifiers.get("pii"),
        publisher_id=identifiers.get("publisher-id"),
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
    affiliations_id_to_entity: dict[str, Organization] | None,
) -> list[Organization]:
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
    affiliations_id_to_entity: dict[str, Organization] | None = None,
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
                    orcid=_format_orcid(author_item.get("orcid")),
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
                # Handle year ranges by taking the first year
                if year and isinstance(year, str):
                    # Extract first year from ranges like "2015-2025"
                    year = year.split("-")[0].strip()
                    try:
                        year = int(year)
                    except ValueError:
                        year = None
                elif year and isinstance(year, int):
                    pass  # Already an int
                else:
                    year = None

                # Handle authors - should be author_list (string) not authors (list)
                authors_data = ref_data.get("authors")
                if isinstance(authors_data, str):
                    author_list = authors_data
                    authors = None  # Don't set authors field for references
                else:
                    author_list = None
                    authors = None

                # Handle journal - should be None for references since we don't have full JournalEntity
                journal_data = ref_data.get("source") or ref_data.get("journal")
                if isinstance(journal_data, str):
                    # For now, store as title in a minimal JournalEntity or just set to None
                    journal = None  # References don't typically have full journal entities
                else:
                    journal = None

                reference_entity = ReferenceEntity(
                    title=ref_data.get("title"),
                    journal=journal,
                    publication_year=year,
                    volume=ref_data.get("volume"),
                    pages=ref_data.get("pages"),
                    doi=ref_data.get("doi"),
                    pmid=ref_data.get("pmid"),
                    author_list=author_list,  # Use author_list for the string
                )
            else:
                # Skip invalid reference data
                continue
            reference_entities.append(reference_entity)
        except Exception as e:
            print(f"Error creating reference entity: {e}")
            continue
    return reference_entities


def _create_institution_entities(affiliations_data: list[Any]) -> list[Organization]:
    """Create Organization objects from affiliation data with institution IDs."""
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

            # Create unique key for deduplication - include name and location to split departments
            unique_key = (
                institution_ids.get("ROR"),
                institution_ids.get("GRID"),
                institution_ids.get("ISNI"),
                institution_name,
                aff.get("city"),
                aff.get("country"),
            )

            if unique_key in seen_institutions:
                continue
            seen_institutions.add(unique_key)

            # Extract country from affiliation data if available
            country = aff.get("country")
            city = aff.get("city")

            # Create institution entity with identifiers
            institution_entity = Organization(
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

    # Mapping for section types that don't match the enum
    section_type_mapping = {
        "section": "other",
        "coi-statement": "acknowledgments",  # Conflict of interest often goes in acknowledgments
        "author_notes": "acknowledgments",  # Author notes often go in acknowledgments
        "competing-interests": "acknowledgments",
        "funding": "acknowledgments",
        "data-availability": "other",
        "ethics-statement": "other",
        "patient-consent": "other",
        "author-contributions": "acknowledgments",
        "disclosure": "acknowledgments",
    }

    for section_data in sections_data:
        try:
            if isinstance(section_data, dict):
                # Extract section title and content
                title = section_data.get("title") or section_data.get("heading", "")
                content = section_data.get("content") or section_data.get("text", "")

                # Skip sections with no content
                if not content:
                    continue

                # Map section type to valid enum value
                raw_section_type = section_data.get("type")
                if raw_section_type:
                    mapped_type = section_type_mapping.get(raw_section_type, raw_section_type)
                    # Ensure it's a valid SectionType enum value
                    if hasattr(SectionType, mapped_type):
                        section_type = getattr(SectionType, mapped_type)
                    else:
                        section_type = SectionType.other
                else:
                    section_type = SectionType.other

                section_entity = SectionEntity(
                    title=title,
                    content=content,
                    order=section_data.get("order"),
                    section_type=section_type,
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
        affiliations_id_to_entity: dict[str, Organization] = {}
        if xml_data.get("affiliations"):
            affiliations_lookup = {}
            for aff in xml_data.get("affiliations", []):
                if not isinstance(aff, dict) or not aff.get("id"):
                    continue

                # Use clean institution text if available, otherwise fall back to text/institution
                clean_text = aff.get("institution_text")
                if not clean_text:
                    # For institution-wrap affiliations, construct clean text from parsed_institutions
                    if aff.get("parsed_institutions"):
                        inst_parts = []
                        for inst in aff.get("parsed_institutions", []):
                            parts = []
                            if inst.get("name"):
                                parts.append(inst["name"])
                            if inst.get("city"):
                                parts.append(inst["city"])
                            if inst.get("country"):
                                parts.append(inst["country"])
                            if parts:
                                inst_parts.append(", ".join(parts))
                        clean_text = "; ".join(inst_parts)
                    else:
                        clean_text = aff.get("text") or aff.get("institution", "")

                affiliations_lookup[aff["id"]] = clean_text

            # Create a mapping from affiliation ID to Organization
            for aff in xml_data.get("affiliations", []):
                if not isinstance(aff, dict):
                    continue
                aff_id = aff.get("id")
                if not aff_id:
                    continue

                institution_ids = aff.get("institution_ids", {})
                institution_name = aff.get("institution") or aff.get("text", "")

                # For institution-wrap, use parsed_institutions data
                if aff.get("parsed_institutions"):
                    # Use the first parsed institution for the main entity
                    parsed_inst = aff["parsed_institutions"][0]
                    institution_name = parsed_inst.get("name", "")
                    institution_ids = parsed_inst.get("institution_ids", {})
                    city = parsed_inst.get("city")
                    country = parsed_inst.get("country")
                else:
                    city = aff.get("city")
                    country = aff.get("country")

                # Skip if no institution identifiers and no name
                if not institution_ids and not institution_name:
                    continue

                # Create institution entity
                institution_entity = Organization(
                    display_name=institution_name,
                    ror_id=institution_ids.get("ROR"),
                    grid_id=institution_ids.get("GRID"),
                    isni=institution_ids.get("ISNI"),
                    country=country,
                    city=city,
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
    elif merged_data and isinstance(merged_data, dict):
        # Merged data is paper data
        return merged_data, merged_data.get("authors", [])
    else:
        # No paper data found, check for author-level data
        return None, enrichment_data.get("authors", [])


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

    # Extract external IDs
    external_ids = paper_data.get("external_ids", {})
    biblio = paper_data.get("biblio", {})

    # Extract topics as strings
    topics_raw = paper_data.get("topics", [])
    topics = []
    if isinstance(topics_raw, list):
        for topic in topics_raw:
            if isinstance(topic, dict) and "display_name" in topic:
                topics.append(topic["display_name"])
            elif isinstance(topic, str):
                topics.append(topic)

    # Extract journal ISSN properly
    journal_issn = None
    if isinstance(journal_info, dict):
        journal_issn = journal_info.get("issn")
    elif biblio.get("issn"):
        journal_issn = biblio.get("issn")
    # Handle list case
    if isinstance(journal_issn, list) and journal_issn:
        journal_issn = journal_issn[0]

    # Extract license information
    license_data = paper_data.get("license")
    license_url = None
    license_text = None
    if isinstance(license_data, dict):
        license_url = license_data.get("url")
        license_text = license_data.get("license") or license_data.get("text")
    elif isinstance(license_data, str):
        license_url = license_data

    return PaperEntity(
        doi=paper_data.get("doi") or enrichment_data.get("doi") or external_ids.get("DOI"),
        pmcid=paper_data.get("pmcid") or external_ids.get("PubMedCentral"),
        pmid=paper_data.get("pmid") or external_ids.get("PubMed"),
        title=paper_data.get("title"),
        abstract=paper_data.get("abstract"),
        journal=journal_entity,
        publication_year=paper_data.get("publication_year") or paper_data.get("year"),
        publication_date=_pad_partial_date(paper_data.get("publication_date")),
        authors=[],  # Will be populated below
        keywords=paper_data.get("keywords", []),
        mesh_terms=paper_data.get("mesh_terms", []),
        topics=topics,  # Processed topics as strings
        citation_count=paper_data.get("citation_count"),
        influential_citation_count=paper_data.get("influential_citation_count"),
        cited_by_count=paper_data.get("cited_by_count"),
        reference_count=paper_data.get("reference_count"),
        is_oa=paper_data.get("is_oa"),
        oa_status=paper_data.get("oa_status"),
        oa_url=paper_data.get("oa_url"),
        publisher=paper_data.get("publisher"),
        publication_type=paper_data.get("publication_type") or paper_data.get("type"),
        semantic_scholar_corpus_id=paper_data.get("corpus_id") or external_ids.get("CorpusId"),
        openalex_id=paper_data.get("openalex_id") or paper_data.get("ids", {}).get("openalex"),
        license_url=license_url,
        license_text=license_text,
        fields_of_study=paper_data.get("fields_of_study", []),
        pub_types=paper_data.get("pub_types", []),
        volume=biblio.get("volume"),
        issue=biblio.get("issue"),
        first_page=biblio.get("first_page"),
        last_page=biblio.get("last_page"),
        pages=biblio.get("pages"),
        journal_issn=journal_issn,
        page_info=biblio.get("pages"),
        grants=_create_grant_entities(paper_data.get("funding")),
    )


def _create_enrichment_author_entities(authors_data: list[dict[str, Any]]) -> list[AuthorEntity]:
    """Create AuthorEntity objects from enrichment authors data."""
    author_entities = []

    for author_data in authors_data:
        try:
            # Extract ORCID
            orcid = _format_orcid(author_data.get("orcid"))

            # Extract affiliation text
            affiliation_text = None
            affiliations = author_data.get("affiliations", [])
            if affiliations:
                affiliation_text = "; ".join(affiliations)

            # Extract institutions list
            institutions = []
            institutions_data = author_data.get("institutions", [])
            for inst_data in institutions_data:
                if isinstance(inst_data, dict):
                    inst_entity = Organization(
                        display_name=inst_data.get("display_name"),
                        ror_id=inst_data.get("ror_id"),
                        country=inst_data.get("country"),
                        institution_type=inst_data.get("type"),
                        city=inst_data.get("city"),
                        latitude=inst_data.get("latitude"),
                        longitude=inst_data.get("longitude"),
                        website=inst_data.get("website"),
                        established=inst_data.get("established"),
                    )
                    institutions.append(inst_entity)

            # Map position
            position_raw = author_data.get("position") or author_data.get("sequence")
            position = None
            if position_raw == "first":
                position = "first"
            elif position_raw == "additional":
                position = "middle"
            elif position_raw == "last":
                position = "last"

            author_entity = AuthorEntity(
                full_name=author_data.get("name")
                or f"{author_data.get('given_name', '')} {author_data.get('family_name', '')}".strip(),
                first_name=author_data.get("given_name"),
                last_name=author_data.get("family_name"),
                orcid=orcid,
                affiliation_text=affiliation_text,
                institutions=institutions,
                openalex_id=author_data.get("openalex_id"),
                position=position,
            )
            author_entities.append(author_entity)
        except Exception as e:
            print(f"Error creating author entity: {e}")
            continue

    return author_entities


def _create_enrichment_institution_entities(
    enrichment_data: dict[str, Any],
) -> list[Organization]:
    """Create Organization objects from enrichment data."""
    institution_entities = []

    # Extract institutions from OpenAlex data
    openalex_data = enrichment_data.get("openalex", {})
    institutions_data = openalex_data.get("institutions", [])

    # Get ROR data for enrichment
    ror_data = enrichment_data.get("ror", {})

    # Create a mapping of ROR IDs to ROR data for quick lookup
    ror_mapping = {}
    for ror_id, data in ror_data.items():
        if isinstance(data, dict):
            ror_mapping[ror_id] = data

    for inst_data in institutions_data:
        try:
            if isinstance(inst_data, dict):
                # Get ROR ID from OpenAlex data
                ror_id = inst_data.get("ror_id") or inst_data.get("ror")

                # If we have ROR data for this institution, merge it
                ror_info = None
                if ror_id and ror_id in ror_mapping:
                    ror_info = ror_mapping[ror_id]
                    # Merge ROR data with OpenAlex data, but exclude parent_organization
                    merged_data = {**inst_data}
                    for key, value in ror_info.items():
                        if (
                            key != "parent_organization"
                        ):  # Skip parent_organization as Organization doesn't have this field
                            merged_data[key] = value
                else:
                    merged_data = inst_data

                # Use ROR display_name if available, otherwise OpenAlex
                display_name = (
                    merged_data.get("display_name")  # ROR display_name
                    or inst_data.get("display_name")  # OpenAlex display_name
                    or inst_data.get("name")  # Fallback
                )

                # Ensure ROR ID is properly formatted
                final_ror_id = merged_data.get("ror_id") or ror_id
                if final_ror_id and not final_ror_id.startswith("https://ror.org/"):
                    final_ror_id = f"https://ror.org/{final_ror_id}"

                # Extract alternative names from ROR data
                names = []
                if ror_info and ror_info.get("names"):
                    for name_entry in ror_info["names"]:
                        if isinstance(name_entry, dict) and name_entry.get("value"):
                            names.append(name_entry["value"])

                institution_entity = Organization(
                    display_name=display_name,
                    ror_id=final_ror_id,
                    openalex_id=inst_data.get("id"),
                    country=merged_data.get("country") or merged_data.get("country_code"),
                    city=merged_data.get("city"),
                    latitude=merged_data.get("latitude"),
                    longitude=merged_data.get("longitude"),
                    institution_type=merged_data.get("institution_type")
                    or merged_data.get("type"),
                    grid_id=merged_data.get("grid_id"),
                    isni=merged_data.get("isni"),
                    wikidata_id=merged_data.get("wikidata_id"),
                    website=merged_data.get("website"),
                    established=merged_data.get("established"),
                    domains=merged_data.get("domains", []),
                    relationships=merged_data.get("relationships", []),
                    status=merged_data.get("status"),
                    names=names if names else [],
                    locations=merged_data.get("locations", []),
                    links=merged_data.get("links", []),
                )
                institution_entities.append(institution_entity)
        except Exception as e:
            print(f"Error creating institution entity: {e}")
            continue

    # Deduplicate institutions by ROR ID
    seen_ror_ids = set()
    deduplicated_entities = []

    for entity in institution_entities:
        ror_key = entity.ror_id
        if ror_key and ror_key in seen_ror_ids:
            continue  # Skip duplicates
        if ror_key:
            seen_ror_ids.add(ror_key)
        deduplicated_entities.append(entity)

    return deduplicated_entities
    """Create AuthorEntity objects from enrichment author data."""
    author_entities = []
    for author_dict in authors_data:
        try:
            if isinstance(author_dict, dict):
                # Extract name information
                full_name = (
                    author_dict.get("name")
                    or author_dict.get("full_name")
                    or author_dict.get("display_name")
                    or f"{author_dict.get('first_name', '')} {author_dict.get('last_name', '')}".strip()
                    or ""
                )

                # Extract affiliation information
                affiliation_text = author_dict.get("affiliation")
                if not affiliation_text and author_dict.get("affiliations"):
                    # Use first affiliation if available
                    affiliations = author_dict["affiliations"]
                    if isinstance(affiliations, list) and affiliations:
                        affiliation_text = affiliations[0].get("name") or affiliations[0].get(
                            "display_name"
                        )

                # Extract institutions
                institutions = []
                if author_dict.get("institutions"):
                    for inst in author_dict["institutions"]:
                        if isinstance(inst, dict):
                            institutions.append(inst.get("display_name") or inst.get("name", ""))

                author_entity = AuthorEntity(
                    full_name=full_name,
                    orcid=_format_orcid(author_dict.get("orcid")),
                    affiliation_text=affiliation_text,
                    openalex_id=author_dict.get("openalex_id") or author_dict.get("id"),
                    semantic_scholar_author_id=author_dict.get("semantic_scholar_author_id")
                    or author_dict.get("author_id"),
                    institutions=institutions if institutions else None,
                    h_index=author_dict.get("h_index"),
                    citation_count=author_dict.get("citation_count"),
                    paper_count=author_dict.get("paper_count") or author_dict.get("works_count"),
                    orcid_works_count=author_dict.get("orcid_works_count"),
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
        institution_entities = _create_enrichment_institution_entities(enrichment_data)

        entities_data.append(
            {
                "entity": paper_entity,
                "related_entities": {
                    "authors": author_entities,
                    "institutions": institution_entities,
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
