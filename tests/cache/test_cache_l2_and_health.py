"""Additional unit tests for pyeuropepmc.cache.cache covering the L2
(diskcache-backed) persistence layer, schema validation/migration helpers,
get_health's status branches, and other paths not exercised by
tests/cache/test_cache_backend.py (which only covers the L1-only path)."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest

from pyeuropepmc.cache.cache import (
    DISKCACHE_AVAILABLE,
    CacheBackend,
    CacheConfig,
    CacheLayer,
    _check_and_migrate_schema,
    _validate_diskcache_schema,
)


class TestValidateDiskcacheSchema:
    def test_no_db_file_is_valid(self, tmp_path):
        assert _validate_diskcache_schema(tmp_path) is True

    def test_valid_schema_with_size_column(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE Cache (rowid INTEGER PRIMARY KEY, key TEXT, size INTEGER)")
        conn.commit()
        conn.close()
        assert _validate_diskcache_schema(tmp_path) is True

    def test_corrupt_db_file_raises_and_removes_file(self, tmp_path):
        db_path = tmp_path / "cache.db"
        db_path.write_text("not a real sqlite file")
        # A corrupt file raises sqlite3.DatabaseError, which the migration
        # helper converts to ConfigurationError after removing the bad file.
        from pyeuropepmc.core.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            _validate_diskcache_schema(tmp_path)
        assert not db_path.exists()


class TestCheckAndMigrateSchema:
    def test_migrates_missing_size_column(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE Cache (rowid INTEGER PRIMARY KEY, key TEXT)")
        conn.commit()
        conn.close()

        assert _check_and_migrate_schema(db_path) is True

        conn = sqlite3.connect(str(db_path))
        cols = [c[1] for c in conn.execute("PRAGMA table_info(Cache)").fetchall()]
        conn.close()
        assert "size" in cols

    def test_already_has_size_column_no_migration_needed(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE Cache (rowid INTEGER PRIMARY KEY, size INTEGER)")
        conn.commit()
        conn.close()
        assert _check_and_migrate_schema(db_path) is True

    def test_migration_failure_removes_db_and_raises(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE Cache (rowid INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        from pyeuropepmc.core.exceptions import ConfigurationError

        with (
            patch(
                "pyeuropepmc.cache.cache._migrate_schema_columns",
                side_effect=sqlite3.Error("boom"),
            ),
            pytest.raises(ConfigurationError),
        ):
            _check_and_migrate_schema(db_path)
        assert not db_path.exists()


@pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
class TestCacheBackendL2Lifecycle:
    """Exercise the L1+L2 code paths using a real diskcache instance."""

    def _backend(self, tmp_path: Path) -> CacheBackend:
        config = CacheConfig(
            enabled=True,
            cache_dir=tmp_path,
            ttl=60,
            size_limit_mb=1,
            enable_l2=True,
            l2_size_limit_mb=1,
        )
        return CacheBackend(config)

    def test_l2_cache_initialized(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            assert backend.l2_cache is not None
            assert backend.config.enable_l2 is True
        finally:
            backend.close()

    def test_set_and_get_writes_through_both_layers(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            assert backend.set("k1", "v1") is True
            assert backend.get("k1") == "v1"
            # Direct L2 lookup should also see it (write-through)
            assert backend.l2_cache.get("k1") == "v1"
        finally:
            backend.close()

    def test_l2_only_hit_promotes_to_l1(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("k2", "v2", layer=CacheLayer.L2)
            assert "k2" not in backend.l1_cache
            assert backend.get("k2") == "v2"
            assert backend.l1_cache["k2"] == "v2"
        finally:
            backend.close()

    def test_delete_removes_from_both_layers(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("k3", "v3")
            assert backend.delete("k3") is True
            assert backend.get("k3") is None
            assert backend.l2_cache.get("k3") is None
        finally:
            backend.close()

    def test_clear_l2_layer(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("k4", "v4")
            assert backend.clear() is True
            assert backend.get("k4") is None
        finally:
            backend.close()

    def test_evict_by_tag_removes_from_l2(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("k5", "v5", tag="mytag")
            count = backend.evict("mytag")
            assert count >= 1
            assert backend.get("k5") is None
        finally:
            backend.close()

    def test_get_stats_includes_l2(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("k6", "v6")
            backend.get("k6")
            stats = backend.get_stats()
            assert "l2" in stats["layers"]
        finally:
            backend.close()

    def test_invalidate_pattern_l2(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("search:a", "1")
            backend.set("search:b", "2")
            count = backend.invalidate_pattern("search:*")
            assert count >= 1
        finally:
            backend.close()

    def test_invalidate_older_than_l2(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("k7", "v7")
            result = backend.invalidate_older_than(0)
            assert isinstance(result, int)
        finally:
            backend.close()

    def test_warm_cache_l2(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            result = backend.warm_cache({"k8": "v8", "k9": "v9"})
            assert result >= 1
            assert backend.get("k8") == "v8"
        finally:
            backend.close()

    def test_get_health_healthy(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("k10", "v10")
            backend.get("k10")
            health = backend.get_health()
            assert health["status"] in {"healthy", "warning", "critical"}
            assert health["available"] is True
        finally:
            backend.close()

    def test_compact(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("k11", "v11")
            assert backend.compact() is True
        finally:
            backend.close()

    def test_get_keys_with_pattern(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.set("alpha:1", "x")
            backend.set("beta:1", "y")
            keys = backend.get_keys(pattern="alpha:*")
            assert "alpha:1" in keys
            assert "beta:1" not in keys
        finally:
            backend.close()

    def test_close_releases_l2(self, tmp_path):
        backend = self._backend(tmp_path)
        backend.set("k12", "v12")
        backend.close()
        assert backend.l1_cache is None
        assert backend.l2_cache is None

    def test_l2_reinitializes_on_existing_cache_dir(self, tmp_path):
        backend1 = self._backend(tmp_path)
        backend1.set("persisted", "value")
        backend1.close()

        backend2 = self._backend(tmp_path)
        try:
            assert backend2.l2_cache is not None
            # Reopening must not discard what the first backend wrote.
            assert backend2.get("persisted") == "value"
        finally:
            backend2.close()


class TestCacheGetHealthBranches:
    def _backend(self, tmp_path: Path) -> CacheBackend:
        config = CacheConfig(enabled=True, cache_dir=tmp_path, ttl=60, size_limit_mb=1)
        return CacheBackend(config)

    def test_critical_when_size_utilization_high(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            with patch.object(backend, "get_stats", return_value={"size_mb": 10, "hit_rate": 1.0}):
                health = backend.get_health()
            assert health["status"] == "critical"
        finally:
            backend.close()

    def test_warning_when_size_utilization_moderate(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            with patch.object(
                backend, "get_stats", return_value={"size_mb": 0.85, "hit_rate": 1.0}
            ):
                health = backend.get_health()
            assert health["status"] == "warning"
        finally:
            backend.close()

    def test_warning_when_error_rate_high(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            with patch.object(
                backend,
                "get_stats",
                return_value={"size_mb": 0, "hit_rate": 1.0, "errors": 10, "hits": 90},
            ):
                health = backend.get_health()
            assert health["status"] == "warning"
            assert any("error rate" in w.lower() for w in health["warnings"])
        finally:
            backend.close()

    def test_warning_when_hit_rate_low(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            with patch.object(
                backend,
                "get_stats",
                return_value={"size_mb": 0, "hit_rate": 0.1, "hits": 10, "misses": 200},
            ):
                health = backend.get_health()
            assert health["status"] == "warning"
        finally:
            backend.close()

    def test_healthy_when_all_good(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            with patch.object(backend, "get_stats", return_value={"size_mb": 0, "hit_rate": 1.0}):
                health = backend.get_health()
            assert health["status"] == "healthy"
        finally:
            backend.close()

    def test_exception_in_get_stats_returns_error_status(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            with patch.object(backend, "get_stats", side_effect=RuntimeError("boom")):
                health = backend.get_health()
            assert health["status"] == "error"
            assert any("Health check failed" in w for w in health["warnings"])
        finally:
            backend.close()

    def test_cache_none_returns_unavailable(self, tmp_path):
        backend = self._backend(tmp_path)
        try:
            backend.l1_cache = None
            backend.l2_cache = None
            health = backend.get_health()
            assert health["status"] == "unavailable"
        finally:
            backend.close()


class TestCacheConfigUnavailableFlags:
    def test_enabled_forced_false_when_cachetools_unavailable(self, caplog):
        with (
            patch("pyeuropepmc.cache.cache.CACHETOOLS_AVAILABLE", False),
            caplog.at_level("WARNING"),
        ):
            config = CacheConfig(enabled=True)
        assert config.enabled is False
        assert any("cachetools not available" in r.message for r in caplog.records)

    def test_enable_l2_forced_false_when_diskcache_unavailable(self, caplog):
        with (
            patch("pyeuropepmc.cache.cache.DISKCACHE_AVAILABLE", False),
            caplog.at_level("WARNING"),
        ):
            config = CacheConfig(enabled=True, enable_l2=True)
        assert config.enable_l2 is False
        assert any("diskcache not available" in r.message for r in caplog.records)
