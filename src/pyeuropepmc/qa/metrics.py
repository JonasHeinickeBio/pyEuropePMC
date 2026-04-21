"""
RDF data quality metrics module for PyEuropePMC TTL file validation.

This module provides comprehensive metrics calculation for RDF graphs,
including triple counts, entity analysis, property statistics, and data quality indicators.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import DCTERMS


@dataclass
class QualityMetrics:
    """Data quality metrics for an RDF graph."""

    # Basic counts
    total_triples: int = 0
    total_entities: int = 0
    total_properties: int = 0

    # Entity statistics
    entities_by_type: dict[str, int] = field(default_factory=dict)
    entities_by_namespace: dict[str, int] = field(default_factory=dict)

    # Property statistics
    properties_used: dict[str, int] = field(default_factory=dict)
    predicates_by_namespace: dict[str, int] = field(default_factory=dict)

    # Data quality indicators
    papers_with_title: int = 0
    papers_with_doi: int = 0
    papers_with_pmid: int = 0
    papers_with_pmcid: int = 0
    papers_with_authors: int = 0
    papers_with_abstract: int = 0

    # Duplicate detection
    duplicate_uris: list[str] = field(default_factory=list)
    duplicate_values: dict[str, list[str]] = field(default_factory=dict)

    # Missing fields
    missing_titles: list[str] = field(default_factory=list)
    missing_dois: list[str] = field(default_factory=list)
    missing_authors: list[str] = field(default_factory=list)

    # Namespace coverage
    used_namespaces: list[str] = field(default_factory=list)

    # Timestamp
    calculated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            "total_triples": self.total_triples,
            "total_entities": self.total_entities,
            "total_properties": self.total_properties,
            "entities_by_type": self.entities_by_type,
            "entities_by_namespace": self.entities_by_namespace,
            "properties_used": self.properties_used,
            "predicates_by_namespace": self.predicates_by_namespace,
            "papers_with_title": self.papers_with_title,
            "papers_with_doi": self.papers_with_doi,
            "papers_with_pmid": self.papers_with_pmid,
            "papers_with_pmcid": self.papers_with_pmcid,
            "papers_with_authors": self.papers_with_authors,
            "papers_with_abstract": self.papers_with_abstract,
            "duplicate_uris": self.duplicate_uris,
            "duplicate_values": self.duplicate_values,
            "missing_titles": self.missing_titles,
            "missing_dois": self.missing_dois,
            "missing_authors": self.missing_authors,
            "used_namespaces": self.used_namespaces,
            "calculated_at": self.calculated_at,
        }

    def to_json(self) -> str:
        """Convert metrics to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=2)

    def get_summary(self) -> str:
        """Get a human-readable summary of the metrics."""
        lines = [
            "=" * 60,
            "RDF Data Quality Metrics Summary",
            "=" * 60,
            f"Calculated at: {self.calculated_at}",
            "",
            "Basic Statistics:",
            f"  Total Triples:     {self.total_triples}",
            f"  Total Entities:    {self.total_entities}",
            f"  Total Properties:  {self.total_properties}",
            "",
            "Namespace Coverage:",
        ]
        for ns in self.used_namespaces[:10]:
            lines.append(f"  - {ns}")
        if len(self.used_namespaces) > 10:
            lines.append(f"  ... and {len(self.used_namespaces) - 10} more")

        lines.extend(
            [
                "",
                "Entity Types:",
            ]
        )
        for entity_type, count in sorted(self.entities_by_type.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"  - {entity_type}: {count}")

        lines.extend(
            [
                "",
                "Data Completeness:",
                f"  Papers with title:    {self.papers_with_title}",
                f"  Papers with DOI:      {self.papers_with_doi}",
                f"  Papers with PMID:     {self.papers_with_pmid}",
                f"  Papers with PMCID:    {self.papers_with_pmcid}",
                f"  Papers with authors:  {self.papers_with_authors}",
                f"  Papers with abstract: {self.papers_with_abstract}",
                "",
                "Data Quality Issues:",
                f"  Duplicate URIs:       {len(self.duplicate_uris)}",
                f"  Missing titles:       {len(self.missing_titles)}",
                f"  Missing DOIs:         {len(self.missing_dois)}",
                f"  Missing authors:      {len(self.missing_authors)}",
                "",
            ]
        )
        return "\n".join(lines)


class RDFMetricsCalculator:
    """Calculator for comprehensive RDF data quality metrics."""

    # Known paper entity types
    PAPER_TYPES = {
        "http://purl.org/ontology/bibo/AcademicArticle",
        "http://purl.org/ontology/bibo/Article",
        "http://purl.org/ontology/bibo/Document",
    }

    # Field predicates
    PREDICATES = {
        "title": DCTERMS.title,
        "doi": DCTERMS.identifier,
        "pmid": URIRef("https://w3id.org/pyeuropepmc/vocab#pmid"),
        "pmcid": URIRef("https://w3id.org/pyeuropepmc/vocab#pmcid"),
        "abstract": DCTERMS.abstract,
        "author": DCTERMS.creator,
        "subject": DCTERMS.subject,
        "issued": DCTERMS.issued,
    }

    def __init__(self, graph: Graph):
        """
        Initialize the metrics calculator.

        Args:
            graph: RDF graph to analyze
        """
        self.graph = graph
        self.metrics = QualityMetrics(calculated_at=datetime.now().isoformat())

    def calculate(self) -> QualityMetrics:
        """
        Calculate all metrics for the graph.

        Returns:
            QualityMetrics object with all calculated metrics
        """
        self._count_triples()
        self._analyze_entities()
        self._analyze_properties()
        self._calculate_completeness()
        self._detect_duplicates()
        self._find_missing_fields()
        self._extract_namespaces()

        return self.metrics

    def _count_triples(self) -> None:
        """Count total triples in the graph."""
        self.metrics.total_triples = len(self.graph)

    def _analyze_entities(self) -> None:
        """Analyze entities in the graph."""
        entities = set()
        entity_types = Counter()
        entity_namespaces = Counter()

        # Get all subjects (entities)
        for subject in self.graph.subjects():
            entities.add(subject)

            # Count entity types
            for obj in self.graph.objects(subject, RDF.type):
                entity_types[str(obj)] += 1
                entity_namespaces[self._get_namespace(str(obj))] += 1

        # Also count blank nodes
        for subject in self.graph.subjects(RDF.type, None):
            if isinstance(subject, URIRef):
                entity_namespaces[self._get_namespace(str(subject))] += 1

        self.metrics.total_entities = len(entities)
        self.metrics.entities_by_type = dict(entity_types)
        self.metrics.entities_by_namespace = dict(entity_namespaces)

    def _analyze_properties(self) -> None:
        """Analyze properties used in the graph."""
        properties = Counter()
        predicates_by_ns = Counter()

        for pred in self.graph.predicates():
            pred_str = str(pred)
            properties[pred_str] += 1
            predicates_by_ns[self._get_namespace(pred_str)] += 1

        self.metrics.total_properties = len(properties)
        self.metrics.properties_used = dict(properties)
        self.metrics.predicates_by_namespace = dict(predicates_by_ns)

    def _calculate_completeness(self) -> None:
        """Calculate data completeness metrics for papers."""
        papers = self._get_paper_entities()

        for paper in papers:
            if self._has_predicate(paper, DCTERMS.title):
                self.metrics.papers_with_title += 1

            if self._has_predicate(paper, DCTERMS.identifier):
                self.metrics.papers_with_doi += 1

            if self._has_predicate(paper, self.PREDICATES["pmid"]):
                self.metrics.papers_with_pmid += 1

            if self._has_predicate(paper, self.PREDICATES["pmcid"]):
                self.metrics.papers_with_pmcid += 1

            if self._has_predicate(paper, DCTERMS.creator):
                self.metrics.papers_with_authors += 1

            if self._has_predicate(paper, DCTERMS.abstract):
                self.metrics.papers_with_abstract += 1

    def _detect_duplicates(self) -> None:
        """Detect duplicate URIs and values."""
        # Check for duplicate URIs
        all_uris = [str(s) for s in self.graph.subjects() if isinstance(s, URIRef)]
        uri_counts = Counter(all_uris)
        self.metrics.duplicate_uris = [uri for uri, count in uri_counts.items() if count > 1]

        # Check for duplicate values in specific fields
        papers = self._get_paper_entities()

        # Check for duplicate titles
        titles = []
        for p in papers:
            if self._has_predicate(p, DCTERMS.title):
                for title in self.graph.objects(p, DCTERMS.title):
                    titles.append(str(title))
        title_counts = Counter(titles)
        self.metrics.duplicate_values["titles"] = [
            title for title, count in title_counts.items() if count > 1
        ]

    def _find_missing_fields(self) -> None:
        """Find papers with missing critical fields."""
        papers = self._get_paper_entities()

        for paper in papers:
            if not self._has_predicate(paper, DCTERMS.title):
                self.metrics.missing_titles.append(str(paper))

            if not self._has_predicate(paper, DCTERMS.identifier):
                self.metrics.missing_dois.append(str(paper))

            if not self._has_predicate(paper, DCTERMS.creator):
                self.metrics.missing_authors.append(str(paper))

    def _extract_namespaces(self) -> None:
        """Extract all used namespaces."""
        namespaces = set()

        for s in self.graph.subjects():
            if isinstance(s, URIRef):
                namespaces.add(self._get_namespace(str(s)))

        for p in self.graph.predicates():
            namespaces.add(self._get_namespace(str(p)))

        for o in self.graph.objects():
            if isinstance(o, URIRef):
                namespaces.add(self._get_namespace(str(o)))

        self.metrics.used_namespaces = sorted(list(namespaces))

    def _get_paper_entities(self) -> list[URIRef]:
        """Get all paper entities from the graph."""
        papers = []
        for paper_type in self.PAPER_TYPES:
            papers.extend(self.graph.subjects(RDF.type, URIRef(paper_type)))
        return list(set(papers))

    def _has_predicate(self, subject: URIRef, predicate: URIRef) -> bool:
        """Check if a subject has a specific predicate."""
        return (subject, predicate, None) in self.graph

    def _get_namespace(self, uri: str) -> str:
        """Extract namespace from URI."""
        if "#" in uri:
            return uri.split("#")[0] + "#"
        elif "/" in uri:
            return uri.rsplit("/", 1)[0] + "/"
        return uri


def calculate_metrics(ttl_file: str | Path) -> QualityMetrics:
    """
    Calculate metrics for a TTL file.

    Args:
        ttl_file: Path to the TTL file

    Returns:
        QualityMetrics object
    """
    graph = Graph()
    graph.parse(str(ttl_file), format="turtle")

    calculator = RDFMetricsCalculator(graph)
    return calculator.calculate()


def calculate_metrics_for_directory(directory: str | Path) -> dict[str, QualityMetrics]:
    """
    Calculate metrics for all TTL files in a directory.

    Args:
        directory: Path to directory containing TTL files

    Returns:
        Dictionary mapping filenames to their metrics
    """
    results = {}
    dir_path = Path(directory)

    for ttl_file in dir_path.glob("*.ttl"):
        metrics = calculate_metrics(ttl_file)
        results[ttl_file.name] = metrics

    return results
