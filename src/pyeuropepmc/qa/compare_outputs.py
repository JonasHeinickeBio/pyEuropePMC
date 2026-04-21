"""Comparison module for detecting regressions between TTL output files."""

from dataclasses import asdict, dataclass
import json
from typing import Any

from rdflib import Graph, Namespace, URIRef
from rdflib.compare import graph_diff, to_canonical_graph


@dataclass
class ComparisonResult:
    """Result of comparing two TTL files."""

    file1: str
    file2: str
    added_triples: int
    removed_triples: int
    changed_triples: int
    common_triples: int
    entities_added: list[str]
    entities_removed: list[str]
    entities_changed: list[str]
    namespace_changes: dict[str, dict[str, int]]
    overall_change_score: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class OutputComparator:
    """Compare two TTL output files to detect regressions."""

    def __init__(self):
        """Initialize the comparator."""
        self.ns_manager = Namespace("")

    def load_graph(self, ttl_file: str) -> Graph:
        """Load a TTL file into an RDF graph."""
        g = Graph()
        g.parse(ttl_file, format="turtle")
        return g

    def compare_files(self, file1: str, file2: str) -> ComparisonResult:
        """Compare two TTL files."""
        g1 = self.load_graph(file1)
        g2 = self.load_graph(file2)

        return self.compare_graphs(g1, g2, file1, file2)

    def compare_graphs(
        self, g1: Graph, g2: Graph, file1: str = "file1", file2: str = "file2"
    ) -> ComparisonResult:
        """Compare two RDF graphs."""
        g1_canonical = to_canonical_graph(g1)
        g2_canonical = to_canonical_graph(g2)

        in_both, only_in_g1, only_in_g2 = graph_diff(g1_canonical, g2_canonical)

        added_triples = len(only_in_g2)
        removed_triples = len(only_in_g1)

        common_triples = len(in_both)

        entities_added = self._extract_entities(only_in_g2)
        entities_removed = self._extract_entities(only_in_g1)
        entities_changed = self._detect_changed_entities(g1, g2)

        namespace_changes = self._analyze_namespace_changes(g1, g2)

        total_triples = len(g1_canonical) + len(g2_canonical)
        if total_triples == 0:
            overall_change_score = 0.0
        else:
            changed = added_triples + removed_triples
            overall_change_score = changed / total_triples

        return ComparisonResult(
            file1=file1,
            file2=file2,
            added_triples=added_triples,
            removed_triples=removed_triples,
            changed_triples=len(entities_changed),
            common_triples=common_triples,
            entities_added=entities_added,
            entities_removed=entities_removed,
            entities_changed=entities_changed,
            namespace_changes=namespace_changes,
            overall_change_score=round(overall_change_score, 4),
        )

    def _extract_entities(self, graph: Graph) -> list[str]:
        """Extract unique entity URIs from a graph."""
        entities = set()
        for s, _p, _o in graph:
            if isinstance(s, URIRef):
                entities.add(str(s))
        return sorted(list(entities))[:50]

    def _detect_changed_entities(self, g1: Graph, g2: Graph) -> list[str]:
        """Detect entities that have changed between two graphs."""
        changes = set()

        for s, _p, _o in g1:
            if (s, _p, _o) not in g2 and isinstance(s, URIRef):
                changes.add(str(s))

        for s, _p, _o in g2:
            if (s, _p, _o) not in g1 and isinstance(s, URIRef):
                changes.add(str(s))

        return sorted(list(changes))[:50]

    def _analyze_namespace_changes(self, g1: Graph, g2: Graph) -> dict[str, dict[str, int]]:
        """Analyze changes in namespace usage."""
        ns_changes = {}

        ns_counts1 = self._get_namespace_counts(g1)
        ns_counts2 = self._get_namespace_counts(g2)

        all_namespaces = set(ns_counts1.keys()) | set(ns_counts2.keys())

        for ns in all_namespaces:
            count1 = ns_counts1.get(ns, 0)
            count2 = ns_counts2.get(ns, 0)

            if count1 != count2:
                ns_changes[ns] = {
                    "file1_count": count1,
                    "file2_count": count2,
                    "change": count2 - count1,
                }

        return ns_changes

    def _get_namespace_counts(self, graph: Graph) -> dict[str, int]:
        """Count triples by namespace."""
        ns_counts = {}

        for _s, _p, _o in graph:
            for entity in [_s, _o]:
                if isinstance(entity, URIRef):
                    ns = str(entity).split("#")[0].split("/")[0]
                    if "?" in ns:
                        ns = ns.split("?")[0]
                    ns_counts[ns] = ns_counts.get(ns, 0) + 1

        return ns_counts

    def compare_multiple_files(
        self, files: list[str], base_file: str | None = None
    ) -> list[ComparisonResult]:
        """Compare multiple files against a base file or sequentially."""
        results = []

        if base_file:
            for file in files:
                result = self.compare_files(base_file, file)
                results.append(result)
        else:
            for i in range(len(files) - 1):
                result = self.compare_files(files[i], files[i + 1])
                results.append(result)

        return results


def compare_ttl_files(file1: str, file2: str, output_format: str = "text") -> str:
    """Compare two TTL files and return results in specified format."""
    comparator = OutputComparator()
    result = comparator.compare_files(file1, file2)

    if output_format == "json":
        return json.dumps(result.to_dict(), indent=2)
    else:
        return _format_comparison_result(result)


def _format_comparison_result(result: ComparisonResult) -> str:
    """Format comparison result as human-readable text."""
    lines = [
        f"\n{'=' * 60}",
        f"Comparison: {result.file1} vs {result.file2}",
        f"{'=' * 60}",
        f"Overall Change Score: {result.overall_change_score:.2%}",
        "",
        "Triple Statistics:",
        f"  Added:   {result.added_triples}",
        f"  Removed: {result.removed_triples}",
        f"  Changed: {result.changed_triples}",
        f"  Common:  {result.common_triples}",
        "",
        "Entity Changes:",
        f"  Entities Added:   {len(result.entities_added)}",
        f"  Entities Removed: {len(result.entities_removed)}",
        f"  Entities Changed: {len(result.entities_changed)}",
    ]

    if result.namespace_changes:
        lines.append("")
        lines.append("Namespace Changes:")
        for ns, changes in list(result.namespace_changes.items())[:10]:
            change = "+" if changes["change"] > 0 else ""
            change_str = f"{change}{changes['change']}"
            lines.append(
                f"  {ns}: {changes['file1_count']} -> {changes['file2_count']} ({change_str})"
            )

    if result.entities_added:
        lines.append("")
        lines.append("Sample Added Entities:")
        for entity in result.entities_added[:5]:
            lines.append(f"  + {entity}")

    if result.entities_removed:
        lines.append("")
        lines.append("Sample Removed Entities:")
        for entity in result.entities_removed[:5]:
            lines.append(f"  - {entity}")

    if result.entities_changed:
        lines.append("")
        lines.append("Sample Changed Entities:")
        for entity in result.entities_changed[:5]:
            lines.append(f"  ~ {entity}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python compare_outputs.py <file1.ttl> <file2.ttl> [output_format]")
        print("  output_format: 'text' (default) or 'json'")
        sys.exit(1)

    file1 = sys.argv[1]
    file2 = sys.argv[2]
    output_format = sys.argv[3] if len(sys.argv) > 3 else "text"

    result = compare_ttl_files(file1, file2, output_format)
    print(result)
