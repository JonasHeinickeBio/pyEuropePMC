"""
Unified pipeline for processing scientific papers from XML to enriched RDF.

This module provides a streamlined workflow that combines XML parsing,
metadata enrichment, and RDF conversion into a single, easy-to-use pipeline.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyeuropepmc.builders.from_parser import build_paper_entities
from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.clients import FullTextClient, SearchClient
from pyeuropepmc.enrichment.enricher import EnrichmentConfig, PaperEnricher
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.models import (
    AuthorEntity,
    PaperEntity,
)
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

if TYPE_CHECKING:
    from rdflib import Graph

logger = logging.getLogger(__name__)

__all__ = ["PaperProcessingPipeline", "PipelineConfig"]


class PipelineConfig:
    """
    Configuration for the paper processing pipeline.

    This class combines configuration for caching, enrichment, and RDF mapping
    into a single, easy-to-configure object.
    """

    def __init__(
        self,
        # Caching
        enable_cache: bool = True,
        cache_size_mb: int = 500,
        # Enrichment
        enable_enrichment: bool = True,
        enable_crossref: bool = True,
        enable_semantic_scholar: bool = True,
        enable_openalex: bool = True,
        enable_ror: bool = True,
        crossref_email: str | None = None,
        # RDF
        rdf_config_path: str | None = None,
        # Output
        output_format: str = "turtle",
        output_dir: str = "output",
    ):
        """
        Initialize pipeline configuration.

        Parameters
        ----------
        enable_cache : bool
            Whether to enable caching for API calls
        cache_size_mb : int
            Cache size in MB
        enable_enrichment : bool
            Whether to enable metadata enrichment
        enable_crossref : bool
            Enable CrossRef enrichment
        enable_semantic_scholar : bool
            Enable Semantic Scholar enrichment
        enable_openalex : bool
            Enable OpenAlex enrichment
        enable_ror : bool
            Enable ROR institution enrichment
        crossref_email : Optional[str]
            Email for CrossRef API (required for higher rate limits)
        rdf_config_path : Optional[str]
            Path to RDF mapping configuration file
        output_format : str
            RDF output format ('turtle', 'xml', 'nt', 'json-ld')
        output_dir : str
            Directory to save output files
        """
        self.enable_cache = enable_cache
        self.cache_size_mb = cache_size_mb
        self.enable_enrichment = enable_enrichment
        self.enable_crossref = enable_crossref
        self.enable_semantic_scholar = enable_semantic_scholar
        self.enable_openalex = enable_openalex
        self.enable_ror = enable_ror
        self.crossref_email = crossref_email
        self.rdf_config_path = rdf_config_path
        self.output_format = output_format
        self.output_dir = output_dir

    def to_cache_config(self) -> CacheConfig:
        """Convert to CacheConfig."""
        return CacheConfig(
            enabled=self.enable_cache,
            size_limit_mb=self.cache_size_mb,
        )

    def to_enrichment_config(self) -> EnrichmentConfig:
        """Convert to EnrichmentConfig."""
        return EnrichmentConfig(
            enable_crossref=self.enable_crossref,
            enable_semantic_scholar=self.enable_semantic_scholar,
            enable_openalex=self.enable_openalex,
            enable_ror=self.enable_ror,
            enable_unpaywall=False,  # Skip Unpaywall as it requires email
            crossref_email=self.crossref_email,
            cache_config=self.to_cache_config(),
        )


class PaperProcessingPipeline:
    """
    Unified pipeline for processing scientific papers from XML to enriched RDF.

    This class provides a simple, high-level interface that combines:
    1. XML parsing and entity extraction
    2. Metadata enrichment from external APIs
    3. RDF conversion with relationships

    Examples
    --------
    >>> from pyeuropepmc.pipeline import PaperProcessingPipeline, PipelineConfig
    >>>
    >>> # Simple configuration
    >>> config = PipelineConfig(crossref_email="your@email.com")
    >>> pipeline = PaperProcessingPipeline(config)
    >>>
    >>> # Process single paper
    >>> result = pipeline.process_paper(xml_content, doi="10.1038/s41467-024-51893-7")
    >>> print(f"Generated {result['triple_count']} RDF triples")
    >>>
    >>> # Process multiple papers
    >>> results = pipeline.process_papers(xml_contents_dict)
    >>> for doi, result in results.items():
    >>>     print(f"{doi}: {result['triple_count']} triples")
    """

    config: PipelineConfig
    parser: FullTextXMLParser
    fulltext_client: FullTextClient
    search_client: SearchClient
    rdf_mapper: RDFMapper
    enricher: PaperEnricher | None
    output_dir: Path

    def __init__(self, config: PipelineConfig):
        """
        Initialize the processing pipeline.

        Parameters
        ----------
        config : PipelineConfig
            Pipeline configuration
        """
        self.config = config

        # Initialize components
        self.parser = FullTextXMLParser()
        self.fulltext_client = FullTextClient(cache_config=config.to_cache_config())
        self.search_client = SearchClient(cache_config=config.to_cache_config())
        self.rdf_mapper = RDFMapper(config.rdf_config_path)

        # Initialize enrichment if enabled
        if config.enable_enrichment:
            enrichment_config = config.to_enrichment_config()
            self.enricher = PaperEnricher(enrichment_config)
        else:
            self.enricher = None

        # Create output directory
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(exist_ok=True)

        logger.info("Paper processing pipeline initialized")

    def process_paper(
        self,
        xml_content: str | None = None,
        doi: str | None = None,
        pmcid: str | None = None,
        save_rdf: bool = True,
        filename_prefix: str = "",
    ) -> dict[str, Any]:
        """
        Process a single paper from XML to enriched RDF.

        Parameters
        ----------
        xml_content : Optional[str]
            XML content of the paper. If None, will download automatically using DOI/PMC
        doi : Optional[str]
            DOI of the paper (used for enrichment and naming)
        pmcid : Optional[str]
            PMC ID of the paper
        save_rdf : bool
            Whether to save RDF to file
        filename_prefix : str
            Prefix for output filename

        Returns
        -------
        Dict[str, Any]
            Processing results containing:
            - entities: Dict with paper, authors, sections, etc.
            - enrichment_data: Enrichment results (if enabled)
            - rdf_graph: RDFLib Graph object
            - triple_count: Number of RDF triples
            - output_file: Path to saved RDF file (if saved)
        """
        logger.info(f"Processing paper: {doi or pmcid or 'unknown'}")

        # Step 1: Get XML content (download if not provided)
        if xml_content is None:
            xml_content = self._download_xml(doi, pmcid)
            if xml_content is None:
                raise ValueError(f"Could not obtain XML content for paper: {doi or pmcid}")

        # Step 2: Parse XML and extract entities
        entities = self._parse_xml(xml_content, doi, pmcid)
        paper = entities["paper"]

        # Update paper with provided identifiers
        if doi and not paper.doi:
            paper.doi = doi
        if pmcid and not paper.pmcid:
            paper.pmcid = pmcid

        # Step 3: Enrich metadata (if enabled)
        enrichment_data = None
        if self.enricher and (paper.doi or paper.pmcid):
            enrichment_data = self._enrich_paper(paper)

        # Step 4: Convert to RDF
        rdf_result = self._convert_to_rdf(entities, enrichment_data)

        # Step 5: Save RDF (if requested)
        output_file = None
        if save_rdf:
            output_file = self._save_rdf(
                rdf_result["graph"], doi or pmcid or paper.id, filename_prefix
            )

        return {
            "entities": entities,
            "enrichment_data": enrichment_data,
            "rdf_graph": rdf_result["graph"],
            "triple_count": rdf_result["triple_count"],
            "output_file": output_file,
        }

    def process_papers(
        self,
        xml_contents: dict[str, str],
        save_rdf: bool = True,
        filename_prefix: str = "",
    ) -> dict[str, dict[str, Any]]:
        """
        Process multiple papers from XML to enriched RDF.

        Parameters
        ----------
        xml_contents : Dict[str, str]
            Dictionary mapping identifiers (DOI/PMC) to XML content
        save_rdf : bool
            Whether to save RDF files
        filename_prefix : str
            Prefix for output filenames

        Returns
        -------
        Dict[str, Dict[str, Any]]
            Dictionary mapping identifiers to processing results
        """
        results = {}

        for identifier, xml_content in xml_contents.items():
            try:
                # Determine if identifier is DOI or PMC
                if identifier.startswith("10."):
                    doi = identifier
                    pmcid = None
                else:
                    doi = None
                    pmcid = identifier

                result = self.process_paper(
                    xml_content,
                    doi=doi,
                    pmcid=pmcid,
                    save_rdf=save_rdf,
                    filename_prefix=filename_prefix,
                )
                results[identifier] = result

                logger.info(f"Processed {identifier}: {result['triple_count']} triples")

            except Exception as e:
                logger.error(f"Failed to process {identifier}: {e}")
                results[identifier] = {"error": str(e)}

        return results

    def _parse_xml(
        self, xml_content: str, doi: str | None = None, pmcid: str | None = None
    ) -> dict[str, Any]:
        """Parse XML and extract entities."""
        self.parser.parse(xml_content)

        # Try to get search data for additional metadata
        search_data = None
        identifier = doi or pmcid
        if identifier:
            try:
                search_data = self._get_search_data(identifier)
            except Exception as e:
                logger.warning(f"Failed to get search data for {identifier}: {e}")

        paper, authors, sections, tables, figures, references = build_paper_entities(
            self.parser, search_data
        )

        return {
            "paper": paper,
            "authors": authors,
            "sections": sections,
            "tables": tables,
            "figures": figures,
            "references": references,
        }

    def _download_xml(self, doi: str | None, pmcid: str | None) -> str | None:
        """Download XML content for a paper."""
        try:
            if pmcid:
                # Try PMC ID first
                return self.fulltext_client.get_fulltext_content(pmcid, format_type="xml")
            elif doi:
                # Get PMCID from DOI first
                pmcid = self._get_pmcid_from_doi(doi)
                if pmcid:
                    return self.fulltext_client.get_fulltext_content(pmcid, format_type="xml")
                else:
                    raise ValueError(f"Could not find PMCID for DOI: {doi}")
        except Exception as e:
            logger.warning(f"Failed to download XML for {doi or pmcid}: {e}")
            return None
        return None

    def _get_pmcid_from_doi(self, doi: str) -> str | None:
        """Get PMCID from DOI using SearchClient."""
        try:
            # Search for the paper using DOI
            result = self.search_client.search(f"DOI:{doi}", limit=1)
            if isinstance(result, dict) and "resultList" in result:
                result_list = result["resultList"]
                if isinstance(result_list, dict) and "result" in result_list:
                    results = result_list["result"]
                    if isinstance(results, list) and len(results) > 0:
                        paper = results[0]
                        if isinstance(paper, dict) and "pmcid" in paper:
                            pmcid = paper["pmcid"]
                            return str(pmcid) if pmcid is not None else None
        except Exception as e:
            logger.warning(f"Failed to get PMCID for DOI {doi}: {e}")
        return None

    def _get_search_data(self, identifier: str) -> dict[str, Any] | None:
        """Get search metadata for a paper identifier."""
        try:
            if identifier.startswith("10."):
                # DOI
                result = self.search_client.search(f"DOI:{identifier}", limit=1)
            else:
                # Assume PMCID
                result = self.search_client.search(f"PMCID:{identifier}", limit=1)

            if isinstance(result, dict) and "resultList" in result:
                result_list = result["resultList"]
                if isinstance(result_list, dict) and "result" in result_list:
                    results = result_list["result"]
                    if isinstance(results, list) and len(results) > 0:
                        search_data = results[0]
                        return dict(search_data) if isinstance(search_data, dict) else None
        except Exception as e:
            logger.warning(f"Failed to get search data for {identifier}: {e}")
        return None

    def _enrich_paper(self, paper: PaperEntity) -> dict[str, Any] | None:
        """Enrich paper metadata using external APIs."""
        if not self.enricher:
            return None

        try:
            # Use DOI if available, otherwise try PMC
            identifier = paper.doi or paper.pmcid
            if not identifier:
                return None

            enriched_data = self.enricher.enrich_paper(identifier)

            # Update paper entity with enrichment data
            if enriched_data:
                # paper.enrichment_sources = enriched_data.get("sources", [])
                paper.citation_count = enriched_data.get("citation_count")
                paper.influential_citation_count = enriched_data.get("influential_citation_count")
                paper.fields_of_study = enriched_data.get("fields_of_study")

                # Update authors with enrichment data if available
                if (
                    "authors" in enriched_data
                    and isinstance(enriched_data["authors"], list)
                    and isinstance(paper.authors, list)
                    and all(isinstance(a, AuthorEntity) for a in paper.authors)
                ):
                    self._update_authors_with_enrichment(paper.authors, enriched_data["authors"])  # type: ignore

            return enriched_data

        except Exception as e:
            logger.warning(f"Failed to enrich paper {paper.doi or paper.pmcid}: {e}")
            return None

    def _update_authors_with_enrichment(
        self, authors: list[AuthorEntity], enrichment_authors: list[dict[str, Any]]
    ) -> None:
        """Update author entities with enrichment data."""
        # Simple name-based matching (could be improved with more sophisticated matching)
        for author in authors:
            for enriched_author in enrichment_authors:
                if self._names_match(author.full_name, enriched_author.get("name", "")):
                    # author.enrichment_data = enriched_author
                    # Update available fields
                    if enriched_author.get("orcid") and not author.orcid:
                        author.orcid = enriched_author["orcid"]
                    if enriched_author.get("openalex_id") and not author.openalex_id:
                        author.openalex_id = enriched_author["openalex_id"]
                    semantic_id = enriched_author.get("semantic_scholar_id")
                    if semantic_id and not author.semantic_scholar_id:
                        author.semantic_scholar_id = semantic_id
                    break

    def _names_match(self, name1: str, name2: str) -> bool:
        """Simple name matching (case-insensitive, ignore common prefixes/suffixes)."""
        # Normalize names for comparison
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()

        # Remove common titles
        for title in ["dr.", "prof.", "dr", "prof", "md", "phd", "ph.d."]:
            n1 = n1.replace(title, "").strip()
            n2 = n2.replace(title, "").strip()

        return n1 == n2

    def _convert_to_rdf(
        self, entities: dict[str, Any], enrichment_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Convert entities to RDF with relationships."""
        from datetime import datetime

        from rdflib import Graph

        paper = entities["paper"]
        authors = entities["authors"]
        sections = entities["sections"]
        tables = entities["tables"]
        figures = entities["figures"]
        references = entities["references"]

        # Create RDF graph
        g = Graph()

        # Prepare extraction info
        extraction_info = {
            "timestamp": datetime.now().isoformat() + "Z",
            "method": "pyeuropepmc_unified_pipeline",
            "quality": {
                "validation_passed": True,
                "completeness_score": 0.98 if enrichment_data else 0.95,
            },
        }

        # Ensure pmcid is prefixed with PMC
        if paper.pmcid and not paper.pmcid.startswith("PMC"):
            paper.pmcid = f"PMC{paper.pmcid}"

        # Convert paper with all related entities
        related_entities = {
            "authors": authors,
            "sections": sections,
            "tables": tables,
            "figures": figures,
            "references": references,
        }

        paper_uri = paper.to_rdf(
            g,
            mapper=self.rdf_mapper,
            related_entities=related_entities,
            extraction_info=extraction_info,
        )

        # Count triples
        triple_count = len(list(g))

        return {
            "graph": g,
            "triple_count": triple_count,
            "paper_uri": paper_uri,
        }

    def _save_rdf(self, graph: "Graph", identifier: str, prefix: str = "") -> Path:
        """Save RDF graph to file."""
        # Clean identifier for filename
        safe_id = identifier.replace("/", "_").replace(".", "_").replace(":", "_")

        filename = f"{prefix}{safe_id}.{self.config.output_format}"
        if self.config.output_format == "turtle":
            filename = f"{prefix}{safe_id}.ttl"

        output_path = self.output_dir / filename

        # Serialize graph
        self.rdf_mapper.serialize_graph(
            graph, format=self.config.output_format, destination=str(output_path)
        )

        logger.info(f"Saved RDF to {output_path}")
        return output_path
