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

import hashlib
import logging
import os
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
            {source}:{doc_id}:{format} → metadata.json
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
            Minimum free disk space to maintain in MB (default: 1GB)
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
        """
        # Sanitize ID for filesystem
        safe_id = artifact_id.replace("/", "_").replace(":", "_")
        return self.index_dir / f"{safe_id}.json"

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
        """Save index entry."""
        import json

        index_path = self._get_index_path(artifact_id)
        index_path.write_text(json.dumps(metadata.to_dict(), indent=2))

    def _load_index(self, artifact_id: str) -> ArtifactMetadata | None:
        """Load index entry."""
        import json

        index_path = self._get_index_path(artifact_id)
        if not index_path.exists():
            return None

        try:
            data = json.loads(index_path.read_text())
            return ArtifactMetadata.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load index for {artifact_id}: {e}")
            return None

    def _ensure_space(self, required_bytes: int) -> None:
        """
        Ensure sufficient disk space by running garbage collection if needed.

        Parameters
        ----------
        required_bytes : int
            Bytes needed for new artifact
        """
        current_usage = self.get_disk_usage()

        # Check if we need to free space
        if current_usage["used_bytes"] + required_bytes > self.size_limit_bytes:
            # Calculate how much to free (target 80% of limit)
            target_bytes = int(self.size_limit_bytes * 0.8)
            bytes_to_free = (current_usage["used_bytes"] + required_bytes) - target_bytes

            logger.info(
                f"Disk usage exceeds limit. Freeing {bytes_to_free / (1024 * 1024):.1f}MB..."
            )
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
        artifacts = []
        for index_file in self.index_dir.glob("*.json"):
            try:
                metadata = self._load_index(index_file.stem.replace("_", ":"))
                if metadata:
                    artifacts.append((index_file.stem, metadata.last_accessed, metadata.size))
            except Exception as e:
                logger.debug(f"Error loading {index_file}: {e}")
                continue

        # Sort by access time (oldest first)
        artifacts.sort(key=lambda x: x[1])

        # Delete oldest artifacts until we've freed enough space
        bytes_freed = 0
        for artifact_id, _, size in artifacts:
            if bytes_freed >= bytes_to_free:
                break

            # Delete index entry
            real_id = artifact_id.replace("_", ":")
            if self.delete(real_id):
                bytes_freed += size
                logger.debug(f"GC removed: {real_id} ({size} bytes)")

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
        referenced_hashes = set()
        for index_file in self.index_dir.glob("*.json"):
            try:
                metadata = self._load_index(index_file.stem.replace("_", ":"))
                if metadata:
                    referenced_hashes.add(metadata.hash_value)
            except (OSError, ValueError, KeyError) as e:
                logger.warning(f"Skipping corrupted index file {index_file}: {e}")
                continue

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

        # Get filesystem stats
        stat = os.statvfs(self.base_dir)
        fs_available = stat.f_bavail * stat.f_frsize
        fs_total = stat.f_blocks * stat.f_frsize

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
