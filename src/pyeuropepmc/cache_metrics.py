"""
Comprehensive cache metrics and telemetry for PyEuropePMC.

This module provides detailed performance monitoring including:
- Latency percentiles (P50, P95, P99)
- Hit rate tracking per layer
- Size and eviction metrics
- Time-windowed statistics
"""

import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LatencyStats:
    """
    Latency statistics with percentiles.
    
    Attributes:
        samples: Recent latency samples (in milliseconds)
        max_samples: Maximum number of samples to retain
    """
    
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    max_samples: int = 1000
    
    def add_sample(self, latency_ms: float) -> None:
        """
        Add a latency sample.
        
        Args:
            latency_ms: Latency in milliseconds
        """
        self.samples.append(latency_ms)
    
    def get_percentile(self, percentile: int) -> float:
        """
        Calculate latency percentile.
        
        Args:
            percentile: Percentile (0-100)
            
        Returns:
            Latency at percentile in milliseconds
        """
        if not self.samples:
            return 0.0
        
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * percentile / 100)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    def get_mean(self) -> float:
        """
        Get mean latency.
        
        Returns:
            Mean latency in milliseconds
        """
        if not self.samples:
            return 0.0
        return statistics.mean(self.samples)
    
    def get_median(self) -> float:
        """
        Get median latency.
        
        Returns:
            Median latency in milliseconds
        """
        if not self.samples:
            return 0.0
        return statistics.median(self.samples)
    
    def get_stddev(self) -> float:
        """
        Get standard deviation of latency.
        
        Returns:
            Standard deviation in milliseconds
        """
        if len(self.samples) < 2:
            return 0.0
        return statistics.stdev(self.samples)
    
    def get_stats(self) -> dict[str, float]:
        """
        Get comprehensive latency statistics.
        
        Returns:
            Dictionary with latency metrics
        """
        if not self.samples:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "mean": 0.0,
                "median": 0.0,
                "stddev": 0.0,
                "min": 0.0,
                "max": 0.0,
                "sample_count": 0,
            }
        
        return {
            "p50": self.get_percentile(50),
            "p95": self.get_percentile(95),
            "p99": self.get_percentile(99),
            "mean": self.get_mean(),
            "median": self.get_median(),
            "stddev": self.get_stddev(),
            "min": min(self.samples),
            "max": max(self.samples),
            "sample_count": len(self.samples),
        }


@dataclass
class LayerMetrics:
    """
    Metrics for a single cache layer.
    
    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        sets: Number of set operations
        deletes: Number of delete operations
        errors: Number of errors
        evictions: Number of evictions
        latency: Latency statistics
    """
    
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    evictions: int = 0
    latency: LatencyStats = field(default_factory=LatencyStats)
    
    def get_hit_rate(self) -> float:
        """
        Calculate hit rate.
        
        Returns:
            Hit rate as fraction (0.0-1.0)
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def get_miss_rate(self) -> float:
        """
        Calculate miss rate.
        
        Returns:
            Miss rate as fraction (0.0-1.0)
        """
        return 1.0 - self.get_hit_rate()
    
    def get_error_rate(self) -> float:
        """
        Calculate error rate.
        
        Returns:
            Error rate as fraction (0.0-1.0)
        """
        total = self.hits + self.misses + self.sets + self.deletes
        if total == 0:
            return 0.0
        return self.errors / total
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Metrics as dictionary
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "evictions": self.evictions,
            "hit_rate": self.get_hit_rate(),
            "miss_rate": self.get_miss_rate(),
            "error_rate": self.get_error_rate(),
            "latency": self.latency.get_stats(),
        }


class CacheMetrics:
    """
    Comprehensive cache metrics collector.
    
    Tracks metrics for L1 and L2 layers, plus overall statistics.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.l1_metrics = LayerMetrics()
        self.l2_metrics = LayerMetrics()
        self._lock = Lock()
        self._start_time = time.time()
    
    def record_l1_hit(self, latency_ms: float = 0.0) -> None:
        """Record L1 cache hit."""
        with self._lock:
            self.l1_metrics.hits += 1
            if latency_ms > 0:
                self.l1_metrics.latency.add_sample(latency_ms)
    
    def record_l1_miss(self, latency_ms: float = 0.0) -> None:
        """Record L1 cache miss."""
        with self._lock:
            self.l1_metrics.misses += 1
            if latency_ms > 0:
                self.l1_metrics.latency.add_sample(latency_ms)
    
    def record_l1_set(self, latency_ms: float = 0.0) -> None:
        """Record L1 set operation."""
        with self._lock:
            self.l1_metrics.sets += 1
            if latency_ms > 0:
                self.l1_metrics.latency.add_sample(latency_ms)
    
    def record_l1_delete(self, latency_ms: float = 0.0) -> None:
        """Record L1 delete operation."""
        with self._lock:
            self.l1_metrics.deletes += 1
            if latency_ms > 0:
                self.l1_metrics.latency.add_sample(latency_ms)
    
    def record_l1_error(self) -> None:
        """Record L1 error."""
        with self._lock:
            self.l1_metrics.errors += 1
    
    def record_l1_eviction(self) -> None:
        """Record L1 eviction."""
        with self._lock:
            self.l1_metrics.evictions += 1
    
    def record_l2_hit(self, latency_ms: float = 0.0) -> None:
        """Record L2 cache hit."""
        with self._lock:
            self.l2_metrics.hits += 1
            if latency_ms > 0:
                self.l2_metrics.latency.add_sample(latency_ms)
    
    def record_l2_miss(self, latency_ms: float = 0.0) -> None:
        """Record L2 cache miss."""
        with self._lock:
            self.l2_metrics.misses += 1
            if latency_ms > 0:
                self.l2_metrics.latency.add_sample(latency_ms)
    
    def record_l2_set(self, latency_ms: float = 0.0) -> None:
        """Record L2 set operation."""
        with self._lock:
            self.l2_metrics.sets += 1
            if latency_ms > 0:
                self.l2_metrics.latency.add_sample(latency_ms)
    
    def record_l2_delete(self, latency_ms: float = 0.0) -> None:
        """Record L2 delete operation."""
        with self._lock:
            self.l2_metrics.deletes += 1
            if latency_ms > 0:
                self.l2_metrics.latency.add_sample(latency_ms)
    
    def record_l2_error(self) -> None:
        """Record L2 error."""
        with self._lock:
            self.l2_metrics.errors += 1
    
    def record_l2_eviction(self) -> None:
        """Record L2 eviction."""
        with self._lock:
            self.l2_metrics.evictions += 1
    
    def get_overall_metrics(self) -> dict[str, Any]:
        """
        Get overall cache metrics across all layers.
        
        Returns:
            Combined metrics dictionary
        """
        with self._lock:
            total_hits = self.l1_metrics.hits + self.l2_metrics.hits
            total_misses = self.l1_metrics.misses + self.l2_metrics.misses
            total_sets = self.l1_metrics.sets + self.l2_metrics.sets
            total_deletes = self.l1_metrics.deletes + self.l2_metrics.deletes
            total_errors = self.l1_metrics.errors + self.l2_metrics.errors
            
            total_requests = total_hits + total_misses
            hit_rate = total_hits / total_requests if total_requests > 0 else 0.0
            
            # Combine latency samples
            all_samples = list(self.l1_metrics.latency.samples) + list(
                self.l2_metrics.latency.samples
            )
            
            if all_samples:
                avg_latency = statistics.mean(all_samples)
            else:
                avg_latency = 0.0
            
            return {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "total_sets": total_sets,
                "total_deletes": total_deletes,
                "total_errors": total_errors,
                "hit_rate": hit_rate,
                "miss_rate": 1.0 - hit_rate,
                "error_rate": (
                    total_errors / (total_requests + total_sets + total_deletes)
                    if (total_requests + total_sets + total_deletes) > 0
                    else 0.0
                ),
                "avg_latency_ms": avg_latency,
                "uptime_seconds": time.time() - self._start_time,
            }
    
    def get_metrics(self) -> dict[str, Any]:
        """
        Get comprehensive metrics for all layers.
        
        Returns:
            Dictionary with L1, L2, and overall metrics
        """
        with self._lock:
            return {
                "l1": self.l1_metrics.to_dict(),
                "l2": self.l2_metrics.to_dict(),
                "overall": self.get_overall_metrics(),
                "timestamp": time.time(),
            }
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self.l1_metrics = LayerMetrics()
            self.l2_metrics = LayerMetrics()
            self._start_time = time.time()
    
    def get_summary(self) -> str:
        """
        Get human-readable metrics summary.
        
        Returns:
            Formatted metrics summary
        """
        metrics = self.get_metrics()
        
        l1 = metrics["l1"]
        l2 = metrics["l2"]
        overall = metrics["overall"]
        
        summary = [
            "Cache Metrics Summary",
            "=" * 50,
            f"Overall Hit Rate: {overall['hit_rate']:.2%}",
            f"Total Requests: {overall['total_hits'] + overall['total_misses']}",
            f"Average Latency: {overall['avg_latency_ms']:.2f}ms",
            "",
            "L1 (In-Memory):",
            f"  Hit Rate: {l1['hit_rate']:.2%}",
            f"  Hits/Misses: {l1['hits']}/{l1['misses']}",
            f"  P50 Latency: {l1['latency']['p50']:.2f}ms",
            f"  P99 Latency: {l1['latency']['p99']:.2f}ms",
            "",
            "L2 (Persistent):",
            f"  Hit Rate: {l2['hit_rate']:.2%}",
            f"  Hits/Misses: {l2['hits']}/{l2['misses']}",
            f"  P50 Latency: {l2['latency']['p50']:.2f}ms",
            f"  P99 Latency: {l2['latency']['p99']:.2f}ms",
        ]
        
        return "\n".join(summary)


class MetricsTimer:
    """
    Context manager for timing cache operations.
    
    Usage:
        with MetricsTimer(metrics.record_l1_hit):
            value = cache.get(key)
    """
    
    def __init__(self, record_func):
        """
        Initialize timer.
        
        Args:
            record_func: Function to call with latency_ms parameter
        """
        self.record_func = record_func
        self.start_time = None
    
    def __enter__(self):
        """Start timer."""
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timer and record latency."""
        if self.start_time:
            latency_ms = (time.perf_counter() - self.start_time) * 1000
            self.record_func(latency_ms=latency_ms)
        return False
