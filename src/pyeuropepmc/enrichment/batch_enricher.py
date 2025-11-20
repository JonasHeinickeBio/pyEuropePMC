"""
Batch enrichment utilities for processing multiple papers.

This module provides classes for efficiently processing multiple papers
in batch operations with progress tracking and error handling.
"""

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

from pyeuropepmc.enrichment.config import EnrichmentConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BatchEnricher:
    """
    Handles batch enrichment of multiple papers.

    This class provides efficient batch processing capabilities for
    enriching multiple papers with progress tracking and error handling.
    """

    def __init__(self, config: EnrichmentConfig) -> None:
        """
        Initialize batch enricher.

        Parameters
        ----------
        config : EnrichmentConfig
            Configuration for enrichment
        """
        self.config = config
        # Import here to avoid circular import
        from pyeuropepmc.enrichment.enricher import PaperEnricher

        self.enricher = PaperEnricher(config)

    def enrich_papers(
        self,
        identifiers: list[str],
        show_progress: bool = True,
        max_workers: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Enrich multiple papers in batch mode with progress tracking.

        Parameters
        ----------
        identifiers : list[str]
            List of paper identifiers (DOI, PMID, PMCID)
        show_progress : bool, optional
            Whether to show progress bar, by default True
        max_workers : int, optional
            Maximum number of concurrent workers, by default None (uses ThreadPoolExecutor default)
        **kwargs
            Additional parameters for specific APIs

        Returns
        -------
        dict[str, Any]
            Batch enrichment results with statistics
        """
        if not identifiers:
            return {"results": [], "stats": {"total": 0, "successful": 0, "failed": 0}}

        results = []
        successful = 0
        failed = 0

        pbar = self._setup_progress_bar(show_progress, len(identifiers))

        def enrich_single(identifier: str) -> dict[str, Any]:
            nonlocal successful, failed
            try:
                result = self.enricher.enrich_paper(identifier, **kwargs)
                successful += 1
                return {"identifier": identifier, "status": "success", "data": result}
            except Exception as e:
                failed += 1
                return {"identifier": identifier, "status": "failed", "error": str(e)}

        results = self._process_identifiers(identifiers, enrich_single, pbar, max_workers)

        if pbar:
            pbar.close()

        return {
            "results": results,
            "stats": {
                "total": len(identifiers),
                "successful": successful,
                "failed": failed,
                "success_rate": successful / len(identifiers) if identifiers else 0,
            },
        }

    def _setup_progress_bar(self, show_progress: bool, total: int) -> Any:
        """Set up progress bar if requested."""
        if not show_progress:
            return None

        try:
            from tqdm import tqdm

            return tqdm(total=total, desc="Enriching papers")
        except ImportError:
            logger.warning("tqdm not available, progress bar disabled")
            return None

    def _process_identifiers(
        self,
        identifiers: list[str],
        enrich_func: Callable[[str], dict[str, Any]],
        pbar: Any,
        max_workers: int | None,
    ) -> list[dict[str, Any]]:
        """Process batch of identifiers with optional concurrency."""
        results = []
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(enrich_func, ident) for ident in identifiers]

                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    if pbar:
                        pbar.update(1)
        except ImportError:
            logger.warning("concurrent.futures not available, processing sequentially")
            for ident in identifiers:
                result = enrich_func(ident)
                results.append(result)
                if pbar:
                    pbar.update(1)
        return results

    def enrich_papers_with_progress(
        self, identifiers: list[str], show_progress: bool = True, **kwargs: Any
    ) -> dict[str, dict[str, Any]]:
        """
        Enrich multiple papers with progress tracking.

        Parameters
        ----------
        identifiers : list[str]
            List of identifiers (DOIs or PMCIDs) to enrich
        show_progress : bool, optional
            Whether to show progress information (default: True)
        **kwargs
            Additional parameters for specific APIs

        Returns
        -------
        dict[str, dict[str, Any]]
            Dictionary mapping identifier to enrichment results
        """
        results = {}
        total = len(identifiers)

        for i, identifier in enumerate(identifiers, 1):
            try:
                if show_progress:
                    logger.info(f"Enriching paper {i}/{total}: {identifier}")
                result = self.enricher.enrich_paper(identifier=identifier, **kwargs)
                results[identifier] = result
            except Exception as e:
                logger.error(f"Failed to enrich {identifier}: {e}")
                results[identifier] = {"error": str(e), "identifier": identifier}

        if show_progress:
            successful = sum(
                1 for r in results.values() if isinstance(r, dict) and r.get("sources")
            )
            logger.info(f"Batch enrichment complete: {successful}/{total} successful")

        return results

    def close(self) -> None:
        """Close the underlying enricher."""
        self.enricher.close()

    def __enter__(self) -> "BatchEnricher":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and clean up resources."""
        self.close()
