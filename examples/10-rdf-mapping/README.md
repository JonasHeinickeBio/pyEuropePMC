# RDF Mapping Demo

This folder contains a comprehensive demonstration of RDF mapping workflows in PyEuropePMC, showing the complete pipeline from basic Europe PMC search results to enriched knowledge graph triples.

## Contents

- `rdf_mapping_demo.ipynb`: Main notebook demonstrating the RDF mapping workflow

## Workflow Overview

The demo notebook shows:

1. **Basic Search**: Retrieve paper metadata from Europe PMC API
2. **XML Retrieval**: Fetch full-text XML for selected papers
3. **RDF Conversion**: Parse XML and convert to RDF triples using semantic mappings
4. **Data Enrichment**: Enhance metadata using external APIs (CrossRef, Semantic Scholar, OpenAlex, etc.)
5. **Enriched RDF**: Generate RDF from enriched data with additional triples
6. **Comparison**: Analyze differences between basic and enriched RDF graphs

## Key Features Demonstrated

- Europe PMC search and full-text retrieval
- XML parsing and entity extraction
- RDF triple generation with BIBO, FOAF, and DCT ontologies
- Metadata enrichment from multiple academic APIs
- RDF graph comparison and analysis
- Semantic web integration for knowledge graphs

## Requirements

- PyEuropePMC with all optional dependencies
- API keys for enrichment services (optional, but recommended for full demo)
- Internet connection for API calls

## Usage

Run the notebook cells in order to see the complete workflow. The demo uses real papers from Europe PMC, so results may vary based on current API responses.
