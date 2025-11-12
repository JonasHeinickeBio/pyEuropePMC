# Advanced Cache Architecture Implementation

## Overview
Enhance the current cachetools.TTLCache implementation with a comprehensive multi-layer caching strategy optimized for different data types and access patterns in PyEuropePMC.

## Current State
- ✅ L1 in-memory cache using `cachetools.TTLCache`
- ✅ Key normalization and query normalization
- ✅ Tag-based grouping for selective eviction
- ✅ Statistics tracking (hits, misses, sets, deletes)

## Proposed Architecture

### 1. Cache Segmentation by Data Type

#### A. Search Result Pages (Volatile, Paginated)
**Characteristics:**
- High volatility - index freshness matters
- Paginated data
- Frequently accessed

**Implementation:**
- **TTL:** Short (1–10 minutes)
- **Key Pattern:** `search:{norm_query}:{sort}:{filters}:{page}:{pagesize}:{api_ver}`
- **Storage Strategy:**
  - Main payload: Full page results
  - Meta side-key: `search_meta:{norm_query}` containing:
    - `total_count`
    - `last_page`
    - `server_cursor` (if supported)
    - `time_window` (e.g., `until=2025-11-12T00:00Z`) for reproducibility
- **Policy:** Stale-while-revalidate
  - Serve cached page instantly
  - Background refresh with single-flight guard
  - Return fresh if available in time, else serve stale

**Key Design Details:**
- Normalize query and filters for consistent keying
- Include pagination parameters in key
- Add explicit `api_ver` for namespace versioning
- Bound result sets by time window for reproducibility

#### B. Record Detail (Semi-Stable)
**Characteristics:**
- Individual article/PMID/PMCID metadata
- Rarely changes
- Medium access frequency

**Implementation:**
- **TTL:** Medium/Long (1–7 days)
- **Key Pattern:** `record:{id}:{fields}:{api_ver}`
- **Negative Caching:** Cache 404/410 responses briefly (5–15 minutes) to avoid hammering missing records
- **Storage:** Both L1 (hot records) and L2 (warm/cold records)

#### C. Full-Text Artifacts (Mostly Immutable)
**Characteristics:**
- PDF/XML/ZIP files
- Large files
- Immutable once published

**Implementation:**
- **TTL:** Very long (30–180 days)
- **Key Pattern (Index):** `ft:index:{source}:{doc_id}:{format}` → points to content hash
- **Storage Pattern:** Content-addressed on disk
  - Path: `/cache/artifacts/{sha256[:2]}/{sha256}`
  - Index maps: `id → hash → path`
  - Deduplicates same content under different IDs/URLs
- **Conditional GET Support:**
  - Always send `If-None-Match` / `If-Modified-Since`
  - Treat 304 Not Modified as cache hit
  - Store ETag and Last-Modified headers

### 2. Multi-Layer Cache Strategy

#### L1: In-Memory (Per-Process)
**Implementation:**
- Library: `cachetools.TTLCache` (current)
- Size: 2,000–5,000 entries
- TTL: 30–120 seconds
- Use Case: Hot data, ultra-fast access

#### L2: Persistent/Shared Cache
**Options:**

**For HTTP Responses:**
- Library: `requests-cache` with SQLite backend
- Benefits:
  - Correctly honors Cache-Control headers
  - Handles ETag, Vary headers
  - Built-in 304 Not Modified support
- Use Case: API responses, full-text downloads

**For Python Objects:**
- Library: `diskcache` or Redis
- Benefits:
  - Persistent across restarts
  - Shareable across processes
  - Built-in locking (`diskcache.Cache.lock()`)
- Use Case: Search results, parsed metadata

**Design Principles:**
- L1 TTL ≤ L2 TTL
- Use same normalized keys in both layers
- Guard cache misses with single-flight lock to prevent stampedes

### 3. Pagination at Scale

#### Cursor-Based Pagination
- **Prefer cursors over page numbers** when API supports it
- Cache cursor tokens in search metadata
- Enables exact resumption of iteration

#### Result Set Bounding
- Add `until=now()` or `last_updated < T` to queries
- Makes "page 1…N" reproducible and cacheable
- Include in cache key for consistent results

#### Checkpointing for Long Crawls
- **Key Pattern:** `search:progress:{norm_query}`
- **Store:**
  - Current page/cursor
  - `fetched_count`
  - `last_doc_id`
- Enables restart from interruption point

#### Budgeting and Rate Limiting
- Support `max_results` parameter per fetch
- Don't fetch 10k docs if users rarely need them
- Implement exponential backoff on 429/5xx errors
- Use leaky bucket for rate limiting (e.g., 5–10 RPS)

### 4. Key Design and Invalidation

#### Namespace Versioning
- **Pattern:** Add `:v{int}` in every key prefix
- **Example:** `search:v3:{query}`, `record:v2:{id}`, `ft:v1:index:{id}`
- **Benefits:**
  - Instant broad invalidation by bumping version
  - No need to scan and delete old keys
  - Use on schema changes, ranking updates, bug fixes

#### Per-Artifact Immutability
- **Index key:** Short TTL (hours)
  - `ft:index:{id}` → points to hash
- **Blob key:** Forever
  - `artifacts/{hash}` → actual content
- **Invalidation:** Update index to point to new hash

#### Error TTL Strategy
- Cache transient errors (429, 502, 503, 504) very briefly (10–60s with jitter)
- Include error class in key to avoid poisoning good entries
- **Example:** `error:429:{original_key}` with 30s TTL

### 5. PDF/XML Handling at Scale

#### Optimization Techniques
1. **HEAD Request First:**
   - Check size/type before downloading
   - Grab ETag/Last-Modified
   - Avoid large unnecessary downloads

2. **Range Requests:**
   - Use for very large PDFs if server supports Accept-Ranges
   - Fall back gracefully if not supported

3. **Checksum Verification:**
   - Validate against server-provided checksums
   - Detect silent truncation from server hiccups
   - Minimum: verify MIME type and byte size

4. **MIME-Aware TTLs:**
   - XML/JSON: Shorter TTL (can change more often)
   - PDF: Longer TTL (rarely changes)
   - Always use conditional GET regardless

### 6. Monitoring and Safety

#### Telemetry
- **Hit Rate Metrics:**
  - Track L1/L2 hits/misses separately
  - Alert if L2 hit rate collapses (indicates keying/TTL bug)
- **Performance Metrics:**
  - Cache latency (L1 vs L2 vs miss)
  - Eviction rates
  - Size utilization

#### Disk Management
- **Watchdog Process:**
  - Monitor artifact store volume
  - Cull oldest unreferenced hashes at high-water mark
  - Implement LRU eviction for disk cache

#### Licensing Compliance
- Respect license flags in metadata
- Cache but don't redistribute non-redistributable artifacts
- Log and audit artifact access

### 7. Recommended Technology Mix

#### For Search Pages & Record JSON
- **L1:** `cachetools.TTLCache` (current implementation)
- **L2:** `diskcache` or Redis
- **Pattern:** Write-through or write-behind based on freshness requirements

#### For HTTP Downloads (PDF/XML)
- **HTTP Layer:** `requests-cache` for protocol-correct conditional GET
- **Storage:** Content-addressed disk store for actual bytes
- **Pattern:**
  ```python
  # Index lookup (L1/L2)
  hash = cache.get(f"ft:index:{doc_id}:{format}")
  
  # Content-addressed retrieval
  content = read_artifact(hash)
  
  # If miss, download with conditional GET
  response = session.get(url, headers={"If-None-Match": etag})
  if response.status_code == 304:
      # Still valid, extend TTL
      pass
  elif response.ok:
      # New content, store with hash
      hash = sha256(response.content)
      store_artifact(hash, response.content)
      cache.set(f"ft:index:{doc_id}:{format}", hash)
  ```

#### Namespace Versioning Strategy
- Bump `search:vN` on query logic changes
- Bump `record:vN` on metadata schema changes  
- Bump `ft:vN` on artifact handling changes
- No cross-contamination between versions

## Implementation Phases

### Phase 1: Enhanced L1 Cache (Current + Improvements)
- [ ] Add namespace versioning to keys
- [ ] Implement separate TTL configurations per data type
- [ ] Add stale-while-revalidate support
- [ ] Enhance statistics with L1-specific metrics

### Phase 2: L2 Persistent Cache
- [ ] Add `diskcache` as L2 layer
- [ ] Implement write-through/write-behind logic
- [ ] Add single-flight locking for cache misses
- [ ] Implement L1/L2 coordination

### Phase 3: Content-Addressed Artifact Storage
- [ ] Implement SHA-256 based content addressing
- [ ] Build index: `id → hash → path` mapping
- [ ] Add disk watchdog for size management
- [ ] Implement deduplication logic

### Phase 4: HTTP Caching with requests-cache
- [ ] Integrate `requests-cache` for HTTP responses
- [ ] Implement conditional GET support (ETag, Last-Modified)
- [ ] Add 304 Not Modified handling
- [ ] Test with Europe PMC API

### Phase 5: Advanced Features
- [ ] Cursor-based pagination support
- [ ] Checkpointing for long crawls
- [ ] Negative caching for 404s
- [ ] Error-specific caching strategies

### Phase 6: Monitoring and Observability
- [ ] Add comprehensive telemetry
- [ ] Implement alerting for cache health
- [ ] Build dashboard for cache metrics
- [ ] Add logging for debugging

## API Compatibility

All enhancements should maintain backward compatibility with the current `CacheBackend` API:
- Existing `CacheConfig` parameters supported
- New optional parameters for advanced features
- Graceful degradation when optional dependencies missing

## Testing Strategy

- Unit tests for each cache layer independently
- Integration tests for L1+L2 coordination
- Performance benchmarks for cache hit rates
- Stress tests for high-volume scenarios
- Tests for cache invalidation strategies

## Documentation Requirements

- Architecture decision records (ADRs) for key choices
- API documentation updates
- Usage examples for each data type
- Performance tuning guide
- Monitoring and troubleshooting guide

## Related Issues

- Current PR: Migration to cachetools.TTLCache (foundation)
- Future: Multi-layer cache implementation
- Future: Content-addressed storage
- Future: Advanced pagination support

## References

- [cachetools documentation](https://cachetools.readthedocs.io/)
- [requests-cache documentation](https://requests-cache.readthedocs.io/)
- [diskcache documentation](http://www.grantjenks.com/docs/diskcache/)
- [HTTP Caching RFC 7234](https://tools.ietf.org/html/rfc7234)
