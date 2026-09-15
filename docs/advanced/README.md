# Advanced topics

These pages document the internals and less common utilities of pyEuropePMC: the cache layer, progress reporting for batch downloads, search logging for systematic reviews, and schema coverage checks for XML parsing.

| Page | Covers |
|---|---|
| [Caching internals](caching.md) | `CacheConfig` and `CacheBackend` reference, cache keys, the disk layer, `ArtifactStore` |
| [Progress callbacks](progress-callbacks.md) | `download_fulltext_batch(progress_callback=...)`, `ProgressInfo`, parallel downloads |
| [Search logging](search-logging.md) | `pyeuropepmc.utils.search_logging`: query logs, PRISMA counts, archiving and signing |
| [Schema coverage validation](schema-coverage-validation.md) | `FullTextXMLParser.validate_schema_coverage()` |

## Where other topics are covered

| Task | Where to look |
|---|---|
| Turn on response caching | [Caching](../features/caching/README.md) |
| Fetch every page of a result set | `SearchClient.search_all(query, page_size=100, max_results=None)`; see [Search](../features/search/README.md) |
| Build queries in code | [QueryBuilder](../api/query-builder.md) |
| Search several sources at once | [Multi-source search](../features/multi-source-search.md) |
| Change the pause between requests | The `rate_limit_delay` argument of each client: seconds to wait after each request, default `1.0` |
| Download many articles in parallel | `FullTextClient.download_fulltext_batch_parallel()`; see [Parallel downloads](progress-callbacks.md#parallel-downloads) |
| Put results into a pandas DataFrame | `to_dataframe()`, which needs `pip install "pyeuropepmc[analytics]"`; see [Analytics and visualization](../api/analytics-visualization.md) |
| Follow citations and references | `ArticleClient.get_citations(source, article_id)` and `ArticleClient.get_references(source, article_id)`; for citation graphs, see [Citation graph walking](../features/citation-walking.md) |
