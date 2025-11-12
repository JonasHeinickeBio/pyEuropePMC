"""
Tests for diskcache schema validation and migration.

These tests ensure that the cache system can handle old/incompatible
diskcache database schemas by detecting and migrating them.
"""

import os
from pathlib import Path
import sqlite3

import pytest

from pyeuropepmc.cache import _migrate_diskcache_schema, _validate_diskcache_schema

# Only run these tests if diskcache is available
pytest.importorskip("diskcache")
import diskcache  # noqa: E402


class TestDiskcacheSchemaValidation:
    """Test diskcache schema validation."""

    def test_validate_schema_no_database(self, tmp_path):
        """Test validation when no database exists (should return True)."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Should return True when database doesn't exist
        assert _validate_diskcache_schema(cache_dir) is True

    def test_validate_schema_valid_new_schema(self, tmp_path):
        """Test validation with a valid new schema."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Create a new cache with current diskcache (will have correct schema)
        cache = diskcache.Cache(str(cache_dir))
        cache.set("test", "value")
        cache.close()

        # Should validate successfully
        assert _validate_diskcache_schema(cache_dir) is True

    def test_validate_schema_old_missing_size(self, tmp_path):
        """Test validation with old schema missing 'size' column."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"

        # Create old schema without 'size' column
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Cache (
                rowid INTEGER PRIMARY KEY,
                key BLOB,
                raw INTEGER,
                store_time REAL,
                expire_time REAL,
                access_time REAL,
                access_count INTEGER DEFAULT 0,
                tag BLOB,
                mode INTEGER DEFAULT 0,
                filename TEXT,
                value BLOB
            )
        """
        )
        conn.commit()
        conn.close()

        # Should detect invalid schema
        assert _validate_diskcache_schema(cache_dir) is False

    def test_validate_schema_missing_multiple_columns(self, tmp_path):
        """Test validation with schema missing multiple critical columns."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"

        # Create very old schema missing size, mode, and filename
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Cache (
                rowid INTEGER PRIMARY KEY,
                key BLOB,
                raw INTEGER,
                store_time REAL,
                expire_time REAL,
                access_time REAL,
                access_count INTEGER DEFAULT 0,
                tag BLOB,
                value BLOB
            )
        """
        )
        conn.commit()
        conn.close()

        # Should detect invalid schema
        assert _validate_diskcache_schema(cache_dir) is False

    def test_validate_schema_corrupt_database(self, tmp_path):
        """Test validation with corrupt database file."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"

        # Create corrupt database file
        with open(db_path, "w") as f:
            f.write("This is not a valid SQLite database")

        # Should return False for corrupt database
        assert _validate_diskcache_schema(cache_dir) is False


class TestDiskcacheSchemaMigration:
    """Test diskcache schema migration."""

    def test_migrate_schema_removes_database(self, tmp_path):
        """Test that migration removes the old database."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"

        # Create old database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE Cache (
                rowid INTEGER PRIMARY KEY,
                key BLOB
            )
        """
        )
        conn.commit()
        conn.close()

        assert db_path.exists()

        # Migrate
        _migrate_diskcache_schema(cache_dir)

        # Database should be removed
        assert not db_path.exists()

    def test_migrate_schema_removes_wal_files(self, tmp_path):
        """Test that migration removes WAL and SHM files."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"
        wal_path = cache_dir / "cache.db-wal"
        shm_path = cache_dir / "cache.db-shm"

        # Create database and auxiliary files
        with open(db_path, "w") as f:
            f.write("db")
        with open(wal_path, "w") as f:
            f.write("wal")
        with open(shm_path, "w") as f:
            f.write("shm")

        assert db_path.exists()
        assert wal_path.exists()
        assert shm_path.exists()

        # Migrate
        _migrate_diskcache_schema(cache_dir)

        # All files should be removed
        assert not db_path.exists()
        assert not wal_path.exists()
        assert not shm_path.exists()

    def test_migrate_schema_preserves_directory(self, tmp_path):
        """Test that migration preserves the cache directory."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"

        # Create database
        with open(db_path, "w") as f:
            f.write("db")

        # Migrate
        _migrate_diskcache_schema(cache_dir)

        # Directory should still exist
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_migrate_schema_no_database(self, tmp_path):
        """Test migration when no database exists (should not error)."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Should not raise error
        _migrate_diskcache_schema(cache_dir)

        # Directory should still exist
        assert cache_dir.exists()


class TestDiskcacheSchemaIntegration:
    """Integration tests for schema validation and migration."""

    def test_migration_allows_new_cache_creation(self, tmp_path):
        """Test that after migration, a new cache can be created successfully."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"

        # Create old schema
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Cache (
                rowid INTEGER PRIMARY KEY,
                key BLOB,
                value BLOB
            )
        """
        )
        conn.commit()
        conn.close()

        # Verify old schema is invalid
        assert _validate_diskcache_schema(cache_dir) is False

        # Migrate
        _migrate_diskcache_schema(cache_dir)

        # Now should be able to create new cache
        cache = diskcache.Cache(str(cache_dir))
        assert cache.set("test_key", "test_value") is True
        assert cache.get("test_key") == "test_value"
        cache.close()

        # Validate new schema
        assert _validate_diskcache_schema(cache_dir) is True

    def test_detect_and_fix_old_schema_workflow(self, tmp_path):
        """Test the complete workflow of detecting and fixing old schema."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"

        # Create old schema
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Cache (
                rowid INTEGER PRIMARY KEY,
                key BLOB,
                raw INTEGER,
                store_time REAL,
                expire_time REAL,
                access_time REAL,
                access_count INTEGER DEFAULT 0,
                tag BLOB,
                mode INTEGER DEFAULT 0,
                filename TEXT,
                value BLOB
            )
        """
        )
        # Add some old data
        cursor.execute(
            """
            INSERT INTO Cache (key, value) VALUES (?, ?)
        """,
            (b"old_key", b"old_value"),
        )
        conn.commit()
        conn.close()

        # Workflow: Validate -> Migrate -> Create new
        if not _validate_diskcache_schema(cache_dir):
            _migrate_diskcache_schema(cache_dir)

        # Create new cache and use it
        cache = diskcache.Cache(str(cache_dir))
        cache.set("new_key", "new_value")

        # Should work without errors
        assert cache.get("new_key") == "new_value"

        # Old data should be gone (expected behavior for cache migration)
        assert cache.get("old_key") is None

        cache.close()


class TestSchemaMigrationEdgeCases:
    """Test edge cases in schema migration."""

    def test_migration_with_permission_error(self, tmp_path, monkeypatch):
        """Test migration gracefully handles permission errors."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db_path = cache_dir / "cache.db"

        # Create database
        with open(db_path, "w") as f:
            f.write("db")

        # Mock os.remove to raise PermissionError
        original_remove = os.remove

        def mock_remove(path):
            if "cache.db" in str(path):
                raise PermissionError("Permission denied")
            return original_remove(path)

        monkeypatch.setattr(os, "remove", mock_remove)

        # Should not raise, just log error
        _migrate_diskcache_schema(cache_dir)

        # Database still exists due to permission error
        assert db_path.exists()

    def test_validation_with_nonexistent_directory(self):
        """Test validation with non-existent directory."""
        cache_dir = Path("/nonexistent/cache/dir")

        # Should return True (will be created)
        assert _validate_diskcache_schema(cache_dir) is True

    def test_migration_with_nonexistent_directory(self):
        """Test migration with non-existent directory."""
        cache_dir = Path("/nonexistent/cache/dir")

        # Should not raise error
        _migrate_diskcache_schema(cache_dir)
