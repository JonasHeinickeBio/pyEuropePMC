# Intelligent Deduplication

PyEuropePMC's `LiteratureMerger` provides multi-layer deduplication with configurable precision/recall tradeoffs. The strategy is inspired by the **CORD-19 dataset pipeline**: cluster papers by shared identifiers, select a canonical metadata entry per cluster, and filter non-paper entries.

## Quick Start

```python
from pyeuropepmc.features.enrich.merger import LiteratureMerger, DedupMode

# Merge papers from multiple sources
sources = [pubmed_papers, arxiv_papers, semantic_scholar_papers]

# BALANCED mode (default)
merger = LiteratureMerger(mode=DedupMode.BALANCED)
merged, report = merger.merge_results(sources)

print(f"{report.total_input} → {report.total_output} ({report.duplicates_removed} removed)")
```

## Dedup Layers

Merging happens in sequential layers:

1. **Identifier clustering (CORD-19 style)** — Union-find clustering over any shared identifier: `doi`, `pmid`, `pmcid`, `arxiv`, `mag`, `who` (Covidence ID). Papers that share *any* identifier land in the same cluster; a canonical member is chosen by (license permissiveness → document availability → source reliability) and the remaining members are merged into it. Each cluster gets a deterministic `cluster_id` (e.g. `CORD-65483F50015734B6`).
2. **PMID match** — Exact PubMed ID match (highest confidence)
3. **DOI match** — Normalized DOI comparison (high confidence)
4. **Fuzzy title match** — SequenceMatcher similarity with gates (medium confidence)
5. **Retracted removal** — Remove retracted papers (safety layer)
6. **Non-paper filtering** — Remove front-matter entries (tables of contents, subject indices, editorial boards, instructions for authors, cover pages) — mirrors CORD-19 "cluster filtering"

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
from pyeuropepmc.features.enrich.merger import DedupConfig, DedupMode

config = DedupConfig(
    mode=DedupMode.BALANCED,
    fuzzy_threshold=0.85,           # Custom threshold
    year_window=5,                   # Year difference allowed
    require_author_overlap=True,     # Require shared authors
    require_journal_overlap=False,   # Don't require journal match
    keep_provenance=True,            # Track field-level sources
    # CORD-19 clustering options (defaults shown):
    use_identifier_clustering=True,  # Cluster by any shared identifier
    strict_identifier_conflicts=False,  # Reject shared id if another id conflicts
    prefer_open_access=True,         # Canonical prefers permissive license + full text
    filter_non_papers=True,          # Remove TOC/index/front-matter entries
    persist_cluster_ids=True,        # Attach deterministic cluster_id to merged papers
)
merger = LiteratureMerger(config=config)
```

### Identifier Clustering

Two papers join the same cluster when they share **any** identifier: DOI, PMID, PMCID, arXiv, MAG, or WHO/Covidence ID. With `strict_identifier_conflicts=True`, a shared identifier is *ignored* when the papers also carry a conflicting value for another identifier type (e.g. same DOI but different PMID → separate clusters), mirroring CORD-19.

```python
from pyeuropepmc.features.enrich.merger import cluster_papers_by_identifier

clusters = cluster_papers_by_identifier(papers, strict_conflicts=True)
# e.g. [[0, 3, 7], [1], [2, 5]]  — indices grouped into clusters
```

### Canonical Metadata Selection

Within each cluster the canonical entry is chosen by, in order:

1. **License permissiveness** — CC0 > CC-BY > CC-BY-SA > CC-BY-NC* > CC-BY-ND > open-access > unknown
2. **Document availability** — PMCID / full-text URL / PDF / OA status / abstract
3. **Source reliability** — pubmed > crossref > openalex > semanticscholar > unpaywall > arxiv

Missing fields in the canonical entry are promoted from other cluster members (as in CORD-19), with provenance tracked when `keep_provenance=True`.

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

# CORD-19 clustering stats
print(report.metadata)
# {
#     "identifier_clusters": 12,
#     "clustered_papers": 18,
# }
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
from pyeuropepmc.features.enrich.merger import SOURCE_PRIORITY

# Higher rank = preferred
# pubmed: 100, crossref: 90, openalex: 80, semanticscholar: 70, unpaywall: 60, arxiv: 50
```

## Advanced Matching: PaperMatcher

For incremental matching (paper-by-paper):

```python
from pyeuropepmc.features.enrich.merger import PaperMatcher

matcher = PaperMatcher(fuzzy_threshold=0.85, require_author_overlap=True)

for paper in incoming_papers:
    is_dup, level = matcher.match(paper)
    if not is_dup:
        keep_papers.append(paper)
```
