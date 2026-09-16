"""Regression tests for the artifact store defects fixed alongside these tests.

Covered here:

- artifact IDs that sanitize to the same filename ("a:b" and "a_b") no longer
  share one index file;
- garbage collection and orphan cleanup read the index files directly instead
  of guessing the ID back from the filename;
- ``min_free_space_mb`` is enforced, not just stored.

Every test writes inside a pytest ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from pyeuropepmc.storage.artifact_store import ArtifactStore


class TestIndexIdentityIsPreserved:
    def test_ids_that_sanitize_alike_keep_separate_entries(self, tmp_path):
        """The IDs "a:b" and "a_b" both sanitize to "a_b" and used to overwrite."""
        store = ArtifactStore(tmp_path)

        store.store("a:b", b"colon content")
        store.store("a_b", b"underscore content")

        colon = store.retrieve("a:b")
        underscore = store.retrieve("a_b")

        assert colon is not None and colon[0] == b"colon content"
        assert underscore is not None and underscore[0] == b"underscore content"
        assert len(list((tmp_path / "index").glob("*.json"))) == 2

    def test_ids_differing_only_in_separator_style(self, tmp_path):
        """A slash and a colon both sanitize to an underscore."""
        store = ArtifactStore(tmp_path)

        store.store("pmc/PMC1:pdf", b"slash")
        store.store("pmc:PMC1:pdf", b"colon")

        slashed = store.retrieve("pmc/PMC1:pdf")
        coloned = store.retrieve("pmc:PMC1:pdf")

        assert slashed is not None and slashed[0] == b"slash"
        assert coloned is not None and coloned[0] == b"colon"

    def test_deleting_one_leaves_the_other(self, tmp_path):
        store = ArtifactStore(tmp_path)
        store.store("a:b", b"colon content")
        store.store("a_b", b"underscore content")

        assert store.delete("a:b") is True

        assert store.exists("a:b") is False
        assert store.exists("a_b") is True

    def test_index_file_records_the_artifact_id(self, tmp_path):
        store = ArtifactStore(tmp_path)
        store.store("pmc:PMC123456:pdf", b"content")

        index_file = next((tmp_path / "index").glob("*.json"))
        data = json.loads(index_file.read_text())

        assert data["artifact_id"] == "pmc:PMC123456:pdf"


class TestGarbageCollection:
    def test_collection_removes_least_recently_accessed_entries(self, tmp_path):
        # 1 MB limit, so storing the third 400 KB artifact trips the limit.
        store = ArtifactStore(tmp_path, size_limit_mb=1, min_free_space_mb=0)
        store.store("first:pdf", b"a" * 400_000)
        store.store("second:pdf", b"b" * 400_000)

        retrieved = store.retrieve("second:pdf")  # refresh its access time
        assert retrieved is not None

        store.store("third:pdf", b"c" * 400_000)

        assert store.exists("first:pdf") is False
        assert store.exists("third:pdf") is True

    def test_collection_handles_ids_containing_underscores(self, tmp_path):
        """The ID is read from the file, not guessed from the filename."""
        store = ArtifactStore(tmp_path, size_limit_mb=1, min_free_space_mb=0)
        store.store("under_score:pdf", b"a" * 600_000)
        store.store("other:pdf", b"b" * 600_000)

        # The oldest entry is gone and its content file with it; nothing that
        # is still indexed was collected by mistake.
        remaining = [
            artifact_id
            for _, artifact_id, _ in store._iter_index_entries()
            if artifact_id is not None
        ]
        assert remaining == ["other:pdf"]
        assert store.retrieve("other:pdf") is not None

    def test_orphaned_content_is_removed(self, tmp_path):
        store = ArtifactStore(tmp_path)
        metadata = store.store("pmc:PMC1:pdf", b"content")
        store.delete("pmc:PMC1:pdf")

        stats = store.compact()

        assert stats["orphans_removed"] == 1
        assert not store._get_artifact_path(metadata.hash_value).exists()

    def test_referenced_content_survives_compaction(self, tmp_path):
        store = ArtifactStore(tmp_path)
        metadata = store.store("under_score:pdf", b"content")

        stats = store.compact()

        assert stats["orphans_removed"] == 0
        assert store._get_artifact_path(metadata.hash_value).exists()

    def test_corrupt_index_file_is_skipped(self, tmp_path):
        store = ArtifactStore(tmp_path)
        store.store("good:pdf", b"content")
        (tmp_path / "index" / "broken.json").write_text("{not json")

        assert store.compact()["orphans_removed"] == 0
        assert store.retrieve("good:pdf") is not None


class TestMinimumFreeSpace:
    def test_low_free_space_triggers_collection(self, tmp_path):
        """A store below its size limit still collects to protect the disk."""
        store = ArtifactStore(tmp_path, size_limit_mb=10_000, min_free_space_mb=1)
        store.store("old:pdf", b"a" * 1000)

        usage = store.get_disk_usage()
        # Report only 500 KB free, half of the 1 MB floor.
        usage["fs_available_bytes"] = 500 * 1024

        with (
            patch.object(store, "get_disk_usage", return_value=usage),
            patch.object(store, "_garbage_collect", return_value=0) as gc,
        ):
            store.store("new:pdf", b"b" * 1000)

        gc.assert_called_once()
        assert gc.call_args[0][0] > 0

    def test_ample_free_space_does_not_trigger_collection(self, tmp_path):
        store = ArtifactStore(tmp_path, size_limit_mb=10_000, min_free_space_mb=1)

        with patch.object(store, "_garbage_collect", return_value=0) as gc:
            store.store("new:pdf", b"b" * 1000)

        gc.assert_not_called()

    def test_zero_floor_keeps_the_previous_behaviour(self, tmp_path):
        store = ArtifactStore(tmp_path, size_limit_mb=10_000, min_free_space_mb=0)

        with patch.object(store, "_garbage_collect", return_value=0) as gc:
            store.store("new:pdf", b"b" * 1000)

        gc.assert_not_called()


class TestReadIndexFile:
    def test_entry_without_recorded_id_still_loads(self, tmp_path):
        """Index files written before the ID was recorded stay readable."""
        store = ArtifactStore(tmp_path)
        store.store("pmc:PMC1:pdf", b"content")

        index_file = next((tmp_path / "index").glob("*.json"))
        data = json.loads(index_file.read_text())
        del data["artifact_id"]
        index_file.write_text(json.dumps(data))

        entry = store._read_index_file(index_file)

        assert entry is not None
        artifact_id, metadata = entry
        assert artifact_id is None
        assert metadata.size == len(b"content")

    def test_unreadable_file_returns_none(self, tmp_path):
        store = ArtifactStore(tmp_path)
        broken = Path(tmp_path) / "index" / "broken.json"
        broken.write_text("{not json")

        assert store._read_index_file(broken) is None
