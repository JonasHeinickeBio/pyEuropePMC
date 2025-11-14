
import time
import tempfile
import statistics
import psutil
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Type
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import shutil
import pytest
import requests
import threading
import tracemalloc


# Import all main client classes here
from pyeuropepmc.clients.article import ArticleClient
from pyeuropepmc.clients.search import SearchClient
from pyeuropepmc.clients.fulltext import FullTextClient
from pyeuropepmc.cache.cache import CacheConfig


# A tiny no-op benchmark fixture that mimics pytest-benchmark's minimal API
class _DummyBenchmarkFixture:
    def pedantic(self, func, iterations=1, rounds=1, warmup_rounds=0):
        # iterations per round; run rounds times
        for _ in range(rounds):
            for _ in range(iterations):
                func()

    def __call__(self, func):
        # simple callable fallback
        return func()


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""
    client_class: Type
    cache_config: Optional[CacheConfig] = None
    methods: List[str] = field(default_factory=list)
    # Number of measured iterations (used to compute means). Increase for stability.
    iterations: int = 30
    # Number of warmup (unmeasured) iterations to run before timing
    warmup_iterations: int = 10
    # Number of cold measured runs (measured before warmup, to capture cold start)
    cold_runs: int = 1
    name: str = ""
    cache_dir: Optional[Path] = None
    test_data: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    method_name: str
    client_name: str
    cache_enabled: bool
    execution_times: List[float]
    memory_usages: List[float]
    # Optional cold-start measured times (measured before warmup)
    cold_execution_times: List[float] = field(default_factory=list)
    cold_memory_usages: List[float] = field(default_factory=list)
    cache_stats: Dict[str, Any] = field(default_factory=dict)
    # Per-measured-run cache stats (list aligned with execution_times)
    cache_stats_per_run: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    # Per-measured-run HTTP request counts (aligned with execution_times)
    request_counts_per_run: List[int] = field(default_factory=list)
    # Cold-run request counts
    cold_request_counts: List[int] = field(default_factory=list)
    # Aggregate total requests observed during this benchmark
    total_requests: int = 0
    # Per-run peak RSS in bytes
    rss_peak_bytes_per_run: List[int] = field(default_factory=list)
    # Per-run tracemalloc peak in bytes
    tracemalloc_peak_bytes_per_run: List[int] = field(default_factory=list)
    # Cold-run rss peaks
    cold_rss_peak_bytes: List[int] = field(default_factory=list)
    cold_tracemalloc_peak_bytes: List[int] = field(default_factory=list)

    @property
    def mean_time(self) -> float:
        return statistics.mean(self.execution_times) if self.execution_times else 0

    @property
    def std_dev_time(self) -> float:
        return statistics.stdev(self.execution_times) if len(self.execution_times) > 1 else 0

    @property
    def mean_memory(self) -> float:
        return statistics.mean(self.memory_usages) if self.memory_usages else 0

    @property
    def mean_time_cold(self) -> float:
        return statistics.mean(self.cold_execution_times) if self.cold_execution_times else 0

    @property
    def mean_memory_cold(self) -> float:
        return statistics.mean(self.cold_memory_usages) if self.cold_memory_usages else 0


@dataclass
class BenchmarkSuiteResult:
    """Results from a complete benchmark suite."""
    suite_name: str
    timestamp: str
    results: Dict[str, List[BenchmarkResult]] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)


class BenchmarkRunner:
    """
    Runner for executing benchmark methods with proper isolation.
    """

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.client = None
        self.temp_dirs: List[Path] = []
        # HTTP request instrumentation
        self._original_request = None
        self._current_request_count = 0
        self.request_count_total = 0
        # Memory sampling helpers
        self._mem_sampler_thread = None
        self._mem_sampler_stop = None
        # optional pytest-benchmark fixture (default to a dummy no-op fixture)
        self.benchmark_fixture = _DummyBenchmarkFixture()

    def _create_client(self) -> Any:
        """Create client instance with proper cache isolation."""
        if self.client:
            self._cleanup_client()

        # Create isolated cache directory if needed
        if self.config.cache_config and self.config.cache_config.enabled:
            if self.config.cache_dir is None:
                temp_dir = Path(tempfile.mkdtemp(prefix=f"{self.config.name}_cache_"))
                self.temp_dirs.append(temp_dir)
                self.config.cache_dir = temp_dir

        # Instantiate client based on type
        if self.config.client_class == ArticleClient:
            self.client = self.config.client_class(cache_config=self.config.cache_config)
        elif self.config.client_class == SearchClient:
            self.client = self.config.client_class(cache_config=self.config.cache_config)
        elif self.config.client_class == FullTextClient:
            file_cache_dir = None
            if self.config.cache_config and self.config.cache_config.enabled and self.config.cache_dir:
                file_cache_dir = self.config.cache_dir / "files"
                file_cache_dir.mkdir(parents=True, exist_ok=True)
            self.client = self.config.client_class(
                cache_config=self.config.cache_config,
                cache_dir=file_cache_dir,
                enable_cache=bool(file_cache_dir)
            )
        else:
            self.client = self.config.client_class()

        return self.client

    def _start_request_instrumentation(self):
        """Monkeypatch requests.Session.request to count outgoing HTTP requests."""
        # Only patch once
        if self._original_request is not None:
            return

        try:
            self._original_request = requests.Session.request

            def _wrapped_request(self_sess, method, url, *args, **kwargs):
                try:
                    self._current_request_count += 1
                    self.request_count_total += 1
                except Exception:
                    pass
                return self._original_request(self_sess, method, url, *args, **kwargs)

            requests.Session.request = _wrapped_request
        except Exception:
            # Best-effort instrumentation: if requests isn't used or patching fails, continue
            self._original_request = None

    def _stop_request_instrumentation(self):
        """Restore original requests.Session.request."""
        if self._original_request is not None:
            try:
                requests.Session.request = self._original_request
            except Exception:
                pass
            self._original_request = None

    def _cleanup_client(self):
        """Clean up client and temporary directories."""
        if self.client and hasattr(self.client, '_cache'):
            try:
                self.client._cache.clear_cache()
            except:
                pass

        for temp_dir in self.temp_dirs:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
        self.temp_dirs.clear()

    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)

    def _memory_sampler(self, stop_event: threading.Event, peak_holder: List[int]):
        """Background sampler that updates peak RSS in bytes while not stopped."""
        proc = psutil.Process(os.getpid())
        try:
            while not stop_event.is_set():
                try:
                    rss = proc.memory_info().rss
                    if rss > peak_holder[0]:
                        peak_holder[0] = rss
                except Exception:
                    pass
                # sample at 1ms intervals
                time.sleep(0.001)
        except Exception:
            return

    def _start_memory_sampler(self) -> Tuple[threading.Event, threading.Thread, List[int], int]:
        """Start memory sampler thread. Returns (stop_event, thread, peak_holder, baseline_rss)."""
        stop_event = threading.Event()
        peak_holder: List[int] = [0]
        # set baseline first
        try:
            baseline = psutil.Process(os.getpid()).memory_info().rss
            peak_holder[0] = baseline
        except Exception:
            baseline = 0

        t = threading.Thread(target=self._memory_sampler, args=(stop_event, peak_holder))
        t.daemon = True
        t.start()
        return stop_event, t, peak_holder, baseline

    def _stop_memory_sampler(self, stop_event: threading.Event, thread: threading.Thread):
        try:
            stop_event.set()
            thread.join(timeout=0.5)
        except Exception:
            pass

    def run_method_with_timing(self, method_name: str, *args, **kwargs) -> Tuple[Any, float, float, int, int]:
        """
        Run a method and return result, execution time, and memory usage.
        """
        if not self.client:
            self._create_client()
        method = getattr(self.client, method_name)

        # Measure RSS before the call
        try:
            proc = psutil.Process(os.getpid())
            start_rss = proc.memory_info().rss
        except Exception:
            start_rss = 0

        # Start tracemalloc (best-effort) to capture Python allocation peaks
        try:
            tracemalloc.start()
        except Exception:
            pass

        start_time = time.perf_counter()
        try:
            result = method(*args, **kwargs)
        except Exception as e:
            # on exception, grab tracemalloc info and re-raise
            try:
                current_tr, peak_tr = tracemalloc.get_traced_memory()
                tracemalloc_peak = peak_tr
            except Exception:
                tracemalloc_peak = 0
            try:
                tracemalloc.stop()
            except Exception:
                pass
            raise e

        end_time = time.perf_counter()

        # measure RSS after call
        try:
            end_rss = psutil.Process(os.getpid()).memory_info().rss
        except Exception:
            end_rss = start_rss

        rss_delta_bytes = max(0, end_rss - start_rss)
        memory_used = rss_delta_bytes / (1024 * 1024)

        # tracemalloc peak
        try:
            current_tr, peak_tr = tracemalloc.get_traced_memory()
            tracemalloc_peak = peak_tr
        except Exception:
            tracemalloc_peak = 0
        try:
            tracemalloc.stop()
        except Exception:
            pass

        execution_time = end_time - start_time

        return result, execution_time, memory_used, rss_delta_bytes, tracemalloc_peak

    def benchmark_method(self, method_name: str, method_args: Tuple = (), method_kwargs: Optional[Dict] = None) -> BenchmarkResult:
        """
        Benchmark a method with multiple iterations.
        """
        execution_times = []
        memory_usages = []
        cold_execution_times = []
        cold_memory_usages = []
        cache_stats_per_run: List[Dict[str, Any]] = []
        errors = []
        # Request counting collectors
        request_counts_per_run: List[int] = []
        cold_request_counts: List[int] = []
    # Memory peak collectors
        rss_peak_bytes_per_run: List[int] = []
        tracemalloc_peak_bytes_per_run: List[int] = []
        cold_rss_peak_bytes: List[int] = []
        cold_tracemalloc_peak_bytes: List[int] = []

        # Cold measured runs (measured before warmup) to capture cold-start behavior
        for c in range(getattr(self.config, "cold_runs", 0)):
            try:
                # Use a fresh client for each cold run to simulate cold start
                self._create_client()
                # Instrument per-run requests
                self._current_request_count = 0
                self._start_request_instrumentation()
                result, exec_time, mem_usage, rss_peak_bytes, tracemalloc_peak = self.run_method_with_timing(
                    method_name, *method_args, **(method_kwargs or {})
                )
                self._stop_request_instrumentation()
                cold_execution_times.append(exec_time)
                cold_memory_usages.append(mem_usage)
                cold_request_counts.append(self._current_request_count)
                cold_rss_peak_bytes.append(rss_peak_bytes)
                cold_tracemalloc_peak_bytes.append(tracemalloc_peak)
            except Exception as e:
                errors.append(f"Cold run {c + 1}: {str(e)}")

        # Warmup runs (unmeasured) to populate caches and stabilize behavior
        # If cache is enabled, reuse the same client across warmup+measured runs so the cache
        # populated during warmup is available during measured runs.
        reuse_client_for_measured = bool(self.config.cache_config and getattr(self.config.cache_config, 'enabled', False))

        if reuse_client_for_measured:
            # create one client to be reused for all warmup and measured runs
            self._create_client()

        for w in range(getattr(self.config, "warmup_iterations", 0)):
            try:
                if not reuse_client_for_measured:
                    # create fresh client for each warmup run to mimic real usage
                    self._create_client()
                # Run the method but ignore timing/memory
                method = getattr(self.client, method_name)
                # run warmup without instrumentation by default
                method(*method_args, **(method_kwargs or {}))
            except Exception:
                errors.append(f"Warmup {w + 1}: exception during warmup")
            finally:
                if not reuse_client_for_measured:
                    # clean up transient client used for this warmup
                    try:
                        self._cleanup_client()
                    except Exception:
                        pass

        # Measured runs
        if getattr(self, 'benchmark_fixture', None) is not None:
            # Use pytest-benchmark if provided for robust timing statistics.
            per_run_cache_stats: List[Dict[str, Any]] = []

            def _bench_wrapper():
                # Each invocation corresponds to one measured run
                if not reuse_client_for_measured:
                    self._create_client()

                self._current_request_count = 0
                self._start_request_instrumentation()

                # Use run_method_with_timing to gather memory and tracemalloc info as well
                result, exec_time, mem_usage, rss_peak_bytes, tracemalloc_peak = self.run_method_with_timing(
                    method_name, *method_args, **(method_kwargs or {})
                )

                self._stop_request_instrumentation()

                # record per-run measurements (timing will be provided by pytest-benchmark)
                execution_times.append(exec_time)
                memory_usages.append(mem_usage)
                request_counts_per_run.append(self._current_request_count)
                rss_peak_bytes_per_run.append(rss_peak_bytes)
                tracemalloc_peak_bytes_per_run.append(tracemalloc_peak)

                # per-run cache stats
                run_cache_stats: Dict[str, Any] = {}
                if self.client:
                    if hasattr(self.client, 'get_cache_stats'):
                        try:
                            run_cache_stats['api_cache'] = self.client.get_cache_stats()
                        except Exception:
                            run_cache_stats['api_cache'] = None
                    if hasattr(self.client, 'get_api_cache_stats'):
                        try:
                            run_cache_stats['api_cache'] = self.client.get_api_cache_stats()
                        except Exception:
                            run_cache_stats['api_cache'] = run_cache_stats.get('api_cache')
                    if hasattr(self.client, 'get_file_cache_health'):
                        try:
                            run_cache_stats['file_cache'] = self.client.get_file_cache_health()
                        except Exception:
                            run_cache_stats['file_cache'] = None

                cache_stats_per_run.append(run_cache_stats)

                if not reuse_client_for_measured:
                    try:
                        self._cleanup_client()
                    except Exception:
                        pass

                return result

            # Try to use the pedantic API which allows specifying rounds/iterations
            try:
                # iterations=1 so each round performs a single invocation; rounds == number of runs
                self.benchmark_fixture.pedantic(_bench_wrapper, iterations=1, rounds=self.config.iterations, warmup_rounds=0)
            except Exception:
                # Fallback: call the benchmark fixture once per desired measured run
                for _ in range(self.config.iterations):
                    try:
                        self.benchmark_fixture(_bench_wrapper)
                    except Exception:
                        # If benchmark fixture invocation fails, fallback to direct invocation
                        _bench_wrapper()
        else:
            # No pytest-benchmark fixture: fall back to manual measured loop
            for run in range(self.config.iterations):
                try:
                    if not reuse_client_for_measured:
                        # Create fresh client for each run to ensure isolation
                        self._create_client()

                    # Instrument requests per measured run
                    self._current_request_count = 0
                    self._start_request_instrumentation()

                    result, exec_time, mem_usage, rss_peak_bytes, tracemalloc_peak = self.run_method_with_timing(
                        method_name, *method_args, **(method_kwargs or {})
                    )

                    # Stop instrumentation and record count
                    self._stop_request_instrumentation()

                    execution_times.append(exec_time)
                    memory_usages.append(mem_usage)

                    # record the request count observed for this run
                    request_counts_per_run.append(self._current_request_count)
                    rss_peak_bytes_per_run.append(rss_peak_bytes)
                    tracemalloc_peak_bytes_per_run.append(tracemalloc_peak)

                    # Attempt to collect cache stats after the run, if the client exposes them
                    run_cache_stats: Dict[str, Any] = {}
                    if self.client:
                        if hasattr(self.client, 'get_cache_stats'):
                            try:
                                run_cache_stats['api_cache'] = self.client.get_cache_stats()
                            except Exception:
                                run_cache_stats['api_cache'] = None
                        if hasattr(self.client, 'get_api_cache_stats'):
                            try:
                                run_cache_stats['api_cache'] = self.client.get_api_cache_stats()
                            except Exception:
                                run_cache_stats['api_cache'] = run_cache_stats.get('api_cache')
                        if hasattr(self.client, 'get_file_cache_health'):
                            try:
                                run_cache_stats['file_cache'] = self.client.get_file_cache_health()
                            except Exception:
                                run_cache_stats['file_cache'] = None

                    cache_stats_per_run.append(run_cache_stats)
                except Exception as e:
                    errors.append(f"Run {run + 1}: {str(e)}")
                    # ensure instrumentation restored if exception happened
                    try:
                        self._stop_request_instrumentation()
                    except Exception:
                        pass
                    continue
                finally:
                    if not reuse_client_for_measured:
                        # cleanup per-run transient client
                        try:
                            self._cleanup_client()
                        except Exception:
                            pass

        # Aggregate final cache stats (best-effort)
        cache_stats = {}
        if self.client:
            if hasattr(self.client, 'get_cache_stats'):
                try:
                    cache_stats['api_cache'] = self.client.get_cache_stats()
                except Exception:
                    cache_stats['api_cache'] = None
            if hasattr(self.client, 'get_api_cache_stats'):
                try:
                    cache_stats['api_cache'] = self.client.get_api_cache_stats()
                except Exception:
                    cache_stats['api_cache'] = cache_stats.get('api_cache')
            if hasattr(self.client, 'get_file_cache_health'):
                try:
                    cache_stats['file_cache'] = self.client.get_file_cache_health()
                except Exception:
                    cache_stats['file_cache'] = None

        # If we reused a client for measured runs, clean it up now
        try:
            if reuse_client_for_measured:
                self._cleanup_client()
        except Exception:
            pass

        # Build total requests observed if per-run counts present
        total_requests_observed = sum(request_counts_per_run) + sum(cold_request_counts)

        return BenchmarkResult(
            method_name=method_name,
            client_name=self.config.name,
            cache_enabled=self.config.cache_config is not None and self.config.cache_config.enabled,
            execution_times=execution_times,
            memory_usages=memory_usages,
            cold_execution_times=cold_execution_times,
            cold_memory_usages=cold_memory_usages,
            cache_stats=cache_stats,
            cache_stats_per_run=cache_stats_per_run,
            errors=errors,
            request_counts_per_run=request_counts_per_run,
            cold_request_counts=cold_request_counts,
            total_requests=total_requests_observed
            ,
            rss_peak_bytes_per_run=rss_peak_bytes_per_run,
            tracemalloc_peak_bytes_per_run=tracemalloc_peak_bytes_per_run,
            cold_rss_peak_bytes=cold_rss_peak_bytes,
            cold_tracemalloc_peak_bytes=cold_tracemalloc_peak_bytes
        )

    def __del__(self):
        """Cleanup on destruction."""
        self._cleanup_client()


class BaseBenchmark(ABC):
    """
    Abstract base class for benchmarks.
    """

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.runner = BenchmarkRunner(config)

    @abstractmethod
    def get_test_params(self, method_name: str, iteration: int = 0) -> Tuple[Tuple, Dict]:
        """Get test parameters for a method."""
        pass

    @abstractmethod
    def run_benchmark(self) -> List[BenchmarkResult]:
        """Run the benchmark and return results."""
        pass

    def generate_report(self, results: List[BenchmarkResult]) -> str:
        """Generate a report from results."""
        report_lines: List[str] = []
        report_lines.append(f"# Benchmark Report: {self.config.name}\n")
        report_lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for result in results:
            report_lines.append(f"## {result.method_name}\n")
            if result.errors:
                report_lines.append(f"**Errors:** {len(result.errors)}\n")
                for error in result.errors:
                    report_lines.append(f"- {error}\n")
            else:
                report_lines.append(f"- **Mean Time:** {result.mean_time:.3f}s\n")
                report_lines.append(f"- **Std Dev:** {result.std_dev_time:.3f}s\n")
                report_lines.append(f"- **Mean Memory:** {result.mean_memory:.1f}MB\n")
                report_lines.append(f"- **Cache Enabled:** {result.cache_enabled}\n")

            if result.cache_stats:
                report_lines.append("**Cache Stats:**\n")
                for key, value in result.cache_stats.items():
                    report_lines.append(f"- {key}: {value}\n")
            report_lines.append("\n")

        return "".join(report_lines)

class ArticleClientBenchmark(BaseBenchmark):
    """Benchmark for ArticleClient methods."""

    def get_test_params(self, method_name: str, iteration: int = 0) -> Tuple[Tuple, Dict]:
        """Get test parameters for ArticleClient methods."""
        test_data = self.config.test_data

        if method_name in ["get_article_details", "get_citations", "get_references", "get_database_links"]:
            article_ids = test_data.get("article_ids", ["34308300", "34261881", "34183448"])
            article_id = article_ids[iteration % len(article_ids)]
            return (("MED", article_id), {})
        else:
            return ((), {})

    def run_benchmark(self) -> List[BenchmarkResult]:
        """Run benchmark for all configured methods."""
        results = []

        for method in self.config.methods:
            try:
                method_args, method_kwargs = self.get_test_params(method)
                result = self.runner.benchmark_method(method, method_args, method_kwargs)
                results.append(result)
            except Exception as e:
                # Create error result
                error_result = BenchmarkResult(
                    method_name=method,
                    client_name=self.config.name,
                    cache_enabled=self.config.cache_config is not None and self.config.cache_config.enabled,
                    execution_times=[],
                    memory_usages=[],
                    errors=[str(e)]
                )
                results.append(error_result)

        return results


class SearchClientBenchmark(BaseBenchmark):
    """Benchmark for SearchClient methods."""

    def get_test_params(self, method_name: str, iteration: int = 0) -> Tuple[Tuple, Dict]:
        """Get test parameters for SearchClient methods."""
        test_data = self.config.test_data

        if method_name in ["search", "get_hit_count", "search_ids_only"]:
            queries = test_data.get("search_queries", ["cancer", "diabetes", "neural network"])
            query = queries[iteration % len(queries)]
            return ((query,), {"limit": 10})
        else:
            return ((), {})

    def run_benchmark(self) -> List[BenchmarkResult]:
        """Run benchmark for all configured methods."""
        results = []

        for method in self.config.methods:
            try:
                method_args, method_kwargs = self.get_test_params(method)
                result = self.runner.benchmark_method(method, method_args, method_kwargs)
                results.append(result)
            except Exception as e:
                error_result = BenchmarkResult(
                    method_name=method,
                    client_name=self.config.name,
                    cache_enabled=self.config.cache_config is not None and self.config.cache_config.enabled,
                    execution_times=[],
                    memory_usages=[],
                    errors=[str(e)]
                )
                results.append(error_result)

        return results


class FullTextClientBenchmark(BaseBenchmark):
    """Benchmark for FullTextClient methods."""

    def get_test_params(self, method_name: str, iteration: int = 0) -> Tuple[Tuple, Dict]:
        """Get test parameters for FullTextClient methods."""
        test_data = self.config.test_data

        if method_name == "check_fulltext_availability":
            pmc_ids = test_data.get("pmc_ids", ["PMC12124214", "PMC3312970", "PMC3257301"])
            pmcid = pmc_ids[iteration % len(pmc_ids)]
            return ((pmcid,), {})
        else:
            return ((), {})

    def run_benchmark(self) -> List[BenchmarkResult]:
        """Run benchmark for all configured methods."""
        results = []

        for method in self.config.methods:
            try:
                method_args, method_kwargs = self.get_test_params(method)
                result = self.runner.benchmark_method(method, method_args, method_kwargs)
                results.append(result)
            except Exception as e:
                error_result = BenchmarkResult(
                    method_name=method,
                    client_name=self.config.name,
                    cache_enabled=self.config.cache_config is not None and self.config.cache_config.enabled,
                    execution_times=[],
                    memory_usages=[],
                    errors=[str(e)]
                )
                results.append(error_result)

        return results


class BenchmarkManager:
    """
    Manager for running multiple benchmarks and generating reports.
    """

    def __init__(self):
        self.benchmarks: List[BaseBenchmark] = []
        self.results: Dict[str, List[BenchmarkResult]] = {}

    def add_benchmark(self, benchmark: BaseBenchmark):
        """Add a benchmark to the manager."""
        self.benchmarks.append(benchmark)

    def run_all_benchmarks(self) -> BenchmarkSuiteResult:
        """Run all benchmarks and return comprehensive results."""
        suite_result = BenchmarkSuiteResult(
            suite_name="pyEuropePMC Benchmark Suite",
            timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
        )

        for benchmark in self.benchmarks:
            print(f"Running benchmark: {benchmark.config.name}")
            results = benchmark.run_benchmark()
            self.results[benchmark.config.name] = results
            suite_result.results[benchmark.config.name] = results

        # Generate summary
        suite_result.summary = self._generate_summary(suite_result.results)

        return suite_result

    def _generate_summary(self, results: Dict[str, List[BenchmarkResult]]) -> Dict[str, Any]:
        """Generate summary statistics."""
        summary = {
            "total_benchmarks": len(results),
            "total_methods": sum(len(method_results) for method_results in results.values()),
            "successful_runs": 0,
            "failed_runs": 0,
            "average_speedup": 0.0,
            "cache_enabled_count": 0
        }

        speedups = []

        for benchmark_name, method_results in results.items():
            for result in method_results:
                if result.errors:
                    summary["failed_runs"] += 1
                else:
                    summary["successful_runs"] += 1

                if result.cache_enabled:
                    summary["cache_enabled_count"] += 1

                # Calculate speedup if we have comparison data
                # This would need enhancement for actual speedup calculation

        if speedups:
            summary["average_speedup"] = statistics.mean(speedups)

        return summary

    def generate_comprehensive_report(self, suite_result: BenchmarkSuiteResult) -> str:
        """Generate a comprehensive, GitHub-friendly Markdown report from suite results.

        The report contains per-benchmark tables and a cache-vs-no-cache comparison
        where possible. It returns the full Markdown text.
        """
        # Header and summary
        report_lines = []
        report_lines.append(f"# 🚀 {suite_result.suite_name}\n")
        report_lines.append(f"**Generated:** {suite_result.timestamp}\n\n")
        report_lines.append("## 📊 Summary\n\n")
        report_lines.append(f"- **Total Benchmarks:** {suite_result.summary.get('total_benchmarks', 0)}\n")
        report_lines.append(f"- **Total Methods:** {suite_result.summary.get('total_methods', 0)}\n")
        report_lines.append(f"- **Successful Runs:** {suite_result.summary.get('successful_runs', 0)}\n")
        report_lines.append(f"- **Failed Runs:** {suite_result.summary.get('failed_runs', 0)}\n")
        report_lines.append(f"- **Cache Enabled:** {suite_result.summary.get('cache_enabled_count', 0)}\n\n")

        # Per-benchmark tables
        for benchmark_name, results in suite_result.results.items():
            report_lines.append(f"## {benchmark_name}\n\n")
            report_lines.append("| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |\n")
            report_lines.append("|---|---:|---:|---:|:--:|---:|---:|\n")

            def fmt_mean_time(val: Optional[float]) -> str:
                if val is None:
                    return "-"
                if val < 1e-3:
                    return "<1ms"
                return f"{val:.3f}s"

            for result in results:
                mean_time = fmt_mean_time(result.mean_time) if result.execution_times else "-"
                std_dev = fmt_mean_time(result.std_dev_time) if len(result.execution_times) > 1 else "-"
                mean_mem = f"{result.mean_memory:.1f}MB" if result.memory_usages else "-"
                cache_icon = "✅" if result.cache_enabled else "❌"
                errors = len(result.errors) if result.errors else 0
                requests_count = result.total_requests if getattr(result, 'total_requests', None) is not None else '-'

                report_lines.append(
                    f"| {result.method_name} | {mean_time} | {std_dev} | {mean_mem} | {cache_icon} | {requests_count} | {errors} |\n"
                )

                # Add compact pytest-style aggregates under the row for easy inspection
                if result.execution_times:
                    times = sorted(result.execution_times)
                    cnt = len(times)
                    p50 = statistics.median(times)
                    # simple percentile: pick nearest value
                    p95 = times[min(cnt - 1, int(0.95 * cnt))]
                    mean = result.mean_time
                    stddev = result.std_dev_time
                    ops = (1.0 / mean) if mean and mean > 0 else None

                    def fmt_stat(val: Optional[float]) -> str:
                        if val is None:
                            return "-"
                        if val < 1e-3:
                            return f"{int(val * 1e6)}µs"
                        return f"{val:.3f}s"

                    ops_s = f"{ops:.2f}/s" if ops is not None else "-"
                    report_lines.append(f"<sub>p50: {fmt_stat(p50)} · p95: {fmt_stat(p95)} · ops: {ops_s} · runs: {cnt}</sub>\n")

            report_lines.append("\n")

        # Cache comparison summary: attempt to pair Cached vs NoCache per client base
        report_lines.append("## 🔁 Cache vs No-Cache Comparison\n\n")
        lookup = {name: {r.method_name: r for r in results} for name, results in suite_result.results.items()}

        bases = set()
        for name in suite_result.results.keys():
            if name.endswith("_Cached") or name.endswith("_NoCache"):
                bases.add(name.rsplit("_", 1)[0])

        for base in sorted(bases):
            cached_name = f"{base}_Cached"
            nocache_name = f"{base}_NoCache"
            if cached_name in lookup and nocache_name in lookup:
                report_lines.append(f"### {base} — cached vs no-cache\n\n")
                report_lines.append("| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |\n")
                report_lines.append("|---|---:|---:|---:|\n")

                paired_speedups: List[float] = []

                nocache_results = lookup[nocache_name]
                cached_results = lookup[cached_name]

                methods = sorted(set(list(nocache_results.keys()) + list(cached_results.keys())))

                eps = 1e-4  # 0.1 ms floor for display and speedup handling

                for method in methods:
                    no_r = nocache_results.get(method)
                    ca_r = cached_results.get(method)
                    no_mean = no_r.mean_time if no_r and no_r.execution_times else None
                    ca_mean = ca_r.mean_time if ca_r and ca_r.execution_times else None

                    def fmt_mean(val: Optional[float]) -> str:
                        if val is None:
                            return "-"
                        if val < 1e-3:
                            return "<1ms"
                        return f"{val:.3f}s"

                    no_s = fmt_mean(no_mean)
                    ca_s = fmt_mean(ca_mean)

                    speedup_s = "-"
                    if (no_mean is not None) and (ca_mean is not None):
                        if ca_mean < eps:
                            bound = no_mean / eps if no_mean is not None else None
                            speedup_s = f">{bound:.1f}x" if bound is not None else ">-"
                        else:
                            speed = no_mean / ca_mean if ca_mean > 0 else None
                            if speed is not None:
                                paired_speedups.append(speed)
                                speedup_s = f"{speed:.2f}x"

                    report_lines.append(f"| {method} | {no_s} | {ca_s} | {speedup_s} |\n")

                if paired_speedups:
                    avg_speed = statistics.mean(paired_speedups)
                    report_lines.append(f"\n- **Average speedup for {base} (no-cache / cached):** {avg_speed:.2f}x\n\n")
                else:
                    report_lines.append("\n")

        report_lines.append("---\n")
        report_lines.append("_Notes: Means are computed over measured iterations; '-' indicates missing data. Values like '<1ms' indicate very fast cached responses. Speedups shown as lower-bounds when cached times are too small to measure precisely._\n\n")

        # Add a short "how to run" and pointer to the raw JSON results for GitHub consumers
        report_lines.append("## ⚙️ How to reproduce\n\n")
        report_lines.append("Run the modular benchmark locally and regenerate these artifacts:\n\n")
        report_lines.append("```bash\n")
        report_lines.append("pytest -q tests/benchmark_article_client.py::test_modular_benchmark_system -q\n")
        report_lines.append("```\n\n")
        report_lines.append("- Detailed JSON results: `MODULAR_BENCHMARK_RESULTS.json`\n")

        return "".join(report_lines)

# Default test data
DEFAULT_TEST_DATA = {
    "search_queries": [
        "cancer", "diabetes", "neural network", "machine learning",
        "genetic", "CRISPR", "protein", "RNA", "DNA", "gene",
        "mutation", "therapy", "clinical trial", "drug"
    ],
    "article_ids": [
        "34308300", "34261881", "34183448", "34081923", "33987245",
        "33876412", "33789123", "33694567", "33578901", "33467890",
        "33356789", "33245678", "33134567", "33023456", "32912345"
    ],
    "pmc_ids": [
        "PMC12124214", "PMC3312970", "PMC3257301", "PMC2989456",
        "PMC2876543", "PMC2765432", "PMC2654321", "PMC2543210",
        "PMC2432109", "PMC2321098", "PMC2210987", "PMC2109876",
        "PMC2098765", "PMC1987654", "PMC1876543"
    ]
}


# Test functions using the modular system
@pytest.mark.slow
def test_modular_benchmark_system(benchmark):
    """Test the modular benchmark system."""
    manager = BenchmarkManager()

    # Create benchmark configurations
    configs = [
        BenchmarkConfig(
            client_class=ArticleClient,
            cache_config=None,
            methods=["get_article_details", "get_citations"],
            name="ArticleClient_NoCache",
            test_data=DEFAULT_TEST_DATA
        ),
        BenchmarkConfig(
            client_class=ArticleClient,
            cache_config=CacheConfig(enabled=True, size_limit_mb=100, ttl=3600),
            methods=["get_article_details", "get_citations"],
            name="ArticleClient_Cached",
            test_data=DEFAULT_TEST_DATA
        ),
        BenchmarkConfig(
            client_class=SearchClient,
            cache_config=None,
            methods=["search", "get_hit_count"],
            name="SearchClient_NoCache",
            test_data=DEFAULT_TEST_DATA
        ),
        BenchmarkConfig(
            client_class=SearchClient,
            cache_config=CacheConfig(enabled=True, size_limit_mb=100, ttl=3600),
            methods=["search", "get_hit_count"],
            name="SearchClient_Cached",
            test_data=DEFAULT_TEST_DATA
        ),
        BenchmarkConfig(
            client_class=FullTextClient,
            cache_config=None,
            methods=["check_fulltext_availability"],
            name="FullTextClient_NoCache",
            test_data=DEFAULT_TEST_DATA
        ),
        BenchmarkConfig(
            client_class=FullTextClient,
            cache_config=CacheConfig(enabled=True, size_limit_mb=100, ttl=3600),
            methods=["check_fulltext_availability"],
            name="FullTextClient_Cached",
            test_data=DEFAULT_TEST_DATA
        )
    ]

    # Create and add benchmarks
    for config in configs:
        if config.client_class == ArticleClient:
            bench_inst = ArticleClientBenchmark(config)
        elif config.client_class == SearchClient:
            bench_inst = SearchClientBenchmark(config)
        elif config.client_class == FullTextClient:
            bench_inst = FullTextClientBenchmark(config)
        else:
            continue

        # attach pytest-benchmark fixture to runner so measured runs can use it
        try:
            bench_inst.runner.benchmark_fixture = benchmark
        except Exception:
            pass

        manager.add_benchmark(bench_inst)

    # Run all benchmarks
    suite_result = manager.run_all_benchmarks()

    # Generate and save report
    report = manager.generate_comprehensive_report(suite_result)
    print("\n" + "="*80)
    print("MODULAR BENCHMARK REPORT")
    print("="*80)
    print(report)

    # Save detailed results
    with open("/home/jhe24/AID-PAIS/pyEuropePMC_project/MODULAR_BENCHMARK_RESULTS.json", "w") as f:
        # Build a serializable results structure and include pytest-like aggregates
        serializable_results = {}
        for name, results in suite_result.results.items():
            serializable_results[name] = []
            for r in results:
                entry = {
                    "method_name": r.method_name,
                    "client_name": r.client_name,
                    "cache_enabled": r.cache_enabled,
                    "execution_times": r.execution_times,
                    "memory_usages": r.memory_usages,
                    "cache_stats": r.cache_stats,
                    "errors": r.errors,
                    "request_counts_per_run": getattr(r, 'request_counts_per_run', []),
                    "cold_request_counts": getattr(r, 'cold_request_counts', []),
                    "total_requests": getattr(r, 'total_requests', 0),
                    "rss_peak_bytes_per_run": getattr(r, 'rss_peak_bytes_per_run', []),
                    "tracemalloc_peak_bytes_per_run": getattr(r, 'tracemalloc_peak_bytes_per_run', [])
                }

                # Add pytest-benchmark style aggregates if we have times
                if r.execution_times:
                    times = sorted(r.execution_times)
                    cnt = len(times)
                    p50 = statistics.median(times)
                    p95 = times[min(cnt - 1, int(0.95 * cnt))]
                    mean = r.mean_time
                    stddev = r.std_dev_time
                    ops = (1.0 / mean) if mean and mean > 0 else None

                    entry["aggregates"] = {
                        "count": cnt,
                        "min": times[0],
                        "max": times[-1],
                        "mean": mean,
                        "stddev": stddev,
                        "p50": p50,
                        "p95": p95,
                        "ops": ops
                    }

                serializable_results[name].append(entry)

        json.dump({
            "suite_name": suite_result.suite_name,
            "timestamp": suite_result.timestamp,
            "results": serializable_results,
            "summary": suite_result.summary
        }, f, indent=2, default=str)

    # Save report
    with open("/home/jhe24/AID-PAIS/pyEuropePMC_project/MODULAR_PERFORMANCE_REPORT.md", "w") as f:
        f.write(report)

    print("\n📊 Modular report saved to: MODULAR_PERFORMANCE_REPORT.md")
    print("📊 Detailed results saved to: MODULAR_BENCHMARK_RESULTS.json")


@pytest.mark.benchmark
def test_article_client_benchmark(benchmark):
    """Benchmark ArticleClient using the modular system."""
    config = BenchmarkConfig(
        client_class=ArticleClient,
        cache_config=CacheConfig(enabled=True, size_limit_mb=100, ttl=3600),
        methods=["get_article_details"],
        name="ArticleClient_Benchmark",
        test_data=DEFAULT_TEST_DATA
    )

    benchmark_instance = ArticleClientBenchmark(config)
    # attach pytest-benchmark fixture to the runner so measured runs inside
    # the benchmark harness will use the real pytest fixture instead of the
    # dummy fallback.
    try:
        benchmark_instance.runner.benchmark_fixture = benchmark
    except Exception:
        pass

    def run_benchmark():
        results = benchmark_instance.run_benchmark()
        return results

    benchmark(run_benchmark)


@pytest.mark.benchmark
def test_search_client_benchmark(benchmark):
    """Benchmark SearchClient using the modular system."""
    config = BenchmarkConfig(
        client_class=SearchClient,
        cache_config=CacheConfig(enabled=True, size_limit_mb=100, ttl=3600),
        methods=["search"],
        name="SearchClient_Benchmark",
        test_data=DEFAULT_TEST_DATA
    )

    benchmark_instance = SearchClientBenchmark(config)
    # attach pytest-benchmark fixture to the runner so measured runs inside
    # the benchmark harness will use the real pytest fixture instead of the
    # dummy fallback.
    try:
        benchmark_instance.runner.benchmark_fixture = benchmark
    except Exception:
        pass

    def run_benchmark():
        results = benchmark_instance.run_benchmark()
        return results

    benchmark(run_benchmark)


@pytest.mark.benchmark
def test_fulltext_client_benchmark(benchmark):
    """Benchmark FullTextClient using the modular system."""
    config = BenchmarkConfig(
        client_class=FullTextClient,
        cache_config=CacheConfig(enabled=True, size_limit_mb=100, ttl=3600),
        methods=["check_fulltext_availability"],
        name="FullTextClient_Benchmark",
        test_data=DEFAULT_TEST_DATA
    )

    benchmark_instance = FullTextClientBenchmark(config)
    # attach pytest-benchmark fixture to the runner so measured runs inside
    # the benchmark harness will use the real pytest fixture instead of the
    # dummy fallback.
    try:
        benchmark_instance.runner.benchmark_fixture = benchmark
    except Exception:
        pass

    def run_benchmark():
        results = benchmark_instance.run_benchmark()
        return results

    benchmark(run_benchmark)
