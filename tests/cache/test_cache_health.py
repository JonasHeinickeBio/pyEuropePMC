"""Tests for cache_health module."""

import pytest

from pyeuropepmc.cache_health import (
    CacheHealthMonitor,
    HealthIssue,
    HealthReport,
    HealthStatus,
    HealthThresholds,
    create_default_alert_logger,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""
    
    def test_values(self):
        """Test enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.WARNING.value == "warning"
        assert HealthStatus.CRITICAL.value == "critical"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestHealthThresholds:
    """Tests for HealthThresholds."""
    
    def test_default_values(self):
        """Test default threshold values."""
        thresholds = HealthThresholds()
        
        assert thresholds.min_hit_rate == 0.70
        assert thresholds.max_error_rate == 0.05
        assert thresholds.max_l1_latency_p99 == 5.0
        assert thresholds.max_l2_latency_p99 == 50.0
        assert thresholds.max_l2_disk_usage == 0.90
        assert thresholds.min_l2_hit_rate == 0.30
    
    def test_custom_values(self):
        """Test custom threshold values."""
        thresholds = HealthThresholds(
            min_hit_rate=0.80,
            max_error_rate=0.01,
        )
        
        assert thresholds.min_hit_rate == 0.80
        assert thresholds.max_error_rate == 0.01


class TestHealthIssue:
    """Tests for HealthIssue."""
    
    def test_init(self):
        """Test initialization."""
        issue = HealthIssue(
            severity=HealthStatus.WARNING,
            component="l1",
            metric="hit_rate",
            message="Hit rate low",
            value=0.65,
            threshold=0.70,
        )
        
        assert issue.severity == HealthStatus.WARNING
        assert issue.component == "l1"
        assert issue.metric == "hit_rate"
        assert issue.value == 0.65
        assert issue.threshold == 0.70
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        issue = HealthIssue(
            severity=HealthStatus.CRITICAL,
            component="l2",
            metric="disk_usage",
            message="Disk full",
            value=0.95,
            threshold=0.90,
        )
        
        data = issue.to_dict()
        
        assert data["severity"] == "critical"
        assert data["component"] == "l2"
        assert data["metric"] == "disk_usage"
        assert data["value"] == 0.95


class TestHealthReport:
    """Tests for HealthReport."""
    
    def test_init(self):
        """Test initialization."""
        report = HealthReport(status=HealthStatus.HEALTHY)
        
        assert report.status == HealthStatus.HEALTHY
        assert report.issues == []
    
    def test_is_healthy(self):
        """Test is_healthy check."""
        report = HealthReport(status=HealthStatus.HEALTHY)
        assert report.is_healthy()
        
        report_warning = HealthReport(status=HealthStatus.WARNING)
        assert not report_warning.is_healthy()
    
    def test_has_warnings(self):
        """Test has_warnings check."""
        issue = HealthIssue(
            severity=HealthStatus.WARNING,
            component="test",
            metric="test",
            message="test",
            value=0,
            threshold=1,
        )
        
        report = HealthReport(status=HealthStatus.WARNING, issues=[issue])
        assert report.has_warnings()
    
    def test_has_critical_issues(self):
        """Test has_critical_issues check."""
        issue = HealthIssue(
            severity=HealthStatus.CRITICAL,
            component="test",
            metric="test",
            message="test",
            value=0,
            threshold=1,
        )
        
        report = HealthReport(status=HealthStatus.CRITICAL, issues=[issue])
        assert report.has_critical_issues()
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        issue = HealthIssue(
            severity=HealthStatus.WARNING,
            component="test",
            metric="test",
            message="test",
            value=0,
            threshold=1,
        )
        
        report = HealthReport(
            status=HealthStatus.WARNING,
            issues=[issue],
            metrics={"test": 1},
            timestamp=1234567890.0,
        )
        
        data = report.to_dict()
        
        assert data["status"] == "warning"
        assert len(data["issues"]) == 1
        assert data["metrics"]["test"] == 1
    
    def test_get_summary_healthy(self):
        """Test summary for healthy cache."""
        report = HealthReport(status=HealthStatus.HEALTHY)
        
        summary = report.get_summary()
        
        assert "HEALTHY" in summary
        assert "All systems operational" in summary
    
    def test_get_summary_with_issues(self):
        """Test summary with issues."""
        issue = HealthIssue(
            severity=HealthStatus.WARNING,
            component="l1",
            metric="hit_rate",
            message="Hit rate low",
            value=0.65,
            threshold=0.70,
        )
        
        report = HealthReport(status=HealthStatus.WARNING, issues=[issue])
        
        summary = report.get_summary()
        
        assert "WARNING" in summary
        assert "Issues detected: 1" in summary
        assert "Hit rate low" in summary


class TestCacheHealthMonitor:
    """Tests for CacheHealthMonitor."""
    
    def test_init(self):
        """Test initialization."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        monitor = CacheHealthMonitor(cache)
        
        assert monitor.cache is cache
        assert isinstance(monitor.thresholds, HealthThresholds)
    
    def test_check_health_healthy(self):
        """Test health check with healthy cache."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        
        # Simulate good hit rate
        for _ in range(80):
            cache.set(f"key_{_}", f"value_{_}")
            cache.get(f"key_{_}")  # Hits
        for _ in range(20):
            cache.get("nonexistent_key")  # Misses
        
        monitor = CacheHealthMonitor(cache)
        report = monitor.check_health()
        
        assert report.status == HealthStatus.HEALTHY
        assert len(report.issues) == 0
    
    def test_check_health_low_hit_rate(self):
        """Test health check with low hit rate."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        
        # Simulate poor hit rate (60%)
        for _ in range(60):
            cache.set(f"key_{_}", f"value_{_}")
            cache.get(f"key_{_}")  # Hits
        for _ in range(40):
            cache.get("nonexistent_key")  # Misses
        
        monitor = CacheHealthMonitor(cache)
        report = monitor.check_health()
        
        # Should trigger warning
        assert report.status == HealthStatus.WARNING
        assert any("hit rate" in issue.message.lower() for issue in report.issues)
    
    def test_add_alert_callback(self):
        """Test adding alert callback."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        monitor = CacheHealthMonitor(cache)
        
        called = [False]
        
        def callback(report):
            called[0] = True
        
        monitor.add_alert_callback(callback)
        
        # Simulate poor hit rate to trigger alert
        for _ in range(40):
            cache.get("nonexistent_key")  # Misses
        
        monitor.check_health()
        
        assert called[0]  # Callback should have been called
    
    def test_get_last_report(self):
        """Test getting last report."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        monitor = CacheHealthMonitor(cache)
        
        # Initially no report
        assert monitor.get_last_report() is None
        
        # Check health
        monitor.check_health()
        
        # Should have report now
        report = monitor.get_last_report()
        assert report is not None
        assert isinstance(report, HealthReport)
    
    def test_log_structured_health(self):
        """Test structured logging."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        monitor = CacheHealthMonitor(cache)
        
        report = HealthReport(status=HealthStatus.HEALTHY)
        
        # Should not raise exception
        monitor.log_structured_health(report)


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_create_default_alert_logger(self):
        """Test creating default alert logger."""
        logger_func = create_default_alert_logger()
        
        assert callable(logger_func)
        
        # Test with warning report
        issue = HealthIssue(
            severity=HealthStatus.WARNING,
            component="test",
            metric="test",
            message="test",
            value=0,
            threshold=1,
        )
        report = HealthReport(status=HealthStatus.WARNING, issues=[issue])
        
        # Should not raise exception
        logger_func(report)
