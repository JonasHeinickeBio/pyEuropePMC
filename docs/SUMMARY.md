# Table of contents

* [Introduction](README.md)

## Getting started

* [Overview](getting-started/README.md)
* [Installation](getting-started/installation.md)
* [Quick start](getting-started/quickstart.md)
* [Examples](examples/README.md)
* [FAQ](getting-started/faq.md)
* [Migrating from 1.x to 2.0](migration/v1-to-v2.md)

## Features

* [Features overview](features/README.md)
* [Search](features/search/README.md)
  * [Query builder](features/query-builder-load-save-translate.md)
  * [Systematic review search logging](features/systematic-review-tracking.md)
  * [Deduplication](features/dedup.md)
  * [Citation graph walking](features/citation-walking.md)
  * [MeSH and PICO](features/mesh-pico.md)
* [Multi-source search](features/multi-source-search.md)
  * [ClinicalTrials.gov client](features/clinical-trials.md)
  * [arXiv client](features/arxiv.md)
* [Full-text retrieval](features/fulltext/README.md)
  * [Full-text index (SQLite FTS5)](features/fulltext-index.md)
* [XML parsing](features/parsing/README.md)
  * [JATS normalization](features/parsing/jats-normalization.md)
  * [Rhetorical highlighting](features/rhetorical-highlighting.md)
* [Metadata enrichment](guides/enrichment.md)
  * [ORCID and NIH iCite clients](features/orcid.md)
* [Caching](features/caching/README.md)

## Recipes

* [Query builder](guides/skills/query_builder.md)
* [Full-text parser](guides/skills/fulltext_parser.md)
* [FTP downloader](guides/skills/ftp_downloader.md)
* [Annotations](guides/skills/annotations.md)
* [Enrichment](guides/skills/enrichment.md)
* [Analytics](guides/skills/analytics.md)
* [RDF mapping](guides/skills/rdf_mapping.md)
* [Pipeline](guides/skills/pipeline.md)
* [Caching](guides/skills/caching.md)

## API reference

* [API overview](api/README.md)
* [SearchClient](api/search-client.md)
* [ArticleClient](api/article-client.md)
* [FullTextClient](api/fulltext-client.md)
* [FTPDownloader](api/ftp-downloader.md)
* [QueryBuilder](api/query-builder.md)
* [EuropePMCParser](api/parser.md)
* [FullTextXMLParser](api/xml-parser.md)
  * [XML parser extensions](api/xml-parser-extensions.md)
* [Analytics and visualization](api/analytics-visualization.md)

## Reference

* [Error codes](reference/error-codes.md)
* [Data models and RDF mapping](reference/models.md)
  * [RML mappings](reference/rml_mappings_guide.md)
* [XML element types](reference/xml_element_types_documentation.md)
* [Glossary](GLOSSARY.md)

## Advanced

* [Advanced topics](advanced/README.md)
* [Caching internals](advanced/caching.md)
* [Progress callbacks](advanced/progress-callbacks.md)
* [Search logging](advanced/search-logging.md)
* [Schema coverage validation](advanced/schema-coverage-validation.md)

## Development

* [Development guide](development/README.md)
* [CI, branch protection and releases](development/ci-and-release-workflow.md)
* [Documentation](development/documentation.md)
* [Python version support](development/python-version-strategy.md)
* [Testing](development/testing-improvements.md)
* [Benchmarking and profiling](guides/benchmarking.md)
* [XML parser internals](development/xml-parser-internals.md)
* [Feature Suggester workflow](development/feature-suggester.md)
