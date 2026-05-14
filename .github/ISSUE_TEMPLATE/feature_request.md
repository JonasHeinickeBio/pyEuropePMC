---
name: Feature Request
about: Suggest a new feature or enhancement
title: ''
labels: enhancement
assignees: ''

---

## Summary
<!-- Brief description of the feature -->

## Motivation
<!-- Why should this feature be added? -->

## Description
<!-- Detailed description of what the feature should do -->

### Proposed Implementation
<!-- How should this feature be implemented? -->

#### New Classes/Methods
- `RateLimiter` - Track requests/second, warn at 80% threshold
- `FullTextClient.download_fulltext_batch_parallel()` - Main parallel download method
  - Auto-detect cores: `max_workers = min(os.cpu_count() or 4, 8)`
  - Range: 1-8 workers
  - Per-worker rate limiting

#### Key Features
1. **RateLimiter Class**
   - Per-worker request tracking with time window
   - Auto-calculate threshold based on workers
   - Log warnings at 80% threshold

2. **Progress Tracking**
   - Standard tqdm progress bar
   - Show: items/sec, elapsed time, estimated time remaining
   - Per-worker statistics in verbose mode

3. **Statistics Tracking**
   - Per-worker: time_spent, requests_made, failures, success_count
   - Global summary: total_time, avg_speed, total_requests, success_rate

4. **Error Handling**
   - Individual worker failures don't stop batch
   - Fallback to sequential if parallel fails completely

### Examples
```python
from pyeuropepmc import FullTextClient

client = FullTextClient()

# Auto-detect workers
results = client.download_fulltext_batch_parallel(pmcids)

# Specify worker count
results = client.download_fulltext_batch_parallel(pmcids, max_workers=4)

# Disable progress bar
results = client.download_fulltext_batch_parallel(pmcids, show_progress=False)
```

### Testing
- [ ] Test with 1, 2, 4, 8 workers
- [ ] Verify rate limiting warnings at 80%
- [ ] Test error handling for individual worker failures
- [ ] Compare performance vs sequential download
- [ ] Verify statistics tracking accuracy

### Breaking Changes
<!-- Any breaking changes this introduces? -->

### Additional Context
<!-- Any other context, screenshots, or files -->
