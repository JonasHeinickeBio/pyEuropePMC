# v2.0.0 release readiness

Status of `feature/modular-literature-tools` (HEAD `236be24`) against a clean
2.0.0 release. Checked 2026-09-10.

---

## 🔴 Blockers — `release.yml` `verify` job fails on all of these

The publish workflow runs `poetry check` + `ruff check src/` +
`ruff format --check src/` + `mypy src/` + `pytest tests/ -v` and refuses to
build/publish if any fail. Today:

| Gate | Result | Notes |
|------|--------|-------|
| `poetry check` | ❌ | `poetry.lock` out of sync — `pytest-socket` / `pytest-timeout` are in `pyproject.toml` but not the lock. **Fix: `poetry lock`** (couldn't run in the authoring sandbox; ~2 min on a normal network). |
| `ruff check src/` | ❌ 308 errors | Pre-existing debt (the 2.0 branch's *new* modules are clean). Options: (a) fix, (b) add the offending rules to `[tool.ruff.lint.ignore]` / per-file-ignores, (c) loosen the release gate to `ruff check --select E9,F63,F7,F82`. |
| `ruff format --check src/` | ✅ | clean |
| `mypy src/` | ❌ 539 errors / 57 files | `strict = true`. Pre-existing. Same options as ruff, or set `strict = false` + a smaller error-code allowlist for the release gate. |
| `pytest tests/ -v` | ❌ 2 failures | Both environmental, not real regressions: `test_cli_app::test_app_no_args_shows_help` (Typer ≥0.12 returns exit 2 for no-args help) and `test_enricher::test_unpaywall_requires_email` (a local `.env` leaks `UNPAYWALL_EMAIL` into an unrelated test — passes in CI where no `.env` exists, and passes in isolation). Fix the CLI test's assertion; make the enricher test `monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)`. |

These gates also fail on `main` today, so step 0 is a decision: **fix the debt, or
relax `release.yml` `verify`** to match what CI actually enforces
(`cdci.yml` = bandit + 75 % coverage, `unit-tests.yml` = `pytest -q`).

## 🟠 Should fix before tagging

- **Stale optional-dependency maps.** `DEPENDENCY_GROUPS` /
  `FEATURE_TO_GROUP` are duplicated in `src/pyeuropepmc/_optional_imports.py`
  **and** `src/pyeuropepmc/utils/dependencies.py`, and both are out of date vs
  the real extras: missing `semanticscholar`, `signing`, `ui`; the
  `enrichment` group still lists `tornado` + `flask` (moved to `ui`). Result:
  `OptionalDependencyError` tells users the wrong `pip install` command.
  → collapse to one map, generate/verify it against `[project.optional-dependencies]`.
- **Hard-coded version in the User-Agent.** `pyeuropepmc/1.12.0` is baked into
  `features/common/base.py`, `features/enrich/sources/{openalex,datacite,ror}.py`.
  → read `pyeuropepmc.__version__`.
- **`requirements.txt` is a stale full `poetry export`** (215 lines, still
  lists matplotlib/pandas/flask/langchain/jupyterlab). It contradicts the
  "light core" story and has no lock parity. → regenerate after `poetry lock`,
  or delete it (Poetry + PEP 621 is the documented workflow).
- **No `py.typed` marker.** The package ships type hints but downstream `mypy`
  ignores them. → add `src/pyeuropepmc/py.typed` and ensure it's packaged.
- **`sentence-transformers` has no extra.** `utils/text_match.py` semantic
  matching `ImportError`s at call time with no group to point at. → add
  `ml = ["sentence-transformers>=2.2,<4"]` (kept out of `all` because of torch)
  or document it as bring-your-own.
- **No PR / CI has never run against this branch.** `unit-tests.yml` and
  `cdci.yml` only trigger on PRs / `main`. → open the PR to `main` so coverage
  (≥75 %), bandit, and the unit lane actually get checked.
- **Resolve the CHANGELOG "Known issues" note** (it *is* blocker #1).

## 🟡 Nice to have

- `rdflib` is still a *core* dependency though only `mappers/` uses it — moving
  it to the `rdf` extra would make the core install genuinely minimal.
- No compatibility shims for the old import paths — `import
  pyeuropepmc.clients.search` raises a bare `ModuleNotFoundError`. A thin
  shim package emitting `DeprecationWarning` would be friendlier for a major
  bump (the migration guide covers the mapping either way).
- Broken links: `README.md` line ~586 `from pyeuropepmc.mcp.server import
  EuropePMCClient` (name doesn't exist) + ~6 pre-existing broken relative doc
  links (`examples/09-enrichment/...`, `docs/development/contributing.md`, …).
- Classifiers: add `Programming Language :: Python :: 3.13` (tox tests it);
  reconsider `Development Status :: 5 - Production/Stable` vs a short `2.0.0rc1`.
- Align `[tool.coverage.report] fail_under = 50` with CI's `--fail-under=75`.
- `[[tool.poetry.packages]]` uses the legacy array-of-tables form; the PEP 621
  era prefers `[tool.poetry] packages = [{ include = "pyeuropepmc", from = "src" }]`.

## Release steps once the above is green

1. `poetry lock` → commit lock + regenerated `requirements.txt`.
2. Open PR `feature/modular-literature-tools` → `main`; get `unit-tests` +
   `cdci` green.
3. Squash/merge to `main`.
4. `git tag v2.0.0 && git push origin v2.0.0` → `release.yml` publishes to PyPI,
   `changelog.yml` runs, `deploy-docs.yml` publishes the updated docs
   (including `docs/migration/v1-to-v2.md`).
5. Create the GitHub Release from the `## [2.0.0]` CHANGELOG section.
