"""
File-based enrichment utilities for processing metadata files.

This module provides classes for enriching papers from existing metadata
files with support for various file formats and batch processing.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pyeuropepmc.enrichment.config import EnrichmentConfig

logger = logging.getLogger(__name__)


class FileEnricher:
    """
    Handles enrichment of papers from metadata files.

    This class provides functionality to enrich papers from existing
    metadata files, supporting various formats and batch operations.
    """

    def __init__(self, config: EnrichmentConfig) -> None:
        """
        Initialize file enricher.

        Parameters
        ----------
        config : EnrichmentConfig
            Configuration for enrichment
        """
        self.config = config
        # Import here to avoid circular import
        from pyeuropepmc.enrichment.enricher import PaperEnricher

        self.enricher = PaperEnricher(config)

    def enrich_from_files(
        self, metadata_files: list[str], **kwargs: Any
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
        results: dict[str, dict[str, Any]] = {}
        for file_path in metadata_files:
            try:
                path = Path(file_path)
                logger.info(f"Enriching from metadata file: {path}")

                # Load existing metadata
                with open(path) as f:
                    existing = json.load(f)

                # Get identifier (DOI or PMCID)
                identifier = existing.get("doi") or existing.get("pmcid")
                if not identifier:
                    logger.warning(f"No DOI or PMCID in {path}")
                    results[str(path)] = {"error": "No DOI or PMCID found"}
                    continue

                # Enrich the paper
                enriched = self.enricher.enrich_paper(identifier=identifier, **kwargs)

                # Merge original and enrichment fields, enrichment takes precedence
                merged = dict(existing)
                merged.update(enriched.get("merged", {}))
                merged["enrichment_sources"] = enriched.get("sources", [])
                merged["enrichment_timestamp"] = enriched.get("enrichment_timestamp", None)

                results[str(path)] = {
                    "original": existing,
                    "enriched": enriched,
                    "merged": merged,
                }

            except Exception as e:
                logger.error(f"Failed to enrich from {file_path}: {e}")
                results[str(file_path)] = {"error": str(e)}

        return results

    def enrich_from_directory(
        self,
        directory: str | Path,
        pattern: str = "*.json",
        recursive: bool = False,
        **kwargs: Any,
    ) -> dict[str, dict[str, Any]]:
        """
        Enrich papers from all metadata files in a directory.

        Parameters
        ----------
        directory : str | Path
            Path to directory containing metadata files
        pattern : str, optional
            Glob pattern for file matching (default: "*.json")
        recursive : bool, optional
            Whether to search recursively (default: False)
        **kwargs
            Additional parameters for specific APIs

        Returns
        -------
        dict[str, dict[str, Any]]
            Dictionary mapping file path to enrichment results
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise ValueError(f"Directory does not exist: {directory}")

        files = [
            str(f) for f in (dir_path.rglob(pattern) if recursive else dir_path.glob(pattern))
        ]

        logger.info(f"Found {len(files)} files matching pattern '{pattern}' in {directory}")
        return self.enrich_from_files(files, **kwargs)

    def save_enriched_files(
        self,
        enrichment_results: dict[str, dict[str, Any]],
        output_directory: str | Path,
        overwrite: bool = False,
    ) -> list[str]:
        """
        Save enriched metadata to files.

        Parameters
        ----------
        enrichment_results : dict
            Results from enrich_from_files
        output_directory : str | Path
            Directory to save enriched files
        overwrite : bool, optional
            Whether to overwrite existing files (default: False)

        Returns
        -------
        list[str]
            List of saved file paths
        """
        output_dir = Path(output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files = []
        for file_path, result in enrichment_results.items():
            if "error" in result:
                logger.warning(f"Skipping file with error: {file_path}")
                continue

            try:
                # Create output filename
                input_path = Path(file_path)
                output_filename = f"{input_path.stem}_enriched{input_path.suffix}"
                output_path = output_dir / output_filename

                if output_path.exists() and not overwrite:
                    logger.warning(f"File exists, skipping: {output_path}")
                    continue

                # Save merged data
                merged_data = result.get("merged", {})
                with open(output_path, "w") as f:
                    json.dump(merged_data, f, indent=2, default=str)

                saved_files.append(str(output_path))
                logger.info(f"Saved enriched file: {output_path}")

            except Exception as e:
                logger.error(f"Failed to save enriched file for {file_path}: {e}")

        return saved_files

    def close(self) -> None:
        """Close the underlying enricher."""
        self.enricher.close()

    def __enter__(self) -> "FileEnricher":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and clean up resources."""
        self.close()
