# Development guide

This guide is for contributors to pyEuropePMC. It covers setting up a development environment, the lint, type and security tools, running tests, contribution conventions, CI, the release process, and a map of the repository and the package.

## Contents

- [Setup](#setup)
- [Code quality tools](#code-quality-tools)
- [Running tests](#running-tests)
- [Contributing guidelines](#contributing-guidelines)
- [CI workflows](#ci-workflows)
- [Release process](#release-process)
- [Repository layout](#repository-layout)
- [Package architecture](#package-architecture)

Related pages:

- [CI, branch protection and releases](ci-and-release-workflow.md)
- [Testing](testing-improvements.md)
- [Python version support](python-version-strategy.md)
- [XML parser internals](xml-parser-internals.md)
- [Documentation](documentation.md)
- [Feature Suggester workflow](feature-suggester.md)

## Setup

### Prerequisites

- Python 3.10 or later, the minimum in `requires-python`.
- Git with [Git LFS](https://git-lfs.com/). The full-text fixtures in `tests/fixtures/fulltext_downloads/` are stored with LFS.
- [Poetry](https://python-poetry.org/) 2.3.2, the version CI and the pre-commit hooks pin. Poetry manages `pyproject.toml` and `poetry.lock`.
- Optionally [uv](https://docs.astral.sh/uv/), which CI uses to install the locked dependencies.

### Install with Poetry

Clone the repository:

```bash
git clone https://github.com/JonasHeinickeBio/pyEuropePMC.git
```

```bash
cd pyEuropePMC
```

If Git LFS was not installed when you cloned, fetch the fixtures:

```bash
git lfs pull
```

Install the package in editable mode with the `dev` dependency group and every extra, which is what `cdci.yml` tests against:

```bash
poetry install --all-extras
```

`poetry.toml` places the environment in `.venv` inside the checkout. `poetry install` includes the `dev` group, which is a PEP 735 `[dependency-groups]` table and not an extra, so `pip install -e ".[dev]"` does not install it. Leave out `--all-extras` to work against the light core that `unit-tests.yml` tests.

Install the Git hooks:

```bash
poetry run pre-commit install
```

Check the setup with the default test run:

```bash
poetry run pytest
```

### Install with uv, as CI does

The composite action `.github/actions/setup-python-env` has Poetry export the locked versions and uv install them, which is faster than `poetry install`. To do the same in a fresh clone, export the `dev` group and all extras with the pinned Poetry and export plugin:

```bash
uvx --from poetry==2.3.2 --with poetry-plugin-export==1.10.0 poetry export --without-hashes --format requirements.txt --with dev --all-extras --output /tmp/requirements-dev.txt
```

Create the environment and install into it:

```bash
uv venv .venv --python 3.10
```

```bash
uv pip install -r /tmp/requirements-dev.txt
```

```bash
uv pip install -e . --no-deps
```

`uv pip` installs into the `.venv` directory it finds in the current directory, and Poetry uses the same environment, so `poetry run` works afterwards.

### Dependencies and extras

- **Core dependencies** are listed in `[tool.poetry.dependencies]` and installed by `pip install pyeuropepmc`.
- **Optional dependencies** are each declared once in the same table and combined into extras in `[tool.poetry.extras]`: `analytics`, `visualization`, `export`, `rdf`, `ui`, `signing`, `bibliography`, `zotero`, `agentic`, `semanticscholar`, `enrichment`, `standard` and `all`.
- **The `dev` group** in `[dependency-groups]` contains pytest with pytest-cov, pytest-xdist, pytest-socket, pytest-timeout, pytest-asyncio and pytest-benchmark, plus coverage, ruff, mypy, bandit, pre-commit, memory-profiler, typing-extensions and type stubs.

`poetry.lock` pins every version, and CI never runs `poetry lock`: it validates the lock with `poetry check --lock` and installs from an export of it. `requirements.txt` holds the core dependencies exported from the lock and must match it; see [Updating a dependency](ci-and-release-workflow.md#updating-a-dependency).

## Code quality tools

All tool configuration is in `pyproject.toml`; there is no `mypy.ini`, `pytest.ini` or separate ruff configuration. The commands below are the ones the `Lint, types & security` job in `cdci.yml` runs.

### Ruff

```bash
poetry run ruff check src/ tests/
```

```bash
poetry run ruff format --check src/ tests/
```

The configuration in `[tool.ruff]`:

- line length 99 and target version Python 3.10;
- the rule sets E, F, W, C90 (maximum complexity 15), I (with `pyeuropepmc` as first-party), UP, B and SIM, with E203, E266 and E731 ignored;
- the XML rules described in the next section;
- per-file ignores for tests, `__init__.py` files, the CLI and a few modules with long prompts or complex parsing;
- `docs/` and `examples/` excluded.

### XML parsing with defusedxml

pyEuropePMC parses every XML document with [defusedxml](https://github.com/tiran/defusedxml), which refuses documents that declare entities instead of expanding them. Ruff enforces this with two rules:

- **S313-S319** report calls that parse with the standard library: `xml.etree.cElementTree`, `xml.etree.ElementTree`, `xml.sax.expatreader`, `xml.dom.expatbuilder`, `xml.sax`, `xml.dom.minidom` and `xml.dom.pulldom`.
- **TID251** bans importing `lxml`, with the message "Parse XML with defusedxml, the only XML parser pyeuropepmc uses."

Parse with `defusedxml.ElementTree`:

```python
import defusedxml.ElementTree as DefusedET

root = DefusedET.fromstring("<article><title>Example</title></article>")
print(root.find("title").text)
```

Importing `xml.etree.ElementTree` to build elements or for type annotations does not trigger the ruff rules, but bandit reports the import as B405. Modules that need it import it as `from xml.etree import ElementTree as ET  # nosec B405`.

### mypy

```bash
poetry run mypy src/
```

`[tool.mypy]` checks `src/` only, with `strict = true`, the pydantic plugin and `ignore_missing_imports = true`, and disables the `misc` and `import-untyped` error codes. `python_version = "3.12"` sets the syntax mypy parses, including in third-party stubs; it is not the minimum supported version, which `python-compatibility.yml` checks by compiling the package on each interpreter. Errors are ignored in `pyeuropepmc.agentic.*`, `pyeuropepmc.claims.*`, `pyeuropepmc.ui.*`, `pyeuropepmc.prompts.*`, `pyeuropepmc.cli.claim` and `pyeuropepmc.cli.agentic`, which build on the loosely typed agentic and UI extras.

### Bandit

```bash
poetry run bandit -r ./src --exclude "tests,.venv,.git,.mypy_cache,.pytest_cache" --skip "B101,B303"
```

CI passes the skip list on the command line. The pre-commit hook reads `[tool.bandit]` instead, which also skips B110 and B112, so findings of those two types pass locally and fail in CI.

### Pre-commit hooks

`poetry run pre-commit install` enables these hooks from `.pre-commit-config.yaml`:

| Hook | What it does |
|---|---|
| `ruff` and `ruff-format` (ruff 0.14.14) | lint with `--fix`, and format, `src/` and `tests/` |
| `bandit` (1.8.3) | scan `src/` with the `[tool.bandit]` settings |
| pre-commit-hooks (v5.0.0) | fix trailing whitespace and missing final newlines; check for files over 2,000 KB, merge conflict markers, invalid YAML, JSON and TOML, case conflicts and private keys |
| pygrep-hooks (v1.10.0) | reject blanket `# noqa` comments, `eval()` and `.warn()` logging calls |
| `zizmor` (1.30.1) | audit GitHub Actions files for findings of medium severity or higher, when `.github/workflows/`, `.github/actions/` or `.github/zizmor.yml` changes |
| `mypy` | run `poetry run mypy src/` in the project environment when files in `src/` change |
| `poetry-lock-check` | run `poetry check --lock` when `pyproject.toml` or `poetry.lock` changes |
| `poetry-export-requirements` | regenerate `requirements.txt` from `poetry.lock` when `pyproject.toml`, `poetry.lock` or `requirements.txt` changes |

The `mypy` hook runs the `poetry` found on your `PATH`. The two Poetry hooks install their own Poetry 2.3.2 and poetry-plugin-export 1.10.0.

Run every hook against the whole repository before opening a pull request:

```bash
poetry run pre-commit run --all-files
```

### Make

`make quality` runs ruff, the format check, mypy and bandit over the repository. It calls the tools by name, so run it through Poetry:

```bash
poetry run make quality
```

### CodeScene (optional)

CodeScene code-health analysis needs the `cs` command-line tool and a `CS_ACCESS_TOKEN`. In CI, the `CodeScene delta (advisory)` job in `cdci.yml` runs `cs delta`; it is skipped when the token is not available, as on pull requests from forks, and never fails the workflow. To run it locally, copy `.env.example` to `.env`, set the token, and run the script with `check`, `review`, `delta` or `all`:

```bash
examples/scripts/codescene_analysis.sh delta
```

### Documentation

Pages live under `docs/`. [Documentation](documentation.md) explains how the site is built and published and how to add a page. The site is built with Jekyll, which runs Liquid over every page, so a GitHub Actions expression (a dollar sign followed by double curly braces) in a code sample disappears from the published site. Describe such expressions in words instead.

## Running tests

A plain `pytest` run is offline and fast. The `addopts` in `pyproject.toml` leave out tests marked `slow`, `functional`, `network`, `benchmark` or `e2e`, block network sockets and stop any test after 120 seconds. `tests/conftest.py` marks tests by location, so a test under a `functional/` directory is left out without an explicit marker, and every test in no other category is marked `unit`. [Testing](testing-improvements.md) describes the categories and the CI test jobs in full.

Run the default suite:

```bash
poetry run pytest
```

Run it in parallel with pytest-xdist:

```bash
poetry run pytest -n auto
```

Run only the unit tests:

```bash
poetry run pytest -m unit
```

Run the tests whose names match an expression:

```bash
poetry run pytest -k query_builder
```

Measure coverage as `cdci.yml` does; `coverage report` fails below the `fail_under = 75` threshold, which assumes all extras are installed:

```bash
poetry run pytest --cov
```

```bash
poetry run coverage report
```

Run the tests that call real services, with network access allowed:

```bash
poetry run pytest --run-real
```

Run what the nightly functional job runs:

```bash
poetry run pytest -m functional --run-integration
```

## Contributing guidelines

### Workflow

1. Create a branch from `main`. Direct pushes to `main` are rejected.
2. Make the change, with tests; see [Writing tests](testing-improvements.md#writing-tests).
3. Run the pre-commit hooks and the default test suite.
4. Open a pull request. It can merge once the required checks pass and the branch is up to date with `main`. `gh pr merge --auto --squash` merges it as soon as both are true.

### Commit messages

Commit messages and pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): description`, or `type: description`. When `changelog.yml` generates a changelog entry, it sorts commits by type:

| Type | Changelog section |
|---|---|
| `feat` | Features |
| `fix` | Bug fixes |
| `docs` | Documentation |
| `chore`, `ci`, `build`, `refactor`, `test`, `perf`, `style`, `deps` | Maintenance |
| any type followed by `!`, or a message containing `BREAKING CHANGE` | Breaking changes |

Examples from the history:

```text
refactor!: parse all XML with defusedxml, remove the lxml backend (#246)
fix: add the mcp-name marker the MCP Registry checks, bump to 2.2.1 (#244)
chore(release): bump to 2.2.0 (#243)
```

### Code conventions

- Type-annotate all code; mypy runs in strict mode on `src/`.
- Write NumPy-style docstrings, with `Parameters`, `Returns` and `Raises` sections underlined with dashes, as the existing modules do.
- Parse XML with defusedxml only; see [XML parsing with defusedxml](#xml-parsing-with-defusedxml).
- Keep `import pyeuropepmc` light by importing optional dependencies lazily. `tests/test_lightweight_import.py` and `unit-tests.yml` fail when an optional dependency is imported eagerly.
- Derive new exceptions from `PyEuropePMCError` in `pyeuropepmc.core.exceptions`.
- Record user-visible changes under `## [Unreleased]` in `CHANGELOG.md`.

## CI workflows

A pull request can merge only when these five required checks pass on a branch that is up to date with `main`:

| Check | Workflow | What it runs |
|---|---|---|
| `Lint, types & security` | `cdci.yml` | ruff, mypy, bandit, `poetry check --lock` and the `requirements.txt` sync check |
| `Tests & coverage` | `cdci.yml` | the default suite with all extras on Python 3.10, and the 75% coverage threshold |
| `Unit tests (core deps only)` | `unit-tests.yml` | the default suite with no extras installed |
| `Compatibility Summary` | `python-compatibility.yml` | compilation and imports on Python 3.10 to 3.13, and the suite on Python 3.10 and 3.12 |
| `zizmor` | `zizmor.yml` | a security audit of the workflow files |

Jobs that need the project install it through `.github/actions/setup-python-env`, where Poetry 2.3.2 exports the locked versions and uv installs them. [CI, branch protection and releases](ci-and-release-workflow.md) lists every workflow and explains the branch protection rules.

## Release process

Pushing a tag such as `v2.3.0` starts `release.yml`. It verifies the tagged commit, builds and attests the distributions, publishes them to PyPI with trusted publishing, creates the GitHub Release from the changelog and publishes `server.json` to the MCP Registry. Do not upload with twine: a manual upload has no provenance attestation.

A maintainer makes a release in four steps:

1. On a branch, set the new version in `pyproject.toml`, `src/pyeuropepmc/__init__.py` and `server.json`, and turn `## [Unreleased]` in `CHANGELOG.md` into a section for the version.
2. If the release changes `release.yml`, `server.json` or packaging metadata, dispatch the [dry run on TestPyPI](ci-and-release-workflow.md#dry-run-on-testpypi) from that branch.
3. Open a pull request, for example `chore(release): bump to X.Y.Z`, and merge it.
4. Tag the merge commit on `main` and push the tag.

[Release process](ci-and-release-workflow.md#release-process) lists every prerequisite, the commands and what each job checks.

## Repository layout

| Path | Contents |
|---|---|
| `src/pyeuropepmc/` | the package |
| `tests/` | the test suite; see [Testing](testing-improvements.md#layout) |
| `docs/` | this documentation |
| `examples/` | example notebooks and scripts; `examples/scripts/` holds maintenance scripts such as `check_fields.py` and `codescene_analysis.sh` |
| `benchmark_xmls/xml/` | the JATS XML files the parser benchmark reads |
| `benchmarks/` | pipeline benchmark scripts and sample output |
| `schemas/linkml/` | the LinkML schema for article content |
| `shacl/` | SHACL shapes for the RDF output |
| `server.json` | the MCP Registry entry for `pyeuropepmc-mcp` |
| `.github/` | workflows, the `setup-python-env` composite action, and Dependabot, labeler and zizmor configuration |
| `pyproject.toml` | package metadata, dependencies and tool configuration |
| `poetry.lock`, `requirements.txt` | the locked dependency versions, and the core dependencies exported from them |

## Package architecture

`pyeuropepmc/__init__.py` exports the public API lazily through `_lazy.py` (PEP 562), so `import pyeuropepmc` loads only the light core, and each feature is imported on first use. When an optional dependency is missing, `_optional_imports.py` raises an error that names the command to install it.

| Package | Contents |
|---|---|
| `core/` | `BaseAPIClient` (a requests session with retries through backoff), `ErrorCodes`, and the exceptions derived from `PyEuropePMCError` |
| `features/literature/` | the Europe PMC clients `SearchClient`, `ArticleClient`, `AnnotationsClient` and `FTPDownloader`, plus `QueryBuilder`, `EuropePMCParser`, pagination and result filters |
| `features/fulltext/` | `FullTextClient`; `FullTextXMLParser` with its `parsers/`, `converters/` and `extensions/`; the JATS normalizer, the SQLite FTS5 index, figure extraction and rhetorical-role tagging |
| `features/search/` | `UnifiedSearch`, query translation and the source registry, with sources for arXiv, ClinicalTrials.gov, CORE, DBLP, DOAJ, HAL, PubMed and Zenodo; more sources can register through the `pyeuropepmc.sources` entry-point group |
| `features/enrich/` | `PaperEnricher` and record merging (`LiteratureMerger`), with sources for Crossref, DataCite, Europe PMC, iCite, OpenAlex, ORCID, ROR, Semantic Scholar and Unpaywall |
| `features/citations/`, `features/review/`, `features/bibliography/`, `features/analytics/` | `CitationWalker`; MeSH and PICO tools; BibTeX and Zotero support; analytics and plots |
| `features/common/` | `BaseHTTPClient`, a common base class for API clients |
| `cache/` | `CacheConfig` and `CacheBackend`; the directory has no `__init__.py`, so import them from `pyeuropepmc` |
| `storage/` | `ArtifactStore` |
| `models/`, `builders/`, `mappers/`, `pipeline.py` | entity models, conversion of parser output into models, RDF mapping (`RDFMapper` and RML) and `PaperProcessingPipeline` |
| `conf/` | the mapping files `rdf_map.yml`, `rml_mappings.ttl` and `rdfizer_config.ini` and the vocabulary `pyeuropepmc-vocab.ttl`; they ship in the wheel, and `pyeuropepmc.conf.config_file(name)` returns their path |
| `cli/`, `mcp/` | the `pyeuropepmc` command (`benchmark`, `claim`, `normalize`, `unified_search`) and the `pyeuropepmc-mcp` server |
| `benchmark/` | the parser benchmark suite behind `pyeuropepmc benchmark` |
| `agentic/`, `claims/`, `prompts/`, `ui/` | LLM workflows, claim verification, prompt templates and the Flask web UI, which need the `agentic` and `ui` extras |
| `utils/` | helpers, search logging (`SearchLog`), dependency checks and text matching |

## Getting help

Report bugs and ask questions in [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues).
