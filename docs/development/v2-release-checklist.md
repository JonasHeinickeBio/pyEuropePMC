# v2.0.0 release readiness

Status of `feature/modular-literature-tools` against a clean 2.0.0 release.
Originally checked 2026-09-10; **blockers + should-fix cleared same day**
(HEAD `0274525`).

---

## 🟢 Blockers — all clear

The publish workflow (`release.yml` `verify`) runs `poetry check` +
`ruff check src/` + `ruff format --check src/` + `mypy src/` +
`pytest tests/ -v`. Local status now:

| Gate | Result | Notes |
|------|--------|-------|
| `poetry check` | ✅ | `poetry lock` regenerated (`780246c`). Resolution was hanging for *hours* on `sentence-transformers → torch → nvidia-cuda-*`; the `ml` extra was dropped (`95417e0`) and `pandas/numpy/openai` capped, bringing it to ~7 min. |
| `ruff check src/` | ✅ | 308 → 0 (`4bc23a0`) — per-file-ignores for the CLI/UI/claims/agentic slices, TYPE_CHECKING re-export cleanups. |
| `ruff format --check src/` | ✅ | clean |
| `mypy src/` | ✅ | 539 → 0 (`4bc23a0`) under `strict = true`; targeted `ignore_errors` overrides for `agentic.*` / `claims.*` / `ui.*` / `prompts.*`. |
| `pytest tests/ -v` | ✅ | 3602 passed / 42 skipped. Fixed the 2 environmental failures + one pinned-User-Agent assertion. |

## 🟢 Should fix before tagging — done

- ✅ **Optional-dependency maps consolidated** (`e0a047f`). `DEPENDENCY_GROUPS` /
  `FEATURE_TO_GROUP` now live only in `_optional_imports.py`, re-exported from
  `utils/dependencies.py`, refreshed to the real extras.
- ✅ **Dynamic User-Agent** (`e0a047f`). New `pyeuropepmc._useragent.get_user_agent()`
  reads `__version__`; used by `core/base.py`, `features/common/base.py`, the
  openalex/datacite/ror enrichment clients and the fulltext session.
- ✅ **`requirements.txt`** regenerated as the light core (`780246c`).
- ✅ **`py.typed`** added + packaged via `[tool.poetry] include` (`e0a047f`).
- ✅ **`sentence-transformers`** documented as bring-your-own — deliberately *not*
  an extra (`95417e0`); it was what made `poetry lock` non-terminating.
- ✅ **CHANGELOG "Known issues"** poetry.lock note resolved.
- ⬜ **Open the PR to `main`** so `cdci.yml` (bandit + ≥75 % coverage) and
  `unit-tests.yml` run against the branch for the first time.

## 🟢 Nice to have — done

- ✅ Python 3.13 classifier (`e0a047f`).
- ✅ `[tool.coverage.report] fail_under` 50 → 75 (`e0a047f`).
- ✅ `[[tool.poetry.packages]]` → modern `[tool.poetry] packages` table (`e0a047f`).
- ✅ README `EuropePMCClient` / broken example + `contributing.md` link fixed
  (`e0a047f`).

## 🟡 Nice to have — deferred (post-2.0)

- `rdflib` is still a *core* dependency though only `models/base.py` +
  `mappers/` use it. Moving it to `[rdf]` risks breaking `BaseEntity` for every
  user; do it deliberately with a lazy guard.
- No compatibility shims for the old import paths (`import
  pyeuropepmc.clients.search` → bare `ModuleNotFoundError`). The migration guide
  covers the mapping.
- Multi-source improvements — see `docs/development/multisource-review.md`.

## Release steps once the above is green

1. `poetry lock` → commit lock + regenerated `requirements.txt`.
2. Open PR `feature/modular-literature-tools` → `main`; get `unit-tests` +
   `cdci` green.
3. Squash/merge to `main`.
4. `git tag v2.0.0 && git push origin v2.0.0` → `release.yml` publishes to PyPI,
   `changelog.yml` runs, `deploy-docs.yml` publishes the updated docs
   (including `docs/migration/v1-to-v2.md`).
5. Create the GitHub Release from the `## [2.0.0]` CHANGELOG section.
