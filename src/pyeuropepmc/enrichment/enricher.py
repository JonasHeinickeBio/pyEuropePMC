"""
Paper enrichment orchestrator for combining multiple external APIs.

This module provides a high-level interface for enriching paper metadata
using multiple external APIs (CrossRef, Unpaywall, Semantic Scholar, OpenAlex).
"""

import json
import logging
from pathlib import Path
from typing import Any, cast

from pyeuropepmc.clients.search import SearchClient
from pyeuropepmc.enrichment.batch_enricher import BatchEnricher
from pyeuropepmc.enrichment.config import EnrichmentConfig
from pyeuropepmc.enrichment.crossref import CrossRefClient
from pyeuropepmc.enrichment.datacite import DataCiteClient
from pyeuropepmc.enrichment.file_enricher import FileEnricher
from pyeuropepmc.enrichment.merger import DataMerger
from pyeuropepmc.enrichment.openalex import OpenAlexClient
from pyeuropepmc.enrichment.reporter import EnrichmentReporter
from pyeuropepmc.enrichment.ror import RorClient
from pyeuropepmc.enrichment.semantic_scholar import SemanticScholarClient
from pyeuropepmc.enrichment.unpaywall import UnpaywallClient

logger = logging.getLogger(__name__)

__all__ = ["PaperEnricher", "EnrichmentConfig"]


class PaperEnricher:
    """
    High-level orchestrator for enriching paper metadata.

    This class coordinates multiple external APIs to provide comprehensive
    metadata enrichment while handling errors gracefully and respecting
    rate limits.

    Examples
    --------
    >>> from pyeuropepmc.enrichment import PaperEnricher, EnrichmentConfig
    >>> config = EnrichmentConfig(
    ...     enable_crossref=True,
    ...     enable_semantic_scholar=True,
    ...     crossref_email="your@email.com"
    ... )
    >>> enricher = PaperEnricher(config)
    >>> enriched = enricher.enrich_paper(doi="10.1371/journal.pone.0123456")
    >>> print(f"Sources: {enriched.get('sources')}")
    >>> print(f"Citations: {enriched.get('citation_count')}")
    """

    def __init__(self, config: EnrichmentConfig) -> None:
        """
        Initialize paper enricher.

        Parameters
        ----------
        config : EnrichmentConfig
            Configuration for enrichment
        """
        self.config = config
        self.clients: dict[str, Any] = {}
        self.merger = DataMerger()
        self.reporter = EnrichmentReporter()

        # Initialize enabled clients
        if config.enable_crossref:
            self.clients["crossref"] = CrossRefClient(
                rate_limit_delay=config.rate_limit_delay,
                cache_config=config.cache_config,
                email=config.crossref_email,
            )
            logger.info("CrossRef client initialized")

        if config.enable_datacite:
            self.clients["datacite"] = DataCiteClient(
                rate_limit_delay=config.rate_limit_delay,
                cache_config=config.cache_config,
                email=config.datacite_email,
            )
            logger.info("DataCite client initialized")

        if config.enable_unpaywall:
            if config.unpaywall_email:  # Type guard
                self.clients["unpaywall"] = UnpaywallClient(
                    email=config.unpaywall_email,
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                )
                logger.info("Unpaywall client initialized")
            else:
                logger.warning("Unpaywall enabled but email not provided, skipping initialization")

        if config.enable_semantic_scholar:
            self.clients["semantic_scholar"] = SemanticScholarClient(
                rate_limit_delay=config.rate_limit_delay,
                cache_config=config.cache_config,
                api_key=config.semantic_scholar_api_key,
            )
            logger.info("Semantic Scholar client initialized")

        if config.enable_openalex:
            self.clients["openalex"] = OpenAlexClient(
                rate_limit_delay=config.rate_limit_delay,
                cache_config=config.cache_config,
                email=config.openalex_email,
            )
            logger.info("OpenAlex client initialized")

        if config.enable_ror:
            self.clients["ror"] = RorClient(
                rate_limit_delay=config.rate_limit_delay,
                cache_config=config.cache_config,
                email=config.ror_email,
                client_id=config.ror_client_id,
            )
            logger.info("ROR client initialized")

        logger.info(f"PaperEnricher initialized with {len(self.clients)} clients")

    def __enter__(self) -> "PaperEnricher":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and clean up resources."""
        self.close()

    def close(self) -> None:
        """Close all API clients."""
        for name, client in self.clients.items():
            try:
                client.close()
                logger.debug(f"Closed {name} client")
            except Exception as e:
                logger.warning(f"Error closing {name} client: {e}")

    def enrich_paper(
        self,
        identifier: str | None = None,
        save_responses: bool = False,
        save_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Enrich paper metadata using all configured APIs.

        Parameters
        ----------
        identifier : str, optional
            Paper identifier (DOI or PMCID)
        save_responses : bool, optional
            Whether to save raw API responses and merged result to files (default: False)
        save_dir : str or Path, optional
            Directory to save response files (default: examples/enrichment_responses)
        **kwargs
            Additional parameters for specific APIs

        Returns
        -------
        dict
            Merged enriched metadata from all sources with keys:
            - sources: List of sources that provided data
            - crossref: CrossRef metadata (if available)
            - datacite: DataCite metadata (if available)
            - unpaywall: Unpaywall OA info (if available)
            - semantic_scholar: Semantic Scholar metrics (if available)
            - openalex: OpenAlex metadata (if available)
            - merged: Merged/aggregated metadata from all sources

        Raises
        ------
        ValueError
            If identifier is not provided and required by enabled clients
        """
        if not identifier:
            raise ValueError("Identifier (DOI or PMCID) is required for enrichment")

        # Resolve identifier to DOI if it's a PMCID
        doi = self._resolve_to_doi(identifier)

        results: dict[str, Any] = {
            "identifier": identifier,
            "doi": doi,
            "sources": [],
            "crossref": None,
            "datacite": None,
            "unpaywall": None,
            "semantic_scholar": None,
            "openalex": None,
            "ror": None,
        }

        # Enrich from each source
        for source_name, client in self.clients.items():
            try:
                logger.debug(f"Enriching from {source_name}")
                data = client.enrich(identifier=doi, **kwargs)
                if data:
                    results[source_name] = data
                    results["sources"].append(source_name)
                    logger.info(f"Successfully enriched from {source_name}")
                else:
                    logger.warning(f"No data from {source_name}")
            except Exception as e:
                logger.error(f"Error enriching from {source_name}: {e}", exc_info=True)
                # Continue with other sources

        # Merge results
        if results["sources"]:
            results["merged"] = self.merger.merge_results(results)
            logger.info(f"Enrichment complete with {len(results['sources'])} sources")
        else:
            logger.warning(f"No enrichment data found for identifier: {identifier}")
            results["merged"] = {}

        # Save responses if requested
        if save_responses:
            try:
                self._save_responses(results, save_dir)
            except Exception as e:
                logger.error(f"Failed to save responses: {e}")

        return results

    def _save_responses(self, results: dict[str, Any], save_dir: str | Path | None) -> None:
        """
        Save raw API responses and merged result to JSON files.

        Parameters
        ----------
        results : dict
            Enrichment results
        save_dir : str or Path, optional
            Directory to save files
        """
        if save_dir is None:
            # Default to examples/enrichment_responses in the project
            save_dir = (
                Path(__file__).parent.parent.parent.parent / "examples" / "enrichment_responses"
            )
        else:
            save_dir = Path(save_dir)

        save_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving API responses to {save_dir}")

        doi = results.get("doi", "unknown")
        # Sanitize DOI for filename
        safe_doi = doi.replace("/", "_").replace(".", "_")

        # Save raw responses for each source
        for source in results:
            if (
                source not in ["identifier", "doi", "sources", "merged"]
                and results.get(source) is not None
            ):
                filename = save_dir / f"raw_{source}_{safe_doi}.json"
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(results[source], f, indent=2, ensure_ascii=False)
                    logger.info(f"Saved raw {source} response to {filename}")
                except Exception as e:
                    logger.error(f"Failed to save {source} response: {e}")

        # Save merged result
        merged_filename = save_dir / f"merged_{safe_doi}.json"
        try:
            with open(merged_filename, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved merged result to {merged_filename}")
        except Exception as e:
            logger.error(f"Failed to save merged result: {e}")

    def _resolve_to_doi(self, identifier: str) -> str:
        """
        Resolve identifier to DOI. If it's already a DOI, return as is.
        If it's a DOI URL, extract the DOI. If it's a PMCID, search Europe PMC to find the DOI.

        Parameters
        ----------
        identifier : str
            DOI, DOI URL, or PMCID

        Returns
        -------
        str
            DOI

        Raises
        ------
        ValueError
            If identifier is not a valid DOI, DOI URL, or PMCID, or DOI cannot be found
        """
        # Check if it's a DOI URL (https://doi.org/...)
        if identifier.startswith("https://doi.org/"):
            doi = identifier[len("https://doi.org/") :]
            logger.info(f"Extracted DOI from URL: {doi}")
            return doi

        # Check if it's already a DOI (starts with 10.)
        if identifier.startswith("10."):
            return identifier

        # Check if it's a PMCID (starts with PMC)
        if identifier.upper().startswith("PMC"):
            logger.info(f"Resolving PMCID {identifier} to DOI")
            try:
                with SearchClient() as search_client:
                    results = search_client.search(query=f"PMCID:{identifier}", limit=1)
                    if isinstance(results, dict):
                        papers = results.get("resultList", {}).get("result", [])
                        if papers and len(papers) > 0:
                            doi = papers[0].get("doi")
                            if doi:
                                logger.info(f"Found DOI {doi} for PMCID {identifier}")
                                return cast(str, doi)
                            else:
                                raise ValueError(f"No DOI found for PMCID {identifier}")
                        else:
                            raise ValueError(f"No results found for PMCID {identifier}")
                    else:
                        raise ValueError("Invalid response format from SearchClient")
            except Exception as e:
                logger.error(f"Error resolving PMCID {identifier}: {e}")
                raise ValueError(f"Could not resolve PMCID {identifier} to DOI") from e
        else:
            raise ValueError(
                f"Invalid identifier: {identifier}. Must be DOI "
                "(starting with 10.), DOI URL (https://doi.org/...), or PMCID (starting with PMC)"
            )

    def enrich_papers_batch(
        self,
        identifiers: list[str],
        save_responses: bool = False,
        save_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> dict[str, dict[str, Any]]:
        """
        Enrich multiple papers in batch.

        Parameters
        ----------
        identifiers : list[str]
            List of identifiers (DOIs or PMCIDs) to enrich
        save_responses : bool, optional
            Whether to save raw API responses and merged result to files (default: False)
        save_dir : str or Path, optional
            Directory to save response files (default: examples/enrichment_responses)
        **kwargs
            Additional parameters for specific APIs

        Returns
        -------
        dict[str, dict[str, Any]]
            Dictionary mapping identifier to enrichment results
        """
        batch_enricher = BatchEnricher(self.config)
        with batch_enricher:
            return batch_enricher.enrich_papers_with_progress(identifiers, **kwargs)

    def enrich_from_metadata_files(
        self, metadata_files: list[str | Path], **kwargs: Any
    ) -> dict[str, dict[str, Any]]:
        """
        Enrich papers from existing metadata files.

        Parameters
        ----------
        metadata_files : list[str | Path]
            List of paths to metadata JSON files
        **kwargs
            Additional parameters for specific APIs

        Returns
        -------
        dict[str, dict[str, Any]]
            Dictionary mapping file path to enrichment results
        """
        file_enricher = FileEnricher(self.config)
        with file_enricher:
            # Convert Path objects to strings
            file_paths = [str(f) for f in metadata_files]
            return file_enricher.enrich_from_files(file_paths, **kwargs)

    def generate_enrichment_report(self, enrichment_result: dict[str, Any]) -> str:
        """
        Generate a human-readable report from enrichment results.

        Parameters
        ----------
        enrichment_result : dict
            Result from enrich_paper or enrich_papers_batch

        Returns
        -------
        str
            Formatted report string
        """
        return self.reporter.generate_report(enrichment_result)
