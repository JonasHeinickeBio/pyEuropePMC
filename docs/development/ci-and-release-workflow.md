# CI, branch protection, and the release pipeline

How `main` is protected, how the CI workflows are structured (and why the OS
matrix behaves differently on a PR vs. a push), and how a release actually
goes out. Written after a review of the actual `.github/workflows/*.yml`
files and the repository's branch-protection ruleset — everything below
reflects what is actually configured, not an aspirational description.

## Branch protection on `main`

`main` is protected by a repository ruleset named **"Protect Main"**
(`Settings → Rules → Rulesets`, or `GET /repos/{owner}/{repo}/rulesets`).
It currently enforces:

| Rule | What it does |
|---|---|
| `deletion` | `main` cannot be deleted. |
| `non_fast_forward` | History on `main` cannot be rewritten (no force-push). |
| `pull_request` | **All changes must go through a PR** — direct pushes to `main` are rejected outright, not just non-fast-forward ones. 0 required approvals (see below for why), all three merge methods allowed. |
| `required_status_checks` | A PR cannot merge until these all pass, **and** the branch must be up to date with `main` (`strict_required_status_checks_policy: true`): `Lint, types & security`, `Tests & coverage`, `Unit tests (core deps only)`, `Compatibility Summary`. |

**No bypass, for anyone, ever**: `bypass_actors` is empty and
`current_user_can_bypass` is `"never"` — this predates the checks/PR rules
added here (the `deletion`/`non_fast_forward` rules already had no bypass)
and was kept consistent. Two direct consequences:

- **0 required approvals is deliberate, not an oversight.** With zero
  bypass actors, requiring even 1 approval would lock a solo maintainer out
  of merging their own PRs — GitHub doesn't let you approve your own PR by
  default, and there'd be no escape hatch.
- There is no "just this once" override for an emergency hotfix. A fix to
  `main` always means: branch, PR, wait for the four checks, merge.

## Why there's no merge queue

GitHub's native **Merge Queue is only available on organization-owned
repositories.** `pyEuropePMC` is owned by a personal account
(`JonasHeinickeBio`), and the ruleset API rejects the `merge_queue` rule
outright for that reason — confirmed by testing it in complete isolation
(no other rules), which still failed with the same opaque
`Invalid rule 'merge_queue'` 422. This is a hard platform restriction, not
a configuration problem to work around.

**Substitute in place instead:** `pull_request` (no direct pushes) +
`required_status_checks` with `strict_required_status_checks_policy: true`
(branch must be up to date) + repository-level auto-merge (see below). This
gets most of the same safety property — nothing merges without the checks
passing against a current base — for a repo with low enough PR volume that
the one thing a real queue adds (re-validating against a base that changed
*after* your last "up to date" check, when two PRs land back-to-back) is a
negligible risk.

If this repository is ever transferred to a GitHub organization, enabling
the queue is just adding a `merge_queue` rule to this same ruleset — the
workflows are already wired for it (next section).

## CI workflow structure

| Workflow | File | Runs on | What it checks |
|---|---|---|---|
| CI | `cdci.yml` | push to `main`, PR, merge queue, manual | Lint (`ruff`), type-check (`mypy`), bandit, full test suite with `--all-extras`, coverage ≥75% |
| CI — Light core install | `unit-tests.yml` | push to `main`, PR, merge queue, manual | Tests against a bare `pip install pyeuropepmc` (no extras) — proves the optional-dependency split actually works |
| Python Version Compatibility Matrix | `python-compatibility.yml` | push to `main`, PR (paths-filtered), merge queue, weekly, manual | Syntax/import checks on 3.10–3.13; full test suite on a matrix of Python version × OS |

### The OS matrix is intentionally reduced on a PR, full everywhere else

`python-compatibility.yml`'s `config` job computes the OS matrix once, up
front:

- **`pull_request`**: Ubuntu only. Windows and (especially) macOS runners
  are the expensive legs; a PR-time Linux signal catches most cross-platform
  breakage at a fraction of the cost.
- **Everything else** (`push` to `main`, `schedule`, `workflow_dispatch`,
  and `merge_group`): the full `ubuntu-latest` / `windows-latest` /
  `macos-latest` matrix.

This is a real, previously-demonstrated gap: the Windows-only
`asyncio`/`pytest-socket` regression from the MCP server rewrite (#190)
passed PR CI clean and only broke on the post-merge push-to-`main` run,
requiring a follow-up fix (#202). `merge_group` was added specifically to
close this — see next section — but until/unless this repo can actually use
a merge queue, that trigger is currently **dead code**: it's wired up and
will work the moment a queue exists, but nothing fires it today.

### `merge_group` triggers

`cdci.yml`, `unit-tests.yml`, and `python-compatibility.yml` all listen for
the `merge_group` event. This exists so that **if** this repo moves to an
org and gets a merge queue, the required checks are already capable of
firing against a queued PR — a merge queue's required checks must run on
`merge_group`, or a queued entry just waits forever for a check that never
executes. Until then, these triggers never activate (no merge queue → no
`merge_group` events).

## Release process

`release.yml` triggers on pushing a `v*` tag (or manual `workflow_dispatch`
for a dry run — see below) and runs, in order:

1. **`verify`** — re-runs lint/type-check/tests against the *tagged commit*
   specifically (not just whatever last passed on `main`), and checks the
   tag version matches `pyproject.toml`'s version.
2. **`build`** — builds the wheel/sdist, smoke-tests both install cleanly
   into a fresh venv and report the right `__version__`.
3. **`attest`** — Sigstore build-provenance attestation.
4. **`publish`** — uploads to PyPI via trusted publishing (OIDC, no token).
5. **`github-release`** — creates the GitHub Release from the CHANGELOG
   section for that version. Gated on `github.ref_type == 'tag'`.
6. **`publish-mcp-registry`** — publishes `server.json` to the
   [official MCP Registry](https://registry.modelcontextprotocol.io/) via
   GitHub OIDC (no stored secret — the workflow's own repo identity proves
   ownership of the `io.github.JonasHeinickeBio/*` namespace). Also gated
   on `github.ref_type == 'tag'`, and `continue-on-error: true` since the
   registry is explicitly still in preview — a registry hiccup shouldn't
   fail a release that already shipped to PyPI and GitHub Releases.

### Dry-run before touching the release pipeline itself

If a change touches `release.yml`, `server.json`, or anything else in the
release path, dispatch it manually first rather than finding out only after
a real tag is live:

```bash
gh workflow run release.yml --ref <your-branch> -f environment=testpypi
```

Dispatching against a **branch** (not a tag) means `github.ref_type` is
`"branch"`, so `github-release` and `publish-mcp-registry` — both gated on
`ref_type == 'tag'` — don't fire. Only `verify → build → attest → publish`
(to TestPyPI) run. Two real bugs this session — the MCP Registry namespace
casing mismatch (`io.github.jonasheinickebio` vs. the actual, case-sensitive
`io.github.JonasHeinickeBio`) and the mypy `python_version` regression the
`verify` job would have caught — are exactly the kind of thing this dry run
surfaces for free, before a tag (and its version bump, CHANGELOG entry, and
PyPI upload) is a committed, hard-to-fully-undo fact.

### Auto-merge

Repository-level "Allow auto-merge" is enabled
(`allow_auto_merge: true`). On any PR, `gh pr merge --auto --squash` (or the
"Enable auto-merge" button in the GitHub UI) queues it to merge itself the
moment the four required checks above go green — no need to babysit a PR
waiting on a slow matrix run.
