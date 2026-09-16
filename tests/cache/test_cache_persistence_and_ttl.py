"""Regression tests for the cache defects fixed alongside these tests.

Covered here:

- the L2 database survives a restart and is shared by concurrent backends
  (it used to be deleted on every open, see ``_prepare_l2_database``);
- L1 honours the per-entry ``expire`` and the ``ttl_by_type`` of a data type
  instead of one TTL for the whole layer;
- ``pyeuropepmc.cache`` re-exports the public names;
- ``CacheConfig`` rejects a wrong type and an unknown eviction policy with
  ``ConfigurationError``;
- one lookup counts as one miss, whatever the layers do;
- ``get_keys()``, ``compact()`` and ``invalidate_older_than()`` reach L2.

Every test writes inside a pytest ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import time

import pytest

from pyeuropepmc.cache.cache import (
    CACHETOOLS_AVAILABLE,
    DISKCACHE_AVAILABLE,
    CacheBackend,
    CacheConfig,
    CacheDataType,
    CacheLayer,
)
from pyeuropepmc.core.exceptions import ConfigurationError


def _l2_backend(cache_dir: Path, **overrides: object) -> CacheBackend:
    """Build an L1+L2 backend on ``cache_dir``."""
    kwargs: dict[str, object] = {
        "enabled": True,
        "cache_dir": cache_dir,
        "ttl": 60,
        "size_limit_mb": 1,
        "enable_l2": True,
        "l2_size_limit_mb": 1,
    }
    kwargs.update(overrides)
    return CacheBackend(CacheConfig(**kwargs))  # type: ignore[arg-type]


class TestCachePackageExports:
    def test_public_names_are_importable_from_the_package(self):
        import pyeuropepmc.cache as cache_package

        assert cache_package.CacheConfig is CacheConfig
        assert cache_package.CacheBackend is CacheBackend
        assert cache_package.CacheDataType is CacheDataType
        assert cache_package.CacheLayer is CacheLayer
        assert callable(cache_package.cached)
        assert callable(cache_package.normalize_query_params)
        assert cache_package.CACHETOOLS_AVAILABLE is CACHETOOLS_AVAILABLE

    def test_from_import_works(self):
        from pyeuropepmc.cache import CacheConfig as PackageCacheConfig

        assert PackageCacheConfig is CacheConfig


@pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
class TestL2Persistence:
    def test_entries_survive_a_restart(self, tmp_path):
        """A value written by one backend is readable by the next one."""
        first = _l2_backend(tmp_path)
        first.set("persisted", {"hitCount": 7})
        first.close()

        second = _l2_backend(tmp_path)
        try:
            assert second.get("persisted") == {"hitCount": 7}
        finally:
            second.close()

    def test_concurrent_backends_share_one_directory(self, tmp_path):
        """Two live backends on one cache_dir see each other's entries."""
        writer = _l2_backend(tmp_path)
        reader = _l2_backend(tmp_path)
        try:
            writer.set("shared", "value")
            assert reader.get("shared") == "value"
        finally:
            writer.close()
            reader.close()

    def test_large_values_are_not_orphaned_on_reopen(self, tmp_path):
        """Values diskcache stores as .val files stay reachable."""
        payload = "x" * 200_000  # well past diskcache's inline size limit
        first = _l2_backend(tmp_path)
        first.set("big", payload)
        first.close()

        val_files = list(tmp_path.rglob("*.val"))
        assert val_files, "expected diskcache to store this value in a file"

        second = _l2_backend(tmp_path)
        try:
            assert second.get("big") == payload
        finally:
            second.close()

    def test_an_unusable_database_is_replaced_and_still_serves_entries(self, tmp_path):
        """A file that is not a database is discarded, not carried forward."""
        (tmp_path / "cache.db").write_text("not a sqlite database")

        backend = _l2_backend(tmp_path)
        try:
            assert backend.l2_cache is not None
            assert backend.set("fresh", "value") is True
            assert backend.get("fresh") == "value"
        finally:
            backend.close()

    def test_discarding_a_database_removes_its_sidecars_and_value_files(self, tmp_path):
        """Nothing of the old database is left behind to leak disk space."""
        (tmp_path / "cache.db").write_text("not a sqlite database")
        for suffix in ("-wal", "-shm", "-journal"):
            (tmp_path / f"cache.db{suffix}").write_bytes(b"stale")
        stray_value = tmp_path / "abc.val"
        stray_value.write_bytes(b"orphaned payload")

        CacheBackend._prepare_l2_database(tmp_path)

        assert not (tmp_path / "cache.db").exists()
        for suffix in ("-wal", "-shm", "-journal"):
            assert not (tmp_path / f"cache.db{suffix}").exists()
        assert not stray_value.exists()

    def test_a_database_missing_a_column_is_migrated_and_its_rows_kept(self, tmp_path):
        """An old schema is migrated in place rather than thrown away."""
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE Cache (rowid INTEGER PRIMARY KEY, key TEXT)")
        conn.execute("INSERT INTO Cache (key) VALUES ('kept')")
        conn.commit()
        conn.close()

        CacheBackend._prepare_l2_database(tmp_path)

        assert db_path.exists(), "a migratable database must not be deleted"
        conn = sqlite3.connect(str(db_path))
        try:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(Cache)").fetchall()]
            keys = [row[0] for row in conn.execute("SELECT key FROM Cache").fetchall()]
        finally:
            conn.close()

        assert "size" in columns
        assert keys == ["kept"]

    def test_a_valid_database_is_left_untouched(self, tmp_path):
        """Preparing an existing, healthy database keeps every row."""
        backend = _l2_backend(tmp_path)
        backend.set("kept", "value")
        backend.close()

        before = (tmp_path / "cache.db").stat().st_size
        CacheBackend._prepare_l2_database(tmp_path)

        assert (tmp_path / "cache.db").stat().st_size == before

        reopened = _l2_backend(tmp_path)
        try:
            assert reopened.get("kept") == "value"
        finally:
            reopened.close()


class TestL1PerEntryExpiry:
    def test_expire_argument_applies_to_l1(self, tmp_path):
        """set(expire=...) expires the memory entry, not just the disk one."""
        backend = CacheBackend(CacheConfig(enabled=True, cache_dir=tmp_path, ttl=3600))
        try:
            backend.set("short", "value", expire=1)
            assert backend.get("short") == "value"

            time.sleep(1.1)
            assert backend.get("short") is None
        finally:
            backend.close()

    def test_data_type_ttl_applies_to_l1(self, tmp_path):
        """ttl_by_type decides how long an entry stays in memory."""
        backend = CacheBackend(
            CacheConfig(
                enabled=True,
                cache_dir=tmp_path,
                ttl=3600,
                ttl_by_type={CacheDataType.SEARCH: 1},
            )
        )
        try:
            backend.set("typed", ["PMC1"], data_type=CacheDataType.SEARCH)
            assert backend.get("typed") == ["PMC1"]

            time.sleep(1.1)
            assert backend.get("typed") is None
        finally:
            backend.close()

    def test_entries_without_an_expire_use_the_configured_ttl(self, tmp_path):
        backend = CacheBackend(CacheConfig(enabled=True, cache_dir=tmp_path, ttl=1))
        try:
            backend.set("default_ttl", "value")
            assert backend.get("default_ttl") == "value"

            time.sleep(1.1)
            assert backend.get("default_ttl") is None
        finally:
            backend.close()

    def test_an_already_expired_entry_is_not_stored(self, tmp_path):
        backend = CacheBackend(CacheConfig(enabled=True, cache_dir=tmp_path, ttl=60))
        try:
            backend.set("never", "value", expire=0)
            assert backend.get("never") is None
        finally:
            backend.close()

    @pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
    def test_promotion_from_l2_keeps_the_remaining_lifetime(self, tmp_path):
        """An L2 hit copied into L1 does not get a fresh full TTL."""
        backend = _l2_backend(tmp_path, ttl=3600)
        try:
            backend.set("promoted", "value", expire=1, layer=CacheLayer.L2)
            assert backend.get("promoted") == "value"  # promotes into L1
            assert "promoted" in backend.l1_cache

            time.sleep(1.1)
            assert backend.get("promoted", layer=CacheLayer.L1) is None
        finally:
            backend.close()


class TestCacheConfigValidation:
    def test_ttl_none_raises_configuration_error(self):
        with pytest.raises(ConfigurationError):
            CacheConfig(ttl=None)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"ttl": "86400"},
            {"size_limit_mb": None},
            {"size_limit_mb": 1.5},
            {"l2_size_limit_mb": None},
            {"l2_size_limit_mb": 0},
            {"namespace_version": "1"},
        ],
    )
    def test_wrong_types_and_values_raise_configuration_error(self, kwargs):
        with pytest.raises(ConfigurationError):
            CacheConfig(**kwargs)

    def test_unknown_eviction_policy_is_rejected(self):
        with pytest.raises(ConfigurationError):
            CacheConfig(eviction_policy="random")

    @pytest.mark.parametrize("policy", sorted(CacheConfig.EVICTION_POLICIES))
    def test_supported_eviction_policies_are_accepted(self, policy):
        assert CacheConfig(eviction_policy=policy).eviction_policy == policy

    @pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
    def test_eviction_policy_reaches_the_disk_layer(self, tmp_path):
        backend = _l2_backend(tmp_path, eviction_policy="least-frequently-used")
        try:
            assert backend.l2_cache.eviction_policy == "least-frequently-used"
        finally:
            backend.close()


@pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
class TestStatisticsCountLookupsOnce:
    def test_a_miss_through_two_layers_counts_once(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            backend.get("absent")
            stats = backend.get_stats()

            assert stats["overall"]["misses"] == 1
            assert stats["misses"] == 1
            # Both layers were asked, and both say so.
            assert stats["layers"]["l1"]["misses"] == 1
            assert stats["layers"]["l2"]["misses"] == 1
        finally:
            backend.close()

    def test_an_l2_hit_counts_one_hit_overall(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            backend.set("k", "v", layer=CacheLayer.L2)
            assert backend.get("k") == "v"

            stats = backend.get_stats()
            assert stats["overall"]["hits"] == 1
            assert stats["overall"]["misses"] == 0
            assert stats["overall"]["hit_rate"] == 1.0
        finally:
            backend.close()

    def test_reset_stats_clears_the_overall_counters(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            backend.get("absent")
            backend.reset_stats()

            stats = backend.get_stats()
            assert stats["overall"]["hits"] == 0
            assert stats["overall"]["misses"] == 0
        finally:
            backend.close()


@pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
class TestMaintenanceCoversBothLayers:
    def test_get_keys_lists_l2_only_entries(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            backend.set("mem:1", "v", layer=CacheLayer.L1)
            backend.set("disk:1", "v", layer=CacheLayer.L2)

            keys = backend.get_keys()
            assert "mem:1" in keys
            assert "disk:1" in keys
        finally:
            backend.close()

    def test_get_keys_does_not_repeat_a_key_held_by_both_layers(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            backend.set("both", "v")
            assert backend.get_keys(pattern="both") == ["both"]
        finally:
            backend.close()

    def test_get_keys_respects_the_limit(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            for i in range(5):
                backend.set(f"k{i}", "v")
            assert len(backend.get_keys(limit=3)) == 3
        finally:
            backend.close()

    def test_compact_drops_expired_l2_entries(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            backend.set("gone", "v", expire=1, layer=CacheLayer.L2)
            time.sleep(1.1)

            assert backend.compact() is True
            assert len(backend.l2_cache) == 0
        finally:
            backend.close()

    def test_invalidate_older_than_removes_entries_from_both_layers(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            backend.set("old", "v")
            time.sleep(1.1)
            backend.set("new", "v")

            assert backend.invalidate_older_than(1) == 1
            assert backend.get("old") is None
            assert backend.get("new") == "v"
            assert backend.l2_cache.get("old") is None
        finally:
            backend.close()

    def test_invalidate_older_than_keeps_recent_entries(self, tmp_path):
        backend = _l2_backend(tmp_path)
        try:
            backend.set("recent", "v")
            assert backend.invalidate_older_than(3600) == 0
            assert backend.get("recent") == "v"
        finally:
            backend.close()

    def test_invalidate_older_than_returns_zero_when_disabled(self):
        backend = CacheBackend(CacheConfig(enabled=False))
        assert backend.invalidate_older_than(0) == 0


class TestStoreTimeTracking:
    def test_store_times_are_dropped_on_delete(self, tmp_path):
        backend = CacheBackend(CacheConfig(enabled=True, cache_dir=tmp_path, ttl=60))
        try:
            backend.set("k", "v")
            backend.delete("k")
            assert "k" not in backend._store_times
        finally:
            backend.close()

    def test_store_times_are_dropped_on_clear(self, tmp_path):
        backend = CacheBackend(CacheConfig(enabled=True, cache_dir=tmp_path, ttl=60))
        try:
            backend.set("k", "v")
            backend.clear()
            assert backend._store_times == {}
        finally:
            backend.close()

    def test_store_times_stay_bounded(self, tmp_path, monkeypatch):
        """A long run of writes does not grow the map without bound."""
        backend = CacheBackend(CacheConfig(enabled=True, cache_dir=tmp_path, ttl=60))
        monkeypatch.setattr(backend, "MAX_TRACKED_STORE_TIMES", 100)
        try:
            for i in range(500):
                backend.set(f"k{i}", "v")

            assert len(backend._store_times) <= 100
            # The most recent write is the one still tracked.
            assert "k499" in backend._store_times
        finally:
            backend.close()
