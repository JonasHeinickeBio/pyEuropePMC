"""
Content-addressed artifact storage for PyEuropePMC.

This module provides SHA-256 based content addressing for large files
(PDF, XML, ZIP) with automatic deduplication and disk management.

Features:
- Content-addressed storage (same content = same hash = stored once)
- SHA-256 based addressing
- Index mapping: ID → Hash → Path
- Automatic deduplication
- Disk usage monitoring and management
- LRU-based eviction when disk limit reached
"""

from collections.abc import Iterator
import hashlib
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Any

logger = logging.getLogger(__name__)


class ArtifactMetadata:
    """Metadata for a cached artifact."""

    def __init__(
        self,
        hash_value: str,
        size: int,
        mime_type: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        stored_at: float | None = None,
    ):
        """
        Initialize artifact metadata.

        Parameters
        ----------
        hash_value : str
            SHA-256 hash of the content
        size : int
            Size in bytes
        mime_type : str, optional
            MIME type of the content
        etag : str, optional
            ETag from HTTP response
        last_modified : str, optional
            Last-Modified timestamp from HTTP response
        stored_at : float, optional
            Unix timestamp when stored (defaults to now)
        """
        self.hash_value = hash_value
        self.size = size
        self.mime_type = mime_type
        self.etag = etag
        self.last_modified = last_modified
        self.stored_at = stored_at or time.time()
        self.last_accessed = self.stored_at

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "hash": self.hash_value,
            "size": self.size,
            "mime_type": self.mime_type,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "stored_at": self.stored_at,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactMetadata":
        """Create metadata from dictionary."""
        metadata = cls(
            hash_value=data["hash"],
            size=data["size"],
            mime_type=data.get("mime_type"),
            etag=data.get("etag"),
            last_modified=data.get("last_modified"),
            stored_at=data.get("stored_at"),
        )
        metadata.last_accessed = data.get("last_accessed", metadata.stored_at)
        return metadata


class ArtifactStore:
    """
    Content-addressed artifact storage with deduplication.

    This class provides:
    - SHA-256 based content addressing
    - Automatic deduplication (same content stored once)
    - Index mapping: ID → Hash → Path
    - Disk usage monitoring
    - LRU-based eviction when limit reached

    Storage Structure:
    ```
    base_dir/
        artifacts/
            ab/
                abc123...def (actual content file)
            cd/
                cde456...ghi
        index/
            pmc_PMC123456_pdf.<id digest>.json (metadata for one artifact ID)
    ```
    """

    def __init__(
        self,
        base_dir: Path,
        size_limit_mb: int = 10000,  # 10GB default
        min_free_space_mb: int = 1000,  # 1GB minimum free space
    ):
        """
        Initialize artifact store.

        Parameters
        ----------
        base_dir : Path
            Base directory for artifact storage
        size_limit_mb : int, optional
            Maximum storage size in MB (default: 10GB)
        min_free_space_mb : int, optional
            Minimum free disk space to keep on the filesystem in MB
            (default: 1GB). Storing an artifact that would leave less than
            this free triggers garbage collection first.
        """
        self.base_dir = Path(base_dir)
        self.artifacts_dir = self.base_dir / "artifacts"
        self.index_dir = self.base_dir / "index"
        self.size_limit_bytes = size_limit_mb * 1024 * 1024
        self.min_free_space_bytes = min_free_space_mb * 1024 * 1024

        # Create directories
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Artifact store initialized: {self.base_dir} "
            f"(limit: {size_limit_mb}MB, min_free: {min_free_space_mb}MB)"
        )

    def _get_artifact_path(self, hash_value: str) -> Path:
        """
        Get storage path for a hash using 2-character prefix sharding.

        Parameters
        ----------
        hash_value : str
            SHA-256 hash

        Returns
        -------
        Path
            Full path to artifact file
        """
        # Use first 2 characters for directory sharding
        prefix = hash_value[:2]
        artifact_dir = self.artifacts_dir / prefix
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir / hash_value

    def _get_index_path(self, artifact_id: str) -> Path:
        """
        Get index path for an artifact ID.

        Parameters
        ----------
        artifact_id : str
            Artifact identifier (e.g., "pmc:PMC123456:pdf")

        Returns
        -------
        Path
            Path to index metadata file

        Notes
        -----
        Sanitizing the ID for the filesystem maps different IDs onto the same
        name ("a:b" and "a_b" both become "a_b"), so a digest of the original
        ID is appended to keep entries apart. The sanitized part is kept for
        readability when looking through the index directory.
        """
        # Sanitize ID for filesystem
        safe_id = artifact_id.replace("/", "_").replace(":", "_")
        digest = hashlib.sha256(artifact_id.encode("utf-8")).hexdigest()[:12]
        return self.index_dir / f"{safe_id}.{digest}.json"

    def _compute_hash(self, content: bytes) -> str:
        """
        Compute SHA-256 hash of content.

        Parameters
        ----------
        content : bytes
            Content to hash

        Returns
        -------
        str
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(content).hexdigest()

    def store(
        self,
        artifact_id: str,
        content: bytes,
        mime_type: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> ArtifactMetadata:
        """
        Store artifact content with automatic deduplication.

        If the same content already exists (same hash), it won't be
        stored again. The index will just point to the existing content.

        Parameters
        ----------
        artifact_id : str
            Unique identifier (e.g., "pmc:PMC123456:pdf")
        content : bytes
            Artifact content
        mime_type : str, optional
            MIME type
        etag : str, optional
            ETag from HTTP response
        last_modified : str, optional
            Last-Modified timestamp

        Returns
        -------
        ArtifactMetadata
            Metadata for the stored artifact

        Examples
        --------
        >>> store = ArtifactStore(Path("/cache"))
        >>> metadata = store.store("pmc:PMC123:pdf", pdf_bytes, mime_type="application/pdf")
        >>> print(f"Stored with hash: {metadata.hash_value}")
        """
        # Compute hash
        hash_value = self._compute_hash(content)
        artifact_path = self._get_artifact_path(hash_value)

        # Store content if not already present (deduplication)
        if not artifact_path.exists():
            # Check if we need to free space
            self._ensure_space(len(content))

            # Write content
            artifact_path.write_bytes(content)
            logger.info(f"Stored new artifact: {hash_value} ({len(content)} bytes)")
        else:
            logger.debug(f"Artifact already exists (deduped): {hash_value}")

        # Create/update metadata
        metadata = ArtifactMetadata(
            hash_value=hash_value,
            size=len(content),
            mime_type=mime_type,
            etag=etag,
            last_modified=last_modified,
        )

        # Store index entry
        self._save_index(artifact_id, metadata)

        return metadata

    def retrieve(self, artifact_id: str) -> tuple[bytes, ArtifactMetadata] | None:
        """
        Retrieve artifact by ID.

        Parameters
        ----------
        artifact_id : str
            Unique identifier

        Returns
        -------
        tuple[bytes, ArtifactMetadata] or None
            Content and metadata, or None if not found

        Examples
        --------
        >>> result = store.retrieve("pmc:PMC123:pdf")
        >>> if result:
        >>>     content, metadata = result
        >>>     print(f"Retrieved {len(content)} bytes")
        """
        # Load metadata from index
        metadata = self._load_index(artifact_id)
        if not metadata:
            return None

        # Get content
        artifact_path = self._get_artifact_path(metadata.hash_value)
        if not artifact_path.exists():
            logger.warning(f"Artifact content missing for {artifact_id}: {metadata.hash_value}")
            return None

        # Update access time
        metadata.last_accessed = time.time()
        self._save_index(artifact_id, metadata)

        # Read and return content
        content = artifact_path.read_bytes()
        return content, metadata

    def get_metadata(self, artifact_id: str) -> ArtifactMetadata | None:
        """
        Get metadata without retrieving content.

        Parameters
        ----------
        artifact_id : str
            Unique identifier

        Returns
        -------
        ArtifactMetadata or None
            Metadata if found, None otherwise
        """
        return self._load_index(artifact_id)

    def exists(self, artifact_id: str) -> bool:
        """
        Check if artifact exists.

        Parameters
        ----------
        artifact_id : str
            Unique identifier

        Returns
        -------
        bool
            True if artifact exists
        """
        return self._get_index_path(artifact_id).exists()

    def delete(self, artifact_id: str) -> bool:
        """
        Delete artifact index entry.

        Note: This only removes the index entry, not the actual content.
        Content is removed during garbage collection if no longer referenced.

        Parameters
        ----------
        artifact_id : str
            Unique identifier

        Returns
        -------
        bool
            True if deleted, False if not found
        """
        index_path = self._get_index_path(artifact_id)
        if index_path.exists():
            index_path.unlink()
            logger.debug(f"Deleted index entry: {artifact_id}")
            return True
        return False

    def _save_index(self, artifact_id: str, metadata: ArtifactMetadata) -> None:
        """Save index entry, recording the ID the entry belongs to."""
        payload = metadata.to_dict()
        payload["artifact_id"] = artifact_id
        index_path = self._get_index_path(artifact_id)
        index_path.write_text(json.dumps(payload, indent=2))

    def _load_index(self, artifact_id: str) -> ArtifactMetadata | None:
        """Load index entry."""
        index_path = self._get_index_path(artifact_id)
        if not index_path.exists():
            return None

        entry = self._read_index_file(index_path)
        if entry is None:
            logger.warning(f"Failed to load index for {artifact_id}")
            return None
        return entry[1]

    @staticmethod
    def _read_index_file(index_path: Path) -> tuple[str | None, ArtifactMetadata] | None:
        """
        Read one index file.

        Returns
        -------
        tuple[str | None, ArtifactMetadata] or None
            The artifact ID the file was written for and its metadata, or
            None if the file cannot be read. The ID is None for files written
            before it was recorded.
        """
        try:
            data = json.loads(index_path.read_text())
            return data.get("artifact_id"), ArtifactMetadata.from_dict(data)
        except (OSError, ValueError, KeyError) as e:
            logger.warning(f"Skipping unreadable index file {index_path}: {e}")
            return None

    def _iter_index_entries(self) -> Iterator[tuple[Path, str | None, ArtifactMetadata]]:
        """Yield (path, artifact_id, metadata) for every readable index file."""
        for index_file in self.index_dir.glob("*.json"):
            entry = self._read_index_file(index_file)
            if entry is not None:
                yield index_file, entry[0], entry[1]

    def _ensure_space(self, required_bytes: int) -> None:
        """
        Ensure sufficient disk space by running garbage collection if needed.

        Parameters
        ----------
        required_bytes : int
            Bytes needed for new artifact
        """
        current_usage = self.get_disk_usage()
        used_after = current_usage["used_bytes"] + required_bytes

        # How much the store itself has to give back to stay under its limit
        # (target 80% of it), and to leave min_free_space_mb free on the
        # filesystem once the new artifact is written.
        bytes_to_free = 0
        if used_after > self.size_limit_bytes:
            bytes_to_free = used_after - int(self.size_limit_bytes * 0.8)
            logger.info(
                f"Disk usage exceeds limit. Freeing {bytes_to_free / (1024 * 1024):.1f}MB..."
            )

        free_after = current_usage["fs_available_bytes"] - required_bytes
        if free_after < self.min_free_space_bytes:
            shortfall = self.min_free_space_bytes - free_after
            if shortfall > bytes_to_free:
                bytes_to_free = shortfall
                logger.info(
                    f"Free disk space would drop below "
                    f"{self.min_free_space_bytes / (1024 * 1024):.1f}MB. "
                    f"Freeing {bytes_to_free / (1024 * 1024):.1f}MB..."
                )

        if bytes_to_free > 0:
            self._garbage_collect(bytes_to_free)

    def _garbage_collect(self, bytes_to_free: int) -> int:
        """
        Run garbage collection using LRU strategy.

        Parameters
        ----------
        bytes_to_free : int
            Minimum bytes to free

        Returns
        -------
        int
            Bytes actually freed
        """
        # Build list of all artifacts with their access times
        artifacts = [
            (index_file, artifact_id, metadata.last_accessed, metadata.size)
            for index_file, artifact_id, metadata in self._iter_index_entries()
        ]

        # Sort by access time (oldest first)
        artifacts.sort(key=lambda x: x[2])

        # Delete oldest artifacts until we've freed enough space
        bytes_freed = 0
        for index_file, artifact_id, _, size in artifacts:
            if bytes_freed >= bytes_to_free:
                break

            # Delete index entry by path: the filename cannot be turned back
            # into the ID it was written for.
            try:
                index_file.unlink()
            except OSError as e:
                logger.debug(f"Could not remove index file {index_file}: {e}")
                continue

            bytes_freed += size
            logger.debug(f"GC removed: {artifact_id or index_file.name} ({size} bytes)")

        # Clean up unreferenced content files
        self._clean_orphaned_artifacts()

        logger.info(f"Garbage collection freed {bytes_freed / (1024 * 1024):.1f}MB")
        return bytes_freed

    def _clean_orphaned_artifacts(self) -> int:
        """
        Remove artifact files that are no longer referenced by any index.

        Returns
        -------
        int
            Number of files removed
        """
        # Build set of referenced hashes
        referenced_hashes = {metadata.hash_value for _, _, metadata in self._iter_index_entries()}

        # Find and remove unreferenced artifacts
        removed_count = 0
        for artifact_file in self.artifacts_dir.rglob("*"):
            if artifact_file.is_file():
                hash_value = artifact_file.name
                if hash_value not in referenced_hashes:
                    artifact_file.unlink()
                    removed_count += 1
                    logger.debug(f"Removed orphaned artifact: {hash_value}")

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} orphaned artifacts")

        return removed_count

    def get_disk_usage(self) -> dict[str, Any]:
        """
        Get current disk usage statistics.

        Returns
        -------
        dict
            Usage statistics including used/available bytes and percentages
        """
        total_size = 0
        file_count = 0

        # Calculate total size of artifacts
        for artifact_file in self.artifacts_dir.rglob("*"):
            if artifact_file.is_file():
                total_size += artifact_file.stat().st_size
                file_count += 1

        # Count index entries
        index_count = len(list(self.index_dir.glob("*.json")))

        # Filesystem stats. `shutil.disk_usage` is cross-platform; `os.statvfs`
        # does not exist on Windows at all, so this raised AttributeError there.
        usage = shutil.disk_usage(self.base_dir)
        fs_available = usage.free
        fs_total = usage.total

        return {
            "used_bytes": total_size,
            "used_mb": round(total_size / (1024 * 1024), 2),
            "limit_bytes": self.size_limit_bytes,
            "limit_mb": round(self.size_limit_bytes / (1024 * 1024), 2),
            "used_percent": round((total_size / self.size_limit_bytes) * 100, 2)
            if self.size_limit_bytes > 0
            else 0,
            "artifact_count": file_count,
            "index_count": index_count,
            "fs_available_bytes": fs_available,
            "fs_available_mb": round(fs_available / (1024 * 1024), 2),
            "fs_total_bytes": fs_total,
            "fs_total_mb": round(fs_total / (1024 * 1024), 2),
        }

    def compact(self) -> dict[str, int]:
        """
        Run full compaction: clean orphaned artifacts and optimize storage.

        Returns
        -------
        dict
            Statistics about compaction (orphans_removed, etc.)
        """
        logger.info("Starting artifact store compaction...")

        orphans_removed = self._clean_orphaned_artifacts()

        # Get final stats
        usage = self.get_disk_usage()

        stats = {
            "orphans_removed": orphans_removed,
            "artifacts_remaining": usage["artifact_count"],
            "index_entries": usage["index_count"],
            "used_mb": usage["used_mb"],
        }

        logger.info(f"Compaction complete: {stats}")
        return stats

    def clear(self) -> None:
        """
        Clear all artifacts and index entries.

        Warning: This removes all stored data!
        """
        logger.warning("Clearing all artifacts and index entries...")

        # Remove all artifacts
        if self.artifacts_dir.exists():
            shutil.rmtree(self.artifacts_dir)
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Remove all index entries
        if self.index_dir.exists():
            shutil.rmtree(self.index_dir)
            self.index_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Artifact store cleared")
