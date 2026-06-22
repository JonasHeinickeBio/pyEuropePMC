# pyEuropePMC Benchmark Suite
**Generated:** 2025-10-20 15:49:25

## Summary

- **Total Benchmarks:** 6
- **Total Methods:** 10
- **Successful Runs:** 10
- **Failed Runs:** 0
- **Cache Enabled:** 5

## ArticleClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| get_article_details | 1.102s | 0.008s | 0.0MB | No | 31 | 0 |
<p50: 1.099s, p95: 1.117s, ops: 0.91/s, runs: 30</p>
| get_citations | 1.128s | 0.044s | 0.0MB | No | 31 | 0 |
<p50: 1.115s, p95: 1.229s, ops: 0.89/s, runs: 30</p>

## ArticleClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| get_article_details | <1ms | <1ms | 0.0MB | Yes | 0 | 0 |
<p50: 223us, p95: 245us, ops: 4372.10/s, runs: 30</p>
| get_citations | <1ms | <1ms | 0.0MB | Yes | 0 | 0 |
<p50: 231us, p95: 262us, ops: 4264.25/s, runs: 30</p>

## SearchClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| search | 1.331s | 0.257s | 0.0MB | No | 31 | 0 |
<p50: 1.260s, p95: 2.274s, ops: 0.75/s, runs: 30</p>
| get_hit_count | 1.260s | 0.022s | 0.0MB | No | 31 | 0 |
<p50: 1.257s, p95: 1.301s, ops: 0.79/s, runs: 30</p>

## SearchClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| search | <1ms | <1ms | 0.0MB | Yes | 0 | 0 |
<p50: 480us, p95: 812us, ops: 1827.45/s, runs: 30</p>
| get_hit_count | <1ms | <1ms | 0.0MB | Yes | 0 | 0 |
<p50: 232us, p95: 270us, ops: 4291.13/s, runs: 30</p>

## FullTextClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| check_fulltext_availability | 0.285s | 0.047s | 0.0MB | No | 93 | 0 |
<p50: 0.270s, p95: 0.413s, ops: 3.50/s, runs: 30</p>

## FullTextClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| check_fulltext_availability | <1ms | <1ms | 0.0MB | Yes | 0 | 0 |
<p50: 123us, p95: 158us, ops: 7773.99/s, runs: 30</p>

## Cache vs No-Cache Comparison

### ArticleClient - cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| get_article_details | 1.102s | <1ms | 4820.15x |
| get_citations | 1.128s | <1ms | 4810.94x |

- **Average speedup for ArticleClient (no-cache / cached):** 4815.55x

### FullTextClient - cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| check_fulltext_availability | 0.285s | <1ms | 2219.04x |

- **Average speedup for FullTextClient (no-cache / cached):** 2219.04x

### SearchClient - cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| get_hit_count | 1.260s | <1ms | 5408.62x |
| search | 1.331s | <1ms | 2432.94x |

- **Average speedup for SearchClient (no-cache / cached):** 3920.78x

_Notes: Means are computed over measured iterations; '-' indicates missing data. Values like '<1ms' indicate very fast cached responses. Speedups shown as lower-bounds when cached times are too small to measure precisely._

## XML Parser Quality Benchmark

**Generated:** 2026-06-22 | **Dataset:** 55 open-access JATS articles from Europe PMC

### Quality Metrics

| Metric | Mean | Min | Max | Std Dev |
|--------|------|-----|-----|---------|
| **Composite Score** | **0.9496** | 0.8835 | 0.9908 | 0.0250 |
| Metadata Accuracy | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Text Fidelity | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Element Coverage | 0.9923 | 0.9655 | 1.0000 | 0.0089 |
| Section Accuracy | 0.9339 | 0.7692 | 1.0000 | 0.0518 |
| Inline Recall | 0.8219 | 0.4286 | 0.9732 | 0.1204 |

### Parse Speed

| Metric | Value |
|--------|-------|
| Throughput | 48.0 articles/s |
| Mean parse time | 0.024s |
| Median parse time | 0.021s |

### Content Coverage (55 articles)

| Type | Count |
|------|-------|
| Sections | 1,452 |
| Content blocks | 6,735 |
| Block types | 8 (paragraph, figure, table, quote, heading, formula, list, unknown) |
| Inline types | 9 (xref, italic, superscript, named_content, subscript, bold, styled_content, inline_formula, small_caps) |

### How to reproduce

```bash
# Full quality benchmark
pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --limit 55 --output parser_results.json

# Speed + coverage
pyeuropepmc benchmark run-extra --xml-dir benchmark_xmls/xml --output speed_results.json
```

## How to reproduce

Run the modular benchmark locally and regenerate these artifacts:

```bash
pytest -q tests/benchmark_article_client.py::test_modular_benchmark_system -q
```

- Detailed JSON results: `MODULAR_BENCHMARK_RESULTS.json`
