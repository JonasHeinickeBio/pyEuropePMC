# Copilot Coding Agent Instructions for PyEuropePMC

## Project Overview
- **PyEuropePMC** is a modular Python toolkit for searching, retrieving, and analyzing scientific literature from Europe PMC.
- Core modules: `search.py` (querying), `fulltext.py` (content retrieval), `ftp_downloader.py` (bulk downloads), `parser.py` (response parsing), `cache.py` (optional diskcache-based caching), `filters.py` (advanced result filtering).
- All code is Python 3.10+ and type-annotated. Type safety, robust error handling, and test coverage are enforced.

## Architecture & Patterns
- **Main entry point:** `src/pyeuropepmc/` (all public APIs are exposed here; see `__init__.py`).
- **Clients:** `SearchClient`, `FullTextClient`, and `FTPDownloader` are the main user-facing classes. Use context managers for resource management.
- **Caching:** Optional, via `CacheBackend` in `cache.py`. If `diskcache` is missing, fallback is safe and import will not break.
- **Filtering:** Two filtering functions in `filters.py` for post-query result filtering (supports partial/case-insensitive matching):
  - `filter_pmc_papers`: AND logic - papers must match ALL criteria, and ALL terms within each criteria set (MeSH, keywords, abstract).
  - `filter_pmc_papers_or`: OR logic - papers match if ANY criteria set matches, and ANY term within each set can match.
- **Error handling:** Custom exceptions in each module; all API errors are wrapped in project-specific exceptions.
- **Testing:** All new features require tests in `tests/` (mirroring module structure). Use pytest, with markers for `unit`, `integration`, `slow`, etc.

## Developer Workflow
- **Install:** Use Poetry (`poetry install`) or pip (`pip install -e .[dev]`).
- **Run tests:** `pytest` (all), `pytest -k <pattern>` (subset), `pytest --cov=src/pyeuropepmc` (coverage).
- **Static checks:** `pre-commit run --all-files` (runs ruff, mypy, bandit, etc.).
- **Linting:** `ruff check .` and `ruff format .` (see `pyproject.toml` for config).
- **Type checking:** `mypy src/` (strict mode, see `pyproject.toml`).
- **CI:** GitHub Actions in `.github/workflows/ci.yml` (tests, lint, type check, coverage for 3.10–3.12).
- **Release:** Use `bump2version`, update changelog, run full test suite, then publish via Poetry/Twine.

## Project Conventions
- **Imports:** Absolute imports within `pyeuropepmc`. All public APIs re-exported in `__init__.py`.
- **Docstrings:** Google style. All public methods/classes must have docstrings.
- **Error handling:** Never raise raw exceptions; always wrap in project-specific exceptions.
- **Tests:** Place in `tests/` with same substructure as `src/pyeuropepmc/`. Use fixtures for sample data.
- **Pre-commit:** All code must pass pre-commit before PR/merge.
- **Commit messages:** Conventional Commits (see `docs/development/README.md`).

## Integration Points
- **External dependencies:** `requests`, `diskcache` (optional), `pandas`, `numpy`, `rdflib`, `flask`, `tqdm`, etc. (see `pyproject.toml`).
- **Bulk downloads:** Use `FTPDownloader` for FTP-based retrieval; see `examples/` for usage.
- **Filtering:** Two filtering approaches available:
  - `filter_pmc_papers`: AND logic for precise, specific results (all criteria must match)
  - `filter_pmc_papers_or`: OR logic for broad, exploratory results (any criteria can match)
  - See `examples/filtering_demo.ipynb` for usage comparisons.

## Examples & Documentation
- See `examples/` for usage patterns and advanced scenarios.
- See `docs/` for API reference, advanced usage, and development guidelines.

## When in Doubt
- Prefer mirroring patterns from `search.py`, `cache.py`, and `filters.py`.
- Always add/modify tests for new or changed features.
- Ask for clarification if a workflow or pattern is unclear or missing.
