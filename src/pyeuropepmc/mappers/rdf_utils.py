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
    if not name:
        return None

    # Remove non-alphanumeric except spaces, lowercase, replace spaces with hyphens
    normalized = re.sub(r"[^a-zA-Z0-9\s]", "", name).lower().strip()
    normalized = re.sub(r"\s+", "-", normalized)
    return normalized if normalized else None


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
    if not display_name:
        return str(uuid.uuid4())[:8]

    # Clean the name
    name = display_name.strip()

    # Remove common suffixes that don't add meaning
    name = re.sub(
        r",\s*(?:USA|United States|UK|United Kingdom|Canada|Australia|"
        r"Germany|France|Italy|Spain|Japan|China|India)(?:\..*)?$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    # Split by commas and take the first meaningful part
    parts = [part.strip() for part in name.split(",") if part.strip()]

    if not parts:
        return str(uuid.uuid4())[:8]

    # Take the first part as the main institution name
    main_name = parts[0]

    # Remove common prefixes/suffixes that make names longer
    main_name = re.sub(r"^(?:the\s+)?", "", main_name, flags=re.IGNORECASE)
    main_name = re.sub(
        r"(?:\s+(?:university|college|institute|center|centre|hospital|school|department|division|program|unit|group|laboratory|lab|clinic))$",
        "",
        main_name,
        flags=re.IGNORECASE,
    )

    # If the main name is still too long, take first few words
    words = main_name.split()
    if len(words) > 4:
        main_name = " ".join(words[:4])

    # Normalize the result
    normalized = normalize_name(main_name)

    if normalized and len(normalized) <= 50:  # Reasonable length limit
        return normalized

    # If still too long or empty, create a hash-based identifier
    import hashlib

    hash_obj = hashlib.md5(display_name.encode("utf-8"))  # nosec B324
    return hash_obj.hexdigest()[:12]


def generate_paper_uri(entity: Any) -> URIRef:
    """Generate URI for paper entity."""
    if entity.doi:
        return URIRef(f"https://doi.org/{entity.doi}")
    if entity.pmcid:
        return URIRef(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{entity.pmcid}/")
    return generate_fallback_uri(entity)


def generate_author_uri(entity: Any) -> URIRef:
    """Generate URI for author entity."""
    if getattr(entity, "orcid", None):
        return URIRef(f"https://orcid.org/{entity.orcid}")
    if getattr(entity, "openalex_id", None):
        return URIRef(entity.openalex_id)
    normalized_name = normalize_name(
        getattr(entity, "full_name", "") or getattr(entity, "name", "")
    )
    if normalized_name:
        return URIRef(f"http://example.org/data/author/{normalized_name}")
    return generate_fallback_uri(entity)


def generate_institution_uri(entity: Any) -> URIRef:
    """Generate URI for institution entity."""
    if getattr(entity, "ror_id", None):
        return URIRef(entity.ror_id)
    if getattr(entity, "openalex_id", None):
        return URIRef(entity.openalex_id)
    if getattr(entity, "display_name", None):
        # Create a more compact URI by extracting key institution name
        compact_id = generate_compact_institution_id(entity.display_name)
        return URIRef(f"http://example.org/data/institution/{compact_id}")
    return generate_fallback_uri(entity)


def generate_reference_uri(entity: Any) -> URIRef:
    """Generate URI for reference entity."""
    if getattr(entity, "doi", None):
        return URIRef(f"https://doi.org/{entity.doi}")
    elif getattr(entity, "pmid", None):
        return URIRef(f"https://pubmed.ncbi.nlm.nih.gov/{entity.pmid}/")
    return generate_fallback_uri(entity)


def generate_fallback_uri(entity: Any) -> URIRef:
    """Generate fallback URI for entity."""
    if hasattr(entity, "mint_uri"):
        return URIRef(entity.mint_uri(entity.__class__.__name__.lower().replace("entity", "")))
    else:
        # Generate UUID-based URI
        entity_id = getattr(entity, "id", None) or str(uuid.uuid4())
        class_name = entity.__class__.__name__.lower().replace("entity", "")
        return URIRef(f"http://example.org/data/{class_name}/{entity_id}")


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
    entity_class = entity.__class__.__name__

    # Map entity class names to their URI generation functions
    uri_generators = {
        "PaperEntity": generate_paper_uri,
        "AuthorEntity": generate_author_uri,
        "InstitutionEntity": generate_institution_uri,
        "ReferenceEntity": generate_reference_uri,
    }

    # Get the appropriate generator function, default to fallback
    generator = uri_generators.get(entity_class, generate_fallback_uri)
    return generator(entity)


def map_single_value_fields(
    g: Graph,
    subject: URIRef,
    entity: Any,
    fields_mapping: dict[str, str],
    resolve_predicate: Callable[[str], URIRef],
) -> None:
    """Map single-value fields to RDF triples."""
    for field_name, predicate_str in fields_mapping.items():
        value = getattr(entity, field_name, None)
        if value is not None:
            predicate = resolve_predicate(predicate_str)
            g.add((subject, predicate, Literal(value)))


def map_multi_value_fields(
    g: Graph,
    subject: URIRef,
    entity: Any,
    multi_value_mapping: dict[str, str],
    resolve_predicate: Callable[[str], URIRef],
) -> None:
    """Map multi-value fields to RDF triples."""
    for field_name, predicate_str in multi_value_mapping.items():
        values = getattr(entity, field_name, None)
        if values is not None and isinstance(values, list):
            predicate = resolve_predicate(predicate_str)
            for value in values:
                if value is not None:
                    g.add((subject, predicate, Literal(value)))


def map_paper_ontology_alignments(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """Map ontology alignments for paper entities."""
    # MeSH terms alignment (placeholder)
    if hasattr(entity, "keywords") and entity.keywords:
        for keyword in entity.keywords:
            g.add((subject, resolve_predicate("mesh:hasSubject"), Literal(keyword)))

    # Research domain classification (placeholder)
    if hasattr(entity, "research_domain"):
        g.add(
            (
                subject,
                resolve_predicate("obo:RO_0000053"),
                Literal(entity.research_domain),
            )
        )


def map_author_ontology_alignments(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
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
    g: Graph, subject: URIRef, entity: Any, resolve_predicate: Callable[[str], URIRef]
) -> None:
    """
    Add ontology alignment placeholders and biomedical mappings.
    """
    entity_class_name = entity.__class__.__name__

    if entity_class_name == "PaperEntity":
        map_paper_ontology_alignments(g, subject, entity, resolve_predicate)
    elif entity_class_name == "AuthorEntity":
        map_author_ontology_alignments(g, subject, entity, resolve_predicate)
    elif entity_class_name == "InstitutionEntity":
        map_institution_ontology_alignments(g, subject, entity, resolve_predicate)
    elif entity_class_name == "ReferenceEntity":
        map_reference_ontology_alignments(g, subject, entity, resolve_predicate)

    # Add owl:sameAs links for external identifiers
    add_external_identifiers(g, subject, entity, resolve_predicate)
