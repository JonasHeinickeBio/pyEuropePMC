# Agent Guidance for pyEuropePMC

## Quick‑Start Setup
- Run `make create_environment` – installs **pipx**, **poetry**, creates a virtual env and installs all deps.
- Alternatively, `poetry install` works if you already have a Python 3.10+ interpreter.

## Core Development Commands (Makefile)
- `make requirements`    Install/upgrade pip and pins from **requirements.txt**.
- `make lint`       Run **ruff** static analysis.
- `make format`      Auto‑format with **ruff**.
- `make ruff`       Lint **and** format in‑place.
- `make quality`     Run **ruff**, **ruff --check**, **mypy**, and **bandit**.
- `make quality-full`  Run **quality** plus **CodeScene** analysis.
- `make test`      Run the full pytest suite.
- `make test-coverage` Run tests with coverage, generate HTML report.
- `make sync-rdf`    Synchronise RML mappings (`scripts/sync_rdf_mappings.py`).

## Building & Distribution
- Release workflow uses **semantic‑release** (see `[tool.semantic_release]` in `pyproject.toml`).
- Build wheel/tarball: `poetry build` (also used by CI).

## Running Examples
- All example scripts are under `examples/` and can be executed after installing the package.
- Typical pattern:
  ```bash
  python -m examples.01-getting-started.01-basic-usage
  ```
  (adjust path to the desired example).

## Testing Details
- Tests live in `tests/` and are selected by markers:
  - `unit`, `integration`, `functional`, `slow`, `network`.
  - Use e.g. `pytest -m "not network"` to skip network‑dependent tests.
- CI runs `make test-coverage` and enforces coverage > 50 % (see `[tool.coverage.report]`).

## Repository Structure Highlights
- `src/pyeuropepmc/` – package source.
- `src/pyeuropepmc/clients/` – API client classes (`SearchClient`, `FullTextClient`, `FTPDownloader`).
- `src/pyeuropepmc/query/` – query‑builder utilities.
- `src/pyeuropepmc/enrichment/` – external metadata enrichment (CrossRef, Unpaywall, etc.).
- `conf/` – RDF mapping configuration files.
- `docs/` – generated documentation (GitHub Pages).

## Gotchas & Conventions
- **Ruff** is the sole formatter/linter; do not run `black` or `autopep8`.
- **Bandit** skips B101/B303; security checks are limited to the `src/` tree.
- The `src/pyeuropepmc/ftp_downloader.py` is marked complex (C901) – ignore complexity warnings there.
- The package requires Python 3.10‑3.12; CI enforces this via `requires-python`.
- `Makefile` default target is `help`, which lists all available rules.

## CI / GitHub Actions
- CI pipelines (`cdci.yml`, `python-compatibility.yml`, `deploy-docs.yml`, `codeql.yml`) run the above quality and test commands.
- PR checks expect the `make quality-full` pass.
