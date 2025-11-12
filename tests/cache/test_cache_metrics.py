"""Tests for cache_metrics module."""

import time

import pytest

from pyeuropepmc.cache_metrics import (
    CacheMetrics,
    LatencyStats,
    MetricsTimer,
)


class TestLatencyStats:
    """Tests for LatencyStats."""
    
    def test_init(self):
        """Test initialization."""
        stats = LatencyStats()
        
        assert len(stats.samples) == 0
        assert stats.max_samples == 1000
    
    def test_add_sample(self):
        """Test adding samples."""
        stats = LatencyStats()
        
        stats.add_sample(10.5)
        stats.add_sample(15.2)
        stats.add_sample(8.9)
        
        assert len(stats.samples) == 3
        assert 10.5 in stats.samples
    
    def test_max_samples_limit(self):
        """Test max samples limit."""
        stats = LatencyStats(max_samples=10)
        
        # Add more than max
        for i in range(20):
            stats.add_sample(float(i))
        
        # Should only keep last 10
        assert len(stats.samples) == 10
        assert list(stats.samples) == [float(i) for i in range(10, 20)]
    
    def test_get_percentile(self):
        """Test percentile calculation."""
        stats = LatencyStats()
        
        # Add samples: 1, 2, 3, ..., 100
        for i in range(1, 101):
            stats.add_sample(float(i))
        
        # Test percentiles
        assert stats.get_percentile(50) == 50.0  # Median
        assert stats.get_percentile(95) == 95.0  # 95th percentile
        assert stats.get_percentile(99) == 99.0  # 99th percentile
    
    def test_get_percentile_empty(self):
        """Test percentile with no samples."""
        stats = LatencyStats()
        
        assert stats.get_percentile(50) == 0.0
    
    def test_get_mean(self):
        """Test mean calculation."""
        stats = LatencyStats()
        
        stats.add_sample(10.0)
        stats.add_sample(20.0)
        stats.add_sample(30.0)
        
        assert stats.get_mean() == 20.0
    
    def test_get_median(self):
        """Test median calculation."""
        stats = LatencyStats()
        
        stats.add_sample(10.0)
        stats.add_sample(20.0)
        stats.add_sample(30.0)
        
        assert stats.get_median() == 20.0
    
    def test_get_stddev(self):
        """Test standard deviation."""
        stats = LatencyStats()
        
        stats.add_sample(10.0)
        stats.add_sample(20.0)
        stats.add_sample(30.0)
        
        stddev = stats.get_stddev()
        assert stddev > 0
        assert 9 < stddev < 11  # Roughly 10
    
    def test_get_stats(self):
        """Test comprehensive statistics."""
        stats = LatencyStats()
        
        for i in range(1, 101):
            stats.add_sample(float(i))
        
        result = stats.get_stats()
        
        assert result["p50"] == 50.0
        assert result["p95"] == 95.0
        assert result["p99"] == 99.0
        assert result["mean"] == 50.5
        assert result["median"] == 50.5
        assert result["min"] == 1.0
        assert result["max"] == 100.0
        assert result["sample_count"] == 100
    
    def test_get_stats_empty(self):
        """Test stats with no samples."""
        stats = LatencyStats()
        
        result = stats.get_stats()
        
        assert result["p50"] == 0.0
        assert result["mean"] == 0.0
        assert result["sample_count"] == 0


class TestCacheMetrics:
    """Tests for CacheMetrics."""
    
    def test_init(self):
        """Test initialization."""
        metrics = CacheMetrics()
        
        assert metrics.l1_metrics.hits == 0
        assert metrics.l2_metrics.hits == 0
    
    def test_record_l1_hit(self):
        """Test recording L1 hit."""
        metrics = CacheMetrics()
        
        metrics.record_l1_hit(latency_ms=1.5)
        
        assert metrics.l1_metrics.hits == 1
        assert len(metrics.l1_metrics.latency.samples) == 1
    
    def test_record_l1_miss(self):
        """Test recording L1 miss."""
        metrics = CacheMetrics()
        
        metrics.record_l1_miss(latency_ms=0.5)
        
        assert metrics.l1_metrics.misses == 1
    
    def test_record_l2_hit(self):
        """Test recording L2 hit."""
        metrics = CacheMetrics()
        
        metrics.record_l2_hit(latency_ms=10.0)
        
        assert metrics.l2_metrics.hits == 1
        assert len(metrics.l2_metrics.latency.samples) == 1
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        metrics = CacheMetrics()
        
        # Record 7 hits and 3 misses
        for _ in range(7):
            metrics.record_l1_hit()
        for _ in range(3):
            metrics.record_l1_miss()
        
        overall = metrics.get_overall_metrics()
        
        assert overall["total_hits"] == 7
        assert overall["total_misses"] == 3
        assert overall["hit_rate"] == 0.7  # 70%
        assert overall["miss_rate"] == 0.3  # 30%
    
    def test_record_operations(self):
        """Test recording various operations."""
        metrics = CacheMetrics()
        
        metrics.record_l1_set(latency_ms=0.5)
        metrics.record_l1_delete(latency_ms=0.3)
        metrics.record_l1_error()
        metrics.record_l1_eviction()
        
        assert metrics.l1_metrics.sets == 1
        assert metrics.l1_metrics.deletes == 1
        assert metrics.l1_metrics.errors == 1
        assert metrics.l1_metrics.evictions == 1
    
    def test_get_metrics(self):
        """Test getting comprehensive metrics."""
        metrics = CacheMetrics()
        
        # Record some activity
        metrics.record_l1_hit(latency_ms=1.0)
        metrics.record_l1_miss(latency_ms=0.5)
        metrics.record_l2_hit(latency_ms=10.0)
        
        result = metrics.get_metrics()
        
        assert "l1" in result
        assert "l2" in result
        assert "overall" in result
        assert "timestamp" in result
        
        assert result["l1"]["hits"] == 1
        assert result["l2"]["hits"] == 1
        assert result["overall"]["total_hits"] == 2
    
    def test_reset(self):
        """Test resetting metrics."""
        metrics = CacheMetrics()
        
        # Record activity
        metrics.record_l1_hit()
        metrics.record_l2_hit()
        
        assert metrics.l1_metrics.hits == 1
        
        # Reset
        metrics.reset()
        
        assert metrics.l1_metrics.hits == 0
        assert metrics.l2_metrics.hits == 0
    
    def test_get_summary(self):
        """Test getting human-readable summary."""
        metrics = CacheMetrics()
        
        # Record some activity
        for _ in range(80):
            metrics.record_l1_hit(latency_ms=1.0)
        for _ in range(20):
            metrics.record_l1_miss(latency_ms=0.5)
        
        summary = metrics.get_summary()
        
        assert "Cache Metrics Summary" in summary
        assert "Overall Hit Rate" in summary
        assert "80%" in summary
        assert "L1 (In-Memory)" in summary
    
    def test_thread_safety(self):
        """Test thread safety of metrics recording."""
        import threading
        
        metrics = CacheMetrics()
        
        def record_hits():
            for _ in range(100):
                metrics.record_l1_hit()
        
        # Create multiple threads
        threads = [threading.Thread(target=record_hits) for _ in range(10)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should have 1000 hits total (100 * 10 threads)
        assert metrics.l1_metrics.hits == 1000


class TestMetricsTimer:
    """Tests for MetricsTimer."""
    
    def test_timer_basic(self):
        """Test basic timer usage."""
        call_count = [0]
        recorded_latency = [None]
        
        def record_func(latency_ms):
            call_count[0] += 1
            recorded_latency[0] = latency_ms
        
        with MetricsTimer(record_func):
            time.sleep(0.01)  # Sleep 10ms
        
        assert call_count[0] == 1
        assert recorded_latency[0] is not None
        assert recorded_latency[0] >= 10.0  # At least 10ms
    
    def test_timer_with_exception(self):
        """Test timer with exception."""
        call_count = [0]
        
        def record_func(latency_ms):
            call_count[0] += 1
        
        try:
            with MetricsTimer(record_func):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Should still record latency despite exception
        assert call_count[0] == 1
    
    def test_timer_zero_time(self):
        """Test timer with near-zero execution time."""
        recorded_latency = [None]
        
        def record_func(latency_ms):
            recorded_latency[0] = latency_ms
        
        with MetricsTimer(record_func):
            pass  # No sleep
        
        assert recorded_latency[0] is not None
        assert recorded_latency[0] >= 0  # Non-negative
