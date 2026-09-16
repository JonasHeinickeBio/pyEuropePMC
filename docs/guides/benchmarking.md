# Benchmarking and profiling

The `pyeuropepmc benchmark` commands and the `pyeuropepmc.benchmark` module measure how completely and how fast `FullTextXMLParser` extracts content from JATS XML. This page covers the commands, the five quality metrics, the report format, the Python API and the separate benchmark of the Europe PMC API clients.

## Quick start

The `pyeuropepmc` command is installed with the package.

```bash
# Score one article on all metrics
pyeuropepmc benchmark run-file article.xml

# Function-level timing and memory allocation for one article
pyeuropepmc benchmark profile article.xml --top 20
pyeuropepmc benchmark profile-memory article.xml --top 15

# Benchmark a directory of JATS XML files and save the report
pyeuropepmc benchmark run local --local-path ./my_xmls --limit 10 --output results.json

# Parse speed and content coverage for a directory
pyeuropepmc benchmark run-extra --xml-dir ./my_xmls --output extra.json
```

## Commands

| Command | Arguments and options | What it does |
|---|---|---|
| `list-datasets` | `--verbose/-v` | Lists the standard datasets with article counts and sizes |
| `dataset-info NAME` | | Shows the metadata of one standard dataset |
| `download NAME` | `--data-dir/-d DIR`, `--force/-f` | Downloads a standard dataset |
| `run DATASET` | `--data-dir/-d`, `--local-path/-l`, `--limit/-n`, `--output/-o`, `--profile/-p`, `--profile-memory/-m`, `--skip-errors/-s` or `--no-skip-errors` | Runs all metrics on a dataset. `DATASET` is a standard dataset name, or `local` together with `--local-path`. |
| `run-file FILE` | `--output/-o` | Runs all metrics on one XML file; `--output` saves the metrics as JSON |
| `run-extra` | `--xml-dir/-d` (default `benchmark_xmls/xml`), `--output/-o` (default `benchmark_xmls/benchmark_results.json`) | Measures parse speed and counts sections, content blocks and inline elements |
| `fetch-xmls` | `--target/-t` (default `55`), `--output-dir/-o` (default `benchmark_xmls/xml`), `--rate-limit/-r` (default `0.5` seconds) | Searches Europe PMC for open-access articles with full text and downloads their XML |
| `profile FILE` | `--top/-t` (default `20`) | Times the parsing pipeline with cProfile |
| `profile-memory FILE` | `--top/-t` (default `15`) | Traces memory allocations of the parsing pipeline with tracemalloc |
| `report FILE` | `--verbose/-v` | Prints a saved report (see [Reports](#reports)) |

`run` prints the composite score, the number of successfully parsed articles and the total parse time; the per-metric scores are in the saved report. By default (`--skip-errors`) an article that fails to read or parse is counted as failed and skipped; with `--no-skip-errors` the first such error stops the run.

## Datasets

### The sample in the repository

A git checkout contains 55 open-access Europe PMC articles in `benchmark_xmls/xml`. They are not part of the installed package; `fetch-xmls` downloads a comparable set (network access required).

```bash
pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --limit 55 --output results.json
pyeuropepmc benchmark run-extra --xml-dir benchmark_xmls/xml --output extra.json
```

Pass `--output` to `run-extra`; without it the results overwrite `benchmark_xmls/benchmark_results.json`.

### Standard datasets

| Dataset | Articles | Size | Content |
|---|---:|---:|---|
| `PMC_sample_1943` | 1,943 | 1.5 GB | Articles from 1,943 journals (2011 PMC snapshot) |
| `PLOS_1000` | 1,000 | 1.3 GB | PLOS articles with publisher JATS XML |
| `eLife_984` | 984 | 4.5 GB | eLife articles with publisher JATS XML |
| `biorxiv-10k-test-2000` | 2,000 | 5.4 GB | bioRxiv preprints with reviewed NLM XML |

All four come from the GROBID evaluation collection on Hugging Face (`sciencialab/grobid-evaluation`). Downloads use the `huggingface_hub` package from the `benchmark` extra (`pip install "pyeuropepmc[benchmark]"`); without it a download fails with an error that names the extra. A dataset is stored in `~/pyeuropepmc_benchmark_data/<name>` unless you pass `--data-dir`.

```bash
pyeuropepmc benchmark dataset-info PMC_sample_1943
pyeuropepmc benchmark download PMC_sample_1943
```

`PMC_sample_1943`, `eLife_984` and `biorxiv-10k-test-2000` store their articles as `*.nxml` files and `PLOS_1000` as `*.xml`. `run` and `download` treat a dataset as downloaded when its directory holds files with that dataset's extension.

## Metrics

Each metric scores an article between 0.0 and 1.0.

| Metric | Report key | What it measures |
|---|---|---|
| Element coverage | `element_coverage` | Share of the distinct content element types in the article (structural wrapper elements excluded) that the parser is configured to handle |
| Text fidelity | `text_fidelity` | Characters of body text captured by the structured parser, compared with the text of the `<body>` element |
| Section accuracy | `section_accuracy` | 0.5 × the share of the XML's section paths the parser found, plus 0.5 × the agreement between the number of `<sec>` elements and the parser's body sections |
| Inline recall | `inline_recall` | Share of inline elements in the XML that the parser reports, over 17 tags: `xref`, `bold`, `italic`, `underline`, `sup`, `sub`, `inline-formula`, `named-content`, `styled-content`, `chem-struct`, `sc`, `monospace`, `strike`, `overline`, `roman`, `sans-serif`, `small-caps` |
| Metadata accuracy | `metadata_accuracy` | Agreement of the extracted title, DOI, PMID, PMCID and authors with the values in the XML |

An article's composite score is the unweighted mean of its five scores. In a report, the composite score of a dataset, or of all articles, is the mean of the five metric means.

## Results on the repository sample

Scores from `pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --limit 55` with the current parser; re-run the command to refresh them. The composite minimum, maximum and standard deviation are computed from the per-article scores in `article_results`, because the report stores only the composite mean.

| Metric | Mean | Min | Max | Std dev |
|---|---:|---:|---:|---:|
| Composite score | 0.9976 | 0.9659 | 1.0000 | 0.0048 |
| Metadata accuracy | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Text fidelity | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Element coverage | 0.9925 | 0.9655 | 1.0000 | 0.0087 |
| Section accuracy | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Inline recall | 0.9956 | 0.8564 | 1.0000 | 0.0207 |

### Parse speed

From `pyeuropepmc benchmark run-extra --xml-dir benchmark_xmls/xml` on one machine. Timings depend on the hardware.

| Metric | Value |
|---|---|
| Articles | 55 (0 errors) |
| Mean parse time | 0.007 s |
| Median parse time | 0.006 s |
| Throughput | 169.5 articles/s |
| Fastest article | PMC13244564 (0.001 s, 15 KB) |
| Slowest article | PMC13240100 (0.031 s, 180 KB) |

### Content coverage

| Metric | Count |
|---|---:|
| Sections | 1,502 |
| Content blocks | 6,832 |
| Block types | 9 |
| Inline element types | 11 |

Block types: `paragraph` 5,540, `unknown_block` 829, `figure` 180, `table` 127, `quote` 69, `heading` 59, `formula` 14, `list` 11, `definition_list` 3.

Inline element types: `xref` 5,612, `italic` 3,355, `superscript` 1,438, `named_content` 1,055, `subscript` 958, `bold` 784, `styled_content` 38, `inline_formula` 20, `small_caps` 9, `sans_serif` 6, `underline` 1.

## Profiling

### Function timing

```bash
pyeuropepmc benchmark profile benchmark_xmls/xml/PMC12900525.xml --top 5
```

Output (timings vary):

```text
============================================================
  Function-Level Profile: PMC12900525.xml
============================================================
  Total time: 0.2477s (52,527 calls)

  Top functions by cumulative time:
  Function                                        Calls    Total  Per Call
  -----------------------------------------------------------------------
  get_full_text_sections_structured                   1   0.1238  0.123798
  extract_sections                                    1   0.0736  0.073598
  _handle_table                                       7   0.0507  0.007241
  content_block_extractor                             1   0.0480  0.047999
  _extract_additional_structures                      1   0.0480  0.047995

  Parser method breakdown:
    get_full_text_sections_structured            : 0.1238s
    extract_references                           : 0.0433s
    get_full_text_sections                       : 0.0146s
    extract_metadata                             : 0.0135s
    parse                                        : 0.0106s
    extract_tables                               : 0.0084s
    extract_authors                              : 0.0033s
    extract_figures                              : 0.0002s
```

The profile includes the one-off import of the parser's extension modules, which can appear as `_find_and_load` rows.

Per Call is the cumulative time divided by the number of calls, `profile_text(xml)["by_function"][name]["percall_cum_s"]`; `percall_raw_s` holds the time spent in the function itself per call.

### Memory allocation

```bash
pyeuropepmc benchmark profile-memory benchmark_xmls/xml/PMC12900525.xml --top 3
```

Output (the start of the standard-library paths shortened to `...`):

```text
============================================================
  Memory Profile: PMC12900525.xml
============================================================
  Peak memory   : 2.09 MiB
  Current memory: 1.76 MiB
  Allocated     : 2.09 MiB

  Top allocations:
  Size (KiB)  Location
  --------------------------------------------------
       479.6  .../lib/python3.10/xml/etree/ElementTree.py:1718
       290.1  .../lib/python3.10/xml/etree/ElementTree.py:1656
       260.4  <frozen importlib._bootstrap_external>:672

  Allocations by module:
    stdlib                                  : 1211.0 KiB
    <frozen importlib._bootstrap_external>  : 264.4 KiB
    pyeuropepmc.features                    : 62.8 KiB
    <string>                                : 7.4 KiB
```

`Allocated` repeats the peak value.

Location is the allocation site, `<file>:<line>`, from the `filename` and `lineno` of each `profile_memory(xml)["top_allocations"]` entry. tracemalloc records no function names, so the entries' `function` is empty.

### Profiling a whole run

With `--profile` and `--profile-memory`, `run` prints a profile summary averaged over the articles and stores each article's data under `metadata.profiling` and `metadata.memory` in the report.

```bash
pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --limit 10 --profile --profile-memory
```

## Reports

`run --output FILE` and `BenchmarkReport.save_json()` write a report with this layout:

| Key | Content |
|---|---|
| `title` | Report title (default `"pyEuropePMC Benchmark Report"`) |
| `created_at` | ISO 8601 timestamp in UTC |
| `metadata.parser_version` | `pyeuropepmc.__version__` at run time |
| `metadata.limit`, `metadata.skip_errors` | Run options |
| `metadata.stats` | `total_articles`, `successful`, `failed`, `total_parse_time_s`, `parse_errors` (list of `{article, error}`) |
| `dataset_summaries.<dataset>` | Per-metric summaries, `composite_score`, `article_count`, `parse_time_seconds` (`mean`, `min`, `max`) and `dataset_info` |
| `aggregate_by_dataset.<dataset>` | For each metric `{mean, median, min, max, std, count}`, plus `composite_score` (`{"mean": ...}`) and `article_count` |
| `aggregate_overall` | The same statistics over all articles, plus `total_articles` |
| `article_results[]` | `dataset`, `article` (file name without extension), `metrics` (the output of `compute_all_metrics`) and `metadata` (`file_size_bytes`, `parse_time_seconds`, and `profiling` or `memory` when enabled) |

`pyeuropepmc benchmark report FILE` prints the parser version, creation time, article counts and total parse time, then for each dataset the article count, mean parse time and composite score, and the overall composite and per-metric mean scores. `--verbose` adds each article's composite score and parse time:

```bash
pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --limit 3 --output results.json
pyeuropepmc benchmark report results.json --verbose
```

Output (timings vary):

```text
============================================================
  Benchmark Report: pyEuropePMC Benchmark Report
============================================================
  Parser version  : 2.2.1
  Created         : 2026-09-16T10:07:46.446804+00:00
  Articles        : 3
  Successful      : 3
  Failed          : 0
  Parse time      : 0.06s

  Per-dataset summaries:

  [local]
    Articles       : 3
    Parse time     : 0.018s (mean)
    Composite score: 0.9992

  Overall:
    Composite score: 0.9992
      element_coverage              : 0.9962
      inline_recall                 : 1.0000
      metadata_accuracy             : 1.0000
      section_accuracy              : 1.0000
      text_fidelity                 : 1.0000

  Per-article details:
    PMC12900525                    [local]  score=0.9977  parse=0.0289s
    PMC12967033                    [local]  score=1.0000  parse=0.0144s
    PMC13125388                    [local]  score=1.0000  parse=0.0119s
```

From Python:

```python
from pyeuropepmc.benchmark import BenchmarkReport

report = BenchmarkReport.load_json("results.json")
report.print_summary()
```

Output for the 55-article run:

```text
============================================================
  pyEuropePMC Benchmark Report
  Generated: 2026-09-15T18:35:12.688749+00:00
============================================================

  Overall (55 articles):
    element_coverage           mean = 0.9925
    text_fidelity              mean = 1.0
    section_accuracy           mean = 1.0
    inline_recall              mean = 0.9956
    metadata_accuracy          mean = 1.0
    composite_score            mean = 0.9976

  Per dataset:
    local                      composite = 0.9976    (55 articles)
```

`print_summary(include_articles=True)` also lists the composite scores of the first five articles.

## Python API

All names below are importable from `pyeuropepmc.benchmark`.

### BenchmarkDataset

```python
from pyeuropepmc.benchmark import BenchmarkDataset

local = BenchmarkDataset("local", local_path="benchmark_xmls/xml")
print(local.article_count)
paths = local.get_article_paths(limit=5)

sample = BenchmarkDataset("PMC_sample_1943", data_dir="./benchmark_data")
print(sample.info.article_count, sample.info.size_gb)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | A standard dataset name, or `"local"` |
| `data_dir` | `str \| Path \| None` | `None` | Root directory for standard datasets; `None` means `~/pyeuropepmc_benchmark_data` |
| `source` | `str \| None` | `None` | Custom download source; defaults to the registry entry |
| `local_path` | `str \| Path \| None` | `None` | Directory of XML files; required when `name` is `"local"` (otherwise `ValueError`) |

| Member | Returns | Description |
|---|---|---|
| `download(force=False, progress_callback=None)` | `Path` | Downloads a standard dataset; raises `ValueError` for `"local"` and `ConnectionError` when no download method succeeds |
| `iter_articles()` | iterator of `Path` | Files matching the dataset's pattern (`*.xml`, or `*.nxml` for three standard datasets); raises `FileNotFoundError` if the directory does not exist |
| `get_article_paths(limit=None)` | `list[Path]` | The same files as a list |
| `article_count` | `int` | Number of matching files on disk |
| `is_downloaded` | `bool` | Whether the directory contains files matching the dataset's pattern |
| `info` | `DatasetInfo` | `name`, `source`, `size_gb`, `article_count`, `description` |
| `to_dict()` | `dict` | Dataset metadata for reports |

### BenchmarkRunner

```python
from pyeuropepmc.benchmark import BenchmarkDataset, BenchmarkRunner

dataset = BenchmarkDataset("local", local_path="benchmark_xmls/xml")
runner = BenchmarkRunner(dataset, limit=10, profile=True, profile_memory=True)
report = runner.run_all()

print(runner.stats["successful"], "of", runner.stats["total_articles"], "articles parsed")
runner.print_profile_summary(report)
report.save_json("results.json")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dataset` | `BenchmarkDataset \| list[BenchmarkDataset]` | required | One or more datasets |
| `limit` | `int \| None` | `None` | Maximum number of articles per dataset |
| `config` | `Any` | `None` | Passed to `FullTextXMLParser(config=...)` |
| `report_title` | `str \| None` | `None` | Report title; `None` means `"pyEuropePMC Benchmark Report"` |
| `skip_errors` | `bool` | `True` | Skip an article that fails to read or parse and record it in `stats["parse_errors"]`; with `False` the error is raised and the run stops. Recorded in the report metadata |
| `profile` | `bool` | `False` | Collect cProfile data for each article |
| `profile_memory` | `bool` | `False` | Collect tracemalloc data for each article |
| `profile_top_n` | `int` | `20` | Number of functions kept in the profile summaries |

`run_all()` returns a `BenchmarkReport`. `runner.stats` holds `total_articles`, `successful`, `failed`, `total_parse_time_s` and `parse_errors`.

### BenchmarkReport

```python
from pyeuropepmc.benchmark import BenchmarkReport

report = BenchmarkReport.load_json("results.json")
overall = report.aggregate_overall()
print(overall["composite_score"]["mean"])
print(overall["inline_recall"])
print(sorted(report.aggregate_by_dataset()))
```

| Method | Returns | Description |
|---|---|---|
| `BenchmarkReport(title="pyEuropePMC Benchmark Report")` | | Creates an empty report |
| `add_article_result(dataset_name, article_label, metrics, metadata=None)` | `None` | Adds one article's metrics |
| `add_dataset_summary(dataset_name, summary)` | `None` | Stores a dataset summary |
| `set_metadata(**kwargs)` | `None` | Updates `metadata` |
| `aggregate_by_dataset()` | `dict[str, dict]` | Statistics per dataset (layout as in [Reports](#reports)) |
| `aggregate_overall()` | `dict` | Statistics over all articles |
| `to_dict()`, `to_json(indent=2)` | `dict`, `str` | Serialised report |
| `save_json(path, indent=2)` | `Path` | Writes the report, creating parent directories |
| `load_json(path)` | `BenchmarkReport` | Class method; restores `title`, `created_at`, `metadata`, `dataset_summaries` and `article_results` |
| `print_summary(include_articles=False)` | `None` | Prints overall and per-dataset scores |

### Metrics for one article

```python
from pathlib import Path

from pyeuropepmc.benchmark import compute_all_metrics
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

xml = Path("article.xml").read_text(encoding="utf-8")
metrics = compute_all_metrics(FullTextXMLParser(xml), xml)
print(metrics["composite_score"])
print(metrics["per_metric"])
```

`compute_all_metrics(parser, xml_content)` returns a dict with one detail dict per metric (each with a `score` key), `composite_score` (`float`) and `per_metric` (metric name to score).

### Profiling helpers

```python
from pathlib import Path

from pyeuropepmc.benchmark import MemoryTracker, ProfilerContext, profile_memory, profile_text
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

xml = Path("article.xml").read_text(encoding="utf-8")

with ProfilerContext() as prof:
    FullTextXMLParser(xml).get_full_text_sections_structured()
stats = prof.stats_dict()
print(stats["elapsed_s"], stats["total_calls"])

tracker = MemoryTracker()
tracker.start()
FullTextXMLParser(xml).extract_references()
memory = tracker.stop()
print(memory["peak_mib"], "MiB")

print(profile_text(xml)["parser_breakdown_s"])
print(profile_memory(xml)["peak_mib"], "MiB")
```

| Call | Returns |
|---|---|
| `ProfilerContext(builtins=False).stats_dict()` | `elapsed_s`, `total_calls`, `primitive_calls` and `by_function`, which maps each function name to `filename`, `lineno`, `ncalls`, `tottime_s`, `cumtime_s`, `percall_raw_s` and `percall_cum_s` |
| `MemoryTracker(nframe=3).stop()` | `peak_mib`, `current_mib`, `allocated_mib`, `top_allocations` (each with `size_kib`, `count`, `filename`, `lineno`, `function`, `trace`) and `by_module`. `MemoryTracker` also works as a context manager. |
| `profile_text(xml_content)` | The `stats_dict()` keys plus `parser_breakdown_s` (seconds per parser method) |
| `profile_memory(xml_content)` | The `MemoryTracker.stop()` keys for parsing the article and extracting metadata, sections, authors and references |

## API client benchmark

`tests/benchmark_article_client.py::test_modular_benchmark_system` times the Europe PMC API clients against the live API, with and without caching. It needs a source checkout with the development dependencies and network access, and it sends many requests.

```bash
pytest tests/benchmark_article_client.py::test_modular_benchmark_system \
  -m benchmark --force-enable-socket --timeout=3600 -v
```

The options override the project's default pytest settings, which deselect `benchmark` tests, block network access and stop a test after 120 seconds. The test writes `MODULAR_PERFORMANCE_REPORT.md` and `MODULAR_BENCHMARK_RESULTS.json` to the current directory.

The Weekly Benchmarks workflow (`.github/workflows/benchmark.yml`) runs this test every Monday at 02:00 UTC. It uploads both files as the `benchmark-results` artifact (kept for 90 days) and opens a pull request that refreshes the Performance section of the repository README and `.github/benchmark-history.json`.

## Module layout

```text
src/pyeuropepmc/benchmark/
├── __init__.py    # public exports
├── dataset.py     # BenchmarkDataset, dataset registry, downloads
├── metrics.py     # the five metrics and compute_all_metrics
├── report.py      # BenchmarkReport
├── runner.py      # BenchmarkRunner
├── profiler.py    # ProfilerContext, profile_text
└── memory.py      # MemoryTracker, profile_memory
src/pyeuropepmc/cli/benchmark.py   # the pyeuropepmc benchmark commands
```

## See also

- `pyeuropepmc benchmark --help` and `pyeuropepmc benchmark COMMAND --help`
- [XML parsing](../features/parsing/README.md)
- [XML parser extensions](../api/xml-parser-extensions.md): content blocks and structured sections, which the coverage benchmark counts
