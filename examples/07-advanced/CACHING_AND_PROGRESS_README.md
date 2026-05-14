# ME/CFS KG Readiness Demo: Caching & Progress Updates

## Overview
The `04-mecfs-kg-readiness-demo.py` script has been enhanced with comprehensive caching and real-time progress reporting capabilities for long-running corpus assessments.

## Key Enhancements

### 1. **Checkpoint/Cache System**
- **Automatic Checkpoints**: After each major phase (corpus collection, XML/annotation probes, evaluation), results are saved to a checkpoint file.
- **Resume Capability**: If the script is interrupted, it automatically resumes from the last completed phase on the next run.
- **Efficient Recovery**: Avoids re-running expensive operations like corpus crawls and probes.

**Default Cache Location**: `data/output/.mecfs_demo_cache/checkpoint.json`

**CLI Options**:
```bash
--no-cache              # Disable caching entirely
--clear-cache           # Delete checkpoint and start fresh
--no-resume             # Ignore checkpoint and always start fresh
--cache-dir PATH        # Custom cache directory (default: data/output/.mecfs_demo_cache)
```

### 2. **Enhanced Progress Reporting**

#### Corpus Crawl Phase
```
[Corpus crawl]
    scanned 10,000/100,000 | rate=50.2 papers/sec | ETA=30m12s
    scanned 20,000/100,000 | rate=48.9 papers/sec | ETA=25m41s
    ...
```

- **Real-time metrics**: Papers/second processing rate
- **ETA calculation**: Time-to-completion based on current pace
- **Configurable frequency**: `--progress-every N` (default: 10,000 papers)

#### XML & Annotation Probe Phases
```
[XML and annotation probes]
    Probing 15,679 papers for XML availability...
      XML: 100/15,679 | success=97 | ETA=2m35s
      XML: 200/15,679 | success=194 | ETA=2m28s
```

- **Per-100-item updates** (configurable via `progress_interval`)
- **Cumulative success tracking**
- **Live ETA updates**

#### Phase Timing
```
[Corpus crawl] (elapsed: 8m23s)
[XML and annotation probes] (elapsed: 42m15s)
[Enrichment and capability evaluation] (elapsed: 15s)
```

- All phases display elapsed time
- Time tracking from script start

### 3. **New Data Structures**

#### `ProgressTracker` (Enhanced)
- Added `start_time` and `phase_start_time` fields
- New methods:
  - `_format_time()`: Human-readable time formatting
  - `_estimate_eta()`: ETA calculation from current pace

#### `CheckpointData` (New)
- Serializable dataclass storing intermediate results
- Tracks phases: `"corpus"` → `"probes"` → `"enrichment"` → `"complete"`
- Stores all intermediate metrics and payloads

#### `CheckpointManager` (New)
- Saves/loads checkpoints to/from disk
- Methods:
  - `save(checkpoint)`: Persist checkpoint as JSON
  - `load()`: Load checkpoint if it exists
  - `clear()`: Delete checkpoint and cache directory

### 4. **Improved Corpus Collection**

```python
def _collect_mecfs_corpus(
    client: SearchClient,
    query: str,
    target_papers: int,
    page_size: int,
    progress_every: int = 10_000,
) -> tuple[CorpusMetrics, list[ArticleCandidate]]:
```

- Added `progress_every` parameter
- Calculates processing rate and ETA during crawl
- Prints progress at configurable intervals

### 5. **Nested Progress in Probes**

```python
def _probe_xml_and_annotations(
    articles: list[ArticleCandidate],
    xml_probe_size: int,
    annotation_probe_size: int,
    progress_interval: int = 100,
) -> tuple[ProbeMetrics, dict[str, Any] | None]:
```

- Added `progress_interval` parameter (default: 100 items)
- Separate nested progress loops for XML and annotations
- Real-time success counting and ETA

### 6. **Multi-Phase Main Loop**

The `main()` function now orchestrates:

1. **Checkpoint Setup**: Load existing checkpoint if available
2. **Phase 1: Corpus Crawl** (or restore from checkpoint)
   - Save checkpoint after completion
3. **Phase 2: XML/Annotation Probes** (or restore from checkpoint)
   - Save checkpoint after completion
4. **Phase 3: Enrichment & Evaluation** (or restore from checkpoint)
   - Save checkpoint after completion
5. **Cleanup**: Clear checkpoint on successful completion

### 7. **Argument Parser Extensions**

New CLI arguments:
```bash
--cache-dir PATH        # Where to store checkpoints
--no-cache              # Disable caching
--clear-cache           # Clear cache and restart
--no-resume             # Don't resume from checkpoint
```

## Usage Examples

### Basic run with caching (default)
```bash
python 04-mecfs-kg-readiness-demo.py
# Checkpoints after each phase; resumes if interrupted
```

### Run without caching
```bash
python 04-mecfs-kg-readiness-demo.py --no-cache
# No checkpoint saved; always runs all phases start-to-finish
```

### Clear cache and restart fresh
```bash
python 04-mecfs-kg-readiness-demo.py --clear-cache
# Removes existing checkpoint, starts fresh run
```

### Ignore checkpoint and re-run
```bash
python 04-mecfs-kg-readiness-demo.py --no-resume
# Checkpoint may exist but is ignored; runs all phases anew
```

### Custom cache location
```bash
python 04-mecfs-kg-readiness-demo.py --cache-dir /tmp/my_cache
# Saves checkpoint to /tmp/my_cache/checkpoint.json
```

### Combine options
```bash
python 04-mecfs-kg-readiness-demo.py --target-papers 50000 --progress-every 5000 --cache-dir ./checkpoints
# Smaller target, more frequent updates, custom cache location
```

## Checkpoint File Format

**Location**: `data/output/.mecfs_demo_cache/checkpoint.json`

```json
{
  "phase": "probes",
  "query": "...",
  "target_papers": 100000,
  "page_size": 1000,
  "xml_probe_size": 0,
  "annotation_probe_size": 0,
  "corpus_metrics": {
    "target_papers": 100000,
    "hit_count": 345678,
    "scanned_papers": 20808,
    ...
  },
  "sampled_articles": [
    {"pmcid": "PMC1234567", "pmid": "12345678", "doi": "10.1234/example"},
    ...
  ],
  "timestamp": "2026-04-24T14:32:15.123456+00:00"
}
```

## Behavior Flows

### Scenario 1: Normal Successful Run
```
1. Load checkpoint (none exists)
2. Run corpus crawl → Save checkpoint (phase=probes)
3. Run probes → Save checkpoint (phase=enrichment)
4. Run evaluation → Save checkpoint (phase=complete)
5. Generate report and clear checkpoint
```

### Scenario 2: Interrupted During Probes
```
Run 1:
  1. Run corpus crawl → Save checkpoint (phase=probes)
  2. Run 500/15679 probes → [CRASH]

Run 2:
  1. Load checkpoint (phase=probes with corpus_metrics + sampled_articles)
  2. Skip corpus crawl (restore from checkpoint)
  3. Resume probes from where left off → Save checkpoint (phase=enrichment)
  4. ...
```

### Scenario 3: User Wants Fresh Run
```
python 04-mecfs-kg-readiness-demo.py --clear-cache
  1. Clear existing checkpoint
  2. Run all phases fresh (no resume)
```

## Performance Notes

- **Corpus crawl**: ~50 papers/second (depends on network/rate limits)
  - 100K papers ≈ 33-40 minutes
- **XML probes**: ~2-5 probes/second (depends on file sizes)
  - 15K+ papers ≈ 1-2 hours
- **Annotation probes**: ~1-3 probes/second with multi-identifier fallback
  - 15K+ papers ≈ 2-5 hours
- **Evaluation**: <1 second

**Total time for full 100K corpus**: 4-8 hours (highly dependent on network conditions)

Checkpoints enable breaking this into smaller chunks across multiple days if needed.

## Benefits

✓ **Long-running tasks**: Resume interrupted runs seamlessly
✓ **Debugging**: Quickly test evaluation logic without re-crawling corpus
✓ **Transparency**: Real-time ETAs let you plan around long operations
✓ **Efficiency**: Cache specific phases; skip expensive re-runs
✓ **Profiling**: Accurate timing data for each phase
