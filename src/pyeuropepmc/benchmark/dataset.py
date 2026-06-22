"""
Benchmark dataset management — download, cache, and iterate.

Provides a registry of known benchmark datasets (PMC_sample_1943, PLOS_1000, etc.)
and a :class:`BenchmarkDataset` class for local or remote XML collections.

Download backends (tried in order):
  1. ``huggingface_hub`` (for Hugging Face datasets)
  2. ``requests`` (for direct HTTP/HTTPS URLs)
  3. ``urllib`` (stdlib fallback)
  4. Local filesystem (no download needed)
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import tarfile
from typing import Any
import zipfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------


@dataclass
class DatasetInfo:
    """Metadata describing a known benchmark dataset."""

    name: str
    """Short identifier (e.g. ``PMC_sample_1943``)."""

    source: str
    """Source URL or Hugging Face dataset path."""

    size_gb: float
    """Approximate download size in GB."""

    article_count: int
    """Number of articles in the dataset."""

    description: str
    """Human-readable description."""

    filename_glob: str = "*.xml"
    """Glob pattern to find XML files within the dataset."""

    expected_subdir: str = ""
    """Relative subdirectory where XML files live (empty = root)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "size_gb": self.size_gb,
            "article_count": self.article_count,
            "description": self.description,
        }


DATASETS: dict[str, DatasetInfo] = {
    "PMC_sample_1943": DatasetInfo(
        name="PMC_sample_1943",
        source="https://huggingface.co/datasets/sciencialab/grobid-evaluation",
        size_gb=1.5,
        article_count=1943,
        description=(
            "1943 articles from 1943 different journals (2011 PMC snapshot). "
            "Compiled by Alexandru Constantin. Gold standard for GROBID evaluation."
        ),
        filename_glob="*.nxml",
        expected_subdir="",
    ),
    "biorxiv-10k-test-2000": DatasetInfo(
        name="biorxiv-10k-test-2000",
        source="https://huggingface.co/datasets/sciencialab/grobid-evaluation",
        size_gb=5.4,
        article_count=2000,
        description=(
            "2000 bioRxiv preprints with manually reviewed NLM XML. "
            "Originally compiled by Daniel Ecer (eLife)."
        ),
        filename_glob="*.nxml",
        expected_subdir="",
    ),
    "PLOS_1000": DatasetInfo(
        name="PLOS_1000",
        source="https://huggingface.co/datasets/sciencialab/grobid-evaluation",
        size_gb=1.3,
        article_count=1000,
        description=(
            "1000 PLOS articles with publisher JATS XML. "
            "Randomly selected from PLOS Open Access collection."
        ),
        filename_glob="*.nxml",
        expected_subdir="",
    ),
    "eLife_984": DatasetInfo(
        name="eLife_984",
        source="https://huggingface.co/datasets/sciencialab/grobid-evaluation",
        size_gb=4.5,
        article_count=984,
        description=(
            "984 eLife articles with publisher JATS XML + HTML. "
            "From eLife's open collection on GitHub."
        ),
        filename_glob="*.nxml",
        expected_subdir="",
    ),
}


def dataset_info(name: str) -> DatasetInfo | None:
    """Look up dataset metadata by name (case-insensitive)."""
    for key, info in DATASETS.items():
        if key.lower() == name.lower():
            return info
    return None


# ---------------------------------------------------------------------------
# BenchmarkDataset
# ---------------------------------------------------------------------------


class BenchmarkDataset:
    """
    Manage a benchmark dataset — download, cache, iterate.

    Parameters
    ----------
    name : str
        Dataset name (``"PMC_sample_1943"``, ``"PLOS_1000"``, etc.)
        or ``"local"`` for a local directory.
    data_dir : str or Path, optional
        Root directory for storing/loading datasets.
        Defaults to ``~/pyeuropepmc_benchmark_data``.
    source : str, optional
        Custom download URL or Hugging Face path.
        If omitted, uses the registry default for known datasets.
    local_path : str or Path, optional
        For ``"local"`` datasets, the path to the XML directory.

    Examples
    --------
    >>> ds = BenchmarkDataset("PMC_sample_1943")
    >>> ds.download()
    >>> for article_path in ds.iter_articles():
    ...     print(article_path)
    """

    def __init__(
        self,
        name: str,
        data_dir: str | Path | None = None,
        source: str | None = None,
        local_path: str | Path | None = None,
    ):
        self.name = name
        self._info = dataset_info(name)

        if data_dir is None:
            data_dir = Path.home() / "pyeuropepmc_benchmark_data"
        self.data_dir = Path(data_dir)

        if name.lower() == "local":
            if local_path is None:
                raise ValueError("local_path is required for 'local' datasets")
            self._local_dir = Path(local_path)
        else:
            self._local_dir = self.data_dir / name

        self._source = source or (self._info.source if self._info else "")
        self._article_cache: list[Path] | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> DatasetInfo:
        """Return dataset metadata, or a minimal stub for unknown datasets."""
        if self._info:
            return self._info
        return DatasetInfo(
            name=self.name,
            source=self._source,
            size_gb=0.0,
            article_count=0,
            description="Custom dataset",
        )

    @property
    def is_downloaded(self) -> bool:
        """Check whether the dataset is already downloaded."""
        return self._local_dir.exists() and any(self._local_dir.rglob("*.xml"))

    @property
    def article_count(self) -> int:
        """Count articles currently available locally."""
        return len(list(self._local_dir.rglob(self.info.filename_glob)))

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(
        self,
        force: bool = False,
        progress_callback: Any | None = None,
    ) -> Path:
        """
        Download the dataset to the local cache directory.

        Parameters
        ----------
        force : bool
            If True, re-download even if already cached (default False).
        progress_callback : callable, optional
            Called with ``(bytes_downloaded, total_bytes)`` during download.

        Returns
        -------
        Path
            Path to the local dataset directory.
        """
        if not force and self.is_downloaded:
            logger.info("Dataset %s already downloaded at %s", self.name, self._local_dir)
            return self._local_dir

        if self.name.lower() == "local":
            raise ValueError("'local' datasets cannot be downloaded; provide local_path instead")

        logger.info("Downloading dataset %s from %s", self.name, self._source)

        # Try backends in order
        if _try_huggingface_download(self.name, self._local_dir, force, progress_callback):
            return self._local_dir

        if _try_http_download(self._source, self._local_dir, self.name, force, progress_callback):
            return self._local_dir

        raise ConnectionError(
            f"Could not download dataset {self.name}. Try manually from {self._source}"
        )

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def iter_articles(self) -> Iterator[Path]:
        """
        Yield paths to individual XML article files.

        Yields
        ------
        Path
            Absolute path to each XML file in the dataset.
        """
        if self._article_cache is not None:
            yield from self._article_cache
            return

        if not self._local_dir.exists():
            raise FileNotFoundError(
                f"Dataset directory not found: {self._local_dir}. Call .download() first."
            )

        pattern = self.info.filename_glob
        files = sorted(self._local_dir.rglob(pattern))
        self._article_cache = files
        yield from files

    def get_article_paths(self, limit: int | None = None) -> list[Path]:
        """Return all article paths, optionally limited."""
        paths = list(self.iter_articles())
        if limit is not None:
            paths = paths[:limit]
        return paths

    def reset_cache(self) -> None:
        """Clear the article path cache (e.g. after adding new files)."""
        self._article_cache = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize dataset metadata for reporting."""
        return {
            "name": self.name,
            "source": self._source,
            "local_path": str(self._local_dir),
            "is_downloaded": self.is_downloaded,
            "article_count": self.article_count,
            "info": self.info.to_dict(),
        }


# ---------------------------------------------------------------------------
# Download backends
# ---------------------------------------------------------------------------


def _try_huggingface_download(
    name: str,
    target_dir: Path,
    force: bool = False,
    progress_callback: Any | None = None,
) -> bool:
    """Try downloading from Hugging Face datasets library."""
    try:
        import datasets
    except ImportError:
        return False

    logger.debug("Attempting Hugging Face download for %s", name)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)

        # The GROBID evaluation datasets are on Hugging Face as:
        # sciencialab/grobid-evaluation
        ds = datasets.load_dataset(
            "sciencialab/grobid-evaluation",
            name,
            split="test",
            trust_remote_code=True,
        )

        # The dataset returns article metadata; actual files
        # are stored in the cache. We'll index them.
        manifest: list[dict[str, Any]] = []
        for i, article in enumerate(ds):
            manifest.append(
                {
                    "index": i,
                    "pmcid": article.get("pmcid", f"article_{i:04d}"),
                    "path": article.get("path", ""),
                }
            )

        manifest_path = target_dir / "hf_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(
            "Hugging Face dataset %s indexed %d articles at %s",
            name,
            len(manifest),
            target_dir,
        )
        return True

    except Exception as e:
        logger.warning("Hugging Face download failed: %s", e)
        return False


def _try_http_download(
    source_url: str,
    target_dir: Path,
    name: str,
    force: bool = False,
    progress_callback: Any | None = None,
) -> bool:
    """Try downloading from a direct HTTP URL."""
    # Try requests first, then urllib
    try:
        import requests  # noqa: F401

        _http_download_requests(source_url, target_dir, name, progress_callback)
        return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug("requests download failed: %s", e)

    try:
        _http_download_urllib(source_url, target_dir, name)
        return True
    except Exception as e:
        logger.debug("urllib download failed: %s", e)

    return False


def _http_download_requests(
    url: str,
    target_dir: Path,
    name: str,
    progress_callback: Any | None = None,
) -> None:
    """Download via the ``requests`` library."""
    import requests

    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = target_dir / f"{name}.zip"

    logger.info("Downloading %s → %s", url, archive_path)
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    downloaded = 0
    with open(archive_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if progress_callback and total:
                progress_callback(downloaded, total)

    _extract_archive(archive_path, target_dir)


def _http_download_urllib(url: str, target_dir: Path, name: str) -> None:
    """Download via stdlib ``urllib`` (fallback)."""
    import urllib.request

    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = target_dir / f"{name}.zip"

    logger.info("Downloading %s → %s (urllib)", url, archive_path)
    urllib.request.urlretrieve(url, archive_path)  # nosec

    _extract_archive(archive_path, target_dir)


def _extract_archive(archive_path: Path, target_dir: Path) -> None:
    """Extract zip or tar.gz archive and clean up."""
    logger.info("Extracting %s → %s", archive_path, target_dir)

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(target_dir)
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tf:
            tf.extractall(target_dir)
    else:
        logger.warning("Unknown archive format: %s", archive_path)
        return

    # Remove archive after extraction
    archive_path.unlink()
    logger.info("Extraction complete")
