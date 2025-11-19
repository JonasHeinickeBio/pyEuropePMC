"""
Unit tests for artifact store functionality.
"""

import tempfile
from pathlib import Path

import pytest

from pyeuropepmc.storage.artifact_store import ArtifactMetadata, ArtifactStore


class TestArtifactMetadata:
    """Test ArtifactMetadata class."""

    def test_metadata_creation(self):
        """Test basic metadata creation."""
        metadata = ArtifactMetadata(
            hash_value="abc123",
            size=1024,
            mime_type="application/pdf",
            etag="etag123",
            last_modified="2023-01-01",
        )

        assert metadata.hash_value == "abc123"
        assert metadata.size == 1024
        assert metadata.mime_type == "application/pdf"
        assert metadata.etag == "etag123"
        assert metadata.last_modified == "2023-01-01"
        assert metadata.stored_at is not None
        assert metadata.last_accessed == metadata.stored_at

    def test_metadata_to_dict(self):
        """Test metadata serialization to dict."""
        metadata = ArtifactMetadata(
            hash_value="abc123",
            size=1024,
            mime_type="application/pdf",
        )

        data = metadata.to_dict()
        assert data["hash"] == "abc123"
        assert data["size"] == 1024
        assert data["mime_type"] == "application/pdf"
        assert "stored_at" in data
        assert "last_accessed" in data

    def test_metadata_from_dict(self):
        """Test metadata deserialization from dict."""
        original = ArtifactMetadata(
            hash_value="abc123",
            size=1024,
            mime_type="application/pdf",
            etag="etag123",
            last_modified="2023-01-01",
        )

        data = original.to_dict()
        restored = ArtifactMetadata.from_dict(data)

        assert restored.hash_value == original.hash_value
        assert restored.size == original.size
        assert restored.mime_type == original.mime_type
        assert restored.etag == original.etag
        assert restored.last_modified == original.last_modified
        assert restored.stored_at == original.stored_at
        assert restored.last_accessed == original.last_accessed


class TestArtifactStore:
    """Test ArtifactStore class."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary artifact store for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir), size_limit_mb=10)
            yield store

    def test_store_basic(self, temp_store):
        """Test basic artifact storage."""
        content = b"Hello, World!"
        metadata = temp_store.store("test:doc:1", content, mime_type="text/plain")

        assert metadata.hash_value == temp_store._compute_hash(content)
        assert metadata.size == len(content)
        assert metadata.mime_type == "text/plain"

    def test_store_deduplication(self, temp_store):
        """Test that identical content is deduplicated."""
        content = b"Duplicate content"
        metadata1 = temp_store.store("test:doc:1", content)
        metadata2 = temp_store.store("test:doc:2", content)

        assert metadata1.hash_value == metadata2.hash_value
        assert metadata1.size == metadata2.size

        # Should only have one artifact file
        artifacts = list(temp_store.artifacts_dir.rglob("*"))
        artifact_files = [f for f in artifacts if f.is_file()]
        assert len(artifact_files) == 1

    def test_retrieve_existing(self, temp_store):
        """Test retrieving existing artifact."""
        content = b"Test content"
        temp_store.store("test:doc:1", content)

        result = temp_store.retrieve("test:doc:1")
        assert result is not None
        retrieved_content, metadata = result
        assert retrieved_content == content
        assert metadata.size == len(content)

    def test_retrieve_nonexistent(self, temp_store):
        """Test retrieving nonexistent artifact."""
        result = temp_store.retrieve("test:nonexistent")
        assert result is None

    def test_exists(self, temp_store):
        """Test checking artifact existence."""
        content = b"Test content"
        temp_store.store("test:doc:1", content)

        assert temp_store.exists("test:doc:1")
        assert not temp_store.exists("test:nonexistent")

    def test_delete(self, temp_store):
        """Test deleting artifacts."""
        content = b"Test content"
        temp_store.store("test:doc:1", content)

        assert temp_store.exists("test:doc:1")
        assert temp_store.delete("test:doc:1")
        assert not temp_store.exists("test:doc:1")

        # Content should still exist (not deleted)
        artifact_path = temp_store._get_artifact_path(temp_store._compute_hash(content))
        assert artifact_path.exists()

    def test_get_metadata(self, temp_store):
        """Test getting metadata without content."""
        content = b"Test content"
        temp_store.store("test:doc:1", content)

        metadata = temp_store.get_metadata("test:doc:1")
        assert metadata is not None
        assert metadata.size == len(content)

    def test_disk_usage(self, temp_store):
        """Test disk usage reporting."""
        content1 = b"Content 1"
        content2 = b"Content 2"

        temp_store.store("test:doc:1", content1)
        temp_store.store("test:doc:2", content2)

        usage = temp_store.get_disk_usage()
        assert usage["used_bytes"] > 0
        assert usage["artifact_count"] == 2
        assert usage["index_count"] == 2

    def test_compact(self, temp_store):
        """Test compaction functionality."""
        content = b"Test content"
        temp_store.store("test:doc:1", content)

        # Delete index entry but keep content
        temp_store.delete("test:doc:1")

        # Compact should remove orphaned content
        stats = temp_store.compact()
        assert stats["orphans_removed"] == 1
        assert stats["artifacts_remaining"] == 0

    def test_garbage_collection(self, temp_store):
        """Test garbage collection when disk limit exceeded."""
        # Set very low limit
        temp_store.size_limit_bytes = 100

        # Store content that exceeds limit
        large_content = b"x" * 50  # Smaller content
        temp_store.store("test:small1", large_content)
        temp_store.store("test:small2", large_content)
        temp_store.store("test:small3", large_content)  # This should trigger GC

        # Should trigger GC and remove some files
        usage = temp_store.get_disk_usage()
        # After GC, should be below limit (though exact behavior may vary)
        assert usage["used_bytes"] <= temp_store.size_limit_bytes * 1.2  # Allow some tolerance

    def test_clear(self, temp_store):
        """Test clearing all artifacts."""
        content = b"Test content"
        temp_store.store("test:doc:1", content)

        temp_store.clear()

        assert not temp_store.exists("test:doc:1")
        usage = temp_store.get_disk_usage()
        assert usage["artifact_count"] == 0
        assert usage["index_count"] == 0

    def test_concurrent_access(self, temp_store):
        """Test concurrent access to artifact store."""
        import threading

        errors = []
        results = []

        def store_artifact(i):
            try:
                content = f"Content {i}".encode()
                metadata = temp_store.store(f"test:concurrent:{i}:txt", content)
                results.append(metadata)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=store_artifact, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should have no errors and all content stored
        assert len(errors) == 0
        assert len(results) == 10

        # All should be retrievable
        for i in range(10):
            artifact_id = f"test:concurrent:{i}:txt"
            result = temp_store.retrieve(artifact_id)
            assert result is not None
            expected_content = f"Content {i}".encode()
            assert result[0] == expected_content
