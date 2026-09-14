# Changelog

All notable changes to PyEuropePMC are documented here.

## [2.1.2] - 2026-09-14

### 🐛 Bug Fixes

- **Fixed the MCP Registry publish job** (added in 2.1.1): `server.json`
  named the server `io.github.jonasheinickebio/pyeuropepmc`, but the
  registry's GitHub OIDC verification is case-sensitive and only grants
  permission for the exact-case GitHub login `JonasHeinickeBio` — so the
  2.1.1 release's `publish-mcp-registry` job failed with a 403
  ("You have permission to publish: `io.github.JonasHeinickeBio/*`.
  Attempting to publish: `io.github.jonasheinickebio/pyeuropepmc`").
  Corrected the casing in `server.json` and its documentation references.

## [2.1.1] - 2026-09-14

Docs and CI only — no changes to the installed package's runtime behavior.

### ✨ Features

- **`pyeuropepmc-mcp` is now published to the official
  [MCP Registry](https://registry.modelcontextprotocol.io/)** as
  `io.github.JonasHeinickeBio/pyeuropepmc`
  ([`server.json`](server.json)). Every tagged release republishes it
  automatically via GitHub OIDC (`publish-mcp-registry` job in
  `release.yml`) — no stored secret, the workflow's own repo identity
  proves namespace ownership.

### 🐛 Bug Fixes

- **Fixed the "Python Version Compatibility Matrix" Windows jobs**, broken
  since 2.1.0: every MCP test driving async code via `asyncio.run()`
  failed on Windows with `pytest_socket.SocketBlockedError`, because
  constructing a new event loop there needs a real (loopback-only) socket
  for its internal self-pipe, which `--disable-socket` blocked outright.
  `tests/mcp/conftest.py` now scopes `pytest.mark.allow_hosts(["127.0.0.1",
  "::1"])` to just the MCP test suite.

### 🔧 Maintenance

- Refreshed the README's badges: dynamic Python-version/PyPI badges instead
  of hand-typed ones that had drifted (actual test count is 5,000+, not
  the old "200+"), and a working CodeQL badge (the old one linked to a
  workflow file that doesn't exist, since CodeQL runs via GitHub's
  default-setup code scanning here, not a committed workflow).

## [2.1.0] - 2026-09-13

> **MCP server rewrite.** `pyeuropepmc-mcp` now runs on the official
> [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
> (`FastMCP`) instead of a hand-rolled JSON-RPC/stdio loop. The Python
> library API (`pyeuropepmc.SearchClient`, etc.) is unchanged — this affects
> only the MCP server and its 24 tools.

### ✨ Features

- **Spec-compliant, concurrent MCP server.** Rebuilt on `FastMCP`: tool
  errors are reported via the standard `isError: true` `CallToolResult`
  instead of ad hoc text, every tool call offloads its blocking
  network/disk work to a thread pool (`anyio.to_thread.run_sync`) so one
  slow request no longer stalls every other in-flight call, and input is
  validated against each tool's schema before the tool body ever runs.
- **More transports, more agents.** `pyeuropepmc-mcp --transport
  streamable-http` (or `sse`) runs the server as a standalone network
  service that any MCP-capable agent can reach over HTTP — not just
  stdio-based clients like Claude Desktop. New `--host`, `--port`, and
  `--log-level` flags (also settable via `PYEUROPEPMC_MCP_*` env vars).
- **Cached, reusable clients.** `SearchClient`, `CitationWalker`,
  `ClinicalTrialsClient`, `FigureExtractor`, and the LLM analysis agent are
  now constructed once per process and reused, instead of being rebuilt on
  every call — faster, and it fixes two latent bugs where a fresh
  `CitationWalker` per call reset its own rate limiter and a fresh LLM
  agent per call never hit its own analysis cache.
- **Structured tool output.** Tools return typed Python values instead of
  pre-serialized JSON strings; the SDK derives an output schema and returns
  both `structuredContent` and a human-readable text rendering.
- **Progress notifications.** `unified_search`, `citation_snowball`,
  `paper_screening`, and `literature_review` emit `ctx.info(...)` MCP
  logging notifications mid-call, so a client that surfaces them can show
  progress during a multi-source search instead of going silent.
- **Tool annotations.** Every tool advertises `readOnlyHint`/`openWorldHint`/
  `idempotentHint` metadata so a calling agent can reason about a tool
  without executing it first.

### 💥 Breaking changes (MCP tool interface only)

- **`mcp` is now a required core dependency** (previously the server had no
  real MCP SDK dependency at all). A bare `pip install pyeuropepmc` pulls it
  in automatically.
- **`citation_snowball`'s `strategy` argument is now validated.** An invalid
  value is rejected with a schema-validation error instead of silently
  falling back to `"forward"`.
- **`get_paper_citations` gained a `limit` parameter** (default 100) and
  dropped the `source` parameter, which the previous implementation accepted
  but never used.
- **`literature_review` gained an explicit `excluded_topics` parameter**
  that the previous implementation read from `arguments` without declaring
  in its schema.

### 🧪 Testing

- Rewrote the MCP test suite: 94 hermetic unit tests exercise each tool
  function directly (mocked clients via the module's lazy-singleton caches)
  plus FastMCP-level schema/registry checks, and 4 new e2e tests drive the
  real server subprocess over stdio with the official MCP client instead of
  hand-rolled JSON-RPC framing.

### 📚 Documentation

- Rewrote [`src/pyeuropepmc/mcp/README.md`](src/pyeuropepmc/mcp/README.md)
  and the top-level MCP section of the README for the new transports, tool
  registry, and design notes.

### 🔧 Maintenance

- **Fixed `mypy` aborting entirely on Python 3.12+.** numpy 2.5.x (the
  version `poetry.lock` resolves for Python ≥3.12) ships stubs that use PEP
  695 syntax (`type X = ...`, `class Foo[T]`) throughout — reachable
  transitively via `rapidfuzz` (a core dependency) and `matplotlib`/`pandas`
  (extras), not just via this package's own numpy usage. Under the
  project's `python_version = "3.10"` mypy target this crashed the *entire*
  run ("errors prevented further checking"), so `poetry run mypy src/`
  silently checked nothing on a Python 3.12 host — including the
  `release.yml` `verify` job, which pins Python 3.12. `[tool.mypy]` now
  targets `python_version = "3.12"`; this doesn't loosen protection against
  3.10-incompatible syntax landing in `src/`, since
  `python-compatibility.yml` separately compiles every file under real
  3.10–3.13 interpreters. Bumping the target surfaced one real, previously
  hidden issue: `load_entry_point_sources()`'s pre-3.10 `importlib.metadata`
  fallback (`entry_points().get(...)`) doesn't type-check against a modern
  `EntryPoints`, and was dead code anyway given `requires-python = ">=3.10"`
  — removed.

## [2.0.0] - 2026-09-10

> **Major release.** Package internals were reorganised into a vertical-slice
> layout and most runtime dependencies became optional. The public
> `pyeuropepmc.<Name>` API (e.g. `pyeuropepmc.SearchClient`) is unchanged, but
> deep imports and a bare `pip install` behave differently — see
> [`docs/migration/v1-to-v2.md`](docs/migration/v1-to-v2.md).

### 💥 Breaking changes

- **Vertical-slice package layout.** `src/pyeuropepmc/` is now organised by
  feature. Deep import paths changed:
  | 1.x | 2.0 |
  |-----|-----|
  | `pyeuropepmc.clients.search` | `pyeuropepmc.features.literature.search` |
  | `pyeuropepmc.clients.article` / `annotations` / `ftp_downloader` | `pyeuropepmc.features.literature.*` |
  | `pyeuropepmc.clients.fulltext` | `pyeuropepmc.features.fulltext.fulltext_client` |
  | `pyeuropepmc.enrichment.*` | `pyeuropepmc.features.enrich.*` (external APIs under `features.enrich.sources.*`) |
  | `pyeuropepmc.query.*` (`query_builder`, `filters`, `pagination`) | `pyeuropepmc.features.literature.*` |
  | `pyeuropepmc.processing.fulltext_parser` / `parsers` / `converters` / `extensions` | `pyeuropepmc.features.fulltext.*` |
  | `pyeuropepmc.processing.analytics` / `visualization` | `pyeuropepmc.features.analytics.*` |
  | `pyeuropepmc.processing.annotation_parser` / `annotations_to_rdf` | `pyeuropepmc.features.literature.*` / `features.fulltext.*` |

  Top-level re-exports (`pyeuropepmc.SearchClient`, `pyeuropepmc.QueryBuilder`,
  `pyeuropepmc.PaperEnricher`, …) still work.
- **Dependencies split into optional extras.** A bare `pip install pyeuropepmc`
  now installs a light core only (~14 packages: `requests`, caching, query
  building, JATS parsing, CLI). pandas, numpy, matplotlib, seaborn, rdflib,
  flask, langchain/openai, semanticscholar, Jupyter, etc. are **no longer
  installed by default**. Use extras:
  `analytics`, `visualization`, `export`, `rdf`, `agentic`, `ui`, `signing`,
  `enrichment`, `semanticscholar`, `bibliography`, `zotero`, `standard`, `all`.
  For the previous behaviour: `pip install "pyeuropepmc[all]"`.
- **`import pyeuropepmc` is now lazy (PEP 562).** Submodules and their heavy
  dependencies load on first attribute access. Accessing a feature whose extra
  is missing raises `OptionalDependencyError` with the exact `pip install`
  command. Import time dropped from ~2.6 s to ~0.15 s.
- `uv.lock` removed — Poetry is the single supported install workflow.
- Version bumped `1.18.0 → 2.0.0`; SPDX `MIT` license expression.

### ✨ Features

- **Multi-source literature search** (`pyeuropepmc.features.search`):
  - `UnifiedSearch` federates a single query across many sources in parallel
    (`ThreadPoolExecutor`), normalises and deduplicates the combined results,
    and reports per-source timings and errors.
  - Pluggable **source registry** (`features.search.registry`): `SourceSpec`,
    `register_source()`, `available_sources(installed_only=…)`,
    `source_capabilities()`, `load_source()`, plus a `pyeuropepmc.sources`
    entry-point hook for third-party sources.
  - New source clients: PubMed (E-utilities), arXiv, ClinicalTrials.gov v2,
    DOAJ, DBLP, HAL, CORE, Zenodo — and adapters for Europe PMC, OpenAlex and
    Semantic Scholar.
  - **Query translation** (`features.search.query_translation`): rewrites one
    query into each backend's dialect (arXiv `all:"…"`, free-text for
    OpenAlex/S2, field syntax kept for Europe PMC/PubMed; uses the optional
    `search-query` parser when available).
- **Identifier-cluster deduplication** — new `LiteratureMerger` in
  `features.enrich.merger`: CORD-19-style DOI/PMID/PMCID/title-hash grouping
  with `BALANCED` / `FOCUSED` / `RELAXED` modes, author- and journal-overlap
  gates, retraction and salami-slice awareness, and a structured `MergeReport`.
  (The 1.x `DataMerger` field-level metadata merge is unchanged.)
- **Metadata enrichment sources** consolidated under
  `features.enrich.sources`: CrossRef, OpenAlex, Semantic Scholar (+ pro
  wrapper), ORCID, Unpaywall, DataCite, ROR, and **iCite** (NIH citation
  metrics — new).
- **Agentic workflows** (`pyeuropepmc.agentic`, extra `agentic`): LangChain/
  LangGraph LLM client, `SmartCitationAnalysis`, a tool registry, and a
  multi-agent claim-verification pipeline (`pyeuropepmc.claims`) with an
  optional Flask review UI (`pyeuropepmc.ui`, extra `ui`).
- **JATS normalisation** for text-mining pipelines (`JATSNormalizer`) and a
  `pyeuropepmc normalize` CLI subcommand.
- **XML parser extensions**: content blocks, MathML, peer-review, JATS4R,
  batch processing, LinkML schema, reference resolver, lxml backend.
- `EuropePMCLiteratureAdapter` makes the native Europe PMC `SearchClient` a
  first-class `UnifiedSearch` source.
- `utils/env_loader.py` for `.env` handling; `_optional_imports.py` /
  `utils/dependencies.py` for graceful optional-dependency errors.

### 🧪 Testing

- **Hermetic default test run.** `pytest-socket` blocks real network in the
  default suite (a mis-mocked test fails fast with `SocketBlockedError` instead
  of hanging), `pytest-timeout` caps each test at 120 s, and markers are
  inferred from a test's path (`functional/`, `integration/`, `benchmark`,
  `gui`) so whole directories are excluded without per-file annotation. This
  fixed the full suite hanging and being OOM-killed. Run the excluded lanes
  with `pytest -m functional` / `--run-real` / `-m benchmark` /
  `--run-integration`.
- Tests reorganised to mirror `src/` (`tests/features/…`).
- Recorded fixtures replace several live-API "unit" tests; ~3,640 tests,
  ~50 s, ~410 MB peak.

### 🔧 Maintenance

- `ruff check src/` and `mypy src/` (strict) are clean; `pytest` green
  (3602 passed). The `release.yml` / `cdci.yml` gates pass locally.
- `pyproject.toml` moved to static PEP 621 metadata; `requirements.txt` /
  `poetry.lock` regenerated from it.
- Optional-dependency group maps consolidated into a single source of truth;
  `User-Agent` now reports the real package version; `py.typed` shipped.
- `sentence-transformers` is intentionally **not** an extra — it pulls in
  `torch` + the `nvidia-cuda-*` wheels, which made `poetry lock` effectively
  non-terminating. Semantic text matching asks you to install it directly.

## [1.18.0] - 2026-07-03

### ✨ Features

- **PaperProcessingPipeline Context Manager**: Added `__enter__` and `__exit__` methods
  - Pipeline now supports `with` statement for automatic resource cleanup
  - Consistent with other enrichment clients (`PaperEnricher`, `BatchEnricher`)

### 🐛 Bug Fixes

- **Hugging Face Dataset Loading**: Fixed dataset config name and import handling
  - Changed config name from `"PMC_sample_1943"` to `"default"` in tests
  - Added try-except around `datasets` module import in `_try_huggingface_load_dataset()`
  - Graceful fallback when datasets library is not installed

### 🧪 Testing

- **Benchmark Suite**: Added 35 new tests for profiler, memory tracker, dataset, and runner
  - Profiler tests: context manager, time function, time et parse
  - Memory tests: start/stop flow, snapshot structure with peak/current/allocated
  - Runner tests: normal, profiling, memory profiling, multiple datasets, limits
  - Dataset tests: local subdirs, empty dataset, to_dict structure
- **Pipeline Context Manager Test**: Added test for `PaperProcessingPipeline` with cleanup

### 🔧 Maintenance

- **Version Bump**: Updated to version 1.18.0
  - Updated pyproject.toml version from 1.17.0 to 1.18.0
  - Updated src/pyeuropepmc/__init__.py __version__ to 1.18.0
  - Created git tag v1.18.0 for release

- **All Tests Pass**: 3203 tests pass, 11 skipped, 75.20% coverage

## [1.17.0] - 2026-06-17

### 🐛 Bug Fixes

- **Type Errors**: Fixed mypy type errors in search_logging.py and cache.py
  - Added proper type annotations for optional cryptography and cachetools imports
  - Removed unused `type: ignore` comments

- **Test Failures**: Fixed test assertions in test_helpers_coverage.py
  - Updated error message assertions to match actual validation error messages
  - Changed "Failed to read JSON file" to "JSON file not found" for VALID004
  - Changed "Failed to parse JSON file" for VALID005 validation error

### ✨ Features

- **Documentation Restructuring**: Complete overhaul of documentation organization
  - Moved guides to docs/guides/, reference to docs/reference/, migration to docs/migration/
  - Added comprehensive guides for Semantic Scholar API integration
  - New documentation on professional library usage and rate limiting

### 🔧 Maintenance

- **Version Bump**: Updated to version 1.17.0
  - Updated pyproject.toml version from 1.16.0 to 1.17.0
  - Updated src/pyeuropepmc/__init__.py __version__ to 1.17.0
  - Created git tag v1.17.0 for release

- **Auto-formatting**: Applied ruff format across codebase
  - Fixed import ordering in all test files
  - Cleaned up unused imports
  - Fixed trailing whitespace and EOF issues

## [1.15.0] - 2025-01-20

### ✨ Features

- **Parallel Download Rate Limiting Fix**: Improved rate limiter implementation for parallel batch downloads
  - Rate limiter now only invoked after cache miss (network boundary), preventing unnecessary delays for cached files
  - Fixed exception handler worker_id derivation to use futures mapping instead of stale stats dict
  - More efficient parallel downloads with proper rate limiting at network boundary
  - Fixed `NameError` when exception handlers reference undefined `stats` variable

### 🔧 Maintenance

- **Exception Handling**: Improved worker error handling in parallel downloads
  - Worker_id now correctly derived from `futures[future][0]` tuple
  - Consistent stats tracking regardless of execution context

## [1.14.0] - 2025-01-15

### ✨ Features

- **Enhanced RDF Mapping System**: Complete overhaul of RDF mapping capabilities with YAML-based configuration
  - New `InstitutionEntity` model for institutional data representation
  - Enhanced `ScholarlyWorkEntity` base class with PMID support and validation
  - Comprehensive RDF mapping synchronization script (`scripts/sync_rdf_mappings.py`)
  - Improved enrichment integration for external metadata sources

- **Advanced Enrichment Integration**: Expanded support for external APIs and data enrichment
  - New enrichment RDF generation demo script (`examples/09-enrichment/enrichment_rdf_demo.py`)
  - Enhanced RDF mapping for enrichment data with automatic entity building
  - Integration tests for enrichment workflows (`tests/mappers/test_enrichment_rdf.py`)

- **RDF Mapping Demonstration**: Complete end-to-end RDF mapping workflow example
  - New comprehensive demo notebook (`examples/10-rdf-mapping/rdf_mapping_demo.ipynb`)
  - Shows full pipeline from search → XML retrieval → RDF conversion → enrichment → comparison
  - Includes both basic XML-derived RDF and enriched RDF from external APIs

### 🔧 Maintenance

- **Model Enhancements**: Extended data models with better validation and RDF support
  - Added PMID field to `PaperEntity` with proper validation and normalization
  - Enhanced `AuthorEntity` and other models with enrichment-compatible fields
  - Improved type safety and documentation across all entity models

- **Testing Improvements**: Added comprehensive tests for new RDF mapping features
  - New test suite for enrichment RDF generation (`tests/mappers/test_enrichment_rdf.py`)
  - Enhanced model tests with RDF validation (`tests/models/test_models_rdf.py`)
  - Fixed pagination timing tests for accurate elapsed time measurement

### 📚 Documentation

- **New Examples**: Added comprehensive examples for RDF mapping workflows
  - RDF mapping demo showing complete pipeline from search to enriched RDF
  - Enrichment RDF generation examples with external API integration
  - Updated documentation for new features and capabilities

## [1.13.0] - 2025-01-10

### ✨ Features

- **Advanced Analytics and Visualization**: Comprehensive analytics suite with publication metrics, citation analysis, and interactive dashboards
  - Author statistics and geographic analysis
  - Journal distribution and publication type analysis
  - Quality metrics and duplicate detection
  - Interactive visualization plots for trends and distributions

- **HTTP Caching System**: Robust caching with requests-cache and conditional GET support
  - Configurable cache backends (memory, disk, Redis)
  - Cache invalidation and TTL management
  - Conditional requests to minimize API calls

- **Content-Addressed Artifact Storage**: SHA-256 based storage with deduplication
  - Efficient storage of large documents and metadata
  - Automatic deduplication to save disk space
  - Metadata tracking and artifact management

- **Full Text XML Parser**: Advanced parsing for Europe PMC full-text XML documents
  - Metadata extraction and table parsing
  - Multiple output formats (JSON, Markdown, plain text)
  - Configurable parsing schemas and element patterns

- **Advanced Filtering Utilities**: Enhanced post-query result filtering
  - `filter_pmc_papers`: AND logic for precise filtering
  - `filter_pmc_papers_or`: OR logic for broad exploratory searches
  - Support for MeSH terms, keywords, and abstract matching

- **Full-Text Content Retrieval**: Comprehensive client for retrieving full-text articles
  - Support for multiple formats (XML, PDF, plain text)
  - Progress tracking and error handling
  - Batch processing capabilities

### 🔧 Maintenance

- **Major Codebase Restructuring**: Complete architectural overhaul for better maintainability
  - Modular design with clear separation of concerns
  - Enhanced error handling and type safety
  - Comprehensive test coverage improvements

- **CI/CD Pipeline Enhancements**: Automated testing and quality assurance
  - Pre-commit hooks for code quality
  - Automated dependency updates
  - Coverage reporting and benchmarking


## [1.10.1] - 2025-11-10

### Fixed

- **CodeScene Integration**: Added missing `run_delta_analysis` function to CodeScene analysis script

## [1.10.0] - 2025-11-10

### ✨ Features

- **Enhanced CodeScene Integration**: Secure environment management for code health analysis
  - Improved CodeScene CLI integration with proper environment setup
  - Enhanced code quality monitoring and analysis capabilities

## [1.9.1] - 2025-11-10

### 🔧 Maintenance

- **Dependency Updates**: Updated multiple development and runtime dependencies
  - Updated `requests` to 2.32.5 for security improvements
  - Updated `notebook` to 7.4.7 for compatibility
  - Updated `attrs` to 25.4.0 and `jupyterlab-widgets` to 3.0.16
  - Updated CI actions: `actions/checkout` to v5, `actions/upload-artifact` to v5, `actions/labeler` to v6, `codecov/codecov-action` to v5, `actions/ai-inference` to v2

## [1.9.0] - 2025-11-10

### ✨ Features

- **CodeScene CLI Integration**: Automated code health analysis and quality monitoring
  - Integrated CodeScene CLI for comprehensive code analysis
  - Enhanced CI workflows with code health tracking

### 🔧 Maintenance

- **Query Builder Refactoring**: Improved error handling and removed unnecessary flags
  - Enhanced QueryBuilder with better validation and error handling
  - Removed SEARCH_QUERY_AVAILABLE flag for cleaner implementation
  - Added comprehensive unit tests for QueryBuilder functionality

- **CI Workflow Improvements**: Enhanced testing and issue tracking automation
  - Updated CI workflows for better test coverage and issue management
  - Improved automated dependency management

### Fixed

- Code review fixes: documentation improvements, unused import removal, and exception handling enhancements

## [1.8.1] - 2025-11-06

### Added

- **Advanced Query Builder**: Complete fluent API for building complex Europe PMC search queries
  - Type-safe field specifications with 150+ searchable fields
  - Fluent method chaining for complex boolean logic (AND/OR/NOT)
  - Optional query validation using CoLRev search-query package
  - Load/save queries in standard JSON format
  - Cross-platform query translation (PubMed, Web of Science, etc.)
  - Query evaluation with recall/precision metrics

- **Systematic Review Tracking**: PRISMA/Cochrane-compliant search logging
  - `log_to_search()` method for tracking queries in systematic reviews
  - Integration with search logging utilities for audit trails
  - Raw results saving for reproducibility
  - PRISMA flow diagram data generation
  - Complete systematic review workflow support

- **Field Coverage Validation**: API field synchronization tools
  - `validate_field_coverage()` function to check API vs code field coverage
  - `get_available_fields()` for fetching current API fields
  - Automated field metadata validation

### Improved

- Enhanced type safety with comprehensive Literal types for all search fields
- Better error handling with specific error codes and context
- Improved documentation with extensive examples and API reference
- Graceful fallback when optional dependencies are missing

## [1.8.0] - 2025-10-15

### Added

- AI-powered Feature Suggester GitHub Action for automated feature suggestions

## [1.7.0] - 2025-09-20

### Added

- **Full Text XML Parser**: Comprehensive XML parsing with metadata extraction
  - Support for table and figure extraction from full-text XML
  - Multiple output format conversions
  - Enhanced metadata parsing capabilities

## [1.6.0] - 2025-08-25

### Added

- **Advanced Filtering Utilities**: Powerful post-query result filtering
  - `filter_pmc_papers()`: AND logic filtering with MeSH, keywords, and abstract matching
  - `filter_pmc_papers_or()`: OR logic filtering for broader result sets
  - Case-insensitive and partial matching support

## [1.5.0] - 2025-08-10

### Added

- **Optional Disk Cache Integration**: Performance optimization with safe fallbacks
  - Disk-based caching using diskcache library
  - Backward compatibility when diskcache is not installed
  - Type-safe implementation with proper error handling

## [1.4.0] - 2025-07-28

### Added

- **Comprehensive Test Suite**: Expanded testing coverage
  - Additional unit tests for all functionality
  - Improved test organization and coverage reporting

### Improved

- Enhanced documentation with detailed usage examples
- Better code organization and maintainability

## [1.3.0] - 2025-07-22

### Added

- **Full-Text Content Retrieval**: Complete full-text access implementation
  - `FullTextClient` for downloading PDF, XML, and HTML content
  - Multiple fallback endpoints for robust retrieval
  - Intelligent content availability checking
  - Atomic download operations with proper error handling

## [1.2.0] - 2025-07-16

### Added

- **Full-Text Content Retrieval**: Complete implementation of full-text content access
  - `FullTextClient` class for downloading PDF, XML, and HTML content
  - Support for multiple fallback endpoints for robust content retrieval
  - Intelligent content availability checking
  - Atomic download operations with proper error handling

- **Bulk FTP Downloads**: Efficient bulk PDF downloads from Europe PMC FTP servers
  - `FTPDownloader` class for querying and downloading from FTP archives
  - Smart directory searching algorithm for optimal PMC ID location
  - Bulk download and extraction capabilities
  - ZIP file handling with automatic PDF extraction

- **Enhanced Test Coverage**: Comprehensive test suite with 200+ tests
  - Unit tests for all new functionality
  - Functional tests with realistic server responses
  - Edge case coverage and error handling validation

### Improved

- Enhanced error handling with specific error codes for full-text operations
- Updated documentation with full-text API reference
- Improved type annotations throughout the codebase
- Better rate limiting and respectful API usage

## [1.1.0] - 2025-06-25

### Added

- **Enhanced BaseAPIClient**: Improved session management and context support
- **Advanced Search Parameter Validation**: Better input validation and error handling
- **Unit Tests**: Comprehensive test coverage for search functionality
- **Copilot Instructions**: Coding standards and development guidelines

### Improved

- Enhanced EuropePMCParser error handling
- Better CI/CD pipeline with coverage reporting
- Improved documentation and usage examples

## [1.0.2] - 2025-06-15

### Fixed

- Minor bug fixes and improvements
- CI/CD pipeline refinements

## [1.0.1] - 2025-06-12

### Fixed

- Python setup and dependency configuration fixes
- Semantic release configuration updates

## [1.0.0] - 2025-06-10

### Initial Release

- Initial release with core search functionality
- Support for JSON, XML, and Dublin Core formats
- Comprehensive test suite (200+ tests)
- Complete documentation and examples
- Production-ready error handling and rate limiting

### Core Features

- Europe PMC search API integration
- Smart pagination for large result sets
- Context managers for resource management
- Type hints throughout codebase
- Built-in retry logic and connection handling

For detailed release information, see [docs/development/release-analysis.md](docs/development/release-analysis.md)
