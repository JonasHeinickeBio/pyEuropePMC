"""
RDF Utilities for PyEuropePMC.

This module contains reusable helper functions for RDF mapping operations,
extracted from the RDFMapper class to improve maintainability and modularity.
"""

from collections.abc import Callable
import re
from typing import Any
import uuid

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

from .config_utils import load_rdf_config


class URIFactory:
    """
    Centralized factory for generating consistent URIs across all PyEuropePMC workflows.

    This factory ensures that all entity types use consistent URI schemes and patterns,
    making URIs predictable, resolvable, and interoperable across different data sources.

    URI Schemes:
    - Papers: https://pubmed.ncbi.nlm.nih.gov/{pmid}/ (preferred),
      https://doi.org/{doi}, or fallback to first-author-year-journal
    - Authors: {base_uri}author/{normalized_name} (preferred),
      with ORCID/OpenAlex as owl:sameAs
    - Institutions: {ror_id} (preferred), or {base_uri}institution/{compact_id}
    - References: https://doi.org/{doi} (preferred), or https://pubmed.ncbi.nlm.nih.gov/{pmid}/
    - Other entities: {base_uri}{entity_type}/{entity_id}

    Examples
    --------
    >>> factory = URIFactory()
    >>> paper_uri = factory.generate_uri(paper_entity)
    >>> author_uri = factory.generate_uri(author_entity)
    """

    def __init__(self) -> None:
        """Initialize the URI factory with standard generators."""
        self._base_uri = None  # Lazy load
        self.generators = {
            "PaperEntity": self._generate_paper_uri,
            "AuthorEntity": self._generate_author_uri,
            "InstitutionEntity": self._generate_institution_uri,
            "ReferenceEntity": self._generate_reference_uri,
            "JournalEntity": self._generate_journal_uri,
            "SectionEntity": self._generate_section_uri,
            "TableEntity": self._generate_table_uri,
        }

    @property
    def base_uri(self) -> str:
        """Get the base URI from configuration, loading it fresh each time."""
        config = load_rdf_config()
        return str(config.get("base_uri", "http://example.org/data/"))

    def generate_uri(self, entity: Any) -> URIRef:
        """
        Generate a URI for the given entity using the appropriate scheme.

        Parameters
        ----------
        entity : Any
            Entity instance to generate URI for

        Returns
        -------
        URIRef
            Generated URI for the entity
        """
        entity_class = entity.__class__.__name__
        generator = self.generators.get(entity_class, self._generate_fallback_uri)
        return generator(entity)

    def _generate_paper_uri(self, entity: Any) -> URIRef:
        """Generate URI for paper entity."""
        # Prioritize PMID for PubMed resolvable URIs
        if getattr(entity, "pmid", None):
            return URIRef(f"https://pubmed.ncbi.nlm.nih.gov/{entity.pmid}/")
        if getattr(entity, "doi", None):
            return URIRef(f"https://doi.org/{entity.doi}")
        if getattr(entity, "pmcid", None):
            return URIRef(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{entity.pmcid}/")
        # Fallback: first author last name + year + short journal
        return self._generate_paper_fallback_uri(entity)

    def _generate_author_uri(self, entity: Any) -> URIRef:
        """Generate URI for author entity."""
        # Prioritize normalized name for consistent URIs
        normalized_name = self._normalize_name(
            getattr(entity, "full_name", "") or getattr(entity, "name", "")
        )
        if normalized_name:
            return URIRef(f"{self.base_uri}author/{normalized_name}")
        # Fall back to ORCID if no name available
        if getattr(entity, "orcid", None):
            return URIRef(f"https://orcid.org/{entity.orcid}")
        # Then OpenAlex ID
        if getattr(entity, "openalex_id", None):
            return URIRef(entity.openalex_id)
        return self._generate_fallback_uri(entity)

    def _generate_institution_uri(self, entity: Any) -> URIRef:
        """Generate URI for institution entity."""
        if getattr(entity, "ror_id", None):
            return URIRef(entity.ror_id)
        if getattr(entity, "openalex_id", None):
            return URIRef(entity.openalex_id)
        if getattr(entity, "display_name", None):
            compact_id = self._generate_compact_institution_id(entity.display_name)
            return URIRef(f"{self.base_uri}institution/{compact_id}")
        return self._generate_fallback_uri(entity)

    def _generate_reference_uri(self, entity: Any) -> URIRef:
        """Generate URI for reference entity."""
        if getattr(entity, "doi", None):
            return URIRef(f"https://doi.org/{entity.doi}")
        if getattr(entity, "pmid", None):
            return URIRef(f"https://pubmed.ncbi.nlm.nih.gov/{entity.pmid}/")
        return self._generate_fallback_uri(entity)

    def _generate_journal_uri(self, entity: Any) -> URIRef:
        """Generate URI for journal entity using abbreviation."""
        # Prioritize medline abbreviation, then ISO abbreviation
        abbreviation = getattr(entity, "medline_abbreviation", None) or getattr(
            entity, "iso_abbreviation", None
        )
        if abbreviation:
            # Normalize abbreviation for URI use
            normalized_abbr = self._normalize_journal_abbr(abbreviation)
            if normalized_abbr:
                return URIRef(f"{self.base_uri}journal/{normalized_abbr}")
        # Fallback to title-based URI
        if getattr(entity, "title", None):
            normalized_title = self._normalize_name(entity.title)
            if normalized_title:
                return URIRef(f"{self.base_uri}journal/{normalized_title}")
        # Final fallback to NLM ID if available
        if getattr(entity, "nlmid", None):
            return URIRef(f"{self.base_uri}journal/{entity.nlmid.lower()}")
        return self._generate_fallback_uri(entity)

    def _generate_section_uri(self, entity: Any) -> URIRef:
        """Generate URI for section entity using title-based identifier."""
        title = getattr(entity, "title", None)
        if title:
            # Normalize the title for URI use
            normalized_title = self._normalize_name(title)
            if normalized_title:
                return URIRef(f"{self.base_uri}section/{normalized_title}")
        # Fallback to label
        label = getattr(entity, "label", None)
        if label:
            normalized_label = self._normalize_name(label)
            if normalized_label:
                return URIRef(f"{self.base_uri}section/{normalized_label}")
        return self._generate_fallback_uri(entity)

    def _generate_table_uri(self, entity: Any) -> URIRef:
        """Generate URI for table entity using label-based identifier."""
        # First try table_label (e.g., "Table 1")
        table_label = getattr(entity, "table_label", None)
        if table_label:
            normalized_label = self._normalize_name(table_label)
            if normalized_label:
                return URIRef(f"{self.base_uri}table/{normalized_label}")
        # Fallback to caption
        caption = getattr(entity, "caption", None)
        if caption:
            # Take first 50 chars of caption for URI
            short_caption = caption[:50] if len(caption) > 50 else caption
            normalized_caption = self._normalize_name(short_caption)
            if normalized_caption:
                return URIRef(f"{self.base_uri}table/{normalized_caption}")
        # Fallback to label
        label = getattr(entity, "label", None)
        if label and label != "Untitled Table":
            normalized_label = self._normalize_name(label)
            if normalized_label:
                return URIRef(f"{self.base_uri}table/{normalized_label}")
        return self._generate_fallback_uri(entity)

    def generate_grant_uri(self, funder_dict: dict[str, Any]) -> URIRef:
        """
        Generate a meaningful URI for a grant/funding record.

        Parameters
        ----------
        funder_dict : dict
            Dictionary containing funder information with keys like:
            - fundref_doi: FundRef DOI (e.g., "https://doi.org/10.13039/501100001809")
            - award_id: Award/grant identifier (e.g., "82170974")
            - source: Funding source name

        Returns
        -------
        URIRef
            Generated URI for the grant
        """
        award_id = funder_dict.get("award_id")
        fundref_doi = funder_dict.get("fundref_doi")
        source = funder_dict.get("source")

        # Build a meaningful identifier
        parts = []
        if fundref_doi:
            # Extract the funder ID from the FundRef DOI
            # e.g., "https://doi.org/10.13039/501100001809" -> "501100001809"
            funder_id = fundref_doi.split("/")[-1] if "/" in fundref_doi else fundref_doi
            # Clean up any URL parts
            funder_id = funder_id.replace("https://doi.org/10.13039/", "").replace(
                "http://doi.org/10.13039/", ""
            )
            if funder_id:
                parts.append(funder_id)
        if award_id:
            # Normalize award ID for URI use
            normalized_award = re.sub(r"[^a-zA-Z0-9-]", "-", str(award_id)).lower()
            parts.append(normalized_award)

        if parts:
            grant_id = "-".join(parts)
            return URIRef(f"{self.base_uri}grant/{grant_id}")

        # Fallback: use source if available
        if source:
            normalized_source = self._normalize_name(source)
            if normalized_source:
                return URIRef(f"{self.base_uri}grant/{normalized_source}")

        # Final fallback to UUID
        return URIRef(f"{self.base_uri}grant/{uuid.uuid4()}")

    def _normalize_journal_abbr(self, abbreviation: str) -> str | None:
        """Normalize journal abbreviation for URI use."""
        if not abbreviation:
            return None
        # Remove periods and convert to lowercase
        normalized = abbreviation.replace(".", "").strip().lower()
        # Replace spaces with hyphens
        normalized = re.sub(r"\s+", "-", normalized)
        # Remove any remaining non-alphanumeric characters except hyphens
        normalized = re.sub(r"[^a-z0-9-]", "", normalized)
        return normalized if normalized else None

    def _generate_paper_fallback_uri(self, entity: Any) -> URIRef:  # noqa: C901
        """Generate fallback URI for paper using first author + year + short journal."""
        # Extract first author last name
        first_author_last_name = None
        authors = getattr(entity, "authors", None)
        if authors and isinstance(authors, list) and authors:
            first_author = authors[0]
            if isinstance(first_author, dict):
                first_author_last_name = first_author.get("last_name")
            elif isinstance(first_author, str):
                # If authors is a string, try to extract last name
                first_author_last_name = first_author.split()[-1] if first_author else None

        # Extract publication year
        year = getattr(entity, "publication_year", None)

        # Extract short journal name
        short_journal = None
        journal = getattr(entity, "journal", None)
        if journal:
            if isinstance(journal, str):
                short_journal = journal
            else:
                # Try abbreviations first, then title
                short_journal = (
                    getattr(journal, "medline_abbreviation", None)
                    or getattr(journal, "iso_abbreviation", None)
                    or getattr(journal, "title", None)
                )

        # Build the identifier
        parts = []
        if first_author_last_name:
            parts.append(first_author_last_name.lower())
        if year:
            parts.append(str(year))
        if short_journal:
            # Shorten journal name: take first word or up to first comma/space
            journal_short = short_journal.split()[0].split(",")[0].lower()
            # Remove non-alphanumeric characters
            journal_short = re.sub(r"[^a-zA-Z0-9]", "", journal_short)
            if journal_short:
                parts.append(journal_short)

        if parts:
            identifier = "-".join(parts)
            return URIRef(f"{self.base_uri}paper/{identifier}")
        else:
            # Final fallback to UUID if no components available
            return self._generate_fallback_uri(entity)

    def _generate_fallback_uri(self, entity: Any) -> URIRef:
        """Generate fallback URI using UUID for any entity type."""
        import uuid

        entity_type = entity.__class__.__name__.lower().replace("entity", "")
        return URIRef(f"{self.base_uri}{entity_type}/{uuid.uuid4()}")

    def _normalize_name(self, name: str) -> str | None:
        """Normalize a name for URI use."""
        if not name:
            return None
        normalized = re.sub(r"[^a-zA-Z0-9\s]", "", name).lower().strip()
        normalized = re.sub(r"\s+", "-", normalized)
        return normalized if normalized else None

    def _generate_compact_institution_id(self, display_name: str) -> str:
        """Generate compact institution identifier."""
        if not display_name:
            return str(uuid.uuid4())[:8]

        name = display_name.strip()
        name = re.sub(
            r",\s*(?:USA|United States|UK|United Kingdom|Canada|Australia|"
            r"Germany|France|Italy|Spain|Japan|China|India)(?:\..*)?$",
            "",
            name,
            flags=re.IGNORECASE,
        )

        parts = [part.strip() for part in name.split(",") if part.strip()]
        if not parts:
            return str(uuid.uuid4())[:8]

        main_name = parts[0]
        main_name = re.sub(r"^(?:the\s+)?", "", main_name, flags=re.IGNORECASE)
        main_name = re.sub(
            r"(?:\s+(?:university|college|institute|center|centre|hospital|school|department|division|program|unit|group|laboratory|lab|clinic))$",
            "",
            main_name,
            flags=re.IGNORECASE,
        )

        words = main_name.split()
        if len(words) > 4:
            main_name = " ".join(words[:4])

        normalized = self._normalize_name(main_name)
        if normalized and len(normalized) <= 50:
            return normalized

        import hashlib

        hash_obj = hashlib.md5(display_name.encode("utf-8"))  # nosec B324
        return hash_obj.hexdigest()[:12]


# Global URI factory instance for reuse
uri_factory: URIFactory = URIFactory()


def normalize_name(name: str) -> str | None:
    """
    Normalize an author name for use in URIs.

    Parameters
    ----------
    name : str
        Author full name

    Returns
    -------
    str | None
        Normalized name suitable for URIs, or None if empty
    """
    return uri_factory._normalize_name(name)


def generate_compact_institution_id(display_name: str) -> str:
    """
    Generate a compact, meaningful identifier for institutions.

    This function creates shorter URIs by extracting key components from institution names,
    avoiding overly long URIs while maintaining meaningful identifiers.

    Parameters
    ----------
    display_name : str
        Full institution display name

    Returns
    -------
    str
        Compact identifier suitable for URIs

    Examples
    --------
    >>> generate_compact_institution_id("BC Cancer - Victoria, Victoria, BC V8R 6V5")
    'bc-cancer-victoria'
    >>> generate_compact_institution_id(
    ...     "Brigham and Women's Hospital, Dana-Farber Cancer Institute and "
    ...     "Harvard Medical School, Boston, MA"
    ... )
    'brigham-womens-hospital'
    """
    return uri_factory._generate_compact_institution_id(display_name)


def generate_paper_uri(entity: Any) -> URIRef:
    """Generate URI for paper entity."""
    return uri_factory._generate_paper_uri(entity)


def generate_author_uri(entity: Any) -> URIRef:
    """Generate URI for author entity."""
    return uri_factory._generate_author_uri(entity)


def generate_institution_uri(entity: Any) -> URIRef:
    """Generate URI for institution entity."""
    return uri_factory._generate_institution_uri(entity)


def generate_reference_uri(entity: Any) -> URIRef:
    """Generate URI for reference entity."""
    return uri_factory._generate_reference_uri(entity)


def generate_fallback_uri(entity: Any) -> URIRef:
    """Generate fallback URI for entity."""
    return uri_factory._generate_fallback_uri(entity)


def generate_entity_uri(entity: Any) -> URIRef:
    """
    Generate a resolvable URI for an entity based on its identifiers.

    Parameters
    ----------
    entity : Any
        Entity instance

    Returns
    -------
    URIRef
        Generated URI for the entity
    """
    return uri_factory.generate_uri(entity)


def map_single_value_fields(
    g: Any,
    subject: URIRef,
    entity: Any,
    fields_mapping: dict[str, str | dict[str, Any]],
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None = None,
) -> None:
    """
    Map single-value fields to RDF triples with proper datatype handling.

    Args:
        g: RDF graph
        subject: Subject URI
        entity: Entity object
        fields_mapping: Mapping of field names to predicates (string) or dicts
            with predicate and datatype
        resolve_predicate: Function to resolve predicate strings to URIRefs
        context: Optional named graph context
    """
    for field_name, predicate_config in fields_mapping.items():
        value = getattr(entity, field_name, None)
        if value is None:
            continue

        # Handle both old format (string) and new format (dict with predicate and datatype)
        predicate_str: str | None
        datatype_str: str | None

        if isinstance(predicate_config, dict):
            predicate_str = predicate_config.get("predicate")
            datatype_str = predicate_config.get("datatype")
        else:
            predicate_str = predicate_config
            datatype_str = None

        if predicate_str is None:
            continue

        predicate = resolve_predicate(predicate_str)

        # Determine the appropriate datatype
        if datatype_str:
            # Parse datatype from config (e.g., "xsd:string" -> XSD.string)
            datatype = _parse_datatype(datatype_str)
        else:
            # Fallback to legacy behavior for backward compatibility
            datatype = _infer_datatype(field_name, value)

        # Create literal with datatype
        literal = Literal(value, datatype=datatype) if datatype else Literal(value)

        if context:
            g.graph(context).add((subject, predicate, literal))
        else:
            g.add((subject, predicate, literal))


def _parse_datatype(datatype_str: str) -> URIRef | None:
    """
    Parse a datatype string (e.g., 'xsd:string') into an RDF datatype URIRef.

    Args:
        datatype_str: Datatype string in prefix:localname format

    Returns:
        URIRef for the datatype, or None if parsing fails
    """
    if not datatype_str:
        return None

    # Handle xsd: prefix
    if datatype_str.startswith("xsd:"):
        local_name = datatype_str.split(":", 1)[1]
        # Map to XSD namespace
        xsd_types = {
            "string": XSD.string,
            "integer": XSD.integer,
            "int": XSD.integer,
            "decimal": XSD.decimal,
            "float": XSD.float,
            "double": XSD.double,
            "boolean": XSD.boolean,
            "date": XSD.date,
            "dateTime": XSD.dateTime,
            "time": XSD.time,
            "gYear": XSD.gYear,
            "gYearMonth": XSD.gYearMonth,
            "anyURI": XSD.anyURI,
        }
        return xsd_types.get(local_name)

    return None


def _infer_datatype(field_name: str, value: Any) -> URIRef | None:
    """
    Infer XSD datatype based on field name and value (legacy fallback).

    Args:
        field_name: Name of the field
        value: Field value

    Returns:
        URIRef for the inferred datatype, or None for default string
    """
    # Special handling for publication year - combine conditions
    if (
        field_name == "publication_year"
        and isinstance(value, int | str)
        and str(value).isdigit()
        and len(str(value)) == 4
    ):
        return XSD.gYear

    # Handle integers
    if isinstance(value, int) and not isinstance(value, bool):
        return XSD.integer

    # Handle floats/decimals
    if isinstance(value, float):
        return XSD.decimal

    # Handle booleans
    if isinstance(value, bool):
        return XSD.boolean

    # Handle dates (check for ISO date format)
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return XSD.date

    # Handle year-only dates
    if isinstance(value, str) and re.match(r"^\d{4}$", value):
        return XSD.gYear

    # Handle URLs
    if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
        return XSD.anyURI

    # Default: no specific datatype (will be xsd:string by default)
    return None


def map_multi_value_fields(
    g: Any,
    subject: URIRef,
    entity: Any,
    multi_value_mapping: dict[str, str],
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None = None,
) -> None:
    """Map multi-value fields to RDF triples."""
    for field_name, predicate_str in multi_value_mapping.items():
        values = getattr(entity, field_name, None)
        if values is not None and isinstance(values, list):
            predicate = resolve_predicate(predicate_str)
            for value in values:
                if value is not None:
                    if context:
                        g.graph(context).add((subject, predicate, Literal(value)))
                    else:
                        g.add((subject, predicate, Literal(value)))


def map_paper_ontology_alignments(
    g: Any,
    subject: URIRef,
    entity: Any,
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None = None,
) -> None:
    """
    Map ontology alignments for paper entities with enhanced MeSH support.

    Uses official MeSH vocabulary (meshv:) for proper semantic representation.
    Handles both simple string MeSH terms and structured MeSHHeadingEntity objects
    with qualifiers, creating proper semantic relationships in RDF.
    """
    from pyeuropepmc.models.mesh import MeSHHeadingEntity

    # MeSH terms alignment - handle both string and structured entities
    if not (hasattr(entity, "mesh_terms") and entity.mesh_terms):
        # If no mesh_terms but keywords exist, map keywords as simple MeSH terms
        if hasattr(entity, "keywords") and entity.keywords:
            for keyword in entity.keywords:
                if isinstance(keyword, str) and keyword.strip():
                    _add_simple_mesh_term(g, subject, keyword, resolve_predicate, context)
        return

    for mesh_term in entity.mesh_terms:
        # Handle structured MeSH heading with qualifiers
        if isinstance(mesh_term, MeSHHeadingEntity):
            _add_structured_mesh_term(g, subject, mesh_term, resolve_predicate, context)
        # Handle simple string MeSH term (backward compatibility)
        elif isinstance(mesh_term, str) and mesh_term.strip():
            _add_simple_mesh_term(g, subject, mesh_term, resolve_predicate, context)


def _add_structured_mesh_term(
    g: Any,
    subject: URIRef,
    mesh_term: Any,
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None,
) -> None:
    """Add structured MeSH heading with qualifiers to RDF graph."""
    # Create MeSH descriptor URI (normalized)
    descriptor_normalized = mesh_term.descriptor_name.replace(" ", "_")
    mesh_uri = URIRef(f"http://id.nlm.nih.gov/mesh/{descriptor_normalized}")

    # Declare as MeSH Descriptor using official vocabulary
    _add_triple(
        g,
        mesh_uri,
        resolve_predicate("rdf:type"),
        resolve_predicate("meshv:Descriptor"),
        context,
    )

    # Link paper to descriptor using meshv:hasDescriptor
    _add_triple(g, subject, resolve_predicate("meshv:hasDescriptor"), mesh_uri, context)

    # Add preferred label and standard label
    _add_triple(
        g,
        mesh_uri,
        resolve_predicate("meshv:prefLabel"),
        Literal(mesh_term.descriptor_name),
        context,
    )
    _add_triple(
        g,
        mesh_uri,
        resolve_predicate("rdfs:label"),
        Literal(mesh_term.descriptor_name),
        context,
    )

    # Add descriptor UI if available
    if mesh_term.descriptor_ui:
        _add_triple(
            g,
            mesh_uri,
            resolve_predicate("meshv:identifier"),
            Literal(mesh_term.descriptor_ui),
            context,
        )

    # Handle qualifiers using official MeSH vocabulary
    for qualifier in mesh_term.qualifiers:
        _add_mesh_qualifier(
            g, subject, mesh_uri, qualifier, descriptor_normalized, resolve_predicate, context
        )


def _add_mesh_qualifier(
    g: Any,
    subject: URIRef,
    mesh_uri: URIRef,
    qualifier: Any,
    descriptor_normalized: str,
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None,
) -> None:
    """Add MeSH qualifier and DescriptorQualifierPair to RDF graph."""
    qualifier_normalized = qualifier.qualifier_name.replace(" ", "_")
    qualifier_uri = URIRef(f"http://id.nlm.nih.gov/mesh/{qualifier_normalized}")

    # Declare as MeSH Qualifier
    _add_triple(
        g,
        qualifier_uri,
        resolve_predicate("rdf:type"),
        resolve_predicate("meshv:Qualifier"),
        context,
    )

    # Create DescriptorQualifierPair
    pair_uri = URIRef(
        f"http://id.nlm.nih.gov/mesh/{descriptor_normalized}_{qualifier_normalized}_pair"
    )

    _add_triple(
        g,
        pair_uri,
        resolve_predicate("rdf:type"),
        resolve_predicate("meshv:DescriptorQualifierPair"),
        context,
    )
    _add_triple(g, pair_uri, resolve_predicate("meshv:hasDescriptor"), mesh_uri, context)
    _add_triple(g, pair_uri, resolve_predicate("meshv:hasQualifier"), qualifier_uri, context)
    _add_triple(g, subject, resolve_predicate("meshv:hasDescriptor"), pair_uri, context)

    # Add qualifier labels and abbreviation
    _add_triple(
        g,
        qualifier_uri,
        resolve_predicate("meshv:prefLabel"),
        Literal(qualifier.qualifier_name),
        context,
    )
    _add_triple(
        g,
        qualifier_uri,
        resolve_predicate("rdfs:label"),
        Literal(qualifier.qualifier_name),
        context,
    )
    if qualifier.abbreviation:
        _add_triple(
            g,
            qualifier_uri,
            resolve_predicate("meshv:abbreviation"),
            Literal(qualifier.abbreviation),
            context,
        )


def _add_simple_mesh_term(
    g: Any,
    subject: URIRef,
    mesh_term: str,
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None,
) -> None:
    """Add simple string MeSH term to RDF graph (backward compatibility)."""
    _add_triple(
        g,
        subject,
        resolve_predicate("meshv:hasDescriptor"),
        Literal(mesh_term.strip()),
        context,
    )


def _add_triple(
    g: Any, subject: URIRef, predicate: URIRef, obj: URIRef | Literal, context: URIRef | None
) -> None:
    """Helper to add triple to graph with or without context."""
    if context:
        g.graph(context).add((subject, predicate, obj))
    else:
        g.add((subject, predicate, obj))


# Legacy function kept for backward compatibility
def _map_paper_ontology_alignments_legacy(
    g: Any,
    subject: URIRef,
    entity: Any,
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None = None,
) -> None:
    """Legacy function - kept for backward compatibility. Use map_paper_ontology_alignments."""
    map_paper_ontology_alignments(g, subject, entity, resolve_predicate, context)


# Original continuation of map_paper_ontology_alignments
def _finalize_ontology_alignments(
    g: Any,
    subject: URIRef,
    entity: Any,
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None = None,
) -> None:
    """Finalize ontology alignments with keywords mapping."""
    # Also map keywords as MeSH terms for backward compatibility
    if hasattr(entity, "keywords") and entity.keywords:
        for keyword in entity.keywords:
            if isinstance(keyword, str) and keyword.strip():
                if context:
                    g.graph(context).add(
                        (subject, resolve_predicate("mesh:hasSubject"), Literal(keyword.strip()))
                    )
                else:
                    g.add(
                        (subject, resolve_predicate("mesh:hasSubject"), Literal(keyword.strip()))
                    )

    # Research domain classification (placeholder)
    if hasattr(entity, "research_domain"):
        if context:
            g.graph(context).add(
                (
                    subject,
                    resolve_predicate("obo:RO_0000053"),
                    Literal(entity.research_domain),
                )
            )
        else:
            g.add(
                (
                    subject,
                    resolve_predicate("obo:RO_0000053"),
                    Literal(entity.research_domain),
                )
            )


def map_author_ontology_alignments(
    g: Any,
    subject: URIRef,
    entity: Any,
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None = None,
) -> None:
    """Map ontology alignments for author entities."""
    # Note: Institutions are now handled via relationships instead of literal affiliations
    pass


def map_institution_ontology_alignments(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """Map ontology alignments for institution entities."""
    # Add geographic coordinates if available
    if (
        hasattr(entity, "latitude")
        and hasattr(entity, "longitude")
        and entity.latitude is not None
        and entity.longitude is not None
    ):
        # Already handled in fields mapping, but can add geo:SpatialThing type
        g.add(
            (
                subject,
                resolve_predicate("rdf:type"),
                URIRef("http://www.w3.org/2003/01/geo/wgs84_pos#SpatialThing"),
            )
        )


def map_reference_ontology_alignments(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """Map ontology alignments for reference entities."""
    # Currently no specific alignments for references
    pass


def add_paper_identifiers(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """Add external identifiers for paper."""
    if entity.doi:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://doi.org/{entity.doi}"),
            )
        )
    if entity.pmcid:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{entity.pmcid}/"),
            )
        )
        # Add Europe PMC link for PMC articles (strip PMC prefix if present)
        pmcid_numeric = (
            entity.pmcid.replace("PMC", "") if entity.pmcid.startswith("PMC") else entity.pmcid
        )
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://europepmc.org/article/PMC/{pmcid_numeric}/"),
            )
        )
    if entity.pmid:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://pubmed.ncbi.nlm.nih.gov/{entity.pmid}/"),
            )
        )
        # Add Europe PMC link for PubMed articles
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://europepmc.org/article/MED/{entity.pmid}"),
            )
        )


def add_author_identifiers(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """Add external identifiers for author."""
    if hasattr(entity, "orcid") and entity.orcid:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://orcid.org/{entity.orcid}"),
            )
        )
    if hasattr(entity, "openalex_id") and entity.openalex_id:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(entity.openalex_id),
            )
        )


def add_institution_identifiers(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """Add external identifiers for institution."""
    if hasattr(entity, "ror_id") and entity.ror_id:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(entity.ror_id),
            )
        )
    if hasattr(entity, "openalex_id") and entity.openalex_id:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(entity.openalex_id),
            )
        )
    if hasattr(entity, "wikidata_id") and entity.wikidata_id:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://www.wikidata.org/wiki/{entity.wikidata_id}"),
            )
        )


def add_reference_identifiers(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """Add external identifiers for reference."""
    if hasattr(entity, "doi") and entity.doi:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://doi.org/{entity.doi}"),
            )
        )
    if hasattr(entity, "pmid") and entity.pmid:
        g.add(
            (
                subject,
                resolve_predicate("owl:sameAs"),
                URIRef(f"https://pubmed.ncbi.nlm.nih.gov/{entity.pmid}/"),
            )
        )


def add_external_identifiers(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """Add owl:sameAs links for external identifiers."""
    entity_class_name = entity.__class__.__name__

    # Map entity class names to their identifier addition functions
    identifier_adders = {
        "PaperEntity": add_paper_identifiers,
        "AuthorEntity": add_author_identifiers,
        "InstitutionEntity": add_institution_identifiers,
        "ReferenceEntity": add_reference_identifiers,
    }

    # Get the appropriate adder function, skip if not found
    adder = identifier_adders.get(entity_class_name)
    if adder:
        adder(g, subject, entity, resolve_predicate)


def map_ontology_alignments(
    g: Any,
    subject: URIRef,
    entity: Any,
    resolve_predicate: Callable[[str], URIRef],
    context: URIRef | None = None,
) -> None:
    """
    Add ontology alignment placeholders and biomedical mappings.
    """
    entity_class_name = entity.__class__.__name__

    if entity_class_name == "PaperEntity":
        map_paper_ontology_alignments(g, subject, entity, resolve_predicate, context)
    elif entity_class_name == "AuthorEntity":
        map_author_ontology_alignments(g, subject, entity, resolve_predicate, context)
    elif entity_class_name == "InstitutionEntity":
        map_institution_ontology_alignments(g, subject, entity, resolve_predicate)
    elif entity_class_name == "ReferenceEntity":
        map_reference_ontology_alignments(g, subject, entity, resolve_predicate)

    # Add owl:sameAs links for external identifiers
    add_external_identifiers(g, subject, entity, resolve_predicate)
