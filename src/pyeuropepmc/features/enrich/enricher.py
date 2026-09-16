"""
Paper enrichment orchestrator for combining multiple external APIs.

This module provides a high-level interface for enriching paper metadata
using multiple external APIs (CrossRef, Unpaywall, Semantic Scholar, OpenAlex).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
from pathlib import Path
import re
from typing import Any, cast
from urllib.parse import urlparse

from pyeuropepmc.features.enrich.batch_enricher import BatchEnricher
from pyeuropepmc.features.enrich.config import EnrichmentConfig
from pyeuropepmc.features.enrich.data_merger import DataMerger
from pyeuropepmc.features.enrich.file_enricher import FileEnricher
from pyeuropepmc.features.enrich.reporter import EnrichmentReporter
from pyeuropepmc.features.enrich.sources.crossref import CrossRefClient
from pyeuropepmc.features.enrich.sources.datacite import DataCiteClient
from pyeuropepmc.features.enrich.sources.europepmc import EuropePMCEnrichmentClient
from pyeuropepmc.features.enrich.sources.icite import ICiteClient
from pyeuropepmc.features.enrich.sources.openalex import OpenAlexClient
from pyeuropepmc.features.enrich.sources.ror import RorClient
from pyeuropepmc.features.enrich.sources.semantic_scholar import SemanticScholarClient
from pyeuropepmc.features.enrich.sources.unpaywall import UnpaywallClient
from pyeuropepmc.features.literature.search import SearchClient

logger = logging.getLogger(__name__)

# Sources keyed by PMID rather than DOI.
_PMID_KEYED = {"icite"}

__all__ = ["PaperEnricher", "EnrichmentConfig"]


class PaperEnricher:
    """
    High-level orchestrator for enriching paper metadata.

    This class coordinates multiple external APIs to provide comprehensive
    metadata enrichment while handling errors gracefully and respecting
    rate limits.

    Examples
    --------
    >>> from pyeuropepmc.features.enrich import PaperEnricher, EnrichmentConfig
    >>> config = EnrichmentConfig(
    ...     enable_crossref=True,
    ...     enable_semantic_scholar=True,
    ...     crossref_email="your@email.com"
    ... )
    >>> enricher = PaperEnricher(config)
    >>> enriched = enricher.enrich_paper("10.1371/journal.pone.0123456")
    >>> print(f"Sources: {enriched.get('sources')}")
    >>> print(f"Citations: {enriched['merged'].get('citation_count')}")
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

        # Each entry: (enabled, factory). A client that fails to construct is
        # logged and skipped — one broken source must not sink the enricher.
        _factories: list[tuple[bool, str, Any]] = [
            (
                config.enable_europepmc,
                "europepmc",
                lambda: EuropePMCEnrichmentClient(
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                ),
            ),
            (
                config.enable_crossref,
                "crossref",
                lambda: CrossRefClient(
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                    email=config.crossref_email,
                ),
            ),
            (
                config.enable_datacite,
                "datacite",
                lambda: DataCiteClient(
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                    email=config.datacite_email,
                ),
            ),
            (
                config.enable_unpaywall and bool(config.unpaywall_email),
                "unpaywall",
                lambda: UnpaywallClient(
                    email=cast(str, config.unpaywall_email),
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                ),
            ),
            (
                config.enable_semantic_scholar,
                "semantic_scholar",
                lambda: SemanticScholarClient(
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                    api_key=config.semantic_scholar_api_key,
                ),
            ),
            (
                config.enable_openalex,
                "openalex",
                lambda: OpenAlexClient(
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                    email=config.openalex_email,
                ),
            ),
            (
                config.enable_icite,
                "icite",
                lambda: ICiteClient(
                    rate_limit_delay=min(config.rate_limit_delay, 0.5),
                    cache_config=config.cache_config,
                ),
            ),
            (
                config.enable_ror,
                "ror",
                lambda: RorClient(
                    rate_limit_delay=config.rate_limit_delay,
                    cache_config=config.cache_config,
                    email=config.ror_email,
                    client_id=config.ror_client_id,
                ),
            ),
        ]

        if config.enable_unpaywall and not config.unpaywall_email:
            logger.warning("Unpaywall enabled but no email provided — skipping that source")

        for enabled, name, factory in _factories:
            if not enabled:
                continue
            try:
                self.clients[name] = factory()
                logger.info("%s enrichment client initialized", name)
            except Exception as e:  # noqa: BLE001 - degrade, don't abort
                logger.error("Failed to initialize %s client, skipping: %s", name, e)

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
        Enrich paper metadata using all configured APIs, in parallel.

        Europe PMC supplies the base record; CrossRef / OpenAlex / Semantic
        Scholar / iCite / Unpaywall top it up. Sources are queried concurrently.

        Parameters
        ----------
        identifier : str, optional
            Paper identifier — DOI, DOI URL, PMID or PMCID. May also be passed
            as ``doi=``, ``pmid=`` or ``pmcid=``.
        save_responses : bool, optional
            Write raw + merged JSON to ``save_dir`` (default: ``False``).
        save_dir : str or Path, optional
            Directory for response files (default: the current working dir).
        **kwargs
            Additional parameters passed through to each source's ``enrich()``.

        Returns
        -------
        dict
            ``{identifier, doi, pmid, sources: [...], <source>: <data>, merged: {...}}``.

        Raises
        ------
        ValueError
            If no identifier is provided.
        """
        # enrich_paper(doi=...) and friends: take the alias, and keep all of
        # them out of the kwargs forwarded to every source.
        aliases = [kwargs.pop(key, None) for key in ("doi", "pmcid", "pmid")]
        identifier = identifier or next((value for value in aliases if value), None)
        if not identifier:
            raise ValueError("An identifier (DOI, DOI URL, PMID or PMCID) is required")

        ids = self._resolve_ids(identifier)
        doi = ids.get("doi")
        pmid = ids.get("pmid")

        results: dict[str, Any] = {
            "identifier": identifier,
            "doi": doi,
            "pmid": pmid,
            "sources": [],
        }
        for name in self.clients:
            results.setdefault(name, None)
        results.setdefault("ror", None)

        # Fan out over every non-ROR source concurrently. Each client is
        # independent and only does read requests, so this is safe.
        targets = {
            name: (pmid if name in _PMID_KEYED else (doi or pmid or identifier))
            for name, client in self.clients.items()
            if name != "ror"
        }
        runnable = {n: t for n, t in targets.items() if t}

        def _one(name: str) -> tuple[str, Any]:
            client = self.clients[name]
            return name, client.enrich(identifier=runnable[name], **kwargs)

        if runnable:
            with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
                futures = {pool.submit(_one, n): n for n in runnable}
                for fut in as_completed(futures):
                    name = futures[fut]
                    try:
                        _, data = fut.result()
                    except Exception as e:  # noqa: BLE001 - per-source, keep going
                        logger.error("Error enriching from %s: %s", name, e, exc_info=True)
                        continue
                    if data:
                        results[name] = data
                        results["sources"].append(name)
                        logger.info("Enriched from %s", name)
                    else:
                        logger.debug("No data from %s", name)

        # Merge results
        if results["sources"]:
            results["merged"] = self.merger.merge_results(results)
            logger.info(f"Enrichment complete with {len(results['sources'])} sources")
        else:
            logger.warning(f"No enrichment data found for identifier: {identifier}")
            results["merged"] = {}

        # Enrich institutions with ROR data if ROR is enabled and we have author data
        if self.config.enable_ror and results.get("merged", {}).get("authors"):
            try:
                ror_enriched_institutions = self._enrich_institutions_with_ror(results["merged"])
                if ror_enriched_institutions:
                    results["ror"] = ror_enriched_institutions
                    results["sources"].append("ror")
                    # Re-merge with ROR data to update author institutions
                    results["merged"] = self.merger.merge_results(results)
                    logger.info(
                        f"Added ROR enrichment for {len(ror_enriched_institutions)} institutions"
                    )
                else:
                    logger.debug("No additional ROR enrichment needed")
            except Exception as e:
                logger.error(f"Error enriching institutions with ROR: {e}")

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
            (default: examples/enrichment_responses relative to project root)
        """
        save_dir = Path.cwd() / "enrichment_responses" if save_dir is None else Path(save_dir)

        save_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving API responses to {save_dir}")

        # Name the files after the DOI; without one (a PMID or PMCID that
        # Europe PMC could not map to a DOI) fall back to the identifier given.
        key = results.get("doi") or results.get("identifier") or "unknown"
        safe_doi = re.sub(r"[^A-Za-z0-9-]+", "_", str(key)).strip("_") or "unknown"

        # Save raw responses for each source
        for source in results:
            if (
                source not in ["identifier", "doi", "pmid", "sources", "merged"]
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

    def _resolve_ids(self, identifier: str) -> dict[str, str | None]:
        """
        Resolve any identifier (DOI / DOI URL / PMID / PMCID / free text) to a
        ``{doi, pmid, pmcid}`` bundle via a single Europe PMC lookup.

        Never raises — missing pieces come back as ``None`` and the enricher
        falls back to the raw identifier for DOI-keyed sources.
        """
        ident = identifier.strip()
        low = ident.lower()
        out: dict[str, str | None] = {"doi": None, "pmid": None, "pmcid": None}

        parsed = urlparse(ident)
        host = parsed.netloc.lower()
        if host == "doi.org" or host.endswith(".doi.org"):
            # The DOI is the URL path, not just the last "/"-segment - a DOI
            # itself contains a "/" between its prefix and suffix.
            out["doi"] = parsed.path.lstrip("/")
        elif low.startswith("10."):
            out["doi"] = ident
        elif ident.upper().startswith("PMC"):
            out["pmcid"] = ident.upper()
        elif ident.isdigit():
            out["pmid"] = ident

        # One Europe PMC query fills in whatever is still missing.
        if out["doi"]:
            query = f'DOI:"{out["doi"]}"'
        elif out["pmcid"]:
            query = f"PMCID:{out['pmcid']}"
        elif out["pmid"]:
            query = f"EXT_ID:{out['pmid']} AND SRC:MED"
        else:
            query = ident

        try:
            with SearchClient() as sc:
                records = sc.search_and_parse(query, format="json", pageSize=1)
            if records:
                rec = records[0]
                out["doi"] = out["doi"] or (rec.get("doi") or None)
                out["pmid"] = out["pmid"] or (rec.get("pmid") or None)
                out["pmcid"] = out["pmcid"] or (rec.get("pmcid") or None)
        except Exception as e:  # noqa: BLE001 - best effort
            logger.warning("Europe PMC id resolution failed for %r: %s", identifier, e)

        return out

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
        try:
            # Check if it's a DOI URL (https://doi.org/...)
            if identifier.startswith("https://doi.org/"):
                doi = identifier[len("https://doi.org/") :]
                logger.info(f"Extracted DOI from URL: {doi}")
                return doi

            # Check if it's already a DOI (starts with 10.)
            if identifier.startswith("10."):
                logger.debug(f"Identifier is already a DOI: {identifier}")
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
                    "(starting with 10.), DOI URL (https://doi.org/...), "
                    "or PMCID (starting with PMC)"
                )
        except Exception as e:
            logger.error(f"Error resolving identifier {identifier}: {e}")
            raise

    def enrich(
        self,
        papers: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Enrich papers (convenience method wrapper).

        Parameters
        ----------
        papers : list[dict[str, Any]], optional
            List of paper dictionaries to enrich. If None, uses single identifier from kwargs.
        **kwargs
            Additional parameters: either 'identifier' for single paper or 'papers' for batch

        Returns
        -------
        dict[str, Any]
            Enrichment results
        """
        if papers is not None:
            if len(papers) == 1:
                identifier = (
                    papers[0].get("doi") or papers[0].get("pmcid") or papers[0].get("pmid")
                )
                if identifier:
                    return self.enrich_paper(identifier=identifier, **kwargs)
            return self.enrich_papers_batch(
                [p.get("doi") or p.get("pmcid") for p in papers if p.get("doi") or p.get("pmcid")],
                **kwargs,
            )

        identifier = kwargs.pop("identifier", None)
        if identifier:
            return self.enrich_paper(identifier=identifier, **kwargs)

        raise ValueError("Either papers list or identifier required")

    def enrich_papers_batch(
        self,
        identifiers: list[str],
        save_responses: bool = True,
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
            Whether to save raw API responses and merged result to files (default: True)
        save_dir : str or Path, optional
            Directory to save response files (default: examples/enrichment_responses)
        **kwargs
            Additional parameters for specific APIs

        Returns
        -------
        dict[str, dict[str, Any]]
            Dictionary mapping identifier to enrichment results
        """
        try:
            batch_enricher = BatchEnricher(self.config)
            with batch_enricher:
                return batch_enricher.enrich_papers_with_progress(
                    identifiers, save_responses=save_responses, save_dir=save_dir, **kwargs
                )
        except Exception as e:
            logger.error(f"Error in batch enrichment: {e}", exc_info=True)
            raise

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
        try:
            file_enricher = FileEnricher(self.config)
            with file_enricher:
                # Convert Path objects to strings
                file_paths = [str(f) for f in metadata_files]
                return file_enricher.enrich_from_files(file_paths, **kwargs)
        except Exception as e:
            logger.error(f"Error enriching from metadata files: {e}", exc_info=True)
            raise

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
        try:
            return self.reporter.generate_report(enrichment_result)
        except Exception as e:
            logger.error(f"Error generating enrichment report: {e}", exc_info=True)
            raise

    def _enrich_institutions_with_ror(self, merged_data: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich institutions in author data with detailed ROR information.

        Only enriches institutions that don't already have ROR enrichment data.

        Parameters
        ----------
        merged_data : dict
            Merged enrichment data containing authors

        Returns
        -------
        dict
            Dictionary mapping ROR IDs to enriched institution data
        """
        ror_client = self.clients.get("ror")
        if not ror_client:
            return {}

        # Collect unique ROR IDs from author institutions that need enrichment
        ror_ids_to_enrich = set()
        authors = merged_data.get("authors", [])

        for author in authors:
            if isinstance(author, dict):
                institutions = author.get("institutions", [])
                for inst in institutions:
                    if isinstance(inst, dict):
                        # Skip institutions that are already ROR-enriched
                        if inst.get("ror_enriched"):
                            inst_name = inst.get("display_name", "Unknown")
                            logger.debug(f"Institution {inst_name} already ROR-enriched, skipping")
                            continue

                        ror_id = inst.get("ror_id")
                        if ror_id:
                            # Normalize ROR ID
                            normalized_id = ror_client._normalize_ror_id(ror_id)
                            if normalized_id:
                                ror_ids_to_enrich.add(normalized_id)

        if not ror_ids_to_enrich:
            logger.debug("No ROR IDs found that need enrichment")
            return {}

        # Enrich each ROR ID
        enriched_institutions = {}
        for ror_id in ror_ids_to_enrich:
            try:
                logger.debug(f"Enriching institution with ROR ID: {ror_id}")
                ror_data = ror_client.enrich(identifier=ror_id)
                if ror_data:
                    enriched_institutions[ror_id] = ror_data
                    logger.info(f"Successfully enriched institution: {ror_id}")
                else:
                    logger.warning(f"No ROR data found for: {ror_id}")
            except Exception as e:
                logger.error(f"Error enriching ROR ID {ror_id}: {e}")

        return enriched_institutions
