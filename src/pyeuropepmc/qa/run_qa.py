#!/usr/bin/env python
"""Main QA runner for comprehensive TTL validation."""

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from pyeuropepmc.qa.compare_outputs import OutputComparator
from pyeuropepmc.qa.consistency_checks import ConsistencyChecker
from pyeuropepmc.qa.metrics import QualityMetrics, RDFMetricsCalculator
from pyeuropepmc.qa.schema_validation import SchemaValidator
from pyeuropepmc.qa.sparql_queries import SPARQLValidator


class QARunner:
    """Run comprehensive QA checks on TTL files."""

    def __init__(self, schema_path: str | None = None):
        """Initialize the QA runner."""
        self.schema_path = schema_path
        self.schema_validator = SchemaValidator(schema_path) if schema_path else None
        self.comparator: OutputComparator = OutputComparator()
        self.results_cache: dict[str, dict[str, Any]] = {}

    def run_qa_on_file(
        self,
        ttl_file: str,
        include_metrics: bool = True,
        include_sparql: bool = True,
        include_schema: bool = True,
        include_consistency: bool = True,
        include_comparison: str | None = None,
    ) -> dict[str, Any]:
        """Run all QA checks on a single file."""
        ttl_file_str = str(ttl_file)

        if ttl_file_str in self.results_cache:
            return self.results_cache[ttl_file_str]

        summary: dict[str, Any] = {}
        result: dict[str, Any] = {
            "file": ttl_file_str,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "passed",
            "summary": summary,
        }

        try:
            from rdflib import Graph

            graph = Graph()
            graph.parse(ttl_file_str, format="turtle")
            result["triples"] = len(graph)
        except Exception as e:
            result["overall_status"] = "error"
            result["error"] = f"Failed to parse TTL file: {str(e)}"
            self.results_cache[ttl_file_str] = result
            return result

        if include_metrics:
            try:
                metrics_calc = RDFMetricsCalculator(graph)
                metrics = metrics_calc.calculate()
                result["checks"]["metrics"] = metrics.to_dict()
                result["summary"]["completeness"] = self._calculate_completeness(metrics)
            except Exception as e:
                result["checks"]["metrics"] = {"error": str(e)}

        if include_sparql:
            try:
                sparql_validator = SPARQLValidator(graph)
                all_results = sparql_validator.run_all_tests()
                result["checks"]["sparql"] = {k: v.to_dict() for k, v in all_results.items()}
                passed = sum(1 for r in all_results.values() if r.passed)
                result["summary"]["sparql_passed"] = f"{passed}/{len(all_results)}"
            except Exception as e:
                result["checks"]["sparql"] = {"error": str(e)}

        if include_schema and self.schema_validator:
            try:
                schema_results = self.schema_validator.validate_graph(graph, ttl_file)
                result["checks"]["schema"] = schema_results.to_dict()
                result["summary"]["schema_errors"] = schema_results.errors_count
                result["summary"]["schema_warnings"] = schema_results.warnings_count
            except Exception as e:
                result["checks"]["schema"] = {"error": str(e)}

        if include_consistency:
            try:
                consistency_checker = ConsistencyChecker()
                consistency_results = consistency_checker.check_all(graph)
                result["checks"]["consistency"] = consistency_results
                result["summary"]["orphan_count"] = consistency_results["orphan_count"]
                result["summary"]["relationship_errors"] = consistency_results[
                    "relationship_errors"
                ]
            except Exception as e:
                result["checks"]["consistency"] = {"error": str(e)}

        if include_comparison:
            try:
                comparison = self.comparator.compare_files(include_comparison, ttl_file)
                result["checks"]["comparison"] = comparison.to_dict()
                result["summary"]["change_score"] = comparison.overall_change_score
            except Exception as e:
                result["checks"]["comparison"] = {"error": str(e)}

        self._determine_overall_status(result)
        self.results_cache[ttl_file] = result

        return result

    def _calculate_completeness(self, metrics: "QualityMetrics") -> float:
        """Calculate overall completeness from metrics."""
        # Simple calculation based on available fields
        total_fields = 6  # title, doi, pmid, pmcid, authors, abstract
        present = 0

        if metrics.papers_with_title > 0:
            present += 1
        if metrics.papers_with_doi > 0:
            present += 1
        if metrics.papers_with_pmid > 0:
            present += 1
        if metrics.papers_with_pmcid > 0:
            present += 1
        if metrics.papers_with_authors > 0:
            present += 1
        if metrics.papers_with_abstract > 0:
            present += 1

        return present / total_fields if total_fields > 0 else 0

    def _determine_overall_status(self, result: dict[str, Any]):
        """Determine overall QA status based on all checks."""
        if "error" in result:
            result["overall_status"] = "error"
            return

        checks = result.get("checks", {})

        scores = []

        if "metrics" in checks and not checks["metrics"].get("error"):
            completeness = checks["metrics"].get("completeness", 0)
            scores.append(completeness)

        if "schema" in checks and not checks["schema"].get("error"):
            schema_data = checks["schema"]
            if schema_data.get("errors_count", 0) > 0 or not schema_data.get("is_valid", True):
                result["overall_status"] = "failed"
                return

        if "consistency" in checks and not checks["consistency"].get("error"):
            consistency_data = checks["consistency"]
            if (
                consistency_data.get("orphan_count", 0) > 10
                or consistency_data.get("relationship_errors", 0) > 0
            ):
                result["overall_status"] = "warning"

        if scores:
            avg_score = sum(scores) / len(scores)
            if avg_score >= 0.8:
                result["overall_status"] = "passed"
            elif avg_score >= 0.5:
                result["overall_status"] = "warning"
            else:
                result["overall_status"] = "failed"

    def run_qa_on_directory(
        self,
        directory: str,
        output_format: str = "json",
        output_file: str | None = None,
        compare_with: str | None = None,
    ) -> str:
        """Run QA on all TTL files in a directory."""
        dir_path = Path(directory)
        ttl_files = sorted(dir_path.glob("*.ttl"))

        if not ttl_files:
            return f"No TTL files found in {directory}"

        all_results = []
        for ttl_file in ttl_files:
            result = self.run_qa_on_file(str(ttl_file), include_comparison=compare_with)
            all_results.append(result)

        summary = self._generate_summary(all_results)

        if output_format == "json":
            output = json.dumps(
                {
                    "summary": summary,
                    "files": all_results,
                    "generated_at": datetime.now().isoformat(),
                },
                indent=2,
            )
        else:
            output = self._format_text_output(all_results, summary)

        if output_file:
            with open(output_file, "w") as f:
                f.write(output)

        return output

    def _generate_summary(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate summary statistics."""
        total = len(results)
        statuses: dict[str, int] = {}
        for r in results:
            status = r.get("overall_status", "unknown")
            statuses[status] = statuses.get(status, 0) + 1

        avg_completeness = 0.0
        avg_change_score = 0.0
        count = 0
        for r in results:
            if "summary" in r:
                if "completeness" in r["summary"]:
                    avg_completeness += r["summary"]["completeness"]
                if "change_score" in r["summary"]:
                    avg_change_score += r["summary"]["change_score"]
                    count += 1

        avg_completeness = avg_completeness / total if total > 0 else 0.0
        avg_change_score = avg_change_score / count if count > 0 else 0.0

        return {
            "total_files": total,
            "by_status": statuses,
            "average_completeness": round(avg_completeness, 4),
            "average_change_score": round(avg_change_score, 4),
        }

    def _format_text_output(self, results: list[dict[str, Any]], summary: dict[str, Any]) -> str:
        """Format results as human-readable text."""
        lines = [
            "\n" + "=" * 70,
            "QA VALIDATION SUMMARY",
            "=" * 70,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Total files analyzed: {summary['total_files']}",
            "",
            "Status breakdown:",
        ]

        for status, count in summary["by_status"].items():
            lines.append(f"  {status.capitalize():12} : {count}")

        lines.extend(
            [
                "",
                f"Average completeness:   {summary['average_completeness']:.1%}",
                f"Average change score:   {summary['average_change_score']:.1%}",
                "=" * 70,
                "",
            ]
        )

        for result in results:
            lines.append(f"File: {Path(result['file']).name}")
            lines.append(f"  Status: {result['overall_status'].upper()}")

            if "summary" in result:
                if "completeness" in result["summary"]:
                    lines.append(f"  Completeness: {result['summary']['completeness']:.1%}")
                if "sparql_passed" in result["summary"]:
                    lines.append(f"  SPARQL: {result['summary']['sparql_passed']}")
                if "orphan_count" in result["summary"]:
                    lines.append(f"  Orphans: {result['summary']['orphan_count']}")

            lines.append("")

        return "\n".join(lines)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run comprehensive QA validation on TTL files")
    parser.add_argument("directory", help="Directory containing TTL files")
    parser.add_argument("-s", "--schema", help="Path to LinkML schema YAML file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument(
        "-f", "--format", choices=["text", "json"], default="json", help="Output format"
    )
    parser.add_argument("--compare", help="Compare against this TTL file")
    parser.add_argument("--no-metrics", action="store_true", help="Skip metrics calculation")
    parser.add_argument("--no-sparql", action="store_true", help="Skip SPARQL validation")
    parser.add_argument("--no-schema", action="store_true", help="Skip schema validation")
    parser.add_argument("--no-consistency", action="store_true", help="Skip consistency checks")

    args = parser.parse_args()

    runner = QARunner(schema_path=args.schema)

    output = runner.run_qa_on_directory(
        args.directory,
        output_format=args.format,
        output_file=args.output,
        compare_with=args.compare,
    )

    if output is not None and not args.output:
        print(output)


if __name__ == "__main__":
    main()
