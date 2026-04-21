#!/usr/bin/env python
"""CLI script for validating TTL files."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any
import warnings

from rdflib import Graph
from rdflib.exceptions import ParserError

from pyeuropepmc.qa.compare_outputs import OutputComparator
from pyeuropepmc.qa.consistency_checks import ConsistencyChecker
from pyeuropepmc.qa.metrics import RDFMetricsCalculator
from pyeuropepmc.qa.schema_validation import SchemaValidator
from pyeuropepmc.qa.sparql_queries import SPARQLValidator

warnings.filterwarnings("ignore")


class TTLValidator:
    """Main validator class for TTL files."""

    def __init__(self, schema_path: str | None = None):
        """Initialize the validator."""
        self.schema_path = schema_path
        self.metrics_calculator: RDFMetricsCalculator | None = None
        self.sparql_validator: SPARQLValidator | None = None
        self.schema_validator = SchemaValidator(schema_path) if schema_path else None
        self.consistency_checker = ConsistencyChecker()
        self.comparator = OutputComparator()

    def validate_file(
        self,
        ttl_file: str,
        run_schema: bool = True,
        run_sparql: bool = True,
        run_consistency: bool = True,
        run_metrics: bool = True,
        compare_with: str | None = None,
    ) -> dict[str, Any]:
        """Validate a single TTL file."""
        results: dict[str, Any] = {
            "file": ttl_file,
            "status": "passed",
            "errors": list[Any](),
            "warnings": list[Any](),
            "metrics": dict[str, Any](),
            "sparql": dict[str, dict[str, Any]](),
            "schema": dict[str, Any](),
            "consistency": dict[str, Any](),
            "comparisons": list[Any](),
        }

        try:
            graph = Graph()
            graph.parse(ttl_file, format="turtle")
        except ParserError as e:
            results["status"] = "failed"
            results["errors"].append(f"Parse error: {str(e)}")
            return results
        except Exception as e:
            results["status"] = "failed"
            results["errors"].append(f"Unexpected error: {str(e)}")
            return results

        if run_metrics:
            try:
                calculator = RDFMetricsCalculator(graph)
                metrics = calculator.calculate()
                results["metrics"] = metrics.to_dict()
                if metrics.total_triples == 0:
                    results["warnings"].append("No triples found in TTL file")
                else:
                    completeness = metrics.papers_with_title / max(metrics.papers_with_doi, 1)
                    if completeness < 0.5:
                        msg = f"Low completeness: {metrics.papers_with_title} entities have titles"
                        results["warnings"].append(msg)
            except Exception as e:
                results["warnings"].append(f"Metrics calculation failed: {str(e)}")

        if run_sparql:
            try:
                validator = SPARQLValidator(graph)
                all_results = validator.run_all_tests()
                results["sparql"] = {k: v.to_dict() for k, v in all_results.items()}
                failed_queries = [q for q, r in all_results.items() if not r.passed]
                if failed_queries:
                    results["warnings"].append(
                        f"Failed SPARQL queries: {', '.join(failed_queries)}"
                    )
            except Exception as e:
                results["warnings"].append(f"SPARQL validation failed: {str(e)}")

        if run_schema and self.schema_validator:
            try:
                schema_results = self.schema_validator.validate_graph(graph, ttl_file)
                results["schema"] = schema_results.to_dict()
                errors = [e for e in schema_results.issues if e.severity == "error"]
                if errors:
                    results["status"] = "failed"
                    results["errors"].extend([f"{e.subject}: {e.message}" for e in errors])
            except Exception as e:
                results["warnings"].append(f"Schema validation failed: {str(e)}")

        if run_consistency:
            try:
                checker = ConsistencyChecker()
                consistency_results = checker.check_all(graph)
                results["consistency"] = consistency_results
                if consistency_results["orphan_count"] > 0:
                    results["warnings"].append(
                        f"Found {consistency_results['orphan_count']} orphaned entities"
                    )
                if consistency_results["relationship_errors"] > 0:
                    results["warnings"].append(
                        f"Found {consistency_results['relationship_errors']} relationship errors"
                    )
            except Exception as e:
                results["warnings"].append(f"Consistency check failed: {str(e)}")

        if compare_with:
            try:
                comparator = OutputComparator()
                comparison = comparator.compare_files(compare_with, ttl_file)
                results["comparisons"].append(comparison.to_dict())
                if comparison.overall_change_score > 0.3:
                    score_pct = comparison.overall_change_score * 100
                    results["warnings"].append(
                        f"High change score vs {compare_with}: {score_pct:.1f}%"
                    )
            except Exception as e:
                results["warnings"].append(f"Comparison failed: {str(e)}")

        if results["errors"]:
            results["status"] = "failed"

        return results

    def validate_directory(self, directory: str, **kwargs) -> list[dict[str, Any]]:
        """Validate all TTL files in a directory."""
        dir_path = Path(directory)
        ttl_files = list(dir_path.glob("*.ttl"))

        results = []
        for ttl_file in ttl_files:
            result = self.validate_file(str(ttl_file), **kwargs)
            results.append(result)

        return results


def run_validation(
    ttl_files: list[str],
    schema_path: str | None = None,
    run_schema: bool = True,
    run_sparql: bool = True,
    run_consistency: bool = True,
    run_metrics: bool = True,
    compare_with: str | None = None,
    output_format: str = "text",
    output_file: str | None = None,
) -> str | None:
    """Run validation on TTL files."""
    validator: TTLValidator = TTLValidator(schema_path)

    all_results = []

    for ttl_file in ttl_files:
        result = validator.validate_file(
            ttl_file,
            run_schema=run_schema,
            run_sparql=run_sparql,
            run_consistency=run_consistency,
            run_metrics=run_metrics,
            compare_with=compare_with,
        )
        all_results.append(result)

    summary = _generate_summary(all_results)

    if output_format == "json":
        output = json.dumps({"summary": summary, "details": all_results}, indent=2)
    else:
        output = _format_text_output(all_results, summary)

    if output_file:
        with open(output_file, "w") as f:
            f.write(output)

    return output


def _generate_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate summary statistics."""
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = total - passed

    total_errors = sum(len(r["errors"]) for r in results)
    total_warnings = sum(len(r["warnings"]) for r in results)

    return {
        "total_files": total,
        "passed": passed,
        "failed": failed,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "pass_rate": passed / total if total > 0 else 0,
    }


def _format_text_output(results: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    """Format validation results as human-readable text."""
    lines = [
        "\n" + "=" * 70,
        "TTL VALIDATION SUMMARY",
        "=" * 70,
        f"Total files:    {summary['total_files']}",
        f"Passed:         {summary['passed']}",
        f"Failed:         {summary['failed']}",
        f"Pass rate:      {summary['pass_rate']:.1%}",
        f"Total errors:   {summary['total_errors']}",
        f"Total warnings: {summary['total_warnings']}",
        "=" * 70,
    ]

    for result in results:
        lines.append(f"\nFile: {result['file']}")
        lines.append(f"Status: {result['status'].upper()}")

        if result["metrics"]:
            lines.append(f"  Metrics: {result['metrics']['overall_completeness']:.1%} complete")

        if result["schema"]:
            lines.append(f"  Schema: {len(result['schema']['errors'])} errors")

        if result["consistency"]:
            lines.append(
                f"  Consistency: {result['consistency']['orphan_count']} orphans, "
                f"{result['consistency']['relationship_errors']} relationship errors"
            )

        if result["errors"]:
            lines.append("  Errors:")
            for error in result["errors"][:5]:
                lines.append(f"    - {error}")

        if result["warnings"]:
            lines.append("  Warnings:")
            for warning in result["warnings"][:5]:
                lines.append(f"    ! {warning}")

    return "\n".join(lines)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate TTL files against schema, SPARQL queries, and consistency rules"
    )
    parser.add_argument("files", nargs="+", help="TTL files to validate")
    parser.add_argument("-s", "--schema", help="Path to LinkML schema YAML file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument(
        "-f", "--format", choices=["text", "json"], default="text", help="Output format"
    )
    parser.add_argument("--no-schema", action="store_true", help="Skip schema validation")
    parser.add_argument("--no-sparql", action="store_true", help="Skip SPARQL validation")
    parser.add_argument("--no-consistency", action="store_true", help="Skip consistency checks")
    parser.add_argument("--no-metrics", action="store_true", help="Skip metrics calculation")
    parser.add_argument("--compare", help="Compare against this TTL file")
    parser.add_argument("-d", "--directory", help="Validate all TTL files in directory")

    args = parser.parse_args()

    if args.directory:
        ttl_files = [str(f) for f in Path(args.directory).glob("*.ttl")]
        if not ttl_files:
            print(f"No TTL files found in {args.directory}")
            sys.exit(1)
    else:
        ttl_files = args.files

    output = run_validation(
        ttl_files,
        schema_path=args.schema,
        run_schema=not args.no_schema,
        run_sparql=not args.no_sparql,
        run_consistency=not args.no_consistency,
        run_metrics=not args.no_metrics,
        compare_with=args.compare,
        output_format=args.format,
        output_file=args.output,
    )

    if output is not None and not args.output:
        print(output)

    if args.format == "json" and output:
        summary = json.loads(output)
        if summary and summary.get("summary", {}).get("failed", 0) > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
