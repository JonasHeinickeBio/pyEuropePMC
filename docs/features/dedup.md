# Intelligent Deduplication

PyEuropePMC's `LiteratureMerger` provides multi-layer deduplication with configurable precision/recall tradeoffs.

## Quick Start

```python
from pyeuropepmc.literature import LiteratureMerger, DedupMode

# Merge papers from multiple sources
sources = [pubmed_papers, arxiv_papers, semantic_scholar_papers]

# BALANCED mode (default)
merger = LiteratureMerger(mode=DedupMode.BALANCED)
merged, report = merger.merge_results(sources)

print(f"{report.total_input} → {report.total_output} ({report.duplicates_removed} removed)")
```

## Dedup Layers

Merging happens in 4 sequential layers:

1. **PMID match** — Exact PubMed ID match (highest confidence)
2. **DOI match** — Normalized DOI comparison (high confidence)
3. **Fuzzy title match** — SequenceMatcher similarity with gates (medium confidence)
4. **Retracted removal** — Remove retracted papers where duplicates exist (safety layer)

## DedupModes

Three algorithm modes control the tradeoff between precision and recall:

### BALANCED (default)

```python
merger = LiteratureMerger(mode=DedupMode.BALANCED)
```

- Threshold: 0.90
- Requires author overlap (Jaccard ≥ 0.3)
- Good for most use cases

### FOCUSED (high recall)

```python
merger = LiteratureMerger(mode=DedupMode.FOCUSED)
```

- Threshold: 0.80
- No author or journal gates
- Catches more duplicates, may have some false positives
- Best for comprehensive literature reviews

### RELAXED (high precision)

```python
merger = LiteratureMerger(mode=DedupMode.RELAXED)
```

- Threshold: 0.95
- Requires author overlap + journal overlap
- Minimal false positives
- Best for exact duplicate detection

## Custom Configuration

```python
from pyeuropepmc.literature import DedupConfig, DedupMode

config = DedupConfig(
    mode=DedupMode.BALANCED,
    fuzzy_threshold=0.85,           # Custom threshold
    year_window=5,                   # Year difference allowed
    require_author_overlap=True,     # Require shared authors
    require_journal_overlap=False,   # Don't require journal match
    keep_provenance=True,            # Track field-level sources
)
merger = LiteratureMerger(config=config)
```

## MergeReport

The merge operation returns a detailed report:

```python
merged, report = merger.merge_results(sources)

# Summary dictionary
summary = report.summary()
print(summary)
# {
#     "total_input": 150,
#     "total_output": 120,
#     "duplicates_removed": 30,
#     "dedup_rate": 0.20,
#     "by_match_level": {
#         "pmid": 10,
#         "doi": 8,
#         "fuzzy": 12,
#         "retracted_removed": 0,
#     },
# }

# Per-record details
for record in report.records:
    print(f"{record.match_level}: {record.kept_id} ← {record.removed_id}")
```

## Provenance Tracking

When `keep_provenance=True`, merged papers track field-level sources:

```python
for paper in merged:
    prov = paper.get("_provenance", {})
    if prov:
        print(f"Provenance for '{paper.get('title', '')[:50]}...':")
        for field, source in prov.items():
            print(f"  {field}: {source}")
```

## Source Priority

When merging fields from multiple records, sources are prioritized:

```python
from pyeuropepmc.literature import SOURCE_PRIORITY

# Higher rank = preferred
# pubmed: 100, crossref: 80, openalex: 60, semanticscholar: 40
```

## Advanced Matching: PaperMatcher

For incremental matching (paper-by-paper):

```python
from pyeuropepmc.literature import PaperMatcher

matcher = PaperMatcher(fuzzy_threshold=0.85, require_author_overlap=True)

for paper in incoming_papers:
    is_dup, level = matcher.match(paper)
    if not is_dup:
        keep_papers.append(paper)
```
