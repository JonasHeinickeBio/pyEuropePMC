# Testing

This page describes how the test suite is organised, what a plain `pytest` run includes, how tests are sorted into categories, how to run the categories the default run leaves out, and which CI jobs run which tests.

## Layout

Tests live under `tests/` and mostly follow the package structure:

- `tests/features/<area>/` holds the tests for each feature package, usually split into `unit/`, `functional/` (live services) and, where real Europe PMC documents are used offline, `real_data/`.
- `tests/integration/` holds showcase tests against live APIs.
- `tests/mcp/unit/` and `tests/mcp/e2e/` test the MCP server.
- `tests/unit/` holds further tests, among them agentic, claims, bibliography and GUI tests.
- Directories such as `tests/core/`, `tests/cache/`, `tests/models/`, `tests/mappers/` and `tests/cli/` cover the other packages.
- `tests/fixtures/` holds recorded API responses and, in `fulltext_downloads/`, full-text XML and PDF files stored with Git LFS.

pytest collects files named `test_*.py` or `*_test.py`.

## The default run

`pytest` with no arguments applies `addopts` from `[tool.pytest.ini_options]` in `pyproject.toml`:

```text
-ra -q --strict-markers --disable-socket --allow-unix-socket --timeout=120 -m 'not slow and not functional and not network and not benchmark and not e2e'
```

- The `-m` expression leaves out every test marked `slow`, `functional`, `network`, `benchmark` or `e2e`.
- `--disable-socket` (pytest-socket) makes any network connection fail at once with `SocketBlockedError`. `--allow-unix-socket` keeps Unix sockets available.
- `--timeout=120` (pytest-timeout) stops any test that runs for more than two minutes.
- `--strict-markers` turns an unregistered marker into an error.

Three more rules apply to every run:

- Tests marked `integration` are not deselected, but `tests/integration/conftest.py` skips them unless `--run-integration` is given.
- At the start of a session, `tests/conftest.py` looks for Git LFS pointer files in `tests/fixtures/fulltext_downloads/`. If it finds any, it runs `git lfs pull`, and it stops the session if pointers remain.
- If pytest-socket or pytest-timeout is not installed, `tests/conftest.py` registers placeholder options so that the flags still parse. The run then has no network guard or timeout.

## Test categories

`tests/conftest.py` adds markers from each test's location, so most tests need none:

| Marker | Added when |
|---|---|
| `functional` | the path contains `/functional/`, or the file name starts with `interactive_` or ends with `_interactive_test.py` |
| `integration` | the path contains `/integration/` |
| `gui` | the path contains `/gui/` |
| `benchmark` and `slow` | the test requests the pytest-benchmark `benchmark` fixture, or its file name starts with `benchmark_` |
| `unit` | the test has none of `functional`, `integration`, `network`, `slow`, `benchmark`, `e2e` and `gui` |

Mark explicitly what the location cannot express, such as `slow`, `network` or `e2e`. Explicit markers count when `unit` is inferred, so a `network` test in a unit-test module is not marked `unit`.

Tests marked `functional`, `integration`, `network` or `e2e` also get `enable_socket`, so they can reach the network when you select them. Tests under `tests/mcp/` are allowed loopback connections (`127.0.0.1` and `::1`), which asyncio needs to create an event loop on Windows.

When a `functional` test fails with a network error, the failure is reported as a skip, so an outage of a third-party service does not fail the run. Network errors here are the client error codes `NET001` and `NET002`, read timeouts, exhausted retries, refused connections and failed name resolution. Assertion failures and other exceptions still fail.

## Running the excluded tests

A `-m` option on the command line replaces the default marker expression instead of adding to it.

`--run-real` runs the tests that call real services. It replaces the marker expression with `functional or network or e2e` and turns the socket guard off. Tests that are also marked `integration` still need `--run-integration`:

```bash
poetry run pytest --run-real
```

The nightly CI job runs every `functional` test, including those also marked `integration`:

```bash
poetry run pytest -m functional --run-integration
```

The live-API tests in `tests/integration/`:

```bash
poetry run pytest tests/integration --run-integration
```

Long-running tests. Slow tests that are also `functional`, `network` or `e2e` call live services:

```bash
poetry run pytest -m slow
```

The modular benchmark, which `benchmark.yml` runs every week, measures live API calls. Its file name does not match the test-file pattern, so name the test explicitly; `-m benchmark` on its own selects nothing. `--force-enable-socket` lifts the socket guard and `--timeout=3600` replaces the two-minute limit:

```bash
poetry run pytest tests/benchmark_article_client.py::test_modular_benchmark_system -m benchmark --force-enable-socket --timeout=3600
```

## Writing tests

- Keep new tests offline. Mock the HTTP layer instead of calling the service; `tests/features/search/unit/test_search_caching.py`, for example, patches the client's `_make_request`.
- Put a test that needs the network under a `functional/` directory, or mark it `@pytest.mark.network`. Either keeps it out of the default run and lets it through the socket guard when it is selected.
- Register a new marker under `markers` in `[tool.pytest.ini_options]`; otherwise `--strict-markers` fails the run.
- Make tests that need an optional dependency skip when it is missing, for example with `pytest.importorskip`. `unit-tests.yml` and `python-compatibility.yml` run the suite without any extras.

## Tests in CI

| Job | Workflow | Python | Dependencies | Command |
|---|---|---|---|---|
| `Tests & coverage` | `cdci.yml` | 3.10 | all extras | `pytest --cov`, then `coverage report` with `fail_under = 75` |
| `Unit tests (core deps only)` | `unit-tests.yml` | 3.10 | core only | `pytest -q` |
| `Tests (Python 3.12 on windows-latest)` and the other matrix legs | `python-compatibility.yml` | 3.10 and 3.12 | core only | `pytest -q --tb=short` |
| `Functional Tests` | `integration-tests.yml` | 3.10 | all extras | `pytest -v -m functional --run-integration` |
| `Run modular benchmarks (weekly)` | `benchmark.yml` | 3.10 | core only | the benchmark command above |
| `Verify` | `release.yml` | 3.12 | all extras | `pytest -q` |

Every job also installs the `dev` group. The functional tests run nightly and on pushes to `main`; when they fail, the workflow opens or updates a single issue labelled `functional-test-failure`.

In `python-compatibility.yml`, pull requests run the tests on Ubuntu only. Pushes to `main`, the weekly run and manual runs add Windows and macOS; macOS runs Python 3.12 only. On Windows, two tests that depend on file-locking behaviour, `test_download_pdf_by_pmcid_all_fail` and `test_try_bulk_xml_download_success`, are deselected with `-k`. A manual run accepts `test_level` (`all`, or `syntax-only` to skip the test jobs) and `skip_platforms` (a comma-separated list such as `windows,macos`).
