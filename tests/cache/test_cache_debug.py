"""Debug test to check cache basics."""

import tempfile
import shutil
from pathlib import Path
from pyeuropepmc.cache import CacheBackend, CacheConfig
import diskcache


def test_cache_basic_operations():
    """Test that basic cache operations work."""
    tmpdir = Path(tempfile.mkdtemp())

    try:
        # Test raw diskcache first
        print("\n=== Testing raw diskcache ===")
        raw_cache = diskcache.Cache(str(tmpdir / "raw"))
        raw_result = raw_cache.set("test_key", "test_value", expire=60)
        print(f"Raw diskcache set result: {raw_result}")
        raw_value = raw_cache.get("test_key")
        print(f"Raw diskcache get result: {raw_value}")
        raw_cache.close()

        # Now test our wrapper
        print("\n=== Testing CacheBackend wrapper ===")
        config = CacheConfig(enabled=True, cache_dir=tmpdir / "wrapper", ttl=60)
        backend = CacheBackend(config)

        print(f"Cache enabled: {backend.config.enabled}")
        print(f"Cache object: {backend.cache}")
        print(f"Cache object type: {type(backend.cache)}")
        print(f"Cache dir exists: {backend.config.cache_dir.exists()}")

        # Try to set a value
        try:
            result = backend.set("test_key", "test_value")
            print(f"Set result: {result}")
            print(f"Set result type: {type(result)}")
        except Exception as e:
            print(f"Set exception: {e}")
            import traceback
            traceback.print_exc()
            result = False

        print(f"Stats after set: {backend._stats}")

        # Try to get the value
        value = backend.get("test_key")
        print(f"Get result: {value}")
        print(f"Stats after get: {backend._stats}")

        assert result is True, f"Set should return True, got {result}"
        assert value == "test_value", f"Expected 'test_value', got {value}"

        backend.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    test_cache_basic_operations()
