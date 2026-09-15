# Python version support

This page records which Python versions pyEuropePMC supports and how CI tests each of them. It also sets out the plan for Python 3.10 reaching end of life in October 2026 and for adding Python 3.14 and 3.15.

## Current support

`pyproject.toml` declares `requires-python = ">=3.10,<4.0"` and classifiers for Python 3.10, 3.11, 3.12 and 3.13.

| Python | Upstream status in September 2026 | End of life | Tested in CI |
|---|---|---|---|
| 3.10 | security fixes only | October 2026 | the full test suite on Linux and Windows, and every other Linux job |
| 3.11 | security fixes only | October 2027 | compilation, imports and the CLI |
| 3.12 | security fixes only | October 2028 | the full test suite on Linux, Windows and macOS, and release verification |
| 3.13 | bug fixes | October 2029 | compilation, imports and the CLI |
| 3.14 | bug fixes; released 7 October 2025 | October 2030 | not tested or declared |
| 3.15 | pre-release; release planned for 1 October 2026 | October 2031 | not tested |

The upstream dates come from the [Python Developer's Guide](https://devguide.python.org/versions/).

### What runs on which version

- `python-compatibility.yml` compiles the package, imports and constructs the public clients, and runs `pyeuropepmc --help` on Python 3.10, 3.11, 3.12 and 3.13, on Ubuntu with core dependencies only.
- The same workflow runs the default test suite on Python 3.10 and 3.12 on Ubuntu and Windows, and on 3.12 on macOS. Pull requests run the Ubuntu legs only.
- `cdci.yml`, `unit-tests.yml`, `integration-tests.yml`, `benchmark.yml` and `analyze_repo.yml` run on Python 3.10, which is also the default of the `setup-python-env` composite action.
- `release.yml` verifies and builds on Python 3.12.
- ruff targets Python 3.10 (`target-version = "py310"`), so its pyupgrade fixes never introduce syntax the minimum version lacks.
- mypy parses code as Python 3.12 (`python_version = "3.12"`) regardless of the minimum version. Compiling on each interpreter is what catches syntax a version does not support.

## Proposed policy

- Support every CPython version that has not reached end of life.
- Drop a version in the first release after its end of life, and announce the drop in the changelog of the release before.
- Run the full test suite on all three operating systems for the oldest supported version and one newer version, and check compilation and imports on every other supported version.
- Declare a new version in the classifiers once the default test suite passes on it.

`requires-python` is part of the package metadata, so pip and uv on a Python version that is no longer supported keep installing the last release that supports it.

## Plan: dropping Python 3.10

Python 3.10 reaches end of life in October 2026.

### Before the end of October 2026

- Add a note under `## [Unreleased]` in `CHANGELOG.md` that the first release after October 2026 requires Python 3.11 or later.
- Keep Python 3.10 in every job until the drop, so the last release that supports it is fully tested.

### The pull request that drops Python 3.10

1. In `pyproject.toml`:
   - set `requires-python = ">=3.11,<4.0"`, and `python = ">=3.11,<4.0"` in `[tool.poetry.dependencies]`;
   - remove the `Programming Language :: Python :: 3.10` classifier;
   - set `target-version = "py311"` in `[tool.ruff]`;
   - update the `[tool.mypy]` comment that refers to Python 3.10.
2. Re-lock. `poetry check --lock` fails as soon as the Python constraint changes:

   ```bash
   poetry lock
   ```

   Then regenerate `requirements.txt` with the pinned exporter:

   ```bash
   uvx --from poetry==2.3.2 --with poetry-plugin-export==1.10.0 poetry export --without-hashes -f requirements.txt -o requirements.txt
   ```

3. Apply the pyupgrade fixes the new target enables. With `py311`, ruff reports eight `UP017` findings, where `datetime.timezone.utc` becomes `datetime.UTC`:

   ```bash
   poetry run ruff check --fix src/ tests/
   ```

4. Move the Python 3.10 jobs to 3.11:
   - `python-version: '3.10'` in `cdci.yml` (both jobs), `unit-tests.yml`, `integration-tests.yml`, `benchmark.yml` and `analyze_repo.yml`;
   - the `python-version` default in `.github/actions/setup-python-env/action.yml`;
   - in `python-compatibility.yml`, the `syntax-check` matrix, the `core-tests` matrix and its macOS exclusion, and the support text in the `compatibility-summary` job.
5. Update `PYTHON_VERSION` in the `Makefile`, and update or delete `tox.ini`, which still lists `py310`.
6. Update the pages that name Python 3.10 as the minimum, including `README.md`, `docs/README.md`, the pages in `docs/getting-started/` and this page.
7. Record the change under breaking changes in `CHANGELOG.md`.

No required status check has a Python version in its name, so the branch ruleset does not change.

## Plan: Python 3.14 and 3.15

Python 3.14 is neither declared nor tested. Two locked dependencies publish no Python 3.14 wheels, so installing on 3.14 builds them from source:

- `rapidfuzz`, a core dependency, is constrained to `>=2.15.0,<3.0`. The locked 2.15.2 has CPython wheels up to 3.12 only, so installs on 3.13 already build it from source. Current rapidfuzz releases have 3.14 wheels and require Python 3.11 or later.
- `numpy`, used by the `analytics`, `visualization`, `export`, `standard` and `all` extras, is locked at 2.2.6, which has wheels up to 3.13. numpy releases from 2.3 on require Python 3.11 or later, and 2.5 requires 3.12.

Both fit naturally after the 3.10 drop:

1. Widen the `rapidfuzz` upper bound. `poetry lock` keeps the versions already locked where they still fit, so move both packages explicitly:

   ```bash
   poetry update rapidfuzz numpy
   ```

2. Add `'3.14'` to the `syntax-check` matrix in `python-compatibility.yml`. The composite action sets `allow-prereleases: true`, so 3.15 release candidates can be added the same way.
3. When the default test suite passes on 3.14, add the classifier and consider moving the second fully tested version from 3.12 to a newer one.
4. Add Python 3.15 to the `syntax-check` matrix once it is released.
