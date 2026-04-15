"""
Performance analyzers and bottleneck detectors.

Provides statistical analysis and detailed bottleneck detection
for benchmark results.
"""

from collections import defaultdict
import statistics
from typing import Any


class PerformanceAnalyzer:
    """
    Analyzes benchmark results to identify performance patterns
    and statistical characteristics.
    """

    def __init__(self, results: list[dict[str, Any]]):
        """
        Initialize the analyzer.

        Args:
            results: List of benchmark result dictionaries
        """
        self.results = results

    def get_basic_statistics(self) -> dict[str, Any]:
        """
        Calculate basic statistics for benchmark results.

        Returns:
            Dictionary with basic statistics
        """
        if not self.results:
            return {}

        times = [r.get("avg_time", 0) for r in self.results]
        success_rates = [r.get("success_rate", 1.0) for r in self.results]

        return {
            "total_results": len(self.results),
            "avg_time": statistics.mean(times) if times else 0,
            "median_time": statistics.median(times) if times else 0,
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "min_time": min(times) if times else 0,
            "max_time": max(times) if times else 0,
            "success_rate": statistics.mean(success_rates) if success_rates else 1,
            "total_errors": sum(r.get("error_count", 0) for r in self.results),
        }

    def analyze_by_operation(self) -> dict[str, dict[str, Any]]:
        """
        Analyze performance grouped by operation type.

        Returns:
            Dictionary with statistics for each operation type
        """
        by_operation = defaultdict(list)

        for result in self.results:
            op_type = result.get("operation_type", "unknown")
            by_operation[op_type].append(result)

        analysis = {}
        for op_type, op_results in by_operation.items():
            times = [r.get("avg_time", 0) for r in op_results]
            analysis[op_type] = {
                "count": len(op_results),
                "avg_time": statistics.mean(times) if times else 0,
                "median_time": statistics.median(times) if times else 0,
                "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
                "min_time": min(times) if times else 0,
                "max_time": max(times) if times else 0,
                "success_rate": (
                    statistics.mean([r.get("success_rate", 1.0) for r in op_results])
                    if op_results
                    else 1
                ),
            }

        return analysis

    def analyze_by_input_size(self) -> dict[str, dict[str, Any]]:
        """
        Analyze performance grouped by input size.

        Returns:
            Dictionary with statistics for each input size category
        """
        if not self.results:
            return {}

        sizes = [r.get("input_size", 0) for r in self.results]
        if not sizes:
            return {}

        _min_size, _max_size = min(sizes), max(sizes)

        # Create size categories
        categories = [
            (0, 10),
            (10, 100),
            (100, 1000),
            (1000, 10000),
            (10000, float("inf")),
        ]

        analysis = {}
        for low, high in categories:
            label = f"{low}-{high}"
            category_results = [r for r in self.results if low <= r.get("input_size", 0) < high]

            if category_results:
                times = [r.get("avg_time", 0) for r in category_results]
                analysis[label] = {
                    "count": len(category_results),
                    "avg_time": statistics.mean(times) if times else 0,
                    "input_range": f"{low} to {high}",
                }

        return analysis

    def identify_fastest_slowest(self) -> dict[str, dict[str, Any]]:
        """
        Identify fastest and slowest operations.

        Returns:
            Dictionary with fastest and slowest operations
        """
        if not self.results:
            return {}

        fastest = min(self.results, key=lambda x: x.get("avg_time", float("inf")))
        slowest = max(self.results, key=lambda x: x.get("avg_time", 0))

        return {
            "fastest": {
                "function": fastest.get("function_name", "unknown"),
                "operation_type": fastest.get("operation_type", "unknown"),
                "avg_time": fastest.get("avg_time", 0),
                "input_size": fastest.get("input_size", 0),
            },
            "slowest": {
                "function": slowest.get("function_name", "unknown"),
                "operation_type": slowest.get("operation_type", "unknown"),
                "avg_time": slowest.get("avg_time", 0),
                "input_size": slowest.get("input_size", 0),
            },
        }

    def get_coefficient_of_variation(self) -> dict[str, float]:
        """
        Calculate coefficient of variation (CV) for each operation type.

        CV = std_dev / mean, indicates relative variability.

        Returns:
            Dictionary with CV for each operation type
        """
        by_operation = self.analyze_by_operation()
        cv_values = {}

        for op_type, stats in by_operation.items():
            mean = stats.get("avg_time", 0)
            std_dev = stats.get("std_dev", 0)

            if mean > 0:
                cv = std_dev / mean
                cv_values[op_type] = cv
            else:
                cv_values[op_type] = 0

        return cv_values

    def to_dict(self) -> dict[str, Any]:
        """
        Convert all analysis to dictionary.

        Returns:
            Complete analysis dictionary
        """
        return {
            "basic_statistics": self.get_basic_statistics(),
            "by_operation": self.analyze_by_operation(),
            "by_input_size": self.analyze_by_input_size(),
            "fastest_slowest": self.identify_fastest_slowest(),
            "coefficient_of_variation": self.get_coefficient_of_variation(),
        }


class BottleneckDetector:
    """
    Detects performance bottlenecks in benchmark results.
    """

    def __init__(self, results: list[dict[str, Any]], threshold: float = 2.0):
        """
        Initialize the bottleneck detector.

        Args:
            results: List of benchmark result dictionaries
            threshold: Number of standard deviations to consider as bottleneck
        """
        self.results = results
        self.threshold = threshold
        self.analyzer = PerformanceAnalyzer(results)

    def detect_absolute_bottlenecks(self) -> list[dict[str, Any]]:
        """
        Detect bottlenecks based on absolute time thresholds.

        Returns:
            List of bottleneck information
        """
        bottlenecks = []
        stats = self.analyzer.get_basic_statistics()
        avg_time = stats.get("avg_time", 0)
        std_dev = stats.get("std_dev", 0)

        for result in self.results:
            avg = result.get("avg_time", 0)
            if avg > avg_time + self.threshold * std_dev:
                bottlenecks.append(
                    {
                        "type": "absolute",
                        "function": result.get("function_name"),
                        "operation_type": result.get("operation_type"),
                        "avg_time": avg,
                        "threshold": avg_time + self.threshold * std_dev,
                        "deviation_from_mean": avg - avg_time,
                    }
                )

        return bottlenecks

    def detect_relative_bottlenecks(self) -> list[dict[str, Any]]:
        """
        Detect bottlenecks based on relative performance within operation type.

        Returns:
            List of bottleneck information
        """
        bottlenecks = []
        by_operation = self.analyzer.analyze_by_operation()

        for op_type, op_stats in by_operation.items():
            op_results = [r for r in self.results if r.get("operation_type") == op_type]
            op_avg = op_stats.get("avg_time", 0)
            op_std = op_stats.get("std_dev", 0)

            if op_std == 0:
                continue

            for result in op_results:
                avg = result.get("avg_time", 0)
                if avg > op_avg + self.threshold * op_std:
                    bottlenecks.append(
                        {
                            "type": "relative",
                            "operation_type": op_type,
                            "function": result.get("function_name"),
                            "avg_time": avg,
                            "threshold": op_avg + self.threshold * op_std,
                            "deviation_from_mean": avg - op_avg,
                        }
                    )

        return bottlenecks

    def detect_scaling_bottlenecks(self) -> list[dict[str, Any]]:
        """
        Detect bottlenecks related to input size scaling.

        Returns:
            List of bottleneck information
        """
        bottlenecks: list[dict[str, Any]] = []

        # Group by input size
        by_size = defaultdict(list)
        for result in self.results:
            size = result.get("input_size", 0)
            by_size[size].append(result)

        # Check for exponential scaling
        sizes = sorted(by_size.keys())
        if len(sizes) < 3:
            return bottlenecks

        for i in range(1, len(sizes)):
            prev_size = sizes[i - 1]
            curr_size = sizes[i]

            prev_times = [r.get("avg_time", 0) for r in by_size[prev_size]]
            curr_times = [r.get("avg_time", 0) for r in by_size[curr_size]]

            prev_avg = sum(prev_times) / len(prev_times) if prev_times else 0
            curr_avg = sum(curr_times) / len(curr_times) if curr_times else 0

            if prev_avg > 0:
                # Check if time scales worse than linearly
                size_ratio = curr_size / prev_size if prev_size > 0 else 1
                time_ratio = curr_avg / prev_avg if prev_avg > 0 else 1

                if time_ratio > size_ratio * 1.5:  # More than 1.5x linear scaling
                    bottlenecks.append(
                        {
                            "type": "scaling",
                            "prev_size": prev_size,
                            "curr_size": curr_size,
                            "prev_avg_time": prev_avg,
                            "curr_avg_time": curr_avg,
                            "size_ratio": size_ratio,
                            "time_ratio": time_ratio,
                        }
                    )

        return bottlenecks

    def detect_consistency_issues(self) -> list[dict[str, Any]]:
        """
        Detect operations with inconsistent performance.

        Returns:
            List of operations with consistency issues
        """
        bottlenecks = []
        by_operation = self.analyzer.get_coefficient_of_variation()

        for op_type, cv in by_operation.items():
            # CV > 0.3 indicates high variability
            if cv > 0.3:
                op_results = [r for r in self.results if r.get("operation_type") == op_type]
                avg_time = statistics.mean([r.get("avg_time", 0) for r in op_results])

                bottlenecks.append(
                    {
                        "type": "consistency",
                        "operation_type": op_type,
                        "coefficient_of_variation": cv,
                        "avg_time": avg_time,
                        "description": (
                            f"High variability in {op_type}: CV={cv:.3f}, avg_time={avg_time:.6f}s"
                        ),
                    }
                )

        return bottlenecks

    def detect_all_bottlenecks(self) -> dict[str, list[dict[str, Any]]]:
        """
        Detect all types of bottlenecks.

        Returns:
            Dictionary with bottlenecks by type
        """
        return {
            "absolute": self.detect_absolute_bottlenecks(),
            "relative": self.detect_relative_bottlenecks(),
            "scaling": self.detect_scaling_bottlenecks(),
            "consistency": self.detect_consistency_issues(),
        }

    def get_top_bottlenecks(self, n: int = 10) -> list[dict[str, Any]]:
        """
        Get top N bottlenecks by severity.

        Args:
            n: Number of top bottlenecks to return

        Returns:
            List of top bottleneck information
        """
        all_bottlenecks = self.detect_all_bottlenecks()
        flat_list = []

        for bottleneck_type, bottlenecks in all_bottlenecks.items():
            for bottleneck in bottlenecks:
                bottleneck["bottleneck_type"] = bottleneck_type
                # Calculate severity score
                severity = 0
                if bottleneck.get("avg_time", 0) > 1.0:
                    severity += 1
                if bottleneck.get("deviation_from_mean", 0) > 0.5:
                    severity += 1
                if bottleneck.get("time_ratio", 0) > 2.0:
                    severity += 2
                bottleneck["severity"] = severity
                flat_list.append(bottleneck)

        flat_list.sort(key=lambda x: x.get("severity", 0), reverse=True)
        return flat_list[:n]

    def generate_report(self) -> dict[str, Any]:
        """
        Generate a comprehensive bottleneck report.

        Returns:
            Complete bottleneck report dictionary
        """
        all_bottlenecks = self.detect_all_bottlenecks()
        top_bottlenecks = self.get_top_bottlenecks()

        total_bottlenecks = sum(len(b) for b in all_bottlenecks.values())

        return {
            "summary": {
                "total_bottlenecks": total_bottlenecks,
                "by_type": {k: len(v) for k, v in all_bottlenecks.items()},
            },
            "bottlenecks": all_bottlenecks,
            "top_bottlenecks": top_bottlenecks,
        }

    def print_report(self) -> None:
        """Print a formatted bottleneck report."""
        report = self.generate_report()

        print("\n" + "=" * 70)
        print("BOTTLENECK ANALYSIS REPORT")
        print("=" * 70)

        summary = report.get("summary", {})
        print(f"\nTotal bottlenecks detected: {summary.get('total_bottlenecks', 0)}")
        print("\nBy type:")
        for bottleneck_type, count in summary.get("by_type", {}).items():
            print(f"  {bottleneck_type}: {count}")

        top = report.get("top_bottlenecks", [])
        if top:
            print("\nTop Bottlenecks:")
            print("-" * 50)
            for i, bottleneck in enumerate(top[:10], 1):
                print(f"\n{i}. {bottleneck.get('function', 'unknown')}")
                print(f"   Type: {bottleneck.get('bottleneck_type')}")
                print(f"   Severity: {bottleneck.get('severity', 0)}")
                if bottleneck.get("avg_time"):
                    print(f"   Avg Time: {bottleneck['avg_time']:.6f}s")

        print("\n" + "=" * 70)
