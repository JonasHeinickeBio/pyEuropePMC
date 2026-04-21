"""Consistency checking module for TTL files."""

from dataclasses import dataclass
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF


@dataclass
class ConsistencyResult:
    """Result of consistency checking."""

    orphan_count: int
    orphan_details: list[dict[str, Any]]
    relationship_errors: int
    relationship_error_details: list[dict[str, Any]]
    integrity_errors: int
    integrity_error_details: list[dict[str, Any]]
    overall_status: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "orphan_count": self.orphan_count,
            "orphan_details": self.orphan_details[:10],  # Limit to first 10
            "relationship_errors": self.relationship_errors,
            "relationship_error_details": self.relationship_error_details[:10],
            "integrity_errors": self.integrity_errors,
            "integrity_error_details": self.integrity_error_details[:10],
            "overall_status": self.overall_status,
        }


class ConsistencyChecker:
    """Check data consistency in RDF graphs."""

    def __init__(self):
        """Initialize the consistency checker."""
        # Define expected namespaces
        self.namespaces = {
            "bibo": Namespace("http://purl.org/ontology/bibo/"),
            "foaf": Namespace("http://xmlns.com/foaf/0.1/"),
            "dcterms": Namespace("http://purl.org/dc/terms/"),
            "meshv": Namespace("http://id.nlm.nih.gov/mesh/vocab#"),
            "pm": Namespace("http://purl.org/spar/pmo/"),
            "owl": Namespace("http://www.w3.org/2002/07/owl#"),
        }

        # Define entity type mappings
        self.entity_types = {
            "paper": [
                "http://purl.org/ontology/bibo/Article",
                "http://purl.org/spar/pmo/Paper",
                "http://purl.org/dc/terms/BibliographicResource",
            ],
            "author": [
                "http://xmlns.com/foaf/0.1/Person",
                "http://purl.org/spar/pmo/Author",
            ],
            "journal": [
                "http://purl.org/ontology/bibo/Periodical",
                "http://purl.org/spar/pmo/Journal",
                "http://xmlns.com/foaf/0.1/Project",
            ],
            "publisher": [
                "http://xmlns.com/foaf/0.1/Organization",
                "http://purl.org/spar/pmo/Publisher",
            ],
        }

    def check_all(self, graph: Graph) -> dict[str, Any]:
        """Run all consistency checks."""
        orphans = self.check_orphans(graph)
        relationships = self.check_relationships(graph)
        integrity = self.check_entity_integrity(graph)

        total_orphans = (
            len(orphans["orphan_authors"])
            + len(orphans["orphan_papers"])
            + len(orphans["orphan_journals"])
        )

        total_relationship_errors = (
            relationships["paper_author_links"]["errors"]
            + relationships["author_journal_links"]["errors"]
            + relationships["other_relationships"]["errors"]
        )

        total_integrity_errors = (
            integrity["papers_with_min_fields"]["errors"]
            + integrity["authors_with_min_fields"]["errors"]
            + integrity["journals_with_min_fields"]["errors"]
        )

        overall_status = "passed"
        if total_orphans > 10:
            overall_status = "failed"
        elif total_orphans > 0 or total_relationship_errors > 0:
            overall_status = "warning"

        return ConsistencyResult(
            orphan_count=total_orphans,
            orphan_details=self._format_orphan_details(orphans),
            relationship_errors=total_relationship_errors,
            relationship_error_details=self._format_relationship_details(relationships),
            integrity_errors=total_integrity_errors,
            integrity_error_details=self._format_integrity_details(integrity),
            overall_status=overall_status,
        ).to_dict()

    def check_orphans(self, graph: Graph) -> dict[str, list[URIRef]]:
        """Check for orphaned entities."""
        orphans = {"orphan_authors": [], "orphan_papers": [], "orphan_journals": []}

        # Find papers
        paper_uris = self._get_entities_by_type(graph, "paper")

        # Find authors
        author_uris = self._get_entities_by_type(graph, "author")

        # Find journals
        journal_uris = self._get_entities_by_type(graph, "journal")

        # Check for orphan papers (no authors, no journals)
        for paper in paper_uris:
            has_author = self._has_relationship(graph, paper, "bibo:author")
            has_journal = self._has_relationship(graph, paper, "bibo:isDocumentOf")

            if not has_author and not has_journal:
                orphans["orphan_papers"].append(paper)

        # Check for orphan authors (no papers)
        for author in author_uris:
            has_paper = self._has_relationship(graph, author, "bibo:author")

            if not has_paper:
                orphans["orphan_authors"].append(author)

        # Check for orphan journals (no papers)
        for journal in journal_uris:
            has_paper = self._has_relationship(graph, journal, "bibo:isDocumentOf")

            if not has_paper:
                orphans["orphan_journals"].append(journal)

        return orphans

    def check_relationships(self, graph: Graph) -> dict[str, dict[str, Any]]:
        """Check relationship validity."""
        relationships = {
            "paper_author_links": {"count": 0, "errors": 0},
            "author_journal_links": {"count": 0, "errors": 0},
            "other_relationships": {"count": 0, "errors": 0},
        }

        # Check paper-author relationships
        for paper in self._get_entities_by_type(graph, "paper"):
            authors = list(graph.objects(paper, self.namespaces["bibo"].author))
            relationships["paper_author_links"]["count"] += len(authors)

            for author in authors:
                if not self._is_valid_entity(graph, author):
                    relationships["paper_author_links"]["errors"] += 1

        # Check author-journal relationships
        for author in self._get_entities_by_type(graph, "author"):
            journals = list(graph.objects(author, self.namespaces["foaf"].member))
            relationships["author_journal_links"]["count"] += len(journals)

            for journal in journals:
                if not self._is_valid_entity(graph, journal):
                    relationships["author_journal_links"]["errors"] += 1

        # Check other relationships
        for _s, _p, _o in graph:
            if not self._is_valid_uri(_o) and not isinstance(_o, Literal):
                relationships["other_relationships"]["errors"] += 1

        return relationships

    def check_entity_integrity(self, graph: Graph) -> dict[str, dict[str, Any]]:
        """Check entity field integrity."""
        integrity = {
            "papers_with_min_fields": {"count": 0, "errors": 0},
            "authors_with_min_fields": {"count": 0, "errors": 0},
            "journals_with_min_fields": {"count": 0, "errors": 0},
        }

        # Check papers
        required_paper_fields = [
            "dcterms:title",
            "dcterms:identifier",
            "bibo:doi",
        ]

        for paper in self._get_entities_by_type(graph, "paper"):
            integrity["papers_with_min_fields"]["count"] += 1

            missing = self._check_missing_fields(graph, paper, required_paper_fields)

            if missing:
                integrity["papers_with_min_fields"]["errors"] += 1

        # Check authors
        required_author_fields = [
            "foaf:name",
        ]

        for author in self._get_entities_by_type(graph, "author"):
            integrity["authors_with_min_fields"]["count"] += 1

            missing = self._check_missing_fields(graph, author, required_author_fields)

            if missing:
                integrity["authors_with_min_fields"]["errors"] += 1

        # Check journals
        required_journal_fields = [
            "dcterms:title",
            "bibo:issn",
        ]

        for journal in self._get_entities_by_type(graph, "journal"):
            integrity["journals_with_min_fields"]["count"] += 1

            missing = self._check_missing_fields(graph, journal, required_journal_fields)

            if missing:
                integrity["journals_with_min_fields"]["errors"] += 1

        return integrity

    def _get_entities_by_type(self, graph: Graph, entity_type: str) -> list[URIRef]:
        """Get entities of a specific type."""
        entities = set()

        if entity_type in self.entity_types:
            for type_uri in self.entity_types[entity_type]:
                for _s, _p, _o in graph.triples((None, RDF.type, URIRef(type_uri))):
                    if isinstance(_s, URIRef):
                        entities.add(_s)

        return list(entities)

    def _has_relationship(self, graph: Graph, subject: URIRef, predicate: str) -> bool:
        """Check if subject has a specific relationship."""
        ns, pred = predicate.split(":")
        predicate_uri = self.namespaces[ns][pred]

        return any(True for _s, _p, _o in graph.triples((subject, predicate_uri, None)))

    def _is_valid_entity(self, graph: Graph, entity: URIRef) -> bool:
        """Check if entity is valid."""
        if not isinstance(entity, URIRef):
            return False

        return any(s == entity for s, _p, _o in graph)

    def _is_valid_uri(self, entity: Any) -> bool:
        """Check if entity is a valid URI."""
        return isinstance(entity, URIRef)

    def _check_missing_fields(
        self, graph: Graph, entity: URIRef, required_fields: list[str]
    ) -> list[str]:
        """Check for missing required fields."""
        missing = []

        for field in required_fields:
            ns, pred = field.split(":")
            field_uri = self.namespaces[ns][pred]

            has_field = any(True for s, p, o in graph.triples((entity, field_uri, None)))

            if not has_field:
                missing.append(field)

        return missing

    def _format_orphan_details(self, orphans: dict[str, list[URIRef]]) -> list[dict[str, Any]]:
        """Format orphan details for output."""
        details = []

        for entity_type, entities in orphans.items():
            for entity in entities[:5]:  # Limit to first 5
                details.append({"type": entity_type, "entity": str(entity)})

        return details

    def _format_relationship_details(
        self, relationships: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Format relationship error details."""
        details = []

        for relationship_type, data in relationships.items():
            if data["errors"] > 0:
                details.append({"relationship": relationship_type, "errors": data["errors"]})

        return details

    def _format_integrity_details(
        self, integrity: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Format integrity error details."""
        details = []

        for entity_type, data in integrity.items():
            if data["errors"] > 0:
                details.append(
                    {"entity_type": entity_type, "total": data["count"], "errors": data["errors"]}
                )

        return details


if __name__ == "__main__":
    import sys

    from rdflib import Graph

    if len(sys.argv) < 2:
        print("Usage: python consistency_checks.py <file.ttl>")
        sys.exit(1)

    ttl_file = sys.argv[1]

    graph = Graph()
    graph.parse(ttl_file, format="turtle")

    checker = ConsistencyChecker()
    results = checker.check_all(graph)

    print("\nConsistency Check Results:")
    print(f"  Orphan count: {results['orphan_count']}")
    print(f"  Relationship errors: {results['relationship_errors']}")
    print(f"  Integrity errors: {results['integrity_errors']}")
    print(f"  Overall status: {results['overall_status']}")
