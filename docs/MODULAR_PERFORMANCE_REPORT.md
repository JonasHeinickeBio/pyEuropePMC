# 🚀 pyEuropePMC Benchmark Suite
**Generated:** 2025-10-20 15:49:25

## 📊 Summary

- **Total Benchmarks:** 6
- **Total Methods:** 10
- **Successful Runs:** 10
- **Failed Runs:** 0
- **Cache Enabled:** 5

## ArticleClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| get_article_details | 1.102s | 0.008s | 0.0MB | ❌ | 31 | 0 |
<sub>p50: 1.099s · p95: 1.117s · ops: 0.91/s · runs: 30</sub>
| get_citations | 1.128s | 0.044s | 0.0MB | ❌ | 31 | 0 |
<sub>p50: 1.115s · p95: 1.229s · ops: 0.89/s · runs: 30</sub>

## ArticleClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| get_article_details | <1ms | <1ms | 0.0MB | ✅ | 0 | 0 |
<sub>p50: 223µs · p95: 245µs · ops: 4372.10/s · runs: 30</sub>
| get_citations | <1ms | <1ms | 0.0MB | ✅ | 0 | 0 |
<sub>p50: 231µs · p95: 262µs · ops: 4264.25/s · runs: 30</sub>

## SearchClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| search | 1.331s | 0.257s | 0.0MB | ❌ | 31 | 0 |
<sub>p50: 1.260s · p95: 2.274s · ops: 0.75/s · runs: 30</sub>
| get_hit_count | 1.260s | 0.022s | 0.0MB | ❌ | 31 | 0 |
<sub>p50: 1.257s · p95: 1.301s · ops: 0.79/s · runs: 30</sub>

## SearchClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| search | <1ms | <1ms | 0.0MB | ✅ | 0 | 0 |
<sub>p50: 480µs · p95: 812µs · ops: 1827.45/s · runs: 30</sub>
| get_hit_count | <1ms | <1ms | 0.0MB | ✅ | 0 | 0 |
<sub>p50: 232µs · p95: 270µs · ops: 4291.13/s · runs: 30</sub>

## FullTextClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| check_fulltext_availability | 0.285s | 0.047s | 0.0MB | ❌ | 93 | 0 |
<sub>p50: 0.270s · p95: 0.413s · ops: 3.50/s · runs: 30</sub>

## FullTextClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| check_fulltext_availability | <1ms | <1ms | 0.0MB | ✅ | 0 | 0 |
<sub>p50: 123µs · p95: 158µs · ops: 7773.99/s · runs: 30</sub>

## 🔁 Cache vs No-Cache Comparison

### ArticleClient — cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| get_article_details | 1.102s | <1ms | 4820.15x |
| get_citations | 1.128s | <1ms | 4810.94x |

- **Average speedup for ArticleClient (no-cache / cached):** 4815.55x

### FullTextClient — cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| check_fulltext_availability | 0.285s | <1ms | 2219.04x |

- **Average speedup for FullTextClient (no-cache / cached):** 2219.04x

### SearchClient — cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| get_hit_count | 1.260s | <1ms | 5408.62x |
| search | 1.331s | <1ms | 2432.94x |

- **Average speedup for SearchClient (no-cache / cached):** 3920.78x

---
_Notes: Means are computed over measured iterations; '-' indicates missing data. Values like '<1ms' indicate very fast cached responses. Speedups shown as lower-bounds when cached times are too small to measure precisely._

## ⚙️ How to reproduce

Run the modular benchmark locally and regenerate these artifacts:

```bash
pytest -q tests/benchmark_article_client.py::test_modular_benchmark_system -q
```

- Detailed JSON results: `MODULAR_BENCHMARK_RESULTS.json`
