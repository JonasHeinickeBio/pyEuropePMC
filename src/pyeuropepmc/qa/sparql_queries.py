"""
SPARQL query module for PyEuropePMC TTL file validation.

This module provides predefined SPARQL queries for validating RDF data structure
and content against expected patterns and relationships.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import Graph


@dataclass
class QueryResult:
    """Result of a SPARQL query execution."""

    query_name: str
    query_text: str
    passed: bool
    results: list[dict[str, Any]]
    error: str | None = None
    match_count: int = 0
    expected_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "query_name": self.query_name,
            "query_text": self.query_text,
            "passed": self.passed,
            "results": self.results,
            "error": self.error,
            "match_count": self.match_count,
            "expected_count": self.expected_count,
        }

    def to_json(self) -> str:
        """Convert result to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=2)


class SPARQLQueries:
    """Collection of predefined SPARQL queries for validation."""

    @staticmethod
    def get_all_queries() -> dict[str, str]:
        """Get all predefined queries."""
        return {
            "papers_count": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX pyeuropepmc: <https://w3id.org/pyeuropepmc/vocab#>

                SELECT (COUNT(?paper) AS ?count)
                WHERE {
                    ?paper a bibo:AcademicArticle .
                }
            """,
            "papers_with_doi": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX dcterms: <http://purl.org/dc/terms/>

                SELECT ?paper ?doi
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           dcterms:identifier ?doi .
                }
                LIMIT 10
            """,
            "papers_with_pmid": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX pyeuropepmc: <https://w3id.org/pyeuropepmc/vocab#>

                SELECT ?paper ?pmid
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           pyeuropepmc:pmid ?pmid .
                }
                LIMIT 10
            """,
            "papers_with_pmcid": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX pyeuropepmc: <https://w3id.org/pyeuropepmc/vocab#>

                SELECT ?paper ?pmcid
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           pyeuropepmc:pmcid ?pmcid .
                }
                LIMIT 10
            """,
            "authors_count": """
                PREFIX foaf: <http://xmlns.com/foaf/0.1/>

                SELECT (COUNT(DISTINCT ?author) AS ?count)
                WHERE {
                    ?author a foaf:Person .
                }
            """,
            "papers_with_authors": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX dcterms: <http://purl.org/dc/terms/>

                SELECT ?paper (COUNT(?author) AS ?authorCount)
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           dcterms:creator ?author .
                }
                GROUP BY ?paper
                ORDER BY DESC(?authorCount)
                LIMIT 10
            """,
            "papers_with_keywords": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX dcterms: <http://purl.org/dc/terms/>

                SELECT ?paper (COUNT(?keyword) AS ?keywordCount)
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           dcterms:subject ?keyword .
                }
                GROUP BY ?paper
                ORDER BY DESC(?keywordCount)
                LIMIT 10
            """,
            "papers_with_abstract": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX dcterms: <http://purl.org/dc/terms/>

                SELECT ?paper
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           dcterms:abstract ?abstract .
                }
                LIMIT 10
            """,
            "journals_count": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>

                SELECT (COUNT(DISTINCT ?journal) AS ?count)
                WHERE {
                    ?journal a bibo:Journal .
                }
            """,
            "papers_with_journals": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>

                SELECT ?paper ?journal
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           bibo:journal ?journal .
                }
                LIMIT 10
            """,
            "orphaned_authors": """
                PREFIX foaf: <http://xmlns.com/foaf/0.1/>
                PREFIX dcterms: <http://purl.org/dc/terms/>

                SELECT ?author
                WHERE {
                    ?author a foaf:Person .
                    FILTER NOT EXISTS {
                        ?paper dcterms:creator ?author .
                    }
                }
            """,
            "orphaned_journals": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>

                SELECT ?journal
                WHERE {
                    ?journal a bibo:Journal .
                    FILTER NOT EXISTS {
                        ?paper bibo:journal ?journal .
                    }
                }
            """,
            "papers_with_sameas": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>

                SELECT ?paper ?sameAs
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           owl:sameAs ?sameAs .
                }
                LIMIT 10
            """,
            "papers_with_provenance": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX prov: <http://www.w3.org/ns/prov#>

                SELECT ?paper ?timestamp ?generator
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           prov:generatedAtTime ?timestamp ;
                           prov:wasGeneratedBy ?generator .
                }
                LIMIT 10
            """,
            "duplicate_papers_by_title": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX dcterms: <http://purl.org/dc/terms/>

                SELECT ?title (COUNT(?paper) AS ?count)
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           dcterms:title ?title .
                }
                GROUP BY ?title
                HAVING (?count > 1)
            """,
            "invalid_dates": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX dcterms: <http://purl.org/dc/terms/>
                PREFIX xsd: <http://www.w3.org/2001/XMLSchema#

                SELECT ?paper ?date
                WHERE {
                    ?paper a bibo:AcademicArticle ;
                           dcterms:issued ?date .
                    FILTER(!isLiteral(?date) || !datatype(?date) = xsd:gYear)
                }
            """,
            "namespace_coverage": """
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                SELECT ?namespace (COUNT(DISTINCT ?subject) AS ?count)
                WHERE {
                    ?subject ?predicate ?object .
                    BIND(URI(Concat(SubStr(STR(?subject), 1,
                        If(Contains(STR(?subject), "#"),
                            StrPos(STR(?subject), "#") - 1,
                            Len(STR(?subject))
                        )
                    ))) AS ?namespace)
                }
                GROUP BY ?namespace
                ORDER BY DESC(?count)
                LIMIT 10
            """,
            "entity_type_distribution": """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

                SELECT ?type (COUNT(DISTINCT ?entity) AS ?count)
                WHERE {
                    ?entity rdf:type ?type .
                }
                GROUP BY ?type
                ORDER BY DESC(?count)
            """,
            "literal_types": """
                PREFIX xsd: <http://www.w3.org/2001/XMLSchema#

                SELECT ?type (COUNT(?literal) AS ?count)
                WHERE {
                    ?s ?p ?literal .
                    FILTER(isLiteral(?literal))
                    BIND(datatype(?literal) AS ?type)
                }
                GROUP BY ?type
                ORDER BY DESC(?count)
            """,
            "blank_node_usage": """
                SELECT (COUNT(DISTINCT ?blank) AS ?count)
                WHERE {
                    ?blank ?p ?o .
                    FILTER(isBlank(?blank))
                }
            """,
            " papers_with_complete_metadata": """
                PREFIX bibo: <http://purl.org/ontology/bibo/>
                PREFIX dcterms: <http://purl.org/dc/terms/>
                PREFIX pyeuropepmc: <https://w3id.org/pyeuropepmc/vocab#>

                SELECT ?paper
                WHERE {
                    ?paper a bibo:AcademicArticle .
                    ?paper dcterms:title ?title .
                    ?paper dcterms:creator ?author .
                    ?paper pyeuropepmc:pmid ?pmid .
                }
                LIMIT 10
            """,
            "cito_citations": """
                PREFIX cito: <http://purl.org/spar/cito/>

                SELECT ?paper ?citation ?citationType
                WHERE {
                    ?paper cito:?citationType ?citation .
                }
                LIMIT 10
            """,
        }


class SPARQLValidator:
    """Run SPARQL queries against RDF graphs."""

    def __init__(self, graph: Graph) -> None:
        """Initialize the validator with an RDF graph."""
        self.graph = graph
        self.queries = SPARQLQueries()

    def execute_query(self, query_name: str, query_text: str | None = None) -> QueryResult:
        """
        Execute a SPARQL query.

        Args:
            query_name: Name of the query to execute
            query_text: Optional custom query text

        Returns:
            QueryResult object
        """
        if query_text is None:
            query_text = self.queries.get_all_queries().get(query_name)
            if query_text is None:
                return QueryResult(
                    query_name=query_name,
                    query_text="",
                    passed=False,
                    results=[],
                    error=f"Unknown query: {query_name}",
                )

        try:
            results = self.graph.query(query_text)

            # Convert results to list of dictionaries
            result_list = []
            for row in results:
                row_dict = {}
                for var in results.vars:
                    value = row[var]
                    if hasattr(value, "n3"):
                        row_dict[str(var)] = value.n3(self.graph.namespace_manager)
                    else:
                        row_dict[str(var)] = str(value)
                result_list.append(row_dict)

            return QueryResult(
                query_name=query_name,
                query_text=query_text,
                passed=True,
                results=result_list,
                match_count=len(result_list),
            )
        except Exception as e:
            return QueryResult(
                query_name=query_name,
                query_text=query_text,
                passed=False,
                results=[],
                error=str(e),
            )

    def execute_test(self, test_name: str, expected_count: int | None = None) -> QueryResult:
        """
        Execute a predefined test query.

        Args:
            test_name: Name of the test query
            expected_count: Optional expected result count for validation

        Returns:
            QueryResult object with validation status
        """
        result = self.execute_query(test_name)

        if expected_count is not None:
            result.expected_count = expected_count
            result.passed = result.passed and result.match_count == expected_count

        return result

    def run_custom_query(self, query_text: str, query_name: str) -> QueryResult:
        """
        Execute a custom SPARQL query.

        Args:
            query_text: The SPARQL query text
            query_name: Name for the query

        Returns:
            QueryResult object
        """
        return self.execute_query(query_name, query_text)

    def run_all_tests(self) -> dict[str, QueryResult]:
        """
        Run all predefined validation tests.

        Returns:
            Dictionary mapping test names to results
        """
        tests = [
            "papers_count",
            "papers_with_doi",
            "papers_with_pmid",
            "papers_with_pmcid",
            "authors_count",
            "papers_with_authors",
            "papers_with_keywords",
            "papers_with_abstract",
            "journals_count",
            "papers_with_journals",
            "papers_with_sameas",
            "papers_with_provenance",
            "entity_type_distribution",
            "literal_types",
            "cito_citations",
        ]

        results = {}
        for test in tests:
            results[test] = self.execute_test(test)

        return results


def validate_with_sparql(
    ttl_file: str | Path, test_names: list[str] | None = None
) -> dict[str, QueryResult]:
    """
    Validate a TTL file using SPARQL queries.

    Args:
        ttl_file: Path to the TTL file
        test_names: Optional list of specific tests to run

    Returns:
        Dictionary mapping test names to results
    """
    graph = Graph()
    graph.parse(str(ttl_file), format="turtle")

    validator = SPARQLValidator(graph)

    if test_names:
        results = {}
        for test in test_names:
            results[test] = validator.execute_test(test)
        return results

    return validator.run_all_tests()
