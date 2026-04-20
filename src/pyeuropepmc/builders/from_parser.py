"""
Builder functions to convert FullTextXMLParser outputs to entity models.

This module converts parser outputs into LinkML-generated Pydantic entity models
with optional schema validation to ensure data quality and constraint compliance.
"""

from datetime import date
import logging
from typing import TYPE_CHECKING, Any

from pyeuropepmc.builders.schema_validation import SchemaValidator
from pyeuropepmc.models import (
    AuthorEntity,
    FigureEntity,
    GrantEntity,
    JournalEntity,
    Organization,
    PaperEntity,
    ReferenceEntity,
    SectionEntity,
    TableEntity,
    TableRowEntity,
)

if TYPE_CHECKING:
    from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

logger = logging.getLogger(__name__)

__all__ = ["build_paper_entities"]


# Helper functions for data formatting
def _format_pmcid(pmcid: str | None) -> str | None:
    """Format PMCID to ensure it has PMC prefix."""
    if not pmcid:
        return None
    pmcid_str = str(pmcid).strip()
    if pmcid_str.startswith("PMC"):
        return pmcid_str
    return f"PMC{pmcid_str}"


def _format_external_ids(external_ids: dict[str, Any] | None) -> str | None:
    """Format external IDs dict as JSON string."""
    if not external_ids:
        return None
    import json

    return json.dumps(external_ids)


def _clean_affiliation_text(text: str) -> str:
    """
    Clean affiliation text by removing embedded identifiers and normalizing formatting.

    This function removes ROR IDs, GRID IDs, and other embedded identifiers from
    affiliation text to make it more readable for display purposes.

    Parameters
    ----------
    text : str
        Raw affiliation text that may contain embedded identifiers

    Returns
    -------
    str
        Cleaned affiliation text suitable for display
    """
    import re

    if not text:
        return text

    # Remove ROR IDs (format: https://ror.org/ followed by 9 alphanumeric characters)
    text = re.sub(r"https?://ror\.org/[a-zA-Z0-9]{9}", "", text)

    # Remove GRID IDs - look for grid.xxxxx.xxxxxxxxxx pattern ending with letter
    # Use negative lookahead to avoid matching into institution names
    text = re.sub(r"grid\.\d+\.[a-zA-Z0-9]*[a-zA-Z](?![a-zA-Z])", "", text)
    # Also handle GRID IDs with spaces: grid.xxxxx.x xxxx xxxx xxxx
    text = re.sub(r"grid\.\d+\.\w+\s+\d{4}\s+\d{4}\s+\d{4}", "", text)

    # Remove other institutional identifiers (long numeric sequences)
    text = re.sub(r"\b\d{10,}\b", "", text)  # Long numeric sequences like 000000041936754X

    # Remove numeric prefixes that might be affiliation reference IDs
    # Handle cases like "1https://ror.org/..." or "2Department of..."
    text = re.sub(r"^\d+", "", text)
    text = re.sub(r"\b\d+(?=[a-zA-Z])", "", text)  # Remove digits followed immediately by letters

    # Clean up any remaining artifacts (dots followed by numbers)
    text = re.sub(r"\.\d+", "", text)

    # Remove multiple consecutive spaces and normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove leading/trailing commas, semicolons, and spaces
    text = text.strip(" ,;")

    # Remove empty parentheses or brackets
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)

    return text.strip()


def _format_license(license_data: dict[str, Any] | str | None) -> str | None:
    """Format license data as string."""
    if not license_data:
        return None
    if isinstance(license_data, str):
        return license_data
    if isinstance(license_data, dict):
        # Extract text field or convert to string representation
        return license_data.get("text") or str(license_data)
    return str(license_data)


def _parse_pub_date(date_str: str | None) -> date | None:
    """Parse publication date string into date object, handling partial dates."""
    if not date_str:
        return None

    try:
        # Handle different date formats
        parts = date_str.split("-")
        if len(parts) == 3:
            # Full date: YYYY-MM-DD
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        elif len(parts) == 2:
            # Year-month: YYYY-MM, assume first day of month
            return date(int(parts[0]), int(parts[1]), 1)
        elif len(parts) == 1:
            # Year only: YYYY, assume January 1st
            return date(int(parts[0]), 1, 1)
        else:
            logger.warning(f"Unexpected date format: {date_str}")
            return None
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None


def _normalize_section_type(section_type: str | None) -> str:
    """Normalize section type to match SectionType enum values."""
    if not section_type:
        return "other"

    # Mapping for common variations
    type_mapping = {
        "materials|methods": "methods",
        "methods|materials": "methods",
        "materials and methods": "methods",
        "methods and materials": "methods",
        "abstract": "abstract",
        "introduction": "introduction",
        "results": "results",
        "discussion": "discussion",
        "conclusion": "conclusion",
        "acknowledgments": "acknowledgments",
        "references": "references",
        "supplementary": "supplementary",
        "appendix": "appendix",
        "coi-statement": "acknowledgments",
        "author_notes": "acknowledgments",
        "competing-interests": "acknowledgments",
        "funding": "acknowledgments",
        "data-availability": "other",
        "ethics-statement": "other",
        "patient-consent": "other",
        "author-contributions": "acknowledgments",
        "disclosure": "acknowledgments",
    }

    # Return mapped type or default to "other"
    return type_mapping.get(section_type.lower(), "other")


# Module-level validator for optional validation
_schema_validator = SchemaValidator()  # type: ignore[no-untyped-call]


def _validate_and_log_entity_data(
    entity_class: str, data: dict[str, Any], context: str = ""
) -> None:
    """
    Validate entity data against schema and log warnings for issues.

    Parameters
    ----------
    entity_class : str
        Name of the entity class (e.g., "PaperEntity")
    data : dict
        Dictionary of field values
    context : str
        Context string for logging (e.g., "author #1")
    """
    if not _schema_validator.introspector.is_available:
        return

    is_valid, errors = _schema_validator.validate_entity_data(entity_class, data, strict=False)

    if not is_valid and errors:
        context_str = f" ({context})" if context else ""
        logger.warning(f"Schema validation warnings for {entity_class}{context_str}:")
        for error in errors:
            logger.warning(f"  - {error}")


def _create_grant_entities(funding_data: list[dict[str, Any]] | None) -> list[GrantEntity] | None:
    """Create GrantEntity objects from funding data."""
    if not funding_data:
        return None

    grant_entities = []
    for funder in funding_data:
        if isinstance(funder, dict):
            try:
                # Create AuthorEntity objects for recipients
                recipient_entities = None
                if funder.get("recipients"):
                    recipient_entities = []
                    for recipient_data in funder["recipients"]:
                        if isinstance(recipient_data, dict):
                            recipient_entity = AuthorEntity(
                                full_name=recipient_data.get("full_name", ""),
                                first_name=recipient_data.get("given_names"),
                                last_name=recipient_data.get("surname"),
                            )
                            recipient_entities.append(recipient_entity)

                grant_entity = GrantEntity(
                    fundref_doi=funder.get("fundref_doi"),
                    funding_source=funder.get("source"),
                    award_id=funder.get("award_id"),
                    recipients=recipient_entities,
                    recipient=funder.get("recipient_full")
                    or funder.get("recipient_name"),  # Deprecated
                )
                grant_entities.append(grant_entity)
            except Exception as e:
                print(f"Error creating grant entity: {e}")
                continue

    return grant_entities if grant_entities else None


def _build_author_entity(  # noqa: C901
    author_data: str | dict[str, Any], affiliations: list[dict[str, Any]]
) -> AuthorEntity:
    """Build a single AuthorEntity from author data and affiliations."""

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

    if affiliation_refs:
        # Create a lookup dict for affiliations by ID
        aff_lookup = {aff["id"]: aff for aff in affiliations if aff.get("id")}

        # Combine text from all referenced affiliations
        aff_texts = []
        for ref_id in affiliation_refs:
            if ref_id in aff_lookup:
                aff_data = aff_lookup[ref_id]
                # Prefer structured parsed institutions over raw text
                if aff_data.get("parsed_institutions"):
                    # Build clean text from parsed institution data
                    inst_texts = []
                    for inst in aff_data["parsed_institutions"]:
                        parts = []
                        if inst.get("name"):
                            parts.append(inst["name"])
                        if inst.get("city"):
                            parts.append(inst["city"])
                        if inst.get("state_province"):
                            parts.append(inst["state_province"])
                        if inst.get("country"):
                            parts.append(inst["country"])
                        if parts:
                            inst_texts.append(", ".join(parts))
                    if inst_texts:
                        aff_texts.append("; ".join(inst_texts))
                else:
                    # Fallback to cleaned institution_text or text
                    text = aff_data.get("institution_text") or aff_data.get("text") or ""
                    if text:
                        # Clean the affiliation text to remove embedded identifiers
                        cleaned_text = _clean_affiliation_text(text.strip())
                        if cleaned_text:  # Only add non-empty cleaned text
                            aff_texts.append(cleaned_text)

                # Create Organization from affiliation data
                # Use the first parsed institution or fallback to raw data
                if aff_data.get("parsed_institutions") and aff_data["parsed_institutions"]:
                    primary_inst = aff_data["parsed_institutions"][0]
                    institution = Organization(
                        display_name=primary_inst.get("name", ""),
                        city=primary_inst.get("city"),
                        country=primary_inst.get("country"),
                        source_uri=f"urn:pmc-affiliation:{ref_id}",
                    )
                    # Add institution IDs if available
                    inst_ids = primary_inst.get("institution_ids", {})
                    if inst_ids.get("ROR"):
                        institution.ror_id = inst_ids["ROR"]
                    if inst_ids.get("GRID"):
                        institution.grid_id = inst_ids["GRID"]
                    if inst_ids.get("ISNI"):
                        institution.isni = inst_ids["ISNI"]
                else:
                    institution = Organization(
                        display_name=aff_data.get("institution")
                        or aff_data.get("institution_text")
                        or aff_data.get("text", ""),
                        city=aff_data.get("city"),
                        country=aff_data.get("country"),
                        source_uri=f"urn:pmc-affiliation:{ref_id}",
                    )
                # Normalize string fields
                if institution.display_name:
                    institution.display_name = institution.display_name.strip()
                if institution.city:
                    institution.city = institution.city.strip()
                if institution.country:
                    institution.country = institution.country.strip()
                institution_entities.append(institution)

        if aff_texts:
            affiliation_text = "; ".join(aff_texts)
            # Always apply final cleaning to ensure no embedded identifiers remain
            if affiliation_text:
                affiliation_text = _clean_affiliation_text(affiliation_text)

    return AuthorEntity(
        full_name=full_name,
        first_name=author_data.get("given_names", ""),
        last_name=author_data.get("surname", ""),
        orcid=author_data.get("orcid"),
        affiliation_text=affiliation_text,
        institutions=institution_entities if institution_entities else None,
    )


def build_paper_entities(  # noqa: C901
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
    journal_entity = None
    journal_data = meta.get("journal")
    # Volume and issue are now nested in journal data but belong to the Paper, not Journal
    volume = None
    issue = None

    if journal_data:
        # Journal data is now a dict with nested structure
        if isinstance(journal_data, dict):
            title = journal_data.get("title")
            if title:  # Only create journal entity if we have a title
                # Create comprehensive JournalEntity with all available metadata
                journal_entity = JournalEntity(
                    title=title,
                    medline_abbreviation=journal_data.get("nlm_ta"),
                    iso_abbreviation=journal_data.get("iso_abbrev"),
                    nlmid=journal_data.get("nlmid"),
                    issn=journal_data.get("issn_print"),
                    essn=journal_data.get("issn_electronic"),
                    publisher=journal_data.get("publisher_name"),
                    country=journal_data.get("publisher_location"),
                    journal_ids=_format_external_ids(journal_data.get("journal_ids")),
                )
            # Extract volume/issue from journal dict (they belong to Paper, not Journal)
            volume = journal_data.get("volume")
            issue = journal_data.get("issue")
        else:
            # Fallback for simple string format (backward compatibility)
            journal_entity = JournalEntity(title=str(journal_data))

    # Allow top-level metadata to override (backward compatibility)
    volume = meta.get("volume") or volume
    issue = meta.get("issue") or issue

    paper = PaperEntity(
        id=meta.get("pmcid") or meta.get("doi"),
        label=meta.get("title"),
        source_uri=f"urn:pmc:{meta.get('pmcid', '')}" if meta.get("pmcid") else None,
        pmcid=_format_pmcid(meta.get("pmcid")),
        doi=meta.get("doi"),
        title=meta.get("title"),
        journal=journal_entity,
        volume=volume,
        issue=issue,
        pages=meta.get("pages"),
        pub_date=_parse_pub_date(meta.get("pub_date")),
        keywords=meta.get("keywords") or [],
        grants=_create_grant_entities(meta.get("funding")),
        pii=meta.get("identifiers", {}).get("pii"),
        publisher_id=meta.get("identifiers", {}).get("publisher-id"),
        license=_format_license(meta.get("license")),
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
            section_type=_normalize_section_type(sec_data.get("type")),
            order=sec_data.get("order"),
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
    # Generate paper URI for linking references back to the paper
    paper_pmid = meta.get("pmid")
    paper_doi = meta.get("doi")
    paper_pmcid = meta.get("pmcid")

    # Generate paper URI using the same logic as RDF mapper
    paper_uri = "https://w3id.org/pyeuropepmc/data#paper/"
    if paper_pmid:
        paper_uri += paper_pmid
    elif paper_doi:
        paper_uri += paper_doi.replace("/", "-")
    elif paper_pmcid:
        pmcid_str = paper_pmcid
        if not pmcid_str.upper().startswith("PMC"):
            pmcid_str = f"PMC{pmcid_str}"
        paper_uri += pmcid_str

    for ref_data in parser.extract_references():
        year = ref_data.get("year")

        # Create a simple JournalEntity for references if journal info is available
        journal_entity = None
        journal_name = ref_data.get("source") or ref_data.get("journal")
        if journal_name:
            journal_entity = JournalEntity(
                title=journal_name,
                source_uri=f"urn:journal:{journal_name.replace(' ', '_')}",
            )

        reference = ReferenceEntity(
            title=ref_data.get("title"),
            journal=journal_entity,  # Use the simple JournalEntity
            publication_year=int(year) if year is not None else None,
            volume=ref_data.get("volume"),
            pages=ref_data.get("pages"),
            doi=ref_data.get("doi"),
            pmid=ref_data.get("pmid"),
            pmcid=ref_data.get("pmcid"),
            author_list=ref_data.get("authors"),  # Use author_list instead of authors
            citing_paper=paper,  # Link reference back to paper
        )
        references.append(reference)

    return paper, authors, sections, tables, figures, references
