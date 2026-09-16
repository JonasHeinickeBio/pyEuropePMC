# Copilot Coding Agent Instructions for PyEuropePMC

`docs/development/README.md` is the maintained developer guide; when this file and that guide disagree, the guide wins.

## Project overview
- **PyEuropePMC** searches, downloads, parses and analyses scientific literature from Europe PMC and other sources (PubMed, arXiv, ClinicalTrials.gov and more).
- Python 3.10–3.13, fully type-annotated; the package lives in `src/pyeuropepmc/`.
- Public names are exported lazily from `src/pyeuropepmc/__init__.py`: `SearchClient`, `ArticleClient`, `FullTextClient`, `FTPDownloader`, `FullTextXMLParser`, `QueryBuilder`, `UnifiedSearch` and others.

## Layout
- `core/`: the base API client, `ErrorCodes` and the exceptions derived from `PyEuropePMCError`.
- `features/literature/`: the Europe PMC clients, `QueryBuilder`, pagination, and the result filters `filter_pmc_papers` (every criterion must match) and `filter_pmc_papers_or` (any criterion may match) in `filters.py`.
- `features/fulltext/`: `FullTextClient`, `FullTextXMLParser`, the JATS normalizer, the full-text index and figure extraction.
- `features/search/` (`UnifiedSearch` and its sources), `features/enrich/` (`PaperEnricher`), `features/citations/`, `features/bibliography/`, `features/analytics/`.
- `cache/` (`CacheConfig`, `CacheBackend`; caching is opt-in), `models/`, `builders/`, `mappers/` (RDF), `cli/` (the `pyeuropepmc` command) and `mcp/` (the `pyeuropepmc-mcp` server).
- Optional features load their libraries lazily and raise `OptionalDependencyError` naming the extra to install; see `src/pyeuropepmc/_optional_imports.py`.

## Conventions
- **Errors:** raise the project exceptions with an `ErrorCodes` member; every code is documented in `docs/reference/error-codes.md`.
- **XML:** parse with defusedxml only. Ruff rejects the standard-library parsers (S313–S319) and lxml.
- **Docstrings:** every public class and function has one; most modules use NumPy-style `Parameters`/`Returns` sections.
- **Imports:** absolute imports within `pyeuropepmc`.
- **Commits and pull request titles:** Conventional Commits (`type(scope): description`).

## Tests
- pytest, in `tests/`. `tests/conftest.py` infers category markers (`functional` and `integration` from the directory, `unit` for any test in no other category), so mark explicitly only what it cannot infer, such as `slow`, `network` or `e2e`.
- The default run is offline: pytest-socket blocks the network, and slow, functional, network, benchmark and e2e tests are deselected.
- Skip a test that needs an optional package with `pytest.mark.skipif(not is_dependency_available("<package>"), ...)`.

## Workflow
- Set up with `poetry install --all-extras`; the `dev` dependency group is included.
- Before a pull request: `poetry run pytest`, `poetry run ruff check src/ tests/`, `poetry run ruff format --check src/ tests/`, `poetry run mypy src/`, and `poetry run pre-commit run --all-files`.
- CI: `cdci.yml` (lint, types, bandit and the tests with coverage), `unit-tests.yml` (core dependencies only), `python-compatibility.yml` (Python 3.10–3.13) and `zizmor.yml`. Pull requests merge only when the required checks pass.
- Releases: pushing a `vX.Y.Z` tag runs `release.yml`, which publishes to PyPI with trusted publishing; see `docs/development/ci-and-release-workflow.md`.

## Examples and documentation
- `examples/` holds numbered example folders, for instance `examples/07-advanced-filtering/07-filtering-demo.ipynb` for the two filters.
- `docs/` holds the user guides, the API reference and the development guides.
