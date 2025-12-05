"""
Modular RDF Conversion Functions for PyEuropePMC.

This module provides separate and combined functions for converting different
data sources (search results, XML data, enrichment data) to RDF graphs.
Functions are designed to be modular, reusable, and configurable.

Enhanced features:
- Named graphs for better organization (authors, institutions, publications, provenance)
- Citation networks using CiTO ontology
- Author collaboration networks using VIVO ontology
- Institutional hierarchies using ORG ontology
- Quality metrics and temporal information
- SHACL validation support
- Data source attribution and provenance tracking
"""

from collections.abc import Callable
import logging
from typing import Any

from rdflib import Dataset, Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from pyeuropepmc.cache.cache import CacheBackend, CacheDataType
from pyeuropepmc.mappers.config_utils import (
    load_rdf_config,
    setup_dataset,
)
from pyeuropepmc.mappers.exceptions import RDFConversionError
from pyeuropepmc.mappers.processors import (
    _extract_entities_from_enrichment,
    process_enrichment_data,
    process_search_results,
    process_xml_data,
)
from pyeuropepmc.mappers.provenance import add_provenance_and_metadata, add_quality_metrics
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.mappers.semantic_enrichment import (
    build_citation_networks,
    build_collaboration_networks,
    build_institutional_hierarchies,
    process_enrichment_for_rdf,
    process_search_for_rdf,
    process_xml_for_rdf,
)
from pyeuropepmc.mappers.validation import add_shacl_validation_shapes
from pyeuropepmc.mappers.validators import (
    validate_enrichment_data,
    validate_search_results,
    validate_xml_data,
)

__all__ = [
    "RDFConversionError",
    "convert_search_to_rdf",
    "convert_xml_to_rdf",
    "convert_enrichment_to_rdf",
    "convert_pipeline_to_rdf",
    "convert_incremental_to_rdf",
    "convert_to_rdf",
]

logger = logging.getLogger(__name__)


def _get_default_mapper(
    config_path: str | None = None, enable_named_graphs: bool = True
) -> RDFMapper:
    """
    Get a default RDFMapper instance with standard configuration.

    Parameters
    ----------
    config_path : Optional[str]
        Path to custom RDF mapping configuration file
    enable_named_graphs : bool
        Whether to enable named graphs for entity organization

    Returns
    -------
    RDFMapper
        Configured RDF mapper instance
    """
    return RDFMapper(config_path=config_path, enable_named_graphs=enable_named_graphs)


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
    enable_named_graphs: bool = True,
    **processor_kwargs: Any,
) -> Dataset:
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
    Dataset
        RDF dataset containing converted data

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    try:
        validator(data)

        mapper = _get_default_mapper(config_path, enable_named_graphs)
        g = setup_dataset(namespaces)

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


def convert_search_to_rdf(
    search_results: list[dict[str, Any]] | dict[str, Any],
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
) -> Dataset:
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
    Dataset
        RDF dataset containing search result representations

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    return _convert_to_rdf(
        data=search_results,
        validator=validate_search_results,
        processor=process_search_results,
        cache_key_prefix="search_rdf",
        cache_data_type=CacheDataType.SEARCH,
        config_path=config_path,
        namespaces=namespaces,
        cache_backend=cache_backend,
        extraction_info=extraction_info,
        enable_named_graphs=False,
    )


def convert_xml_to_rdf(
    xml_data: dict[str, Any],
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
    include_content: bool = True,
) -> Dataset:
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
    Dataset
        RDF dataset containing XML data representations

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    return _convert_to_rdf(
        data=xml_data,
        validator=validate_xml_data,
        processor=process_xml_data,
        cache_key_prefix="xml_rdf",
        cache_data_type=CacheDataType.FULLTEXT,
        config_path=config_path,
        namespaces=namespaces,
        cache_backend=cache_backend,
        extraction_info=extraction_info,
        include_content=include_content,
        enable_named_graphs=False,
    )


def convert_enrichment_to_rdf(
    enrichment_data: dict[str, Any],
    config_path: str | None = None,
    namespaces: dict[str, str] | None = None,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
) -> Dataset:
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
    Dataset
        RDF dataset containing enrichment data representations

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    return _convert_to_rdf(
        data=enrichment_data,
        validator=validate_enrichment_data,
        processor=process_enrichment_data,
        cache_key_prefix="enrichment_rdf",
        cache_data_type=CacheDataType.RECORD,
        config_path=config_path,
        namespaces=namespaces,
        cache_backend=cache_backend,
        extraction_info=extraction_info,
        enable_named_graphs=False,
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
) -> Dataset:
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
    Dataset
        RDF dataset containing combined pipeline data representations

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    try:
        g = setup_dataset(namespaces)

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
        validate_enrichment_data(enrichment_data)

        # Create a copy of the base graph to avoid modifying the original
        enriched_graph = base_rdf + Graph()

        # Bind any additional namespaces
        if namespaces:
            for prefix, uri in namespaces.items():
                enriched_graph.bind(prefix, Namespace(uri))

        mapper = _get_default_mapper(config_path)

        # Process enrichment data and add to existing graph
        entities_data = _extract_entities_from_enrichment(enrichment_data)

        for entity_data in entities_data:
            entity = entity_data["entity"]
            related_entities = entity_data.get("related_entities", {})

            try:
                entity.to_rdf(
                    enriched_graph,
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
            cache_backend.set(cache_key, enriched_graph, data_type=CacheDataType.RECORD)

        return enriched_graph

    except Exception as e:
        raise RDFConversionError(f"Failed to convert incremental enrichment to RDF: {e}") from e


# Helper functions for data extraction and entity creation


def create_named_graph(name: str, title: str, description: str) -> Graph:
    """
    Create a named graph for better organization of RDF data.

    Parameters
    ----------
    name : str
        Name identifier for the graph
    title : str
        Human-readable title
    description : str
        Description of the graph's contents

    Returns
    -------
    Graph
        Configured named graph
    """
    ng = Graph()

    # Load RDF config for ontologies
    config = load_rdf_config()
    ontologies = config.get("ontologies", {})

    # Bind ontologies from config
    for prefix, uri in ontologies.items():
        ng.bind(prefix, Namespace(uri))

    # Bind standard namespaces
    ng.bind("rdf", RDF)
    ng.bind("rdfs", RDFS)
    ng.bind("xsd", XSD)

    return ng


def convert_to_rdf(  # noqa: C901
    search_results: list[dict[str, Any]] | dict[str, Any] | None = None,
    xml_data: dict[str, Any] | None = None,
    enrichment_data: dict[str, Any] | None = None,
    config_path: str | None = None,
    enable_citation_networks: bool = True,
    enable_collaboration_networks: bool = True,
    enable_institutional_hierarchies: bool = True,
    enable_quality_metrics: bool = True,
    enable_shacl_validation: bool = False,
    cache_backend: CacheBackend | None = None,
    extraction_info: dict[str, Any] | None = None,
) -> tuple[Dataset, dict[str, URIRef]]:
    """
    Convert data to RDF with semantic enrichment and named graphs.

    This function creates a comprehensive RDF knowledge graph with:
    - Named graphs for better organization
    - Citation networks using CiTO ontology
    - Author collaboration networks using VIVO ontology
    - Institutional hierarchies using ORG ontology
    - Quality metrics and temporal information
    - Optional SHACL validation

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
    enable_citation_networks : bool
        Whether to build citation networks
    enable_collaboration_networks : bool
        Whether to build author collaboration networks
    enable_institutional_hierarchies : bool
        Whether to build institutional hierarchies
    enable_quality_metrics : bool
        Whether to add quality metrics
    enable_shacl_validation : bool
        Whether to include SHACL validation shapes
    cache_backend : Optional[CacheBackend]
        Cache backend for storing conversion results
    extraction_info : Optional[Dict[str, Any]]
        Metadata about the extraction process

    Returns
    -------
    tuple[Dataset, dict[str, URIRef]]
        Main RDF dataset and dictionary of named graph URIs

    Raises
    ------
    RDFConversionError
        If conversion fails due to invalid input or processing errors
    """
    try:
        # Load RDF configuration
        rdf_config = load_rdf_config()

        # Initialize main dataset
        main_dataset = setup_dataset()
        named_graph_uris = {}

        # Create named graphs from configuration
        named_graphs_config = rdf_config.get("named_graphs", {})
        required_graphs = rdf_config.get("required_named_graphs", [])

        # Validate required named graphs are present and enabled
        for required_graph in required_graphs:
            if required_graph not in named_graphs_config:
                raise RDFConversionError(
                    f"Required named graph '{required_graph}' not found in configuration."
                )
            elif not named_graphs_config[required_graph].get("enabled", True):
                raise RDFConversionError(
                    f"Required named graph '{required_graph}' is disabled in configuration."
                )

        # Create enabled named graphs
        for graph_name, graph_config in named_graphs_config.items():
            if graph_config.get("enabled", True):
                logger.debug(f"Creating named graph: {graph_name}")
                named_graph_uris[graph_name] = URIRef(
                    graph_config.get(
                        "uri_base", f"https://github.com/JonasHeinickeBio/pyeuropepmc#{graph_name}"
                    )
                )
            else:
                logger.debug(f"Skipping disabled named graph: {graph_name}")

        mapper = _get_default_mapper(config_path)

        # Process search results
        if search_results:
            process_search_for_rdf(
                search_results, main_dataset, named_graph_uris, mapper, extraction_info
            )

        # Process XML data
        if xml_data:
            process_xml_for_rdf(xml_data, main_dataset, named_graph_uris, mapper, extraction_info)

        # Process enrichment data
        if enrichment_data:
            process_enrichment_for_rdf(
                enrichment_data, main_dataset, named_graph_uris, mapper, extraction_info
            )

        # Build semantic networks
        if enable_citation_networks:
            build_citation_networks(main_dataset, named_graph_uris)

        if enable_collaboration_networks:
            build_collaboration_networks(main_dataset, named_graph_uris)

        if enable_institutional_hierarchies:
            build_institutional_hierarchies(main_dataset, named_graph_uris)

        if enable_quality_metrics:
            add_quality_metrics(main_dataset, named_graph_uris)

        # Add provenance information
        add_provenance_and_metadata(main_dataset, named_graph_uris, extraction_info)

        if enable_shacl_validation:
            add_shacl_validation_shapes(main_dataset, named_graph_uris)

        # Cache the result if cache backend is provided
        if cache_backend:
            combined_str = (
                str(search_results or {}) + str(xml_data or {}) + str(enrichment_data or {})
            )
            cache_key = f"rdf_{hash(combined_str)}"
            cache_backend.set(cache_key, main_dataset, data_type=CacheDataType.FULLTEXT)

        return main_dataset, named_graph_uris

    except Exception as e:
        raise RDFConversionError(f"Failed to convert data to RDF: {e}") from e
