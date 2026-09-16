# Migrating from PyEuropePMC 1.x to 2.0

Version 2.0 is a **major release**: the package internals were reorganised
into a *vertical-slice* layout and most runtime dependencies became
**optional extras**. The high-level API you already use is unchanged —
`pyeuropepmc.SearchClient`, `pyeuropepmc.QueryBuilder`,
`pyeuropepmc.PaperEnricher`, `pyeuropepmc.EuropePMCParser`, etc. all still
import from the top level exactly as before. What changed is *how the
package installs* and *where things live if you used deep imports*.

## TL;DR checklist

1. Upgrade: `pip install -U pyeuropepmc`.
2. Run your code / test suite. If you only ever used top-level imports
   (`from pyeuropepmc import SearchClient`), **you likely need to change
   nothing**.
3. If something now raises `OptionalDependencyError`, install the extra it
   names (see [§1](#1-installation)) — or `pip install "pyeuropepmc[all]"`
   to restore the 1.x "everything included" behaviour in one step.
4. If you used a deep import path (`pyeuropepmc.clients.search`,
   `pyeuropepmc.processing.analytics`, …), update it per the
   [import-path table](#2-import-paths) below.
5. If you pin `pydantic` yourself, note it's now a core dependency of
   pyeuropepmc and requires v2 (see [§6](#6-new-core-dependency-pydantic))
   — no action needed unless you pin an incompatible version.

---

## 1. Installation

```bash
# 1.x: one heavy install with pandas, matplotlib, rdflib, flask, Jupyter, ...
pip install pyeuropepmc

# 2.0: light core only (~15 packages: requests, caching, query building,
# JATS/XML parsing, pydantic, the CLI)
pip install pyeuropepmc

# 2.0: opt into what you need
pip install "pyeuropepmc[analytics]"        # pandas / numpy — publication stats
pip install "pyeuropepmc[visualization]"    # matplotlib / seaborn — plots
pip install "pyeuropepmc[export]"           # xlsxwriter / tabulate — Excel/Markdown export
pip install "pyeuropepmc[rdf]"              # nothing now: the core rdflib writes JSON-LD
pip install "pyeuropepmc[agentic]"          # LangChain / LangGraph / OpenAI / Jinja2 — LLM agents
pip install "pyeuropepmc[ui]"               # Flask / Tornado — claim-review web UI
pip install "pyeuropepmc[signing]"          # cryptography — signed search logs
pip install "pyeuropepmc[bibliography]"     # bibtexparser — BibTeX read/write/convert
pip install "pyeuropepmc[zotero]"           # pyzotero — Zotero library sync
pip install "pyeuropepmc[semanticscholar]"  # semanticscholar — S2 client library
pip install "pyeuropepmc[enrichment]"       # semanticscholar

# 2.0: convenience bundles
pip install "pyeuropepmc[standard]"         # analytics + visualization + export + notebook niceties
pip install "pyeuropepmc[all]"              # everything — reproduces 1.x behaviour exactly
```

The `rdf` extra installs nothing any more: rdflib, a core dependency, writes
JSON-LD itself, which made rdflib-jsonld redundant. Since 2.1.0 `[all]` does not
include rdfizer either; RML mapping needs it installed separately:
`pip install rdfizer`.

If you use a feature whose extra isn't installed, you get a clear error
naming the fix instead of an `ImportError` deep in a traceback:

```
OptionalDependencyError: The '<package>' package is required for <feature>.
Install it with: <install command>
```

`import pyeuropepmc` itself is now **lazy** (PEP 562): submodules and their
heavy dependencies load on first attribute access, not at import time.
Measured import time dropped from ~2.6 s to ~0.15 s. This is transparent for
normal use (`pyeuropepmc.SearchClient` still "just works"), but if you did
something unusual like `import pyeuropepmc; sys.modules["pyeuropepmc.features...
"]` directly, that submodule now only exists in `sys.modules` after it's been
touched once.

## 2. Import paths

Top-level names are unchanged — prefer them, they're guaranteed stable:

```python
from pyeuropepmc import (
    SearchClient, ArticleClient, AnnotationsClient, FTPDownloader,
    FullTextClient, EuropePMCParser, QueryBuilder, PaperEnricher,
    EnrichmentConfig, PaperProcessingPipeline, PipelineConfig,
    ArtifactStore,
    UnifiedSearch,          # new in 2.0
    SmartCitationAnalysis,  # new in 2.0, needs pyeuropepmc[agentic]
)
```

If you used deep import paths, update them:

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
| `pyeuropepmc.enrichment.merger` | `pyeuropepmc.features.enrich.merger` (dedup) / `.data_merger` (field merge) |
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

There are no compatibility shims for the old paths — `import
pyeuropepmc.clients.search` raises a bare `ModuleNotFoundError`, not a
deprecation warning. Update the import.

## 3. New: literature deduplication

1.x `pyeuropepmc.enrichment.merger` only had `DataMerger` (field-level metadata
merge of two records for the *same* paper) — that class still exists,
unchanged in behaviour, at `pyeuropepmc.features.enrich.data_merger.DataMerger`.

2.0 adds `LiteratureMerger`, which deduplicates a *list of results from
different sources*:

```python
from pyeuropepmc.features.enrich.merger import LiteratureMerger, DedupConfig, DedupMode

# One list of result dicts per source
europepmc_results = [{"title": "CRISPR screens in cancer", "doi": "10.1000/example.1", "source": "europepmc"}]
pubmed_results = [{"title": "CRISPR screens in cancer", "doi": "10.1000/example.1", "source": "pubmed"}]

merger = LiteratureMerger(config=DedupConfig(mode=DedupMode.BALANCED))
merged, report = merger.merge_results([europepmc_results, pubmed_results])
```

CORD-19-style DOI/PMID/PMCID/title-hash grouping, with `BALANCED` /
`FOCUSED` / `RELAXED` modes, author- and journal-overlap gates, and
retraction/salami-slice awareness. `report` is a structured `MergeReport`
with per-group provenance.

## 4. New: multi-source search

`pyeuropepmc.features.search` did not exist in 1.x, which only searched
Europe PMC. 2.0 adds source clients for PubMed (E-utilities), arXiv,
ClinicalTrials.gov v2, DOAJ, DBLP, HAL, CORE, and Zenodo, plus adapters for
Europe PMC, OpenAlex, and Semantic Scholar — federated by `UnifiedSearch`:

```python
from pyeuropepmc.features.search import UnifiedSearch, registry

registry.available_sources(installed_only=True)
# ['arxiv', 'clinicaltrials', 'core', 'dblp', 'doaj', 'europepmc',
#  'hal', 'openalex', 'pubmed', 'semantic_scholar', 'zenodo']

searcher = UnifiedSearch(sources=["europepmc", "pubmed", "arxiv"])
results, report = searcher.search("CRISPR cancer therapy", limit=25)
print(report.metadata["source_times"], report.metadata["source_errors"])
```

Each source's query is automatically translated into that backend's own
dialect (`features.search.query_translation`) — you write one query, not one
per source. Third-party packages can register additional sources via the
`pyeuropepmc.sources` entry-point group; see
`pyeuropepmc.features.search.registry.register_source()`.

## 5. New: enrichment sources, agentic workflows, and the CLI

None of the following existed in 1.x. They're additive — nothing to migrate,
just new capabilities available once you opt in:

- **iCite** (NIH citation metrics) joins CrossRef, OpenAlex, Semantic
  Scholar, ORCID, Unpaywall, DataCite, and ROR under
  `pyeuropepmc.features.enrich.sources`.
- **Agentic workflows** (`pyeuropepmc.agentic`, extra `agentic`): a
  LangChain/LangGraph-backed LLM client, `SmartCitationAnalysis`, and a tool
  registry.
- **Multi-agent claim verification** (`pyeuropepmc.claims`): extracts
  factual claims from text and verifies each against the literature, with an
  optional Flask review UI (`pyeuropepmc.ui`, extra `ui`) for accepting or
  rejecting claims and exporting a bibliography.
- **JATS normalisation** (`JATSNormalizer`,
  `pyeuropepmc.features.fulltext.jats_normalizer`) prepares full-text XML for
  downstream text-mining pipelines.
- **XML parser extensions** (`pyeuropepmc.features.fulltext.extensions`):
  typed content blocks, MathML-to-LaTeX conversion, peer-review parsing,
  JATS4R compliance validation, a LinkML schema, a reference resolver, and an
  optional lxml backend. The lxml backend has since been removed: all XML is
  now parsed with defusedxml.
- **A CLI**, installed as the `pyeuropepmc` command:
  ```bash
  pyeuropepmc normalize text path/to/article.xml         # JATS -> clean plain text
  pyeuropepmc unified_search search "CRISPR therapy"     # multi-source search + dedup
  pyeuropepmc claim verify "Some factual claim."         # LangGraph claim verification (needs [agentic])
  pyeuropepmc benchmark run                              # XML parser quality/perf benchmarks
  ```
  Run `pyeuropepmc --help`, or `<subcommand> --help`, for the full command
  tree (`normalize` also has `sections`, `bioc`, `classify` and `batch`;
  `unified_search` also has `compare-sources`; `claim` also has `stream` and
  `serve`; `benchmark` has commands for datasets, runs, profiling and reports).
- `pyeuropepmc-mcp`: an [MCP](https://modelcontextprotocol.io/) server
  exposing search/fulltext/enrichment tools to MCP-compatible clients
  (Claude Desktop, etc.).

## 6. New core dependency: pydantic

**`pydantic`** (>=2.7.4) is now a core dependency — installed with a bare
`pip install pyeuropepmc`, no extra needed. It's used by the core data
models (`pyeuropepmc.models.literature`, `.clinical_trial`). If you already
depend on a specific pydantic v1 in the same environment, note pyeuropepmc
requires pydantic v2; the two are not installable side by side.

`python-dateutil` remains **optional**: if installed, date fields with
free-text values get fuzzy-parsed into real `date` objects; if not, they
pass through as cleaned strings. No extra currently bundles it — install it
directly (`pip install python-dateutil`) if you want fuzzy date parsing.

## 7. Running the test suite (if you vendor or fork pyeuropepmc)

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

## 8. What did *not* change

- License: still MIT (now expressed via the SPDX `license = "MIT"` field
  rather than a classifier — no practical difference).
- Supported Python versions: `>=3.10,<4.0`, unchanged (3.13 support added).
- The public top-level API (§2) and its call signatures.
- `DataMerger`'s field-merge behaviour (§3).
- `pyeuropepmc.core.*`, `pyeuropepmc.cache.*`, `pyeuropepmc.models.*`,
  `pyeuropepmc.mappers.*`, `pyeuropepmc.storage.*`, `pyeuropepmc.pipeline`,
  `pyeuropepmc.mcp.*` — no import path or behaviour changes.

## Troubleshooting

**`OptionalDependencyError: ... needs the 'X' package`**
Install the named extra (§1). This replaces what used to be a bare
`ModuleNotFoundError` or `AttributeError` deep in a call stack in 1.x — the
underlying cause (a missing package) is the same, just reported clearly now.

**`ModuleNotFoundError: No module named 'pyeuropepmc.clients'` (or `.query`,
`.processing`, `.enrichment`)**
You're using a 1.x deep import path. Look it up in the [table](#2-import-paths)
above and update it. There is no compatibility shim.

**A script that did `pip install pyeuropepmc` and used pandas/matplotlib/
Flask/etc. now fails with an import error for that library**
Those were installed *incidentally* as part of 1.x's heavy default install,
even if your code only used pyeuropepmc's own wrapper around them. Install
the extra that bundles it (§1), or `pip install "pyeuropepmc[all]"` to
restore the old "everything included" behaviour in one step.
