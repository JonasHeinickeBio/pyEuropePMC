"""
pyEuropePMC Benchmark Suite — standardized, reusable XML parsing benchmarks.

Provides dataset management, XML-level metrics, per-dataset reporting,
function-level profiling, and memory tracking for evaluating the full
text XML parser quality and performance.

Key components
--------------
- :class:`BenchmarkDataset` — Download, cache, and iterate benchmark datasets
- :func:`compute_all_metrics` — Run all XML-level metrics on a parsed article
- :class:`BenchmarkReport` — Accumulate per-dataset and aggregate reports
- :class:`BenchmarkRunner` — Orchestrate batch benchmarks across datasets
- :class:`ProfilerContext` — Function-level timing via ``cProfile``
- :class:`MemoryTracker` — Memory allocation tracking via ``tracemalloc``
- :func:`profile_text` — One-call function profiling for any XML string
- :func:`profile_memory` — One-call memory profiling for any XML string

Datasets supported
------------------
- ``PMC_sample_1943`` — 1,943 PMC articles (GROBID evaluation, Hugging Face)
- ``biorxiv-10k-test-2000`` — 2,000 bioRxiv preprints (GROBID evaluation)
- ``PLOS_1000`` — 1,000 PLOS articles (GROBID evaluation)
- ``eLife_984`` — 984 eLife articles (GROBID evaluation)
- ``local`` — Any local directory of JATS XML files

Usage
-----
>>> from pyeuropepmc.benchmark import BenchmarkDataset, BenchmarkRunner

>>> dataset = BenchmarkDataset("PMC_sample_1943", data_dir="./benchmark_data")
>>> dataset.download()  # downloads once, caches locally

>>> runner = BenchmarkRunner(dataset)
>>> report = runner.run_all()
>>> report.save_json("benchmark_results.json")

>>> # Function-level profiling
>>> from pyeuropepmc.benchmark import profile_text
>>> prof = profile_text(xml_string)
>>> print(prof["parser_breakdown_s"])

>>> # Memory profiling
>>> from pyeuropepmc.benchmark import profile_memory
>>> mem = profile_memory(xml_string)
>>> print(f"Peak: {mem['peak_mib']:.2f} MiB")
"""

from pyeuropepmc.benchmark.dataset import DATASETS, BenchmarkDataset, dataset_info
from pyeuropepmc.benchmark.memory import MemoryTracker, profile_memory, profile_memory_blocks
from pyeuropepmc.benchmark.metrics import compute_all_metrics
from pyeuropepmc.benchmark.profiler import (
    ProfilerContext,
    profile_text,
    time_et_parse,
    time_function,
)
from pyeuropepmc.benchmark.report import BenchmarkReport
from pyeuropepmc.benchmark.runner import BenchmarkRunner

__all__ = [
    "BenchmarkDataset",
    "BenchmarkReport",
    "BenchmarkRunner",
    "DATASETS",
    "MemoryTracker",
    "ProfilerContext",
    "compute_all_metrics",
    "dataset_info",
    "profile_memory",
    "profile_memory_blocks",
    "profile_text",
    "time_et_parse",
    "time_function",
]
