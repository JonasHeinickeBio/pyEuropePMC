"""
Modular RDF Conversion Functions for PyEuropePMC.

This module provides separate and combined functions for converting different
data sources (search results, XML data, enrichment data) to RDF graphs.
Functions are designed to be modular, reusable, and configurable.
"""

from collections.abc import Callable
import logging
from typing import Any

from rdflib import Graph, Namespace

from pyeuropepmc.cache.cache import CacheBackend, CacheDataType
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.models import (
    PaperEntity,
)
from pyeuropepmc.processing.search_parser import EuropePMCParser

logger = logging.getLogger(__name__)


class RDFConversionError(Exception):
    """Exception raised for RDF conversion errors."""

    pass


def _get_default_mapper(config_path: str | None = None) -> RDFMapper:
    """
    Get a default RDFMapper instance with standard configuration.

    Parameters
    ----------
    config_path : Optional[str]
        Path to custom RDF mapping configuration file

    Returns
    -------
    RDFMapper
        Configured RDF mapper instance
    """
    return RDFMapper(config_path=config_path)


def _setup_graph(namespaces: dict[str, str] | None = None) -> Graph:
    """
    Create and configure a new RDF graph with standard namespaces.

    Parameters
    ----------
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind (prefix -> URI)

    Returns
    -------
    Graph
        Configured RDF graph
    """
    g = Graph()

    # Load namespaces from RDF mapping configuration
    try:
        import os
        from pathlib import Path

        import yaml

        # Default to conf/rdf_map.yml in project root
        base_path = Path(__file__).parent.parent.parent.parent
        config_path = str(base_path / "conf" / "rdf_map.yml")

        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Get namespaces from _@prefix section
            prefix_config = config.get("_@prefix", {})
            for prefix, uri in prefix_config.items():
                g.bind(prefix, Namespace(uri))
        else:
            # Fallback to hardcoded namespaces if config file not found
            logger.warning(
                f"RDF mapping config not found at {config_path}, using fallback namespaces"
            )
            _bind_fallback_namespaces(g)
    except Exception as e:
        logger.warning(f"Failed to load RDF mapping config: {e}, using fallback namespaces")
        _bind_fallback_namespaces(g)

    # Bind additional namespaces if provided
    if namespaces:
        for prefix, uri in namespaces.items():
            g.bind(prefix, Namespace(uri))

    return g


def _bind_fallback_namespaces(g: Graph) -> None:
    """
    Bind fallback namespaces when config file cannot be loaded.

    Parameters
    ----------
    g : Graph
        RDF graph to bind namespaces to
    """
    fallback_namespaces = {
        "ex": "http://example.org/",
        "dcterms": "http://purl.org/dc/terms/",
        "foaf": "http://xmlns.com/foaf/0.1/",
        "bibo": "http://purl.org/ontology/bibo/",
        "prov": "http://www.w3.org/ns/prov#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "nif": "http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "mesh": "http://id.nlm.nih.gov/mesh/",
        "obo": "http://purl.obolibrary.org/obo/",
        "org": "http://www.w3.org/ns/org#",
        "cito": "http://purl.org/spar/cito/",
        "datacite": "http://purl.org/spar/datacite/",
        "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        "ror": "https://ror.org/vocab#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
    }

    for prefix, uri in fallback_namespaces.items():
        g.bind(prefix, Namespace(uri))


def _convert_to_rdf(
    data: Any,
    validator: Callable[[Any], None],
    processor: Callable[..., list[dict[str, Any]]],
    cache_key_prefix: str,
    cache_data_type: CacheDataType,
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
    **processor_kwargs: Any,
) -> Graph:
    """
    Generic RDF conversion function that handles common conversion logic.

    Parameters
    ----------
    data : Any
        Input data to convert
    validator : callable
        Function to validate input data
    processor : callable
        Function to process data into entities_data format
    cache_key_prefix : str
        Prefix for cache key generation
    cache_data_type : CacheDataType
        Type of data for caching
    config_path : Optional[str]
        Path to custom RDF mapping configuration file
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind
    cache_backend : Optional[CacheBackend]
        Cache backend for storing conversion results
    extraction_info : Optional[Dict[str, Any]]
        Metadata about the extraction process
    **processor_kwargs
        Additional keyword arguments for the processor function

    Returns
    -------
    Graph
        RDF graph containing converted data

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    try:
        validator(data)

        mapper = _get_default_mapper(config_path)
        g = _setup_graph(namespaces)

        # Process data into entities format
        entities_data = processor(data, **processor_kwargs)

        # Convert entities to RDF
        for entity_data in entities_data:
            entity = entity_data["entity"]
            related_entities = entity_data.get("related_entities", {})

            try:
                entity.to_rdf(
                    g,
                    mapper=mapper,
                    related_entities=related_entities,
                    extraction_info=extraction_info,
                )
            except Exception as e:
                logger.warning(f"Failed to convert entity {entity} to RDF: {e}")
                continue

        # Cache the result if cache backend is provided
        if cache_backend:
            cache_key = f"{cache_key_prefix}_{hash(str(data))}"
            cache_backend.set(cache_key, g, data_type=cache_data_type)

        return g

    except Exception as e:
        raise RDFConversionError(f"Failed to convert data to RDF: {e}") from e


def _validate_search_results(search_results: Any) -> None:
    """
    Validate search results data structure.

    Parameters
    ----------
    search_results : Any
        Search results to validate

    Raises
    ------
    RDFConversionError
        If search results are invalid
    """
    if search_results is None:
        raise RDFConversionError("Search results cannot be None")

    if not search_results:
        raise RDFConversionError("Search results cannot be empty")

    # Check type
    if not isinstance(search_results, list | dict):
        raise RDFConversionError("Search results must be a list or dict")

    # If it's a list, check that it contains dicts
    if isinstance(search_results, list) and not all(
        isinstance(item, dict) for item in search_results
    ):
        raise RDFConversionError("All search results must be dictionaries")


def _validate_xml_data(xml_data: Any) -> None:
    """
    Validate XML parsing results data structure.

    Parameters
    ----------
    xml_data : Any
        XML data to validate

    Raises
    ------
    RDFConversionError
        If XML data is invalid
    """
    if xml_data is None:
        raise RDFConversionError("XML data cannot be None")

    if not xml_data:
        raise RDFConversionError("XML data cannot be empty")

    # Check type
    if not isinstance(xml_data, dict):
        raise RDFConversionError("XML data must be a dictionary")


def _validate_enrichment_data(enrichment_data: Any) -> None:
    """
    Validate enrichment data structure.

    Parameters
    ----------
    enrichment_data : Any
        Enrichment data to validate

    Raises
    ------
    RDFConversionError
        If enrichment data is invalid
    """
    if enrichment_data is None:
        raise RDFConversionError("Enrichment data cannot be None")

    if not enrichment_data:
        raise RDFConversionError("Enrichment data cannot be empty")

    # Check type
    if not isinstance(enrichment_data, dict):
        raise RDFConversionError("Enrichment data must be a dictionary")


def _process_search_results(
    search_results: list[dict[str, Any]] | dict[str, Any],
) -> list[dict[str, Any]]:
    """Process search results into entities_data format."""
    entities_data = []

    # Handle both single result and list of results
    results_list = [search_results] if isinstance(search_results, dict) else search_results

    for result in results_list:
        try:
            # Create a basic paper entity from search result
            parser = EuropePMCParser()
            paper_entity, related_entities = parser.create_paper_entity_from_result(result)
            entities_data.append(
                {
                    "entity": paper_entity,
                    "related_entities": related_entities,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to process search result: {e}")
            continue

    return entities_data


def _process_xml_data(
    xml_data: dict[str, Any], include_content: bool = True
) -> list[dict[str, Any]]:
    """Process XML data into entities_data format."""
    return _extract_entities_from_xml(xml_data, include_content)


def _process_enrichment_data(enrichment_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Process enrichment data into entities_data format."""
    return _extract_entities_from_enrichment(enrichment_data)


def convert_search_to_rdf(
    search_results: list[dict[str, Any]] | dict[str, Any],
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
) -> Graph:
    """
    Convert search results directly to RDF graph.

    This function creates RDF representations of search result metadata,
    including basic paper information, identifiers, and search context.

    Parameters
    ----------
    search_results : Union[List[Dict[str, Any]], Dict[str, Any]]
        Search results from Europe PMC API
    config_path : Optional[str]
        Path to custom RDF mapping configuration file
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind
    cache_backend : Optional[CacheBackend]
        Cache backend for storing conversion results
    extraction_info : Optional[Dict[str, Any]]
        Metadata about the extraction process

    Returns
    -------
    Graph
        RDF graph containing search result representations

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    return _convert_to_rdf(
        data=search_results,
        validator=_validate_search_results,
        processor=_process_search_results,
        cache_key_prefix="search_rdf",
        cache_data_type=CacheDataType.SEARCH,
        config_path=config_path,
        namespaces=namespaces,
        cache_backend=cache_backend,
        extraction_info=extraction_info,
    )


def convert_xml_to_rdf(
    xml_data: dict[str, Any],
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
    include_content: bool = True,
) -> Graph:
    """
    Convert XML parsing results to RDF graph.

    This function creates comprehensive RDF representations from parsed XML data,
    including paper metadata, authors, institutions, and optionally content elements.

    Parameters
    ----------
    xml_data : Dict[str, Any]
        Parsed XML data from fulltext processing
    config_path : Optional[str]
        Path to custom RDF mapping configuration file
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind
    cache_backend : Optional[CacheBackend]
        Cache backend for storing conversion results
    extraction_info : Optional[Dict[str, Any]]
        Metadata about the extraction process
    include_content : bool
        Whether to include content entities (sections, tables, figures)

    Returns
    -------
    Graph
        RDF graph containing XML data representations

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    return _convert_to_rdf(
        data=xml_data,
        validator=_validate_xml_data,
        processor=_process_xml_data,
        cache_key_prefix="xml_rdf",
        cache_data_type=CacheDataType.FULLTEXT,
        config_path=config_path,
        namespaces=namespaces,
        cache_backend=cache_backend,
        extraction_info=extraction_info,
        include_content=include_content,
    )


def convert_enrichment_to_rdf(
    enrichment_data: dict[str, Any],
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
) -> Graph:
    """
    Convert enrichment data to RDF graph.

    This function creates RDF representations of enriched metadata from external sources,
    including additional author information, citations, and institutional data.

    Parameters
    ----------
    enrichment_data : Dict[str, Any]
        Enrichment data from external APIs (Semantic Scholar, OpenAlex, etc.)
    config_path : Optional[str]
        Path to custom RDF mapping configuration file
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind
    cache_backend : Optional[CacheBackend]
        Cache backend for storing conversion results
    extraction_info : Optional[Dict[str, Any]]
        Metadata about the extraction process

    Returns
    -------
    Graph
        RDF graph containing enrichment data representations

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    return _convert_to_rdf(
        data=enrichment_data,
        validator=_validate_enrichment_data,
        processor=_process_enrichment_data,
        cache_key_prefix="enrichment_rdf",
        cache_data_type=CacheDataType.RECORD,
        config_path=config_path,
        namespaces=namespaces,
        cache_backend=cache_backend,
        extraction_info=extraction_info,
    )


def convert_pipeline_to_rdf(
    search_results: list[dict[str, Any]] | dict[str, Any] | None = None,
    xml_data: dict[str, Any] | None = None,
    enrichment_data: dict[str, Any] | None = None,
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
    include_content: bool = True,
) -> Graph:
    """
    Convert complete pipeline data (search + XML + enrichment) to RDF graph.

    This function combines all data sources into a comprehensive RDF representation,
    merging information from search results, XML parsing, and enrichment data.

    Parameters
    ----------
    search_results : Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]
        Search results from Europe PMC API
    xml_data : Optional[Dict[str, Any]]
        Parsed XML data from fulltext processing
    enrichment_data : Optional[Dict[str, Any]]
        Enrichment data from external APIs
    config_path : Optional[str]
        Path to custom RDF mapping configuration file
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind
    cache_backend : Optional[CacheBackend]
        Cache backend for storing conversion results
    extraction_info : Optional[Dict[str, Any]]
        Metadata about the extraction process
    include_content : bool
        Whether to include content entities from XML data

    Returns
    -------
    Graph
        RDF graph containing combined pipeline data representations

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    try:
        g = _setup_graph(namespaces)

        # Convert each data source and merge into single graph
        if search_results:
            search_graph = convert_search_to_rdf(
                search_results, config_path, namespaces, None, extraction_info
            )
            g += search_graph

        if xml_data:
            xml_graph = convert_xml_to_rdf(
                xml_data, config_path, namespaces, None, extraction_info, include_content
            )
            g += xml_graph

        if enrichment_data:
            enrichment_graph = convert_enrichment_to_rdf(
                enrichment_data, config_path, namespaces, None, extraction_info
            )
            g += enrichment_graph

        # Cache the result if cache backend is provided
        if cache_backend:
            combined_str = (
                str(search_results or {}) + str(xml_data or {}) + str(enrichment_data or {})
            )
            cache_key = f"pipeline_rdf_{hash(combined_str)}"
            cache_backend.set(cache_key, g, data_type=CacheDataType.FULLTEXT)

        return g

    except Exception as e:
        raise RDFConversionError(f"Failed to convert pipeline data to RDF: {e}") from e


def convert_incremental_to_rdf(
    base_rdf: Graph,
    enrichment_data: dict[str, Any],
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
) -> Graph:
    """
    Add enrichment data to existing RDF graph incrementally.

    This function takes an existing RDF graph and adds enrichment information
    without recreating the base content, useful for progressive enhancement.

    Parameters
    ----------
    base_rdf : Graph
        Existing RDF graph to enhance
    enrichment_data : Dict[str, Any]
        Enrichment data to add
    config_path : Optional[str]
        Path to custom RDF mapping configuration file
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind
    cache_backend : Optional[CacheBackend]
        Cache backend for storing conversion results
    extraction_info : Optional[Dict[str, Any]]
        Metadata about the extraction process

    Returns
    -------
    Graph
        Enhanced RDF graph with enrichment data added

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    try:
        _validate_enrichment_data(enrichment_data)

        # Create a copy of the base graph to avoid modifying the original
        enhanced_graph = base_rdf + Graph()

        # Bind any additional namespaces
        if namespaces:
            for prefix, uri in namespaces.items():
                enhanced_graph.bind(prefix, Namespace(uri))

        mapper = _get_default_mapper(config_path)

        # Process enrichment data and add to existing graph
        entities_data = _extract_entities_from_enrichment(enrichment_data)

        for entity_data in entities_data:
            entity = entity_data["entity"]
            related_entities = entity_data.get("related_entities", {})

            try:
                entity.to_rdf(
                    enhanced_graph,
                    mapper=mapper,
                    related_entities=related_entities,
                    extraction_info=extraction_info,
                )
            except Exception as e:
                logger.warning(f"Failed to add enriched entity {entity} to RDF: {e}")
                continue

        # Cache the result if cache backend is provided
        if cache_backend:
            cache_key = f"incremental_rdf_{hash(str(base_rdf) + str(enrichment_data))}"
            cache_backend.set(cache_key, enhanced_graph, data_type=CacheDataType.RECORD)

        return enhanced_graph

    except Exception as e:
        raise RDFConversionError(f"Failed to convert incremental enrichment to RDF: {e}") from e


# Helper functions for data extraction and entity creation


def _extract_entities_from_xml(
    xml_data: dict[str, Any], include_content: bool
) -> list[dict[str, Any]]:
    """Extract entities from parsed XML data."""
    entities_data = []

    # Assume xml_data contains parsed structure from FullTextXMLParser
    # This would typically come from build_paper_entities function

    if "paper" in xml_data:
        paper_data = xml_data["paper"]
        # Create a proper PaperEntity from the XML data
        paper_entity = PaperEntity(
            doi=paper_data.get("doi"),
            pmcid=paper_data.get("pmcid"),
            pmid=paper_data.get("pmid"),
            title=paper_data.get("title"),
            abstract=paper_data.get("abstract"),
            journal=paper_data.get("journal"),
            publication_year=paper_data.get("publication_year"),
            authors=paper_data.get("authors", []),
            keywords=paper_data.get("keywords", []),
        )
        entities_data.append(
            {
                "entity": paper_entity,
                "related_entities": {
                    "authors": xml_data.get("authors", []),
                    "sections": xml_data.get("sections", []) if include_content else [],
                    "tables": xml_data.get("tables", []) if include_content else [],
                    "figures": xml_data.get("figures", []) if include_content else [],
                    "references": xml_data.get("references", []) if include_content else [],
                },
            }
        )

    return entities_data


def _extract_entities_from_enrichment(enrichment_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract entities from enrichment data."""
    entities_data = []

    # Enrichment data typically contains enhanced metadata for papers/authors
    # Structure depends on the merger output

    # If enrichment data contains paper-level information
    if "paper" in enrichment_data:
        paper_data = enrichment_data["paper"]
        # Create a proper PaperEntity from the enrichment data
        paper_entity = PaperEntity(
            doi=paper_data.get("doi"),
            pmcid=paper_data.get("pmcid"),
            pmid=paper_data.get("pmid"),
            title=paper_data.get("title"),
            abstract=paper_data.get("abstract"),
            journal=paper_data.get("journal"),
            publication_year=paper_data.get("publication_year"),
            authors=paper_data.get("authors", []),
            keywords=paper_data.get("keywords", []),
        )
        entities_data.append(
            {
                "entity": paper_entity,
                "related_entities": {
                    "authors": enrichment_data.get("authors", []),
                },
            }
        )

    # If enrichment data contains author-level information
    elif "authors" in enrichment_data:
        # Create entities for enriched authors
        for author_data in enrichment_data["authors"]:
            entities_data.append({"entity": author_data, "related_entities": {}})

    return entities_data
