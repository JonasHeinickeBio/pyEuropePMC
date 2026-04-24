"""Functional tests for RDF mapping performance and scalability."""

import time

import pytest
from rdflib import Graph

from pyeuropepmc.mappers import RDFMapper
from pyeuropepmc.models import PaperEntity, AuthorEntity, InstitutionEntity


class TestRDFPerformanceAndScalability:
    """Performance and scalability tests for RDF mapping."""

    @pytest.fixture
    def mapper(self):
        """RDF mapper fixture."""
        return RDFMapper()

    @pytest.fixture
    def performance_paper_batch(self):
        """Generate a batch of papers for performance testing."""
        papers = []
        for i in range(100):
            paper = PaperEntity(
                pmcid=f"PMC{i:07d}",
                doi=f"10.1234/perf.{2024:04d}.{i:04d}",
                title=f"Performance Test Paper {i}",
                abstract=f"This is performance test paper number {i} with some content.",
                keywords=[f"perf_keyword_{i}", f"test_topic_{i}", f"benchmark_{i}"],
                publication_year=2024,
                journal="Performance Test Journal",
                citation_count=i * 5,
                is_oa=True,
            )
            papers.append(paper)
        return papers

    @pytest.fixture
    def scalability_entities(self):
        """Generate a comprehensive set of entities for scalability testing."""
        # Create institutions
        institutions = []
        for i in range(20):
            inst = InstitutionEntity(
                display_name=f"University {i}",
                ror_id=f"https://ror.org/{i:06d}",
                country="Test Country",
                city=f"City {i}",
            )
            institutions.append(inst)

        # Create authors affiliated with institutions
        authors = []
        for i in range(50):
            author = AuthorEntity(
                full_name=f"Author {i}",
                orcid=f"0000-000{i:04d}-{i:04d}-{i:04d}-{i:04d}",
                email=f"author{i}@test.edu",
                affiliation_text=f"Department at University {i % 20}",
            )
            authors.append(author)

        # Create papers with authors
        papers = []
        for i in range(30):
            paper = PaperEntity(
                pmcid=f"PMC{i+1000:07d}",
                doi=f"10.1234/scale.{2024:04d}.{i:04d}",
                title=f"Scalability Test Paper {i}",
                keywords=[f"scale_kw_{j}" for j in range(5)],
                publication_year=2024,
                citation_count=i * 10,
            )
            papers.append(paper)

        return {
            "institutions": institutions,
            "authors": authors,
            "papers": papers,
        }

    def test_rdf_conversion_performance(self, mapper, performance_paper_batch):
        """Test performance of RDF conversion for multiple papers."""
        start_time = time.time()

        g = Graph()
        for paper in performance_paper_batch:
            paper.to_rdf(g, mapper=mapper)

        end_time = time.time()
        conversion_time = end_time - start_time

        # Performance assertions
        assert len(g) >= 1800  # Should have substantial triples
        assert conversion_time < 5.0  # Should complete within 5 seconds

        # Calculate performance metrics
        triples_per_second = len(g) / conversion_time
        assert triples_per_second > 500  # Reasonable performance threshold

        print(f"Converted {len(performance_paper_batch)} papers in {conversion_time:.2f}s")
        print(f"Generated {len(g)} triples ({triples_per_second:.0f} triples/second)")

    def test_memory_usage_scaling(self, mapper, scalability_entities):
        """Test memory usage scaling with complex entity relationships."""
        g = Graph()

        institutions = scalability_entities["institutions"]
        authors = scalability_entities["authors"]
        papers = scalability_entities["papers"]

        # Convert all institutions
        inst_uris = {}
        for inst in institutions:
            uri = inst.to_rdf(g, mapper=mapper)
            inst_uris[inst.display_name] = uri

        # Convert all authors and link to institutions
        author_uris = {}
        for author in authors:
            uri = author.to_rdf(g, mapper=mapper)
            author_uris[author.full_name] = uri

            # Link author to institution
            inst_name = author.affiliation_text.replace("Department at ", "")
            if inst_name in inst_uris:
                mapper.map_relationships(g, uri, author, {"institutions": [institutions[int(inst_name.split()[-1])]]})

        # Convert all papers and link to authors
        paper_uris = {}
        for paper in papers:
            uri = paper.to_rdf(g, mapper=mapper)
            paper_uris[paper.title] = uri

            # Link to random subset of authors (1-3 authors per paper)
            import random
            num_authors = random.randint(1, 3)
            selected_authors = random.sample(authors, num_authors)
            mapper.map_relationships(g, uri, paper, {"authors": selected_authors})

        # Performance metrics
        total_entities = len(institutions) + len(authors) + len(papers)
        total_triples = len(g)

        print(f"Processed {total_entities} entities")
        print(f"Generated {total_triples} triples")
        print(".1f")

        # Scalability assertions
        assert total_triples > 1000  # Substantial graph
        assert total_triples / total_entities > 10  # Good triple density

        # Verify relationship integrity
        relationship_count = 0
        for s, p, o in g:
            if str(p) in ["http://purl.org/dc/terms/creator", "http://www.w3.org/ns/org#memberOf"]:
                relationship_count += 1

        assert relationship_count > 50  # Should have many relationships

    def test_batch_processing_throughput(self, mapper, performance_paper_batch):
        """Test throughput of batch processing operations."""
        import tempfile
        from pathlib import Path

        # Prepare batch data
        entities_data = {}
        for i, paper in enumerate(performance_paper_batch[:20]):  # Test with subset
            entities_data[f"perf_paper_{i}"] = {"entity": paper}

        start_time = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:
            results = mapper.convert_and_save_entities_to_rdf(
                entities_data,
                output_dir=tmpdir,
                prefix="throughput_"
            )

        end_time = time.time()
        batch_time = end_time - start_time

        # Throughput metrics
        files_created = len(results)
        total_triples = sum(len(graph) for graph in results.values())

        print(f"Batch processed {files_created} entities in {batch_time:.2f}s")
        print(f"Created {total_triples} total triples")
        print(".1f")
        print(".1f")

        # Performance assertions
        assert batch_time < 2.0  # Should complete quickly
        assert files_created == 20  # All entities processed
        assert total_triples > 200  # Substantial content

    def test_graph_query_performance(self, mapper, scalability_entities):
        """Test performance of querying the generated RDF graph."""
        g = Graph()

        # Build comprehensive graph
        papers = scalability_entities["papers"]
        authors = scalability_entities["authors"]

        paper_uris = []
        for paper in papers[:10]:  # Test subset
            uri = paper.to_rdf(g, mapper=mapper)
            paper_uris.append(uri)

        author_uris = []
        for author in authors[:20]:  # Test subset
            uri = author.to_rdf(g, mapper=mapper)
            author_uris.append(uri)

        # Add relationships
        for i, paper_uri in enumerate(paper_uris):
            selected_authors = authors[i*2:(i+1)*2]  # 2 authors per paper
            mapper.map_relationships(g, paper_uri, papers[i], {"authors": selected_authors})

        # Query performance tests
        queries = [
            # Count all papers
            ("papers", len([s for s, p, o in g.triples((None, mapper._resolve_predicate("rdf:type"), mapper._resolve_predicate("bibo:AcademicArticle")))])),

            # Count all authors
            ("authors", len([s for s, p, o in g.triples((None, mapper._resolve_predicate("rdf:type"), mapper._resolve_predicate("foaf:Person")))])),

            # Count relationships
            ("creator_rels", len(list(g.triples((None, mapper._resolve_predicate("dcterms:creator"), None))))),

            # Count keywords
            ("keywords", len(list(g.triples((None, mapper._resolve_predicate("dcterms:subject"), None))))),
        ]

        query_times = {}
        for query_name, query_func in queries:
            start_time = time.time()
            result = query_func
            end_time = time.time()
            query_times[query_name] = end_time - start_time
            print(f"Query '{query_name}': {result} results in {query_times[query_name]:.4f}s")

        # Performance assertions
        for query_name, query_time in query_times.items():
            assert query_time < 0.1  # Queries should be fast (< 100ms)

        # Verify query results
        assert queries[0][1] == 10  # 10 papers
        assert queries[1][1] == 20  # 20 authors
        assert queries[2][1] >= 10  # At least 10 creator relationships

    def test_concurrent_access_safety(self, mapper, performance_paper_batch):
        """Test thread safety and concurrent access to mapper."""
        import threading

        g = Graph()
        errors = []

        def convert_paper(paper):
            try:
                paper.to_rdf(g, mapper=mapper)
            except Exception as e:
                errors.append(str(e))

        # Create threads
        threads = []
        for paper in performance_paper_batch[:10]:  # Test subset
            thread = threading.Thread(target=convert_paper, args=(paper,))
            threads.append(thread)

        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()
        end_time = time.time()

        concurrent_time = end_time - start_time

        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent conversion errors: {errors}"

        # Verify all papers were converted
        paper_count = len([s for s, p, o in g.triples((None, mapper._resolve_predicate("rdf:type"), mapper._resolve_predicate("bibo:AcademicArticle")))])
        assert paper_count == 10

        print(f"Concurrent conversion completed in {concurrent_time:.2f}s")
        print(f"Graph contains {len(g)} triples")

    def test_resource_cleanup_efficiency(self, mapper, performance_paper_batch):
        """Test that resources are properly managed during large operations."""
        import gc
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform large RDF conversion
        g = Graph()
        for paper in performance_paper_batch:
            paper.to_rdf(g, mapper=mapper)

        # Force garbage collection
        gc.collect()

        # Check memory after conversion
        after_conversion_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = after_conversion_memory - initial_memory

        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"After conversion: {after_conversion_memory:.1f} MB")
        print(f"Memory increase: {memory_increase:.1f} MB")

        # Memory should not increase excessively
        assert memory_increase < 50  # Less than 50MB increase for 100 papers

        # Verify graph integrity after cleanup
        assert len(g) > 1000  # Should still have content

        # Test serialization works after cleanup
        ttl = mapper.serialize_graph(g, format="turtle")
        assert len(ttl) > 1000  # Should serialize successfully
