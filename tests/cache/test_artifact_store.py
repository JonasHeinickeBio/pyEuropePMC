"""
Tests for content-addressed artifact storage.

These tests verify SHA-256 based storage, deduplication,
garbage collection, and disk management.
"""

import tempfile
from pathlib import Path
import time

import pytest

from pyeuropepmc.artifact_store import ArtifactMetadata, ArtifactStore


class TestArtifactMetadata:
    """Test artifact metadata handling."""

    def test_metadata_creation(self):
        """Test creating metadata."""
        metadata = ArtifactMetadata(
            hash_value="abc123",
            size=1024,
            mime_type="application/pdf",
            etag="xyz789",
            last_modified="2025-11-12T10:00:00Z",
        )

        assert metadata.hash_value == "abc123"
        assert metadata.size == 1024
        assert metadata.mime_type == "application/pdf"
        assert metadata.etag == "xyz789"
        assert metadata.last_modified == "2025-11-12T10:00:00Z"
        assert metadata.stored_at > 0
        assert metadata.last_accessed == metadata.stored_at

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = ArtifactMetadata(hash_value="abc123", size=1024)
        data = metadata.to_dict()

        assert data["hash"] == "abc123"
        assert data["size"] == 1024
        assert "stored_at" in data
        assert "last_accessed" in data

    def test_metadata_from_dict(self):
        """Test creating metadata from dictionary."""
        data = {
            "hash": "abc123",
            "size": 1024,
            "mime_type": "application/pdf",
            "stored_at": 1234567890.0,
            "last_accessed": 1234567900.0,
        }

        metadata = ArtifactMetadata.from_dict(data)

        assert metadata.hash_value == "abc123"
        assert metadata.size == 1024
        assert metadata.mime_type == "application/pdf"
        assert metadata.stored_at == 1234567890.0
        assert metadata.last_accessed == 1234567900.0


class TestArtifactStore:
    """Test artifact store operations."""

    def test_store_initialization(self, tmp_path):
        """Test artifact store initialization."""
        store = ArtifactStore(tmp_path, size_limit_mb=100)

        assert store.base_dir == tmp_path
        assert store.artifacts_dir.exists()
        assert store.index_dir.exists()
        assert store.size_limit_bytes == 100 * 1024 * 1024

    def test_store_and_retrieve_basic(self, tmp_path):
        """Test basic store and retrieve operations."""
        store = ArtifactStore(tmp_path)

        content = b"Hello, World!"
        artifact_id = "test:doc1:txt"

        # Store
        metadata = store.store(artifact_id, content, mime_type="text/plain")

        assert metadata.size == len(content)
        assert metadata.mime_type == "text/plain"
        assert len(metadata.hash_value) == 64  # SHA-256 hex

        # Retrieve
        result = store.retrieve(artifact_id)
        assert result is not None

        retrieved_content, retrieved_metadata = result
        assert retrieved_content == content
        assert retrieved_metadata.hash_value == metadata.hash_value

    def test_deduplication(self, tmp_path):
        """Test that identical content is deduplicated."""
        store = ArtifactStore(tmp_path)

        content = b"Duplicate content test"

        # Store same content with different IDs
        metadata1 = store.store("doc:1:txt", content)
        metadata2 = store.store("doc:2:txt", content)

        # Should have same hash
        assert metadata1.hash_value == metadata2.hash_value

        # Both should retrieve successfully
        result1 = store.retrieve("doc:1:txt")
        result2 = store.retrieve("doc:2:txt")

        assert result1 is not None
        assert result2 is not None
        assert result1[0] == result2[0] == content

        # But only one actual artifact file should exist
        usage = store.get_disk_usage()
        assert usage["artifact_count"] == 1  # Only one physical file
        assert usage["index_count"] == 2  # But two index entries

    def test_hash_computation(self, tmp_path):
        """Test SHA-256 hash computation."""
        store = ArtifactStore(tmp_path)

        content = b"test content"
        expected_hash = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"

        computed_hash = store._compute_hash(content)
        assert computed_hash == expected_hash

    def test_artifact_path_sharding(self, tmp_path):
        """Test that artifacts are sharded into subdirectories."""
        store = ArtifactStore(tmp_path)

        hash_value = "abcdef1234567890"
        path = store._get_artifact_path(hash_value)

        # Should be in subdirectory named after first 2 chars
        assert path.parent.name == "ab"
        assert path.name == hash_value

    def test_exists(self, tmp_path):
        """Test exists check."""
        store = ArtifactStore(tmp_path)

        artifact_id = "test:exists:check"

        # Should not exist initially
        assert not store.exists(artifact_id)

        # Store it
        store.store(artifact_id, b"content")

        # Should exist now
        assert store.exists(artifact_id)

    def test_get_metadata_without_content(self, tmp_path):
        """Test getting metadata without retrieving content."""
        store = ArtifactStore(tmp_path)

        content = b"Large content" * 1000
        artifact_id = "test:large:file"

        # Store
        stored_metadata = store.store(artifact_id, content)

        # Get metadata only
        metadata = store.get_metadata(artifact_id)

        assert metadata is not None
        assert metadata.hash_value == stored_metadata.hash_value
        assert metadata.size == len(content)

    def test_delete(self, tmp_path):
        """Test deleting artifact index."""
        store = ArtifactStore(tmp_path)

        artifact_id = "test:delete:me"
        store.store(artifact_id, b"content")

        # Should exist
        assert store.exists(artifact_id)

        # Delete
        assert store.delete(artifact_id)

        # Should not exist anymore
        assert not store.exists(artifact_id)

        # Deleting again should return False
        assert not store.delete(artifact_id)

    def test_http_metadata_storage(self, tmp_path):
        """Test storing HTTP metadata (ETag, Last-Modified)."""
        store = ArtifactStore(tmp_path)

        content = b"HTTP content"
        artifact_id = "http:test:doc"

        metadata = store.store(
            artifact_id,
            content,
            mime_type="application/pdf",
            etag='"abc123"',
            last_modified="Wed, 12 Nov 2025 10:00:00 GMT",
        )

        assert metadata.etag == '"abc123"'
        assert metadata.last_modified == "Wed, 12 Nov 2025 10:00:00 GMT"

        # Retrieve and check
        result = store.retrieve(artifact_id)
        assert result is not None
        _, retrieved_metadata = result

        assert retrieved_metadata.etag == '"abc123"'
        assert retrieved_metadata.last_modified == "Wed, 12 Nov 2025 10:00:00 GMT"

    def test_last_accessed_update(self, tmp_path):
        """Test that last_accessed is updated on retrieval."""
        store = ArtifactStore(tmp_path)

        artifact_id = "test:accessed:track"
        store.store(artifact_id, b"content")

        # Get initial access time
        metadata1 = store.get_metadata(artifact_id)
        initial_accessed = metadata1.last_accessed

        # Wait a bit
        time.sleep(0.1)

        # Retrieve (updates access time)
        store.retrieve(artifact_id)

        # Check access time was updated
        metadata2 = store.get_metadata(artifact_id)
        assert metadata2.last_accessed > initial_accessed


class TestDiskManagement:
    """Test disk usage monitoring and management."""

    def test_disk_usage_stats(self, tmp_path):
        """Test disk usage statistics."""
        store = ArtifactStore(tmp_path, size_limit_mb=10)

        # Initially empty
        usage = store.get_disk_usage()
        assert usage["used_bytes"] == 0
        assert usage["artifact_count"] == 0
        assert usage["index_count"] == 0
        assert usage["limit_mb"] == 10

        # Store some content
        store.store("doc:1", b"x" * 1024)  # 1KB
        store.store("doc:2", b"y" * 2048)  # 2KB

        usage = store.get_disk_usage()
        assert usage["used_bytes"] == 1024 + 2048
        assert usage["artifact_count"] == 2
        assert usage["index_count"] == 2
        assert usage["used_percent"] > 0

    def test_garbage_collection_lru(self, tmp_path):
        """Test LRU-based garbage collection."""
        store = ArtifactStore(tmp_path, size_limit_mb=1)  # 1MB limit

        # Store multiple artifacts with DIFFERENT content (avoid dedup)
        for i in range(5):
            content = f"unique content {i} ".encode() * 10000  # ~100KB each, unique
            store.store(f"doc:{i}", content)
            time.sleep(0.05)  # Ensure different access times

        usage_before = store.get_disk_usage()

        # Force garbage collection
        bytes_freed = store._garbage_collect(200000)  # Free 200KB

        usage_after = store.get_disk_usage()

        # Should have freed at least 200KB
        assert bytes_freed >= 200000
        assert usage_after["used_bytes"] < usage_before["used_bytes"]

    def test_auto_space_management(self, tmp_path):
        """Test automatic space management when limit exceeded."""
        # Small limit to trigger GC
        store = ArtifactStore(tmp_path, size_limit_mb=1)

        # Store artifacts until limit is approached
        for i in range(15):
            content = b"x" * 100000  # 100KB each = 1.5MB total
            store.store(f"doc:{i}", content)

        # Should have triggered GC automatically
        usage = store.get_disk_usage()
        assert usage["used_bytes"] < store.size_limit_bytes

    def test_orphaned_artifact_cleanup(self, tmp_path):
        """Test cleaning up orphaned artifacts."""
        store = ArtifactStore(tmp_path)

        # Store and then delete index entry
        artifact_id = "test:orphan:cleanup"
        metadata = store.store(artifact_id, b"orphaned content")

        # Delete index but leave artifact file
        index_path = store._get_index_path(artifact_id)
        index_path.unlink()

        # Artifact file still exists
        artifact_path = store._get_artifact_path(metadata.hash_value)
        assert artifact_path.exists()

        # Clean orphans
        removed = store._clean_orphaned_artifacts()

        # Should have removed the orphaned artifact
        assert removed >= 1
        assert not artifact_path.exists()

    def test_compact(self, tmp_path):
        """Test full compaction."""
        store = ArtifactStore(tmp_path)

        # Store some artifacts
        store.store("doc:1", b"content 1")
        store.store("doc:2", b"content 2")

        # Delete one index (creates orphan)
        store.delete("doc:1")

        # Compact
        stats = store.compact()

        assert "orphans_removed" in stats
        assert "artifacts_remaining" in stats
        assert stats["index_entries"] == 1  # Only doc:2 remains


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_retrieve_nonexistent(self, tmp_path):
        """Test retrieving non-existent artifact."""
        store = ArtifactStore(tmp_path)

        result = store.retrieve("nonexistent:doc")
        assert result is None

    def test_get_metadata_nonexistent(self, tmp_path):
        """Test getting metadata for non-existent artifact."""
        store = ArtifactStore(tmp_path)

        metadata = store.get_metadata("nonexistent:doc")
        assert metadata is None

    def test_empty_content(self, tmp_path):
        """Test storing empty content."""
        store = ArtifactStore(tmp_path)

        metadata = store.store("empty:doc", b"")

        assert metadata.size == 0
        assert len(metadata.hash_value) == 64

        result = store.retrieve("empty:doc")
        assert result is not None
        content, _ = result
        assert content == b""

    def test_large_content(self, tmp_path):
        """Test storing large content."""
        store = ArtifactStore(tmp_path)

        # 10MB content
        large_content = b"x" * (10 * 1024 * 1024)
        metadata = store.store("large:doc", large_content)

        assert metadata.size == 10 * 1024 * 1024

        result = store.retrieve("large:doc")
        assert result is not None
        retrieved_content, _ = result
        assert len(retrieved_content) == len(large_content)

    def test_special_characters_in_id(self, tmp_path):
        """Test artifact IDs with special characters."""
        store = ArtifactStore(tmp_path)

        # IDs with colons, slashes, etc.
        artifact_id = "pmc:PMC123456/fulltext:pdf"
        content = b"test content"

        metadata = store.store(artifact_id, content)

        # Should retrieve successfully
        result = store.retrieve(artifact_id)
        assert result is not None
        assert result[0] == content

    def test_clear_all(self, tmp_path):
        """Test clearing all artifacts."""
        store = ArtifactStore(tmp_path)

        # Store multiple artifacts
        for i in range(5):
            store.store(f"doc:{i}", b"content" * i)

        usage_before = store.get_disk_usage()
        assert usage_before["artifact_count"] > 0
        assert usage_before["index_count"] > 0

        # Clear
        store.clear()

        usage_after = store.get_disk_usage()
        assert usage_after["artifact_count"] == 0
        assert usage_after["index_count"] == 0
        assert usage_after["used_bytes"] == 0


class TestDeduplicationScenarios:
    """Test various deduplication scenarios."""

    def test_same_content_different_metadata(self, tmp_path):
        """Test that same content with different metadata is deduplicated."""
        store = ArtifactStore(tmp_path)

        content = b"shared content"

        # Store with different metadata
        m1 = store.store("doc:1", content, mime_type="text/plain", etag="etag1")
        m2 = store.store("doc:2", content, mime_type="application/json", etag="etag2")

        # Same hash (content is identical)
        assert m1.hash_value == m2.hash_value

        # But different metadata
        assert m1.mime_type != m2.mime_type
        assert m1.etag != m2.etag

        # Only one artifact file
        usage = store.get_disk_usage()
        assert usage["artifact_count"] == 1

    def test_dedup_across_types(self, tmp_path):
        """Test deduplication across different artifact types."""
        store = ArtifactStore(tmp_path)

        content = b"universal content"

        # Store as different types
        store.store("pdf:doc1:pdf", content, mime_type="application/pdf")
        store.store("xml:doc1:xml", content, mime_type="application/xml")
        store.store("txt:doc1:txt", content, mime_type="text/plain")

        # All should share same hash
        m1 = store.get_metadata("pdf:doc1:pdf")
        m2 = store.get_metadata("xml:doc1:xml")
        m3 = store.get_metadata("txt:doc1:txt")

        assert m1.hash_value == m2.hash_value == m3.hash_value

        # But only one artifact file
        usage = store.get_disk_usage()
        assert usage["artifact_count"] == 1
        assert usage["index_count"] == 3

    def test_dedup_storage_savings(self, tmp_path):
        """Test storage savings from deduplication."""
        store = ArtifactStore(tmp_path)

        content = b"x" * 1000000  # 1MB

        # Store same content 10 times with different IDs
        for i in range(10):
            store.store(f"doc:{i}", content)

        usage = store.get_disk_usage()

        # Without dedup: ~10MB
        # With dedup: ~1MB
        assert usage["used_mb"] < 2  # Should be close to 1MB, not 10MB
        assert usage["artifact_count"] == 1  # Only one physical file
        assert usage["index_count"] == 10  # But 10 index entries
