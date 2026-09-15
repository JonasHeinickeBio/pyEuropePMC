# API reference

This section documents pyEuropePMC's public classes and functions. This page gives an overview of the main classes, the exceptions they raise and how to configure them; the pages linked below cover each class in detail.

## Imports

Import public names from the top-level package:

```python
from pyeuropepmc import (
    ArticleClient,
    CacheConfig,
    EuropePMCParser,
    FTPDownloader,
    FullTextClient,
    FullTextXMLParser,
    QueryBuilder,
    SearchClient,
    UnifiedSearch,
)
```

`import pyeuropepmc` loads submodules on first use, so an optional dependency is needed only when you use a feature that requires it.

## Main classes

| Class | Purpose | Key methods | Details |
|---|---|---|---|
| `SearchClient` | Search Europe PMC | `search()`, `search_all()`, `get_hit_count()`, `search_and_parse()`, `search_ids_only()`, `export_results()` | [SearchClient](search-client.md) |
| `ArticleClient` | Metadata, citations, references and links for one article | `get_article_details()`, `get_citations()`, `get_references()`, `get_citation_count()`, `get_reference_count()`, `get_supplementary_files()` | [ArticleClient](article-client.md) |
| `FullTextClient` | Full-text XML, PDF and HTML | `get_fulltext_content()`, `check_fulltext_availability()`, `download_xml_by_pmcid()`, `download_pdf_by_pmcid()`, `download_html_by_pmcid()`, `download_fulltext_batch()` | [FullTextClient](fulltext-client.md) |
| `FTPDownloader` | Bulk PDF packages from the Europe PMC FTP site | `query_pmcids_in_ftp()`, `bulk_download_and_extract()` | [FTPDownloader](ftp-downloader.md) |
| `QueryBuilder` | Build query strings | `keyword()`, `field()`, `and_()`, `or_()`, `not_()`, `date_range()`, `citation_count()`, `build()`, `save()`, `translate()` | [QueryBuilder](query-builder.md) |
| `FullTextXMLParser` | Parse JATS XML | `extract_metadata()`, `extract_tables()`, `extract_references()`, `get_full_text_sections_structured()`, `to_plaintext()`, `to_markdown()` | [XML parser](xml-parser.md) |
| `EuropePMCParser` | Parse search responses | `parse_json()`, `parse_xml()`, `parse_dc()` | [EuropePMCParser](parser.md) |
| `UnifiedSearch` | Search several services and merge duplicates | `search()`, `search_all()` | [Multi-source search](../features/multi-source-search.md) |

Analytics and plotting functions are described in [Analytics and visualization](analytics-visualization.md).

## Clients

`SearchClient`, `ArticleClient` and `FullTextClient` are context managers: leaving the `with` block closes the HTTP session, and a closed client raises an error with code `FULL007`.

```python
from pyeuropepmc import ArticleClient, SearchClient

with SearchClient(rate_limit_delay=1.0) as search, ArticleClient() as articles:
    hits = search.search("malaria vaccine", pageSize=5, resultType="core")
    first = hits["resultList"]["result"][0]
    count = articles.get_citation_count(first["source"], first["id"])

print(first["title"], count)
```

| Parameter | Type | Default | Accepted by | Meaning |
|---|---|---|---|---|
| `rate_limit_delay` | float | `1.0` | `SearchClient`, `ArticleClient`, `FullTextClient`, `FTPDownloader` | Seconds to wait between requests |
| `cache_config` | `CacheConfig` or `None` | `None` | `SearchClient`, `ArticleClient`, `FullTextClient` | Cache for API responses; off unless you pass a `CacheConfig`, and kept in memory by default. See [Caching](../features/caching/README.md) |
| `enable_cache` | bool | `True` | `FullTextClient` | Keep downloaded files in a file cache |
| `cache_dir` | path or `None` | `None` | `FullTextClient` | Folder of the file cache; a folder in the system temporary directory when `None` |

The class pages list the other parameters.

## Exceptions

All exceptions are defined in `pyeuropepmc.core.exceptions`, derive from `PyEuropePMCError` and carry an error code:

```text
PyEuropePMCError
├── APIClientError       failed HTTP requests (also pyeuropepmc.APIClientError)
│   └── RateLimitError   defined, but not raised by the current code
├── SearchError          SearchClient errors (also pyeuropepmc.EuropePMCError)
├── FullTextError        FullTextClient and FTPDownloader errors (also pyeuropepmc.FullTextError)
├── ParsingError         XML and search-response parsing
├── ValidationError      invalid arguments and JSON file helpers
├── ConfigurationError   invalid cache configuration
├── QueryBuilderError    QueryBuilder errors
└── UnpaywallError       UnpaywallClient errors (also pyeuropepmc.UnpaywallError)
```

`ClientError`, `APIError`, `FileError` and `ModelError` are also defined but not raised. [Error codes](../reference/error-codes.md) lists every code, where it is raised and what to do about it.

## Configuration

There is no global configuration file: configure each client through its constructor. The Europe PMC API needs no key. Optional integrations read these environment variables:

| Variable | Read by | Purpose |
|---|---|---|
| `UNPAYWALL_EMAIL`, `CROSSREF_EMAIL`, `OPENALEX_EMAIL`, `DATACITE_EMAIL`, `ROR_EMAIL` | Enrichment configuration (`pyeuropepmc.features.enrich.config`) | Contact emails for those services |
| `ROR_CLIENT_ID` | Enrichment configuration | ROR client ID |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar enrichment source | API key |
| `CORE_API_KEY` | CORE search source | API key |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` | `LLMClient` (`agentic` extra) | Model access |
| `LLM_ENABLED`, `LLM_CACHE_ENABLED` | Agentic command-line commands | Turn the LLM and its cache on or off |
| `ZOTERO_LIBRARY_ID`, `ZOTERO_API_KEY`, `ZOTERO_LOCAL` | Zotero integration (`zotero` extra) | Library access |
| `PYEUROPEPMC_MCP_TRANSPORT`, `PYEUROPEPMC_MCP_HOST`, `PYEUROPEPMC_MCP_PORT`, `PYEUROPEPMC_MCP_LOG_LEVEL` | `pyeuropepmc-mcp` | Server transport, address and log level |
| `PYEUROPEPMC_UI_SECRET_KEY`, `PYEUROPEPMC_UI_DEBUG` | Claim-review web interface (`ui` extra) | Flask settings |

Behind a proxy, set `HTTPS_PROXY`, which `requests` reads.

## Pages in this section

- [SearchClient](search-client.md)
- [ArticleClient](article-client.md)
- [FullTextClient](fulltext-client.md)
- [FTPDownloader](ftp-downloader.md)
- [QueryBuilder](query-builder.md), including its [field names](query-builder.md#field-names)
- [EuropePMCParser](parser.md)
- [XML parser](xml-parser.md) and [XML parser extensions](xml-parser-extensions.md)
- [Analytics and visualization](analytics-visualization.md)
