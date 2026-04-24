#!/usr/bin/env python3
"""
Comprehensive Benchmarking Suite for PyEuropePMC Pipeline

This script provides structured benchmarking for the complete PyEuropePMC pipeline:
1. Search for papers with specific criteria
2. Bulk download XML full-text content
3. Parse and analyze XML structure
4. Transform to RDF Knowledge Graphs

Features:
- Modular and reusable components
- Comprehensive timing measurements
- Storage and data size tracking
- Configurable batch processing
- Detailed performance reporting
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any

from pyeuropepmc import FullTextClient, SearchClient
from pyeuropepmc.mappers import rebind_namespaces
from pyeuropepmc.mappers.converters import (
    convert_to_rdf,
)
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser


@dataclass
class BenchmarkMetrics:
    """Container for benchmark timing and size metrics."""

    # Timing metrics (seconds)
    search_time: float = 0.0
    download_time: float = 0.0
    parse_time: float = 0.0
    xml_parsing_time: float = 0.0
    metadata_extraction_time: float = 0.0
    section_extraction_time: float = 0.0
    table_extraction_time: float = 0.0
    reference_extraction_time: float = 0.0
    rdf_conversion_time: float = 0.0
    total_time: float = 0.0

    # Data size metrics
    papers_found: int = 0
    papers_with_pmcid: int = 0
    xml_files_downloaded: int = 0
    xml_total_size_bytes: int = 0
    xml_avg_size_bytes: float = 0.0
    unique_xml_tags: int = 0
    rdf_triples_generated: int = 0
    rdf_file_size_bytes: int = 0

    # XML Parsing metrics
    xml_files_parsed: int = 0
    xml_parse_success_rate: float = 0.0
    xml_parse_errors: int = 0
    metadata_extraction_success: int = 0
    section_extraction_success: int = 0
    table_extraction_success: int = 0
    reference_extraction_success: int = 0

    # Data model validation
    valid_metadata_count: int = 0
    valid_sections_count: int = 0
    valid_tables_count: int = 0
    valid_references_count: int = 0
    avg_sections_per_paper: float = 0.0
    avg_tables_per_paper: float = 0.0
    avg_references_per_paper: float = 0.0

    # Performance metrics
    search_rate_papers_per_sec: float = 0.0
    download_rate_mb_per_sec: float = 0.0
    parse_rate_papers_per_sec: float = 0.0
    xml_parse_rate_papers_per_sec: float = 0.0
    rdf_conversion_rate_triples_per_sec: float = 0.0

    # Error tracking
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            "timing": {
                "search_time_seconds": self.search_time,
                "download_time_seconds": self.download_time,
                "parse_time_seconds": self.parse_time,
                "rdf_conversion_time_seconds": self.rdf_conversion_time,
                "total_time_seconds": self.total_time,
            },
            "data_sizes": {
                "papers_found": self.papers_found,
                "papers_with_pmcid": self.papers_with_pmcid,
                "xml_files_downloaded": self.xml_files_downloaded,
                "xml_total_size_mb": self.xml_total_size_bytes / (1024 * 1024),
                "xml_avg_size_kb": self.xml_avg_size_bytes / 1024,
                "unique_xml_tags": self.unique_xml_tags,
                "rdf_triples_generated": self.rdf_triples_generated,
                "rdf_file_size_mb": self.rdf_file_size_bytes / (1024 * 1024),
            },
            "performance": {
                "search_rate_papers_per_sec": self.search_rate_papers_per_sec,
                "download_rate_mb_per_sec": self.download_rate_mb_per_sec,
                "parse_rate_papers_per_sec": self.parse_rate_papers_per_sec,
                "rdf_conversion_rate_triples_per_sec": self.rdf_conversion_rate_triples_per_sec,
            },
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    # Search parameters
    query: str = "(OPEN_ACCESS:y) AND (CITED:[5 TO *])"
    target_paper_count: int = 1000
    search_page_size: int = 100

    # Download parameters
    max_concurrent_downloads: int = 5
    download_timeout_seconds: int = 30
    skip_existing_xml: bool = True

    # Processing parameters
    batch_size: int = 50
    enable_enrichment: bool = False

    # Output parameters
    output_dir: Path = Path("benchmark_output")
    xml_cache_dir: Path = Path("benchmark_cache/xml")
    results_file: str = "benchmark_results.json"

    # RDF parameters
    rdf_format: str = "turtle"
    enable_citation_networks: bool = True
    enable_collaboration_networks: bool = True
    enable_institutional_hierarchies: bool = True

    def __post_init__(self) -> None:
        """Ensure paths are Path objects."""
        self.output_dir = Path(self.output_dir)
        self.xml_cache_dir = Path(self.xml_cache_dir)


class BenchmarkTimer:
    """Context manager for timing operations."""

    def __init__(self, metrics: BenchmarkMetrics, metric_name: str):
        self.metrics = metrics
        self.metric_name = metric_name
        self.start_time: float | None = None

    def __enter__(self) -> "BenchmarkTimer":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        if self.start_time is not None:
            duration = time.time() - self.start_time
            setattr(self.metrics, self.metric_name, duration)


class BulkSearchLoader:
    """Handles bulk searching for papers with specific criteria."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.client: SearchClient | None = None
        self.metrics = BenchmarkMetrics()

    def search_papers(self) -> list[dict[str, Any]]:
        """Search for papers matching the criteria."""
        print(f"🔍 Searching for {self.config.target_paper_count} papers...")
        print(f"   Query: {self.config.query}")

        self.client = SearchClient()
        all_results: list[dict[str, Any]] = []
        page = 1

        with BenchmarkTimer(self.metrics, "search_time"):
            while len(all_results) < self.config.target_paper_count:
                try:
                    response = self.client.search(
                        self.config.query,
                        pageSize=self.config.search_page_size,
                        resultType="core",
                        page=page,
                    )

                    results = response.get("resultList", {}).get("result", [])  # type: ignore
                    if not results:
                        break

                    all_results.extend(results)
                    print(
                        f"   Page {page}: Found {len(results)} papers (total: {len(all_results)})"
                    )

                    page += 1

                    # Safety check to prevent infinite loops
                    if page > 50:  # Reasonable limit
                        self.metrics.warnings.append(
                            "Search stopped at page 50 to prevent infinite loop"
                        )
                        break

                except Exception as e:
                    self.metrics.errors.append(f"Search error on page {page}: {e}")
                    break

        # Filter to target count
        results = all_results[: self.config.target_paper_count]
        self.metrics.papers_found = len(results)

        # Count papers with PMC IDs
        pmcid_count = sum(1 for r in results if r.get("pmcid"))
        self.metrics.papers_with_pmcid = pmcid_count

        # Calculate performance metrics
        if self.metrics.search_time > 0:
            self.metrics.search_rate_papers_per_sec = len(results) / self.metrics.search_time

        print(f"✅ Found {len(results)} papers ({pmcid_count} with PMC IDs)")
        print(".2f")
        print(".1f")

        return results

    def close(self) -> None:
        """Clean up resources."""
        if self.client:
            self.client.close()


class BulkXMLDownloader:
    """Handles bulk downloading of XML full-text content."""

    def __init__(self, config: BenchmarkConfig, search_results: list[dict[str, Any]]):
        self.config = config
        self.search_results = search_results
        self.client: FullTextClient | None = None
        self.metrics = BenchmarkMetrics()

        # Filter to papers with PMC IDs
        self.pmc_papers = [r for r in search_results if r.get("pmcid")]
        self.config.xml_cache_dir.mkdir(parents=True, exist_ok=True)

    def download_xml_files(self) -> list[Path]:
        """Download XML files for all papers with PMC IDs."""
        print(f"📥 Downloading XML for {len(self.pmc_papers)} papers...")

        self.client = FullTextClient()
        downloaded_files = []
        total_bytes = 0

        with BenchmarkTimer(self.metrics, "download_time"):
            for i, paper in enumerate(self.pmc_papers, 1):
                pmcid = paper["pmcid"]
                xml_file = self.config.xml_cache_dir / f"{pmcid}.xml"

                if self.config.skip_existing_xml and xml_file.exists():
                    print(f"   [{i}/{len(self.pmc_papers)}] Using cached XML: {pmcid}")
                    file_size = xml_file.stat().st_size
                    total_bytes += file_size
                    downloaded_files.append(xml_file)
                    continue

                try:
                    print(f"   [{i}/{len(self.pmc_papers)}] Downloading XML: {pmcid}")
                    xml_content = self.client.get_fulltext_content(pmcid=pmcid, format_type="xml")

                    if xml_content:
                        xml_file.write_text(xml_content, encoding="utf-8")
                        file_size = len(xml_content.encode("utf-8"))
                        total_bytes += file_size
                        downloaded_files.append(xml_file)
                        print(f"      Saved {file_size} bytes")
                    else:
                        self.metrics.warnings.append(f"No XML content available for {pmcid}")

                except Exception as e:
                    self.metrics.errors.append(f"Download failed for {pmcid}: {e}")

        self.metrics.xml_files_downloaded = len(downloaded_files)
        self.metrics.xml_total_size_bytes = total_bytes

        if downloaded_files:
            self.metrics.xml_avg_size_bytes = total_bytes / len(downloaded_files)

        # Calculate performance metrics
        if self.metrics.download_time > 0:
            download_mb = total_bytes / (1024 * 1024)
            self.metrics.download_rate_mb_per_sec = download_mb / self.metrics.download_time

        print(f"✅ Downloaded {len(downloaded_files)} XML files")
        print(".2f")
        print(".1f")
        print(".1f")

        return downloaded_files

    def close(self) -> None:
        """Clean up resources."""
        if self.client:
            self.client.close()


class ComprehensiveXMLParser:
    """Enhanced XML parser that validates all data models and provides comprehensive metrics."""

    def __init__(self, config: BenchmarkConfig, xml_files: list[Path]):
        self.config = config
        self.xml_files = xml_files
        self.metrics = BenchmarkMetrics()

        # Initialize parser
        from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

        self.parser = FullTextXMLParser()

        # Data model validation counters
        self.data_model_counts = {
            "metadata": 0,
            "authors": 0,
            "affiliations": 0,
            "sections": 0,
            "tables": 0,
            "references": 0,
            "keywords": 0,
            "pub_date": 0,
            "plaintext": 0,
            "markdown": 0,
            "schema_info": 0,
            "element_types": 0,
        }

        self.validation_errors: list[str] = []

    def parse_xml_files_comprehensive(self) -> list[dict[str, Any]]:  # noqa: C901
        """Parse XML files with comprehensive data model extraction and validation."""
        print("🔍 Running comprehensive XML parsing with full data model validation...")

        parsed_data = []
        all_element_types = set()

        with BenchmarkTimer(self.metrics, "parse_time"):
            for i, xml_file in enumerate(self.xml_files, 1):
                try:
                    # Parse the XML file
                    with open(xml_file, encoding="utf-8") as f:
                        xml_content = f.read()

                    # Initialize parser with content
                    parser = FullTextXMLParser(xml_content)

                    # Extract all data models
                    data = {
                        "pmcid": xml_file.stem,
                        "file_path": str(xml_file),
                        "file_size": xml_file.stat().st_size,
                    }

                    # Extract metadata
                    metadata = parser.extract_metadata()
                    if metadata:
                        data["metadata"] = metadata
                        self.data_model_counts["metadata"] += 1
                        if self._validate_metadata(metadata):
                            authors = metadata.get("authors", [])
                            self.data_model_counts["authors"] += 1 if authors else 0
                            pub_date = metadata.get("pub_date")
                            self.data_model_counts["pub_date"] += 1 if pub_date else 0
                        else:
                            self.validation_errors.append(f"Invalid metadata for {xml_file.name}")

                    # Extract sections
                    sections = parser.get_full_text_sections()
                    if sections:
                        data["sections"] = sections
                        self.data_model_counts["sections"] += 1

                    # Extract tables
                    tables = parser.extract_tables()
                    if tables:
                        data["tables"] = tables
                        self.data_model_counts["tables"] += 1

                    # Extract references
                    references = parser.extract_references()
                    if references:
                        data["references"] = references
                        self.data_model_counts["references"] += 1

                    # Extract keywords
                    keywords = parser.extract_keywords()
                    if keywords:
                        data["keywords"] = keywords
                        self.data_model_counts["keywords"] += 1

                    # Generate plaintext
                    plaintext = parser.to_plaintext()
                    if plaintext:
                        data["plaintext"] = plaintext
                        self.data_model_counts["plaintext"] += 1

                    # Generate markdown
                    markdown = parser.to_markdown()
                    if markdown:
                        data["markdown"] = markdown
                        self.data_model_counts["markdown"] += 1

                    # Get schema info
                    schema_info = parser.detect_schema()
                    if schema_info:
                        data["schema_info"] = schema_info
                        self.data_model_counts["schema_info"] += 1

                    # Get element types
                    element_types = parser.list_element_types()
                    if element_types:
                        data["element_types"] = element_types
                        self.data_model_counts["element_types"] += 1
                        all_element_types.update(element_types)

                    parsed_data.append(data)

                    if i % 10 == 0 or i == len(self.xml_files):
                        print(f"      Processed {i}/{len(self.xml_files)} files")

                except Exception as e:
                    self.metrics.errors.append(f"Parse error for {xml_file.name}: {e}")

        self.metrics.unique_xml_tags = len(all_element_types)

        # Calculate performance metrics
        if self.metrics.parse_time > 0:
            self.metrics.parse_rate_papers_per_sec = len(parsed_data) / self.metrics.parse_time

        print("✅ Comprehensive XML parsing complete")
        print(f"   Parsed {len(parsed_data)} XML files")
        print(".2f")
        print(f"   Found {len(all_element_types)} unique XML element types")

        # Print data model validation summary
        self._print_data_model_summary()

        return parsed_data

    def _validate_metadata(self, metadata: dict[str, Any]) -> bool:
        """Validate metadata structure."""
        required_fields = ["title", "authors", "journal"]

        for req_field in required_fields:
            if req_field not in metadata or not metadata[req_field]:
                return False

        # Validate journal structure
        journal = metadata.get("journal", {})
        if not isinstance(journal, dict) or "title" not in journal:
            return False

        # Validate authors
        authors = metadata.get("authors", [])
        return isinstance(authors, list) and len(authors) > 0

    def _print_data_model_summary(self) -> None:
        """Print summary of data model extraction success."""
        print("\n📊 Data Model Extraction Summary:")
        for _model, _count in self.data_model_counts.items():
            print("6")

        if self.validation_errors:
            print(f"\n⚠️  Validation Errors: {len(self.validation_errors)}")
            for error in self.validation_errors[:3]:  # Show first 3
                print(f"   - {error}")


class RDFConverter:
    """Handles RDF conversion with benchmarking."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.metrics = BenchmarkMetrics()

    def convert_to_rdf(
        self, search_results: list[dict[str, Any]], xml_data_list: list[dict[str, Any]]
    ) -> Any:
        """Convert all data to RDF Knowledge Graph."""
        print("🔄 Converting to RDF Knowledge Graph...")

        from rdflib import Dataset

        main_dataset = Dataset()
        named_graph_uris = {}

        with BenchmarkTimer(self.metrics, "rdf_conversion_time"):
            try:
                # Process each XML data item
                for xml_data in xml_data_list:
                    # Call convert_to_rdf for each individual XML data item
                    dataset, graph_uris = convert_to_rdf(
                        search_results=search_results,
                        xml_data=xml_data,  # Single dict now
                        enrichment_data=None,  # No enrichment for this benchmark
                        enable_citation_networks=self.config.enable_citation_networks,
                        enable_collaboration_networks=self.config.enable_collaboration_networks,
                        enable_institutional_hierarchies=self.config.enable_institutional_hierarchies,
                        enable_quality_metrics=True,
                        enable_shacl_validation=True,
                    )

                    # Merge datasets by adding all triples
                    for graph in dataset.graphs():
                        for triple in graph:
                            main_dataset.add(triple)

                    # Merge named graph URIs
                    named_graph_uris.update(graph_uris)

                # Rebind namespaces
                rebind_namespaces(main_dataset)

                # Save to file
                output_file = self.config.output_dir / "benchmark_knowledge_graph.ttl"
                main_dataset.serialize(output_file, format=self.config.rdf_format)

                # Update metrics
                self.metrics.rdf_triples_generated = len(main_dataset)
                self.metrics.rdf_file_size_bytes = output_file.stat().st_size

                print("✅ Generated RDF Knowledge Graph")
                print(f"   Triples: {self.metrics.rdf_triples_generated:,}")
                print(".2f")
                print(".1f")
                print(f"   Named graphs: {list(named_graph_uris.keys())}")
                print(f"   Saved to: {output_file}")

            except Exception as e:
                self.metrics.errors.append(f"RDF conversion error: {e}")
                print(f"❌ RDF conversion failed: {e}")
                return None

        # Calculate performance metrics after timing is complete
        if self.metrics.rdf_conversion_time > 0:
            self.metrics.rdf_conversion_rate_triples_per_sec = (
                self.metrics.rdf_triples_generated / self.metrics.rdf_conversion_time
            )

        return main_dataset


class BenchmarkRunner:
    """Main benchmark runner coordinating all components."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metrics
        self.overall_metrics = BenchmarkMetrics()

    def run_full_pipeline(self) -> BenchmarkMetrics:
        """Run the complete benchmarking pipeline."""
        print("🚀 Starting PyEuropePMC Bulk Benchmarking Pipeline")
        print("=" * 60)

        start_time = time.time()

        try:
            # Step 1: Search for papers
            search_loader = BulkSearchLoader(self.config)
            search_results = search_loader.search_papers()
            self.overall_metrics.search_time = search_loader.metrics.search_time
            self.overall_metrics.papers_found = search_loader.metrics.papers_found
            self.overall_metrics.papers_with_pmcid = search_loader.metrics.papers_with_pmcid
            self.overall_metrics.search_rate_papers_per_sec = (
                search_loader.metrics.search_rate_papers_per_sec
            )
            search_loader.close()

            if not search_results:
                raise ValueError("No search results found")

            # Step 2: Download XML files
            xml_downloader = BulkXMLDownloader(self.config, search_results)
            xml_files = xml_downloader.download_xml_files()
            self.overall_metrics.download_time = xml_downloader.metrics.download_time
            self.overall_metrics.xml_files_downloaded = xml_downloader.metrics.xml_files_downloaded
            self.overall_metrics.xml_total_size_bytes = xml_downloader.metrics.xml_total_size_bytes
            self.overall_metrics.xml_avg_size_bytes = xml_downloader.metrics.xml_avg_size_bytes
            self.overall_metrics.download_rate_mb_per_sec = (
                xml_downloader.metrics.download_rate_mb_per_sec
            )
            xml_downloader.close()

            if not xml_files:
                raise ValueError("No XML files downloaded")

            # Step 3: Parse XML files
            xml_parser = ComprehensiveXMLParser(self.config, xml_files)
            parsed_data = xml_parser.parse_xml_files_comprehensive()
            self.overall_metrics.parse_time = xml_parser.metrics.parse_time
            self.overall_metrics.unique_xml_tags = xml_parser.metrics.unique_xml_tags
            self.overall_metrics.parse_rate_papers_per_sec = (
                xml_parser.metrics.parse_rate_papers_per_sec
            )

            # Save element types
            element_types_file = self.config.output_dir / "xml_element_types.txt"
            # Note: ComprehensiveXMLParser doesn't have save_element_types method
            # We'll save element types from the parsed data
            all_element_types = set()
            for data in parsed_data:
                if "element_types" in data:
                    all_element_types.update(data["element_types"])

            with open(element_types_file, "w", encoding="utf-8") as f:
                f.write("# Unique XML Element Types Found\n")
                f.write(f"# Total: {len(all_element_types)}\n")
                f.write("# Generated during comprehensive parsing benchmark\n\n")
                for tag in sorted(all_element_types):
                    f.write(f"{tag}\n")

            print(f"💾 Saved {len(all_element_types)} element types to {element_types_file}")

            # Step 4: Convert to RDF
            rdf_converter = RDFConverter(self.config)
            rdf_converter.convert_to_rdf(search_results, parsed_data)
            self.overall_metrics.rdf_conversion_time = rdf_converter.metrics.rdf_conversion_time
            self.overall_metrics.rdf_triples_generated = (
                rdf_converter.metrics.rdf_triples_generated
            )
            self.overall_metrics.rdf_file_size_bytes = rdf_converter.metrics.rdf_file_size_bytes
            self.overall_metrics.rdf_conversion_rate_triples_per_sec = (
                rdf_converter.metrics.rdf_conversion_rate_triples_per_sec
            )

            # Calculate total time
            self.overall_metrics.total_time = time.time() - start_time

            # Collect all errors and warnings
            self.overall_metrics.errors.extend(search_loader.metrics.errors)
            self.overall_metrics.errors.extend(xml_downloader.metrics.errors)
            self.overall_metrics.errors.extend(xml_parser.metrics.errors)
            self.overall_metrics.errors.extend(rdf_converter.metrics.errors)

            self.overall_metrics.warnings.extend(search_loader.metrics.warnings)
            self.overall_metrics.warnings.extend(xml_downloader.metrics.warnings)

            # Save results
            self.save_results()

            print("\n" + "=" * 60)
            print("✅ Benchmarking Pipeline Complete!")
            print(".2f")
            self.print_summary()

            return self.overall_metrics

        except Exception as e:
            self.overall_metrics.errors.append(f"Pipeline error: {e}")
            print(f"❌ Pipeline failed: {e}")
            return self.overall_metrics

    def save_results(self) -> None:
        """Save benchmark results to JSON file."""
        results_file = self.config.output_dir / self.config.results_file

        results = {
            "config": {
                "query": self.config.query,
                "target_paper_count": self.config.target_paper_count,
                "timestamp": time.time(),
                "version": "1.0",
            },
            "metrics": self.overall_metrics.to_dict(),
        }

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"💾 Results saved to {results_file}")

    def print_summary(self) -> None:
        """Print a summary of the benchmark results."""
        m = self.overall_metrics

        print("📊 Benchmark Summary:")
        print(f"   Papers Found: {m.papers_found} ({m.papers_with_pmcid} with PMC IDs)")
        print(f"   XML Files: {m.xml_files_downloaded}")
        print(".2f")
        print(f"   Unique XML Tags: {m.unique_xml_tags}")
        print(f"   RDF Triples: {m.rdf_triples_generated:,}")
        print(".2f")

        print("\n⏱️  Performance:")
        print(".1f")
        print(".1f")
        print(".1f")
        print(".1f")

        if m.errors:
            print(f"\n⚠️  Errors: {len(m.errors)}")
            for error in m.errors[:3]:  # Show first 3 errors
                print(f"   - {error}")

        if m.warnings:
            print(f"\n⚠️  Warnings: {len(m.warnings)}")
            for warning in m.warnings[:3]:  # Show first 3 warnings
                print(f"   - {warning}")


def main() -> None:
    """Run the benchmarking pipeline with default configuration."""
    # Create benchmark configuration
    config = BenchmarkConfig(
        query="(OPEN_ACCESS:y) AND (CITED:[5 TO *])",
        target_paper_count=1000,
        search_page_size=100,
        max_concurrent_downloads=5,
        batch_size=50,
        output_dir=Path("benchmark_output"),
        xml_cache_dir=Path("benchmark_cache/xml"),
    )

    # Run the benchmark
    runner = BenchmarkRunner(config)
    metrics = runner.run_full_pipeline()

    # Exit with error code if there were critical errors
    if metrics.errors:
        exit(1)


if __name__ == "__main__":
    main()
