# Cache Schema Migration

## Overview

PyEuropePMC's caching system includes automatic schema validation and migration for diskcache databases. This ensures compatibility when upgrading diskcache versions or when encountering old cache databases.

## Problem

The diskcache library version 5.6.3+ requires specific columns in the Cache table, particularly:
- `size` - Used for size-based eviction policies
- `mode` - File mode information
- `filename` - For file-based storage

Older versions of diskcache or cache databases created with earlier versions may not have these columns, resulting in errors like:

```
sqlite3.OperationalError: table Cache has no column named size
```

## Solution

PyEuropePMC automatically detects and fixes incompatible cache schemas:

1. **Schema Validation** (`_validate_diskcache_schema()`):
   - Checks if cache database has required columns
   - Returns `True` if schema is compatible or doesn't exist
   - Returns `False` if schema is incompatible

2. **Schema Migration** (`_migrate_diskcache_schema()`):
   - Removes old incompatible cache database
   - Removes auxiliary files (WAL, SHM, journal)
   - Allows diskcache to create new database with correct schema
   - Logs migration for user awareness

## Usage

### Current Implementation (cachetools)

The current implementation uses `cachetools.TTLCache` for in-memory L1 caching. Schema validation functions are available but not actively used.

### Future Implementation (diskcache L2)

When implementing L2 persistent cache with diskcache:

```python
from pathlib import Path
from pyeuropepmc.cache import _validate_diskcache_schema, _migrate_diskcache_schema
import diskcache

cache_dir = Path("/path/to/cache")

# Validate and migrate if needed
if not _validate_diskcache_schema(cache_dir):
    _migrate_diskcache_schema(cache_dir)

# Now safe to initialize diskcache
cache = diskcache.Cache(str(cache_dir))
```

## Migration Behavior

### What Gets Removed
- `cache.db` - Main SQLite database
- `cache.db-wal` - Write-Ahead Log file
- `cache.db-shm` - Shared Memory file
- `cache.db-journal` - Journal file

### What Gets Preserved
- Cache directory itself
- Any other files in the cache directory

### Data Loss
**Important**: Schema migration removes all cached data. This is acceptable because:
- Cache data is ephemeral by nature
- Cache should not be relied upon for persistent storage
- Fresh data will be fetched and cached as needed

## Logging

Schema validation and migration operations are logged:

```python
# When invalid schema detected
logger.warning(
    "Incompatible diskcache schema detected. "
    f"Missing columns: {missing_columns}. "
    "Old cache will be removed to allow schema migration."
)

# When migration completes
logger.info(
    "Cache schema migration completed. "
    "A new cache will be created with the correct schema."
)
```

## Error Handling

Schema migration is designed to fail gracefully:

- **Permission Errors**: Logged but don't crash the application
- **Missing Directories**: Treated as valid (will be created)
- **Corrupt Databases**: Treated as invalid and removed
- **Unknown Errors**: Logged and cache can be disabled if needed

## Testing

Comprehensive tests are available in `tests/cache/test_diskcache_schema.py`:

- Schema validation with valid/invalid schemas
- Schema migration behavior
- Integration tests (detect → migrate → create new cache)
- Edge cases (permissions, corruption, non-existent paths)

Run tests:
```bash
pytest tests/cache/test_diskcache_schema.py -v
```

## Related Issues

- GitHub Issue: Resolve diskcache SQL schema errors
- Related: Advanced Cache Architecture Implementation (#)

## See Also

- [diskcache documentation](http://www.grantjenks.com/docs/diskcache/)
- [SQLite PRAGMA statements](https://www.sqlite.org/pragma.html)
- [PyEuropePMC Cache Architecture](./cache_architecture.md)
