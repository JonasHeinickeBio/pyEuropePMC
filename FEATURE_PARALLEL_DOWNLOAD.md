# Parallel Download with Rate Limiting

## Summary
Implement ThreadPoolExecutor-based parallel downloading with rate limiting and progress tracking for `fulltext.py` download methods.

## Motivation
Current sequential downloads are slow for large batches. Parallel execution with proper rate limiting will significantly improve performance while staying within Europe PMC API guidelines.

## Description

### New Classes/Methods
- **`RateLimiter`** - Track requests/second, warn at 80% threshold
- **`FullTextClient.download_fulltext_batch_parallel()`** - Main parallel download method
  - Auto-detect cores: `max_workers = min(os.cpu_count() or 4, 8)`
  - Range: 1-8 workers
  - Per-worker rate limiting

### Key Features

1. **RateLimiter Class**
   - Per-worker request tracking with time window
   - Auto-calculate threshold based on workers (1 req/s per worker = 80% warning)
   - Log warnings at 80% threshold
   - Track: requests_made, window_start, warnings_issued

2. **Progress Tracking**
   - Standard tqdm progress bar
   - Show: items/sec, elapsed time, estimated time remaining
   - Worker ID in progress bar (e.g., "Worker 1/4: PMC...")
   - Per-worker statistics in verbose mode

3. **Statistics Tracking**
   - Per-worker: time_spent, requests_made, failures, success_count
   - Global summary: total_time, avg_speed, total_requests, success_rate
   - Store in `download_stats` attribute

4. **Error Handling**
   - Individual worker failures don't stop batch
   - Fallback to sequential if parallel fails completely
   - Detailed error reporting per item

5. **Session Management**
    - Thread-local sessions per worker (no shared sessions)
    - Each worker gets its own Session instance for thread safety
    - Sessions tracked in registry and cleaned up on completion

### Implementation Plan

1. **Add RateLimiter class** (lines ~131-180 in fulltext.py)
2. **Add parallel download method** (after existing `download_fulltext_batch()`)
3. **Add tqdm progress bar support**
4. **Add statistics tracking**
5. **Update documentation**
6. **Add tests**

### Testing
- [ ] Test with 1, 2, 4, 8 workers
- [ ] Verify rate limiting warnings at 80%
- [ ] Test error handling for individual worker failures
- [ ] Compare performance vs sequential download
- [ ] Verify statistics tracking accuracy

### Example Usage
```python
from pyeuropepmc import FullTextClient

client = FullTextClient()

# Auto-detect workers (default)
results = client.download_fulltext_batch_parallel(pmcids)

# Specify worker count
results = client.download_fulltext_batch_parallel(pmcids, max_workers=4)

# Disable progress bar
results = client.download_fulltext_batch_parallel(pmcids, show_progress=False)

# Enable verbose mode
results = client.download_fulltext_batch_parallel(pmcids, verbose=True)

# Check statistics
print(client.download_stats)
```

### Breaking Changes
None - new method is additive, existing `download_fulltext_batch()` remains unchanged.

### Files to Modify
- `src/pyeuropepmc/clients/fulltext.py` - Add RateLimiter class and parallel download method
- `pyeuropepmc/__init__.py` - Export new functionality if needed
- Documentation files as needed

### Performance Targets
- 2 workers: ~50-60% faster than sequential
- 4 workers: ~70-80% faster than sequential
- 8 workers: ~80-90% faster than sequential
- Rate limit warnings at 80% of capacity
