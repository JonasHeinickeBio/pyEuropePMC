"""
Report generators for benchmark results.

Provides various formats for exporting and visualizing benchmark data.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any


class ReportGenerator:
    """
    Base class for report generators.
    """

    def __init__(self, results: list[dict[str, Any]]):
        """
        Initialize the report generator.

        Args:
            results: List of benchmark result dictionaries
        """
        self.results = results

    def generate(self) -> str:
        """
        Generate the report.

        Returns:
            Report content as string
        """
        raise NotImplementedError

    def save(self, filepath: str | Path) -> None:
        """
        Save report to file.

        Args:
            filepath: Path to save the report
        """
        content = self.generate()
        Path(filepath).write_text(content)

    def _get_timestamp(self) -> str:
        """Get current timestamp as string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class JSONReportGenerator(ReportGenerator):
    """
    Generate benchmark reports in JSON format.
    """

    def generate(self) -> str:
        """
        Generate JSON report.

        Returns:
            JSON report string
        """
        report = {
            "metadata": {
                "generated_at": self._get_timestamp(),
                "total_results": len(self.results),
            },
            "results": self.results,
        }
        return json.dumps(report, indent=2, default=str)


class CSVReportGenerator(ReportGenerator):
    """
    Generate benchmark reports in CSV format.
    """

    def generate(self) -> str:
        """
        Generate CSV report.

        Returns:
            CSV report string
        """
        if not self.results:
            return ""

        # Collect all keys from all results
        all_keys: set[str] = set()
        for result in self.results:
            all_keys.update(result.keys())

        # Sort keys for consistent output
        keys = sorted(all_keys)

        lines = []
        # Header
        lines.append(",".join(keys))

        # Data rows
        for result in self.results:
            row = []
            for key in keys:
                value = result.get(key, "")
                if isinstance(value, dict | list):
                    value = json.dumps(value)
                elif value is None:
                    value = ""
                else:
                    value = str(value)
                # Escape commas and quotes
                value = value.replace('"', '""')
                if "," in value or '"' in value:
                    value = f'"{value}"'
                row.append(value)
            lines.append(",".join(row))

        return "\n".join(lines)


class TextReportGenerator(ReportGenerator):
    """
    Generate human-readable text reports.
    """

    def generate(self) -> str:
        """
        Generate text report.

        Returns:
            Text report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("BENCHMARK REPORT")
        lines.append(f"Generated: {self._get_timestamp()}")
        lines.append(f"Total Results: {len(self.results)}")
        lines.append("=" * 70)

        if not self.results:
            lines.append("No results to report.")
            return "\n".join(lines)

        # Group by operation type
        by_operation: dict[str, list[dict[str, Any]]] = {}
        for result in self.results:
            op_type = result.get("operation_type", "unknown")
            if op_type not in by_operation:
                by_operation[op_type] = []
            by_operation[op_type].append(result)

        for op_type, op_results in sorted(by_operation.items()):
            lines.append(f"\n{op_type.upper()}")
            lines.append("-" * 50)
            lines.append(f"Count: {len(op_results)}")

            # Calculate statistics
            times = [r.get("avg_time", 0) for r in op_results]
            if times:
                import statistics

                lines.append(f"Avg Time: {statistics.mean(times):.6f}s")
                lines.append(f"Median: {statistics.median(times):.6f}s")
                if len(times) > 1:
                    lines.append(f"Std Dev: {statistics.stdev(times):.6f}s")
                lines.append(f"Min: {min(times):.6f}s")
                lines.append(f"Max: {max(times):.6f}s")

            # Success rate
            success_rates = [r.get("success_rate", 1.0) for r in op_results]
            if success_rates:
                lines.append(f"Success Rate: {statistics.mean(success_rates) * 100:.2f}%")

            # Top 3 slowest
            sorted_results = sorted(op_results, key=lambda x: x.get("avg_time", 0), reverse=True)[
                :3
            ]
            if sorted_results:
                lines.append("\nTop 3 Slowest:")
                for i, result in enumerate(sorted_results, 1):
                    lines.append(
                        f"  {i}. {result.get('function_name', 'unknown')}: "
                        f"{result.get('avg_time', 0):.6f}s"
                    )

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)


class HTMLReportGenerator(ReportGenerator):
    """
    Generate HTML reports with interactive visualizations.
    """

    def generate(self) -> str:
        """
        Generate HTML report.

        Returns:
            HTML report string
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Benchmark Report - {self._get_timestamp()}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #e7f3fe; padding: 15px; border-radius: 5px; }}
        .bottleneck {{ background-color: #ffe0b2; padding: 10px; margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>Benchmark Report</h1>
    <p>Generated: {self._get_timestamp()}</p>
    <p>Total Results: {len(self.results)}</p>

    <div class="summary">
        <h2>Summary</h2>
"""
        if self.results:
            import statistics

            times = [r.get("avg_time", 0) for r in self.results]
            html += f"""
        <p>Average Time: {statistics.mean(times):.6f}s</p>
        <p>Median Time: {statistics.median(times):.6f}s</p>
        <p>Min Time: {min(times):.6f}s</p>
        <p>Max Time: {max(times):.6f}s</p>
"""
        html += """
    </div>

    <h2>Detailed Results</h2>
    <table>
        <tr>
            <th>Function</th>
            <th>Operation Type</th>
            <th>Avg Time (s)</th>
            <th>Std Dev</th>
            <th>Success Rate</th>
            <th>Input Size</th>
        </tr>
"""

        for result in self.results:
            function = result.get("function_name", "unknown")
            op_type = result.get("operation_type", "unknown")
            avg_time = result.get("avg_time", 0)
            std_dev = result.get("std_dev", 0)
            success_rate = result.get("success_rate", 1.0)
            input_size = result.get("input_size", 0)

            html += f"""
        <tr>
            <td>{function}</td>
            <td>{op_type}</td>
            <td>{avg_time:.6f}</td>
            <td>{std_dev:.6f}</td>
            <td>{success_rate * 100:.2f}%</td>
            <td>{input_size}</td>
        </tr>
"""

        html += """
    </table>
</body>
</html>
"""

        return html


def generate_comprehensive_report(
    results: list[dict[str, Any]],
    output_dir: str | Path | None = None,
    formats: list[str] | None = None,
) -> dict[str, str]:
    """
    Generate comprehensive reports in multiple formats.

    Args:
        results: List of benchmark result dictionaries
        output_dir: Directory to save reports (optional)
        formats: List of formats to generate (json, csv, text, html)

    Returns:
        Dictionary with format names and generated content
    """
    if formats is None:
        formats = ["json", "csv", "text", "html"]

    generators = {
        "json": JSONReportGenerator,
        "csv": CSVReportGenerator,
        "text": TextReportGenerator,
        "html": HTMLReportGenerator,
    }

    {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_results": len(results),
        },
        "results": results,
    }

    generated = {}

    for fmt in formats:
        if fmt in generators:
            generator = generators[fmt](results)
            content = generator.generate()
            generated[fmt] = content

            if output_dir:
                output_path = Path(output_dir) / f"benchmark_report.{fmt}"
                output_path.write_text(content)

    return generated
