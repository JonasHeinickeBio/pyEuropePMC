"""
Health monitoring and alerting for PyEuropePMC cache system.

This module provides:
- Health check functions
- Alert thresholds and detection
- Diagnostic information
- Structured logging for monitoring
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """
    Health status levels.
    """
    
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthThresholds:
    """
    Configurable health thresholds.
    
    Attributes:
        min_hit_rate: Minimum acceptable hit rate (0.0-1.0)
        max_error_rate: Maximum acceptable error rate (0.0-1.0)
        max_l1_latency_p99: Maximum acceptable L1 P99 latency (ms)
        max_l2_latency_p99: Maximum acceptable L2 P99 latency (ms)
        max_l2_disk_usage: Maximum L2 disk usage percentage (0.0-1.0)
        min_l2_hit_rate: Minimum acceptable L2 hit rate (0.0-1.0)
    """
    
    min_hit_rate: float = 0.70  # 70% minimum overall hit rate
    max_error_rate: float = 0.05  # 5% maximum error rate
    max_l1_latency_p99: float = 5.0  # 5ms
    max_l2_latency_p99: float = 50.0  # 50ms
    max_l2_disk_usage: float = 0.90  # 90% disk usage
    min_l2_hit_rate: float = 0.30  # 30% L2 hit rate


@dataclass
class HealthIssue:
    """
    Represents a health issue detected during monitoring.
    
    Attributes:
        severity: Issue severity (warning or critical)
        component: Cache component with issue (l1, l2, overall)
        metric: Metric that triggered the issue
        message: Human-readable description
        value: Current metric value
        threshold: Threshold that was exceeded
    """
    
    severity: HealthStatus
    component: str
    metric: str
    message: str
    value: Any
    threshold: Any
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "severity": self.severity.value,
            "component": self.component,
            "metric": self.metric,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
        }


@dataclass
class HealthReport:
    """
    Complete health report for cache system.
    
    Attributes:
        status: Overall health status
        issues: List of detected issues
        metrics: Current cache metrics
        timestamp: Unix timestamp of report
    """
    
    status: HealthStatus
    issues: list[HealthIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    
    def is_healthy(self) -> bool:
        """Check if cache is healthy."""
        return self.status == HealthStatus.HEALTHY
    
    def has_warnings(self) -> bool:
        """Check if cache has warnings."""
        return any(issue.severity == HealthStatus.WARNING for issue in self.issues)
    
    def has_critical_issues(self) -> bool:
        """Check if cache has critical issues."""
        return any(issue.severity == HealthStatus.CRITICAL for issue in self.issues)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": self.metrics,
            "timestamp": self.timestamp,
        }
    
    def get_summary(self) -> str:
        """
        Get human-readable health summary.
        
        Returns:
            Formatted health summary
        """
        lines = [
            f"Cache Health: {self.status.value.upper()}",
            "=" * 50,
        ]
        
        if not self.issues:
            lines.append("✓ All systems operational")
        else:
            lines.append(f"Issues detected: {len(self.issues)}")
            lines.append("")
            
            for issue in self.issues:
                severity_icon = "⚠️" if issue.severity == HealthStatus.WARNING else "🔥"
                lines.append(f"{severity_icon} [{issue.component}] {issue.message}")
                lines.append(f"   Value: {issue.value}, Threshold: {issue.threshold}")
        
        return "\n".join(lines)


class CacheHealthMonitor:
    """
    Monitor cache health and detect issues.
    """
    
    def __init__(
        self,
        cache_backend: Any,
        thresholds: Optional[HealthThresholds] = None,
        alert_callbacks: Optional[list[Callable[[HealthReport], None]]] = None,
    ):
        """
        Initialize health monitor.
        
        Args:
            cache_backend: Cache backend to monitor
            thresholds: Health thresholds configuration
            alert_callbacks: Functions to call when issues detected
        """
        self.cache = cache_backend
        self.thresholds = thresholds or HealthThresholds()
        self.alert_callbacks = alert_callbacks or []
        self._last_report: Optional[HealthReport] = None
    
    def check_health(self) -> HealthReport:
        """
        Perform comprehensive health check.
        
        Returns:
            Health report with status and issues
        """
        import time
        
        # Get current metrics
        try:
            metrics = self.cache.get_stats()
        except Exception as e:
            logger.error(f"Failed to get cache metrics: {e}")
            return HealthReport(
                status=HealthStatus.UNKNOWN,
                issues=[
                    HealthIssue(
                        severity=HealthStatus.CRITICAL,
                        component="cache",
                        metric="availability",
                        message="Cache metrics unavailable",
                        value=str(e),
                        threshold="N/A",
                    )
                ],
                timestamp=time.time(),
            )
        
        issues: list[HealthIssue] = []
        
        # Check overall hit rate
        overall = metrics.get("overall", {})
        hit_rate = overall.get("hit_rate", 0.0)
        
        if hit_rate < self.thresholds.min_hit_rate:
            issues.append(
                HealthIssue(
                    severity=HealthStatus.WARNING,
                    component="overall",
                    metric="hit_rate",
                    message=f"Overall hit rate below threshold ({hit_rate:.2%})",
                    value=hit_rate,
                    threshold=self.thresholds.min_hit_rate,
                )
            )
        
        # Check error rate
        error_rate = overall.get("error_rate", 0.0)
        if error_rate > self.thresholds.max_error_rate:
            issues.append(
                HealthIssue(
                    severity=HealthStatus.CRITICAL,
                    component="overall",
                    metric="error_rate",
                    message=f"Error rate too high ({error_rate:.2%})",
                    value=error_rate,
                    threshold=self.thresholds.max_error_rate,
                )
            )
        
        # Check L1 latency
        l1_metrics = metrics.get("layers", {}).get("l1", {})
        if l1_metrics:
            l1_latency_p99 = l1_metrics.get("latency_p99", 0.0)
            if l1_latency_p99 > self.thresholds.max_l1_latency_p99:
                issues.append(
                    HealthIssue(
                        severity=HealthStatus.WARNING,
                        component="l1",
                        metric="latency_p99",
                        message=f"L1 P99 latency high ({l1_latency_p99:.2f}ms)",
                        value=l1_latency_p99,
                        threshold=self.thresholds.max_l1_latency_p99,
                    )
                )
        
        # Check L2 metrics
        l2_metrics = metrics.get("layers", {}).get("l2", {})
        if l2_metrics:
            # L2 latency
            l2_latency_p99 = l2_metrics.get("latency_p99", 0.0)
            if l2_latency_p99 > self.thresholds.max_l2_latency_p99:
                issues.append(
                    HealthIssue(
                        severity=HealthStatus.WARNING,
                        component="l2",
                        metric="latency_p99",
                        message=f"L2 P99 latency high ({l2_latency_p99:.2f}ms)",
                        value=l2_latency_p99,
                        threshold=self.thresholds.max_l2_latency_p99,
                    )
                )
            
            # L2 hit rate
            l2_hit_rate = l2_metrics.get("hit_rate", 0.0)
            if l2_hit_rate < self.thresholds.min_l2_hit_rate:
                issues.append(
                    HealthIssue(
                        severity=HealthStatus.WARNING,
                        component="l2",
                        metric="hit_rate",
                        message=f"L2 hit rate low ({l2_hit_rate:.2%})",
                        value=l2_hit_rate,
                        threshold=self.thresholds.min_l2_hit_rate,
                    )
                )
            
            # L2 disk usage
            disk_usage = l2_metrics.get("disk_usage_percent", 0.0) / 100.0
            if disk_usage > self.thresholds.max_l2_disk_usage:
                issues.append(
                    HealthIssue(
                        severity=HealthStatus.CRITICAL,
                        component="l2",
                        metric="disk_usage",
                        message=f"L2 disk usage critical ({disk_usage:.1%})",
                        value=disk_usage,
                        threshold=self.thresholds.max_l2_disk_usage,
                    )
                )
        
        # Determine overall status
        if any(issue.severity == HealthStatus.CRITICAL for issue in issues):
            status = HealthStatus.CRITICAL
        elif issues:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.HEALTHY
        
        # Create report
        report = HealthReport(
            status=status,
            issues=issues,
            metrics=metrics,
            timestamp=time.time(),
        )
        
        # Store report
        self._last_report = report
        
        # Trigger alerts if needed
        if issues:
            self._trigger_alerts(report)
        
        # Log health status
        if status == HealthStatus.HEALTHY:
            logger.debug("Cache health check: HEALTHY")
        else:
            logger.warning(
                f"Cache health check: {status.value.upper()} - {len(issues)} issues detected"
            )
            for issue in issues:
                logger.warning(f"  {issue.message}")
        
        return report
    
    def _trigger_alerts(self, report: HealthReport) -> None:
        """
        Trigger alert callbacks.
        
        Args:
            report: Health report with issues
        """
        for callback in self.alert_callbacks:
            try:
                callback(report)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def get_last_report(self) -> Optional[HealthReport]:
        """
        Get last health report.
        
        Returns:
            Last health report, or None if no checks run yet
        """
        return self._last_report
    
    def add_alert_callback(self, callback: Callable[[HealthReport], None]) -> None:
        """
        Add alert callback function.
        
        Args:
            callback: Function to call with HealthReport when issues detected
        """
        self.alert_callbacks.append(callback)
    
    def log_structured_health(self, report: HealthReport) -> None:
        """
        Log health report in structured format.
        
        Args:
            report: Health report to log
        """
        logger.info(
            "Cache health report",
            extra={
                "status": report.status.value,
                "issue_count": len(report.issues),
                "has_critical": report.has_critical_issues(),
                "has_warnings": report.has_warnings(),
                "overall_hit_rate": report.metrics.get("overall", {}).get(
                    "hit_rate", 0.0
                ),
                "timestamp": report.timestamp,
            },
        )
        
        for issue in report.issues:
            logger.warning(
                "Cache health issue detected",
                extra={
                    "severity": issue.severity.value,
                    "component": issue.component,
                    "metric": issue.metric,
                    "value": issue.value,
                    "threshold": issue.threshold,
                },
            )


def create_default_alert_logger() -> Callable[[HealthReport], None]:
    """
    Create default alert callback that logs to stderr.
    
    Returns:
        Alert callback function
    """
    
    def alert_logger(report: HealthReport) -> None:
        """Log alert to stderr."""
        if report.has_critical_issues():
            logger.error(f"CRITICAL: Cache health issues detected\n{report.get_summary()}")
        elif report.has_warnings():
            logger.warning(f"WARNING: Cache health issues detected\n{report.get_summary()}")
    
    return alert_logger
