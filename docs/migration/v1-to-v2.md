# Migrating from PyEuropePMC 1.x to 2.0

Version 2.0 is a **major release**. Two things changed that can break existing
code:

1. the package was reorganised into a *vertical-slice* layout, so deep import
   paths moved;
2. most runtime dependencies became **optional extras**, so a bare
   `pip install pyeuropepmc` now installs a small core only.

The high-level API is unchanged: `pyeuropepmc.SearchClient`,
`pyeuropepmc.QueryBuilder`, `pyeuropepmc.PaperEnricher`,
`pyeuropepmc.EuropePMCParser`, etc. still import from the top level.

---

## 1. Installation

```bash
# 1.x: one heavy install with pandas, matplotlib, rdflib, flask, Jupyter, ...
pip install pyeuropepmc

# 2.0: light core only
pip install pyeuropepmc

# 2.0: opt into what you need
pip install "pyeuropepmc[analytics]"        # pandas / numpy
pip install "pyeuropepmc[visualization]"    # matplotlib / seaborn
pip install "pyeuropepmc[export]"           # xlsx / markdown-table export
pip install "pyeuropepmc[rdf]"              # RDF / RML mapping
pip install "pyeuropepmc[agentic]"          # LangChain / OpenAI / LangGraph
pip install "pyeuropepmc[ui]"              # Flask review UI
pip install "pyeuropepmc[enrichment]"       # library-backed enrichment sources
pip install "pyeuropepmc[semanticscholar]"  # Semantic Scholar library

# to reproduce 1.x behaviour exactly
pip install "pyeuropepmc[all]"
```

If you use a feature whose extra isn't installed you get a clear error naming
the fix, instead of an `ImportError` deep in a traceback:

```
OptionalDependencyError: literature source 'semantic_scholar' needs the
'semanticscholar' package. Install it with: pip install pyeuropepmc[semanticscholar]
```

## 2. Import paths

Top-level names are unchanged — prefer them:

```python
from pyeuropepmc import SearchClient, ArticleClient, FullTextClient, QueryBuilder
from pyeuropepmc import PaperEnricher, EuropePMCParser, UnifiedSearch  # UnifiedSearch is new
```

Deep imports moved:

| 1.x | 2.0 |
|-----|-----|
| `pyeuropepmc.clients.search` | `pyeuropepmc.features.literature.search` |
| `pyeuropepmc.clients.article` | `pyeuropepmc.features.literature.article` |
| `pyeuropepmc.clients.annotations` | `pyeuropepmc.features.literature.annotations` |
| `pyeuropepmc.clients.ftp_downloader` | `pyeuropepmc.features.literature.ftp_downloader` |
| `pyeuropepmc.clients.fulltext` | `pyeuropepmc.features.fulltext.fulltext_client` |
| `pyeuropepmc.clients.unpaywall_client` | `pyeuropepmc.features.enrich.sources.unpaywall_client` |
| `pyeuropepmc.query.query_builder` | `pyeuropepmc.features.literature.query_builder` |
| `pyeuropepmc.query.filters` | `pyeuropepmc.features.literature.filters` |
| `pyeuropepmc.query.pagination` | `pyeuropepmc.features.literature.pagination` |
| `pyeuropepmc.enrichment` | `pyeuropepmc.features.enrich` |
| `pyeuropepmc.enrichment.enricher` | `pyeuropepmc.features.enrich.enricher` |
| `pyeuropepmc.enrichment.batch_enricher` | `pyeuropepmc.features.enrich.batch_enricher` |
| `pyeuropepmc.enrichment.merger` | `pyeuropepmc.features.enrich.merger` |
| `pyeuropepmc.enrichment.crossref` / `openalex` / `semantic_scholar` / `ror` / `datacite` / `unpaywall` | `pyeuropepmc.features.enrich.sources.<name>` |
| `pyeuropepmc.processing.fulltext_parser` | `pyeuropepmc.features.fulltext.fulltext_parser` |
| `pyeuropepmc.processing.parsers.*` | `pyeuropepmc.features.fulltext.parsers.*` |
| `pyeuropepmc.processing.converters.*` | `pyeuropepmc.features.fulltext.converters.*` |
| `pyeuropepmc.processing.extensions.*` | `pyeuropepmc.features.fulltext.extensions.*` |
| `pyeuropepmc.processing.jats_normalizer` | `pyeuropepmc.features.fulltext.jats_normalizer` |
| `pyeuropepmc.processing.search_parser` | `pyeuropepmc.features.literature.search_parser` |
| `pyeuropepmc.processing.annotation_parser` | `pyeuropepmc.features.fulltext.annotation_parser` |
| `pyeuropepmc.processing.annotations_to_rdf` | `pyeuropepmc.features.literature.annotations_to_rdf` |
| `pyeuropepmc.processing.analytics` | `pyeuropepmc.features.analytics.analytics` |
| `pyeuropepmc.processing.visualization` | `pyeuropepmc.features.analytics.visualization` |

Unchanged: `pyeuropepmc.core.*`, `pyeuropepmc.cache.*`, `pyeuropepmc.models.*`,
`pyeuropepmc.mappers.*`, `pyeuropepmc.storage.*`, `pyeuropepmc.pipeline`,
`pyeuropepmc.mcp.*`.

## 3. New: literature deduplication

1.x `pyeuropepmc.enrichment.merger` only had `DataMerger` (field-level metadata
merge of two records for the *same* paper) — that class still exists at
`pyeuropepmc.features.enrich.data_merger.DataMerger`.

2.0 adds `LiteratureMerger`, which deduplicates a *list of results from
different sources*:

```python
from pyeuropepmc.features.enrich.merger import LiteratureMerger, DedupConfig, DedupMode

merger = LiteratureMerger(config=DedupConfig(mode=DedupMode.BALANCED))
merged, report = merger.merge_results(list_of_result_lists)
```

## 4. New: multi-source search

```python
from pyeuropepmc.features.search import UnifiedSearch, registry

registry.available_sources(installed_only=True)
# ['arxiv', 'clinicaltrials', 'core', 'dblp', 'doaj', 'europepmc',
#  'hal', 'openalex', 'pubmed', 'semantic_scholar', 'zenodo']

searcher = UnifiedSearch(sources=["europepmc", "pubmed", "arxiv"])
results, report = searcher.search("CRISPR cancer therapy", limit=25)
print(report.metadata["source_times"], report.metadata["source_errors"])
```

## 5. Running the test suite

The default `pytest` run is now hermetic (no network, per-test timeout) and
excludes slow/functional/benchmark lanes automatically:

```bash
pytest                       # fast unit run (offline)
pytest -m functional         # real-service tests   (== pytest --run-real)
pytest -m benchmark --benchmark-only
pytest tests/integration --run-integration
```

It needs `pytest-socket` and `pytest-timeout` (in the `dev` group); without
them the suite still runs, just without the guard rails.
