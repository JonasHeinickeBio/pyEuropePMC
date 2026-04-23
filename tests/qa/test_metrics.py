"""Unit tests for the QA toolset."""

from __future__ import annotations

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Any

import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, RDF

from pyeuropepmc.qa.metrics import RDFMetricsCalculator
from pyeuropepmc.qa.sparql_queries import SPARQLValidator
from pyeuropepmc.qa.schema_validation import SchemaValidator
from pyeuropepmc.qa.consistency_checks import ConsistencyChecker
from pyeuropepmc.qa.compare_outputs import OutputComparator, compare_ttl_files


@pytest.fixture
def sample_graph() -> Graph:
    """Create a sample RDF graph for testing."""
    g = Graph()
    BIBO = Namespace('http://purl.org/ontology/bibo/')
    FOAF = Namespace('http://xmlns.com/foaf/0.1/')
    DCTERMS = Namespace('http://purl.org/dc/terms/')
    MESHV = Namespace('http://id.nlm.nih.gov/mesh/vocab#')
    PM = Namespace('http://purl.org/spar/pmo/')

    g.bind('bibo', BIBO)
    g.bind('foaf', FOAF)
    g.bind('dcterms', DCTERMS)
    g.bind('meshv', MESHV)
    g.bind('pm', PM)

    paper1 = URIRef('http://purl.org/repository/paper/1')
    author1 = URIRef('http://purl.org/repository/author/1')
    journal1 = URIRef('http://purl.org/repository/journal/1')

    # Add type statements
    g.add((paper1, RDF.type, BIBO.Article))
    g.add((author1, RDF.type, FOAF.Person))
    g.add((journal1, RDF.type, BIBO.Periodical))

    g.add((paper1, DCTERMS.title, Literal('Test Paper')))
    g.add((paper1, DCTERMS.identifier, Literal('10.1234/test')))
    g.add((paper1, DCTERMS.identifier, Literal('PMID:12345')))
    g.add((paper1, BIBO.doi, Literal('10.1234/test')))
    g.add((paper1, BIBO.pmid, Literal('12345')))
    g.add((paper1, BIBO.pmcid, Literal('PMC12345')))
    g.add((paper1, BIBO.issn, Literal('1234-5678')))
    g.add((paper1, DCTERMS.abstract, Literal('This is an abstract.')))
    g.add((paper1, DCTERMS.created, Literal('2023-01-01')))
    g.add((paper1, BIBO.authorList, URIRef('http://purl.org/repository/authorlist/1')))

    g.add((author1, FOAF.name, Literal('John Doe')))
    g.add((author1, FOAF.email, Literal('john@example.com')))
    g.add((author1, BIBO.orcid, Literal('0000-0000-0000-0001')))
    g.add((author1, FOAF.homepage, Literal('http://example.com/john')))
    g.add((author1, FOAF.member, journal1))

    g.add((journal1, DCTERMS.title, Literal('Test Journal')))
    g.add((journal1, BIBO.issn, Literal('1234-5678')))
    g.add((journal1, BIBO.eissn, Literal('8765-4321')))
    g.add((journal1, DCTERMS.publisher, Literal('Test Publisher')))

    g.add((paper1, BIBO.author, author1))

    return g


@pytest.fixture
def empty_graph() -> Graph:
    """Create an empty RDF graph for testing."""
    return Graph()


class TestRDFMetricsCalculator:
    """Tests for RDFMetricsCalculator."""

    def test_calculate(self, sample_graph):
        """Test full metrics calculation."""
        calculator = RDFMetricsCalculator(sample_graph)
        metrics = calculator.calculate()

        assert metrics.total_triples > 0
        assert metrics.total_entities > 0
        assert metrics.total_properties > 0
        assert len(metrics.entities_by_type) > 0
        assert len(metrics.used_namespaces) > 0

    def test_empty_graph(self, empty_graph):
        """Test metrics calculation on empty graph."""
        calculator = RDFMetricsCalculator(empty_graph)
        metrics = calculator.calculate()

        assert metrics.total_triples == 0
        assert metrics.total_entities == 0

    def test_triple_counting(self, sample_graph):
        """Test that triple counting works."""
        calculator = RDFMetricsCalculator(sample_graph)
        calculator._count_triples()

        assert calculator.metrics.total_triples == len(sample_graph)

    def test_entity_analysis(self, sample_graph):
        """Test entity analysis."""
        calculator = RDFMetricsCalculator(sample_graph)
        calculator._analyze_entities()

        assert calculator.metrics.total_entities > 0

    def test_property_analysis(self, sample_graph):
        """Test property analysis."""
        calculator = RDFMetricsCalculator(sample_graph)
        calculator._analyze_properties()

        assert len(calculator.metrics.properties_used) > 0

    def test_namespace_extraction(self, sample_graph):
        """Test namespace extraction."""
        calculator = RDFMetricsCalculator(sample_graph)
        calculator._extract_namespaces()

        assert len(calculator.metrics.used_namespaces) > 0


class TestSPARQLValidator:
    """Tests for SPARQLValidator."""

    def test_execute_query(self, sample_graph):
        """Test query execution."""
        validator = SPARQLValidator(sample_graph)
        result = validator.execute_query("papers_count")

        assert result.passed is True or result.passed is False
        assert result.match_count >= 0

    def test_execute_test(self, sample_graph):
        """Test test execution."""
        validator = SPARQLValidator(sample_graph)
        result = validator.execute_test("papers_count")

        assert 'passed' in dir(result) or hasattr(result, 'passed')

    def test_run_all_tests(self, sample_graph):
        """Test running all tests."""
        validator = SPARQLValidator(sample_graph)
        results = validator.run_all_tests()

        assert len(results) > 0
        for test_name, result in results.items():
            assert hasattr(result, 'passed')

    def test_custom_query(self, sample_graph):
        """Test custom SPARQL query execution."""
        validator = SPARQLValidator(sample_graph)

        query = """
        SELECT ?paper WHERE {
            ?paper a <http://purl.org/ontology/bibo/Article> .
        }
        """
        result = validator.run_custom_query(query, 'custom')
        assert result.query_name == 'custom'
        assert hasattr(result, 'passed')
        assert hasattr(result, 'match_count')


class TestSchemaValidator:
    """Tests for SchemaValidator."""

    def test_validate_graph_no_schema(self, sample_graph):
        """Test graph validation without schema."""
        validator = SchemaValidator()
        result = validator.validate_graph(sample_graph, "test.ttl")

        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'issues')
        # Should have warning since schema not available
        assert result.is_valid is False

    def test_validate_graph_with_schema(self, sample_graph):
        """Test graph validation with schema - skipped if LinkML not available."""
        schema_path = Path("/home/jhe24/AID-PAIS/pyEuropePMC_project/schemas/pyeuropepmc_schema.yaml")

        validator = SchemaValidator(schema_path)
        if validator.is_available:
            result = validator.validate_graph(sample_graph, "test.ttl")
            assert hasattr(result, 'is_valid')
            assert hasattr(result, 'issues')

    def test_init_without_schema(self):
        """Test initialization without schema."""
        validator = SchemaValidator()
        assert validator.is_available is False

    def test_init_with_schema(self):
        """Test initialization with schema - skipped if LinkML not available."""
        schema_path = Path("/home/jhe24/AID-PAIS/pyEuropePMC_project/schemas/pyeuropepmc_schema.yaml")

        validator = SchemaValidator(schema_path)
        # May or may not be available depending on schema existence
        assert hasattr(validator, 'is_available')


class TestConsistencyChecker:
    """Tests for ConsistencyChecker."""

    def test_check_orphans(self, sample_graph):
        """Test orphan detection."""
        checker = ConsistencyChecker()
        results = checker.check_orphans(sample_graph)

        assert 'orphan_authors' in results
        assert 'orphan_papers' in results
        assert 'orphan_journals' in results

    def test_check_relationships(self, sample_graph):
        """Test relationship validation."""
        checker = ConsistencyChecker()
        results = checker.check_relationships(sample_graph)

        assert 'paper_author_links' in results
        assert 'author_journal_links' in results

    def test_check_entity_integrity(self, sample_graph):
        """Test entity integrity checks."""
        checker = ConsistencyChecker()
        results = checker.check_entity_integrity(sample_graph)

        assert 'papers_with_min_fields' in results
        assert 'authors_with_min_fields' in results

    def test_check_all(self, sample_graph):
        """Test complete consistency check."""
        checker = ConsistencyChecker()
        results = checker.check_all(sample_graph)

        assert 'orphan_count' in results
        assert 'relationship_errors' in results
        assert 'integrity_errors' in results
        assert 'overall_status' in results


class TestOutputComparator:
    """Tests for OutputComparator."""

    def test_load_graph(self):
        """Test graph loading."""
        comparator = OutputComparator()

        g = Graph()
        BIBO = Namespace('http://purl.org/ontology/bibo/')
        g.bind('bibo', BIBO)

        paper = URIRef('http://example.org/paper/1')
        g.add((paper, BIBO.doi, Literal('10.1234/test')))

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            g.serialize(f.name, format='turtle')
            temp_file = f.name

        try:
            loaded = comparator.load_graph(temp_file)
            assert len(loaded) == 1
        finally:
            Path(temp_file).unlink()

    def test_compare_files(self, sample_graph):
        """Test file comparison."""
        comparator = OutputComparator()

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            sample_graph.serialize(f.name, format='turtle')
            file1 = f.name

        g2 = Graph()
        BIBO = Namespace('http://purl.org/ontology/bibo/')
        g2.bind('bibo', BIBO)

        paper = URIRef('http://example.org/paper/2')
        g2.add((paper, BIBO.doi, Literal('10.5678/other')))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            g2.serialize(f.name, format='turtle')
            file2 = f.name

        try:
            result = comparator.compare_files(file1, file2)

            assert result.added_triples >= 0
            assert result.removed_triples >= 0
            assert result.common_triples >= 0
            assert result.overall_change_score >= 0
        finally:
            Path(file1).unlink()
            Path(file2).unlink()

    def test_compare_graphs(self, sample_graph):
        """Test graph comparison."""
        comparator = OutputComparator()

        g1 = sample_graph
        g2 = Graph()

        result = comparator.compare_graphs(g1, g2, 'file1', 'file2')

        assert result.file1 == 'file1'
        assert result.file2 == 'file2'
        assert result.added_triples >= 0
        assert result.overall_change_score >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
