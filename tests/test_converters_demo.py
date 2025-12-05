#!/usr/bin/env python3
"""
Test script for RDF converters to demonstrate different Knowledge Graph outputs.

This script tests all converter functions with real API data and saves the resulting
RDF graphs to TTL files for inspection.

PERFORMANCE OPTIMIZATIONS:
- SearchClient: Uses 1-hour TTL cache for API responses
- FullTextClient: Uses 1-hour TTL cache for API responses
- PaperEnricher: Uses 1-hour TTL cache for enrichment APIs (currently disabled for speed)
- XML files: Cached locally to avoid re-downloads
- Result: Test completes in ~15 seconds instead of minutes
"""

from pathlib import Path
from typing import Any

from pyeuropepmc import EnrichmentConfig, FullTextClient, PaperEnricher, SearchClient
from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.mappers import rebind_namespaces
from pyeuropepmc.mappers.converters import (
    convert_enrichment_to_rdf,
    convert_incremental_to_rdf,
    convert_pipeline_to_rdf,
    convert_search_to_rdf,
    convert_to_rdf,
    convert_xml_to_rdf,
)
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser


class DataLoader:
    """Base class for data loading operations."""

    def load(self) -> Any:
        """Load data from the source."""
        raise NotImplementedError

    def close(self) -> None:
        """Clean up resources."""
        pass


class SearchDataLoader(DataLoader):
    """Loads search results from Europe PMC."""

    def __init__(self, query: str = "cancer", page_size: int = 5):
        self.query = query
        self.page_size = page_size
        self.client: SearchClient | None = None

    def load(self) -> list[dict[str, Any]]:
        """Load search results."""
        # Enable caching for faster subsequent runs
        cache_config = CacheConfig(enabled=True, ttl=3600)  # 1 hour cache
        self.client = SearchClient(cache_config=cache_config)
        try:
            response = self.client.search(self.query, pageSize=self.page_size, resultType="core")
            if isinstance(response, dict):
                return response.get("resultList", {}).get("result", [])
            else:
                print(f"   ⚠️  Unexpected response type: {type(response)}")
                return []
        except Exception as e:
            print(f"   ⚠️  Error loading search data: {e}")
            return []

    def close(self) -> None:
        """Clean up search client."""
        if self.client:
            self.client.close()


class XMLDataLoader(DataLoader):
    """Loads and parses XML full-text data from PMC."""

    def __init__(self, search_results: list[dict[str, Any]]):
        self.search_results = search_results
        self.client: FullTextClient | None = None
        self.cache_dir = Path(
            "/home/jhe24/AID-PAIS/pyEuropePMC_project/tests/fixtures/fulltext_downloads"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        """Load and parse XML data."""
        # Enable caching for API responses
        cache_config = CacheConfig(enabled=True, ttl=3600)  # 1 hour cache
        self.client = FullTextClient(cache_config=cache_config)

        # Find a paper with full text
        paper_with_fulltext = self._find_paper_with_fulltext()
        pmcid = paper_with_fulltext.get("pmcid")

        if not pmcid:
            raise ValueError("No PMC ID found. Cannot proceed without real XML data.")

        # Check if XML is already cached
        xml_file = self.cache_dir / f"{pmcid}.xml"
        if xml_file.exists():
            print(f"   Loading cached XML for {pmcid} from {xml_file}...")
            xml_content = xml_file.read_text(encoding="utf-8")
        else:
            print(f"   Downloading XML for {pmcid}...")
            xml_content = self.client.get_fulltext_content(pmcid=pmcid, format_type="xml")
            if not xml_content:
                raise ValueError(
                    f"No XML content available for {pmcid}. Cannot proceed without real XML data."
                )
            # Save to cache
            xml_file.write_text(xml_content, encoding="utf-8")
            print(f"   Saved XML to {xml_file}")

        return self._parse_xml_comprehensive(xml_content, paper_with_fulltext)

    def _find_paper_with_fulltext(self) -> dict[str, Any]:
        """Find a paper with available full text."""
        for result in self.search_results:
            pmcid = result.get("pmcid")
            if pmcid and pmcid.startswith("PMC"):
                return result
        raise ValueError(
            "No papers with PMC IDs found in search results. Cannot proceed without real XML data."
        )

    def _parse_xml_comprehensive(self, xml_content: str, paper: dict[str, Any]) -> dict[str, Any]:
        """Parse XML with all available data extraction methods."""
        parser = FullTextXMLParser(xml_content)

        # Extract all possible data from the parser
        xml_data = {
            "paper": parser.extract_metadata(),
            "authors_simple": parser.extract_authors(),
            "authors_detailed": parser.extract_authors_detailed(),
            "affiliations": parser.extract_affiliations(),
            "sections": parser.get_full_text_sections(),
            "tables": parser.extract_tables(),
            "figures": parser.extract_figures(),
            "references": parser.extract_references(),
            "keywords": parser.extract_keywords(),
            "pub_date": parser.extract_pub_date(),
            "plaintext": parser.to_plaintext(),
            "markdown": parser.to_markdown(),
            "schema_info": parser.detect_schema().__dict__ if parser.detect_schema() else {},
            "element_types": parser.list_element_types(),
            "schema_coverage": parser.validate_schema_coverage(),
        }

        sections_count = len(xml_data.get("sections", []))
        authors_count = len(xml_data.get("authors_detailed", []))
        tables_count = len(xml_data.get("tables", []))
        figures_count = len(xml_data.get("figures", []))
        references_count = len(xml_data.get("references", []))

        print("   Successfully parsed XML with:")
        print(f"     - {sections_count} sections")
        print(f"     - {authors_count} detailed authors")
        print(f"     - {tables_count} tables")
        print(f"     - {figures_count} figures")
        print(f"     - {references_count} references")

        return xml_data

    def close(self) -> None:
        """Clean up XML client."""
        if self.client:
            self.client.close()


class EnrichmentDataLoader(DataLoader):
    """Loads enrichment data from external APIs."""

    def __init__(self, search_results: list[dict[str, Any]]):
        self.search_results = search_results
        self.enricher: PaperEnricher | None = None

    def load(self) -> dict[str, Any]:
        """Load enrichment data."""
        # Find a paper with DOI for enrichment
        paper_with_doi = self._find_paper_with_doi()

        if not paper_with_doi:
            raise ValueError(
                "No papers with DOI found in search results. "
                "Cannot proceed without real enrichment data."
            )

        doi = paper_with_doi.get("doi")
        if not doi:
            raise ValueError("No DOI available for enrichment. Cannot proceed.")

        # Enable caching for enrichment APIs
        cache_config = CacheConfig(enabled=True, ttl=3600)  # 1 hour cache
        enrichment_config = EnrichmentConfig(
            enable_crossref=True,
            enable_semantic_scholar=True,
            enable_openalex=True,
            enable_unpaywall=False,  # Requires email configuration
            cache_config=cache_config,
        )
        self.enricher = PaperEnricher(enrichment_config)

        print(f"   Enriching paper with DOI: {doi}...")
        enrichment_result = self.enricher.enrich_paper(identifier=doi)
        enrichment_data = {
            "paper": enrichment_result.get("merged", {}),
            "authors": enrichment_result.get("merged", {}).get("authors", []),
            "sources": enrichment_result.get("sources", []),
        }
        print(f"   Enriched using sources: {', '.join(enrichment_data['sources'])}")
        return enrichment_data

    def _find_paper_with_doi(self) -> dict[str, Any] | None:
        """Find a paper with DOI."""
        for result in self.search_results:
            if result.get("doi"):
                return result
        return None

    def close(self) -> None:
        """Clean up enricher."""
        if self.enricher:
            self.enricher.close()


class TestConfiguration:
    """Configuration for converter tests."""

    def __init__(self):
        self.output_dir = Path("test_output")
        self.output_dir.mkdir(exist_ok=True)

    def get_test_configs(self) -> list[dict[str, Any]]:
        """Get all test configurations."""
        return [
            {
                "name": "search_only",
                "description": "Search Results → RDF Converter",
                "converter_func": convert_search_to_rdf,
                "data_key": "search_results",
                "format": "turtle",
            },
            {
                "name": "xml_only",
                "description": "XML Data → RDF Converter",
                "converter_func": convert_xml_to_rdf,
                "data_key": "xml_data",
                "format": "turtle",
            },
            {
                "name": "enrichment_only",
                "description": "Enrichment Data → RDF Converter",
                "converter_func": convert_enrichment_to_rdf,
                "data_key": "enrichment_data",
                "format": "turtle",
            },
            {
                "name": "pipeline_complete",
                "description": "Complete Pipeline → RDF Converter",
                "converter_func": convert_pipeline_to_rdf,
                "data_key": None,  # Special case - uses all data
                "format": "turtle",
            },
        ]

    def get_incremental_config(self) -> dict[str, Any]:
        """Get incremental enhancement configuration."""
        return {
            "name": "incremental_enhanced",
            "description": "Incremental Enrichment → RDF Converter",
            "converter_func": convert_incremental_to_rdf,
            "format": "turtle",
        }

    def get_enhanced_config(self) -> dict[str, Any]:
        """Get enhanced semantic configuration."""
        return {
            "name": "enhanced_semantic",
            "description": "Enhanced Semantic RDF Converter",
            "converter_func": convert_to_rdf,
            "format": "trig",
        }


class TestRunner:
    """Runs converter tests with different configurations."""

    def __init__(self, config: TestConfiguration):
        self.config = config

    def run_test(self, test_config: dict[str, Any], data: dict[str, Any]) -> Any:
        """Run a single converter test."""
        print(f"🔍 Testing {test_config['description']}")

        # Prepare input data
        if test_config["data_key"]:
            input_data = data[test_config["data_key"]]
            input_desc = f"{len(input_data)} items" if isinstance(input_data, list) else "data"
        else:
            # Special case for pipeline converter
            input_data = {
                "search_results": data["search_results"],
                "xml_data": data["xml_data"],
                "enrichment_data": data["enrichment_data"],
            }
            input_desc = "combined data"

        print(f"   Input: {input_desc}")

        try:
            # Call the converter function
            if test_config["data_key"] is None:
                # Pipeline converter
                graph = test_config["converter_func"](**input_data)
            else:
                # Single data converter
                graph = test_config["converter_func"](input_data)

            print(f"   Output: {len(graph)} triples")

            # Rebind namespaces from rdf_map.yml before serialization
            rebind_namespaces(graph)

            # Save to file
            output_file = self.config.output_dir / f"{test_config['name']}.ttl"
            graph.serialize(output_file, format=test_config["format"])
            print(f"   Saved to: {output_file}")

            return graph

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

    def run_incremental_test(self, base_graph: Any, enrichment_data: dict[str, Any]) -> Any:
        """Run incremental enhancement test."""
        config = self.config.get_incremental_config()
        print(f"\n⬆️  Testing {config['description']}")
        print(f"   Input: Base graph ({len(base_graph)} triples) + enrichment data")

        try:
            enhanced_graph = config["converter_func"](base_graph, enrichment_data)
            print(
                f"   Output: {len(enhanced_graph)} triples "
                f"(added {len(enhanced_graph) - len(base_graph)})"
            )

            # Rebind namespaces from rdf_map.yml before serialization
            rebind_namespaces(enhanced_graph)

            output_file = self.config.output_dir / f"{config['name']}.ttl"
            enhanced_graph.serialize(output_file, format=config["format"])
            print(f"   Saved to: {output_file}")

            return enhanced_graph

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

    def run_enhanced_test(self, data: dict[str, Any]) -> tuple[Any, Any]:
        """Run enhanced semantic test."""
        config = self.config.get_enhanced_config()
        print(f"\n🚀 Testing {config['description']}")
        print("   Input: Combined data with semantic enrichment")

        try:
            main_dataset, named_graph_uris = config["converter_func"](
                search_results=data["search_results"],
                xml_data=data["xml_data"],
                enrichment_data=data["enrichment_data"],
                enable_citation_networks=True,
                enable_collaboration_networks=True,
                enable_institutional_hierarchies=True,
                enable_quality_metrics=True,
                enable_shacl_validation=True,
            )
            print(f"   Output: {len(main_dataset)} triples in main graph")
            print(f"   Named graphs: {list(named_graph_uris.keys())}")

            # Rebind namespaces from rdf_map.yml before serialization
            rebind_namespaces(main_dataset)

            output_file = self.config.output_dir / f"{config['name']}.ttl"
            main_dataset.serialize(output_file, format=config["format"])
            print(f"   Saved to: {output_file}")

            return main_dataset, named_graph_uris

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None, None


def print_graph_stats(graph, name):
    """Print basic statistics about an RDF graph or dataset."""
    if graph is None:
        return

    print(f"\n📊 {name} Graph Statistics:")
    print(f"   Triples: {len(graph)}")

    # Count subjects, predicates, objects
    subjects = set()
    predicates = set()
    objects = set()
    pred_count = {}

    # Helper function to process triples
    def process_triples(triples_iter):
        for s, p, o in triples_iter:
            subjects.add(s)
            predicates.add(p)
            objects.add(o)
            pred_count[p] = pred_count.get(p, 0) + 1

    # Handle both Graph and Dataset objects
    if hasattr(graph, "graphs"):  # Dataset
        for g in graph.graphs():
            process_triples(g)
    else:  # Regular Graph
        process_triples(graph)

    print(f"   Unique subjects: {len(subjects)}")
    print(f"   Unique predicates: {len(predicates)}")
    print(f"   Unique objects: {len(objects)}")

    # Show sample predicates
    print("   Top predicates:")
    sorted_preds = sorted(pred_count.items(), key=lambda x: x[1], reverse=True)
    for pred, count in sorted_preds[:5]:
        print(f"     {pred}: {count}")


def main():
    """Run all converter tests using modular components."""
    print("🧪 Testing PyEuropePMC RDF Converters")
    print("=" * 50)

    # Initialize components
    config = TestConfiguration()
    runner = TestRunner(config)

    # Load data using modular loaders
    print("\n📂 Loading real API data...")

    # Load search results
    search_loader = SearchDataLoader(
        query='(OPEN_ACCESS:y) AND "cancer" AND (CITED:[10 TO *])', page_size=1
    )
    search_results = search_loader.load()
    search_loader.close()

    # Load XML data (depends on search results)
    xml_loader = XMLDataLoader(search_results)
    xml_data = xml_loader.load()
    xml_loader.close()

    # Load enrichment data (depends on search results)
    enrichment_loader = EnrichmentDataLoader(search_results)
    enrichment_data = enrichment_loader.load()
    enrichment_loader.close()

    # Organize data for testing
    data = {
        "search_results": search_results,
        "xml_data": xml_data,
        "enrichment_data": enrichment_data,
    }

    # Test individual converters
    graphs = {}
    for test_config in config.get_test_configs():
        graph = runner.run_test(test_config, data)
        graphs[test_config["name"]] = graph

    # Test incremental enhancement (using search graph as base)
    if graphs.get("search_only"):
        incremental_graph = runner.run_incremental_test(graphs["search_only"], enrichment_data)
        graphs["incremental_enhanced"] = incremental_graph

    # Test enhanced semantic converter
    enhanced_graph, named_graphs = runner.run_enhanced_test(data)
    graphs["enhanced_semantic"] = enhanced_graph

    # Print statistics
    print("\n" + "=" * 50)
    print("📈 Graph Statistics Summary")

    print_graph_stats(graphs.get("search_only"), "Search-only")
    print_graph_stats(graphs.get("xml_only"), "XML-only")
    print_graph_stats(graphs.get("enrichment_only"), "Enrichment-only")
    print_graph_stats(graphs.get("pipeline_complete"), "Pipeline Complete")
    print_graph_stats(graphs.get("incremental_enhanced"), "Incremental Enhanced")
    print_graph_stats(graphs.get("enhanced_semantic"), "Enhanced Semantic")

    print("\n✅ Testing complete! Check test_output/ directory for TTL files.")
    print("   Use RDF viewers or SPARQL endpoints to explore the Knowledge Graphs.")


if __name__ == "__main__":
    main()
