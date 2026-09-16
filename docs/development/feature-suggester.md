# Feature Suggester workflow

The Feature Suggester workflow (`.github/workflows/analyze_repo.yml`) analyses the repository once a week, asks a model for improvement suggestions and files them as GitHub issues. This page describes what the workflow runs, what it needs, the files it produces and how to test changes to it.

## Triggers

| Trigger | Details |
|---|---|
| Schedule | `cron: "0 3 * * 1"`, every Monday at 03:00 UTC |
| Manual | Actions → Feature Suggester → Run workflow. The `dry_run` input (boolean, default `false`) runs the whole workflow but prints the suggestions instead of creating issues. |

Runs share the concurrency group `feature-suggester` and are not cancelled when a new run starts. The job runs on `ubuntu-latest` with a 60-minute timeout.

## Permissions and secrets

The job has `contents: read`, `issues: write` and `copilot-requests: write`.

| Name | Kind | Required | Used for |
|---|---|---|---|
| `GITHUB_TOKEN` | Provided by GitHub Actions | Yes | `gh issue list`, `gh label list`, `gh issue create`, and authenticating the Copilot CLI |
| `CS_ACCESS_TOKEN` | Repository secret | No | CodeScene analysis. Without it the CodeScene output files contain `CodeScene CLI not available or CS_ACCESS_TOKEN not set`. |

## What the workflow does

1. **Checkout** with full git history. Credentials are not persisted in `.git/config`.
2. **Set up Python 3.10 and Poetry** through `.github/actions/setup-python-env`, installing all extras.
3. **Install analysis tools**: `scc` 3.1.0 (a failed download only produces a warning) and the CodeScene CLI.
4. **Run repository analysis**, writing to `analysis_output/`:
   - `ruff check src/ tests/` (JSON and text)
   - `bandit -r ./src` (JSON and text)
   - `mypy src/` (text, plus a JSON report in `mypy_report/`)
   - `pytest --cov=src/pyeuropepmc` (coverage JSON and test output)
   - `scc src/` (JSON and text)
   - a grep for `TODO`, `FIXME`, `XXX` and `HACK` in `src/`
   - the list of test files, and the git log of the last three months
   - CodeScene `delta`, `check` and `review` (the first 20 Python files), when `CS_ACCESS_TOKEN` is set
5. **Consolidate analysis results** into `analysis_summary.json`. Large payloads are condensed: coverage keeps the totals and the 25 least-covered files, Bandit keeps its totals and the first 25 issues, other JSON payloads are cut to 20,000 characters and text files to 5,000 characters.
6. **Fetch README and existing issues**:
   - `readme.txt` (the repository README)
   - `existing_issues.json` (number, title and labels of up to 100 open issues) and `existing_issues.txt`
   - `product_context.txt` (the names in `pyeuropepmc.__all__` and the list of pages under `docs/`)
   - `labels.txt` (the repository's labels)
7. **Prepare LLM prompt** in `llm_prompt.txt`. The prompt asks for one to five suggestions that cover both capability gaps and code health, in a fixed JSON format, using only existing labels and not duplicating open issues. It then appends the public API and docs map, the label list, the README, the open issues and `analysis_summary.json`. The git log in `recent_commits.txt` is collected but not added to the prompt.
8. **Set up Node 24 and install the Copilot CLI** (`@github/copilot@1.0.83`).
9. **Run AI inference** with `actions/ai-inference` and `prompt-file: llm_prompt.txt`. `model` is set to an empty string, so the Copilot CLI chooses a model the account can use.
10. **Save the response** to `suggestion_output.json`.
11. **Validate and create issues**:
    - The step fails if the response is not valid JSON.
    - Suggestions without a title or body are skipped.
    - Labels that are not in `labels.txt` are dropped.
    - Each remaining suggestion becomes a `gh issue create` call. If that call fails while labels are attached, it is retried once without labels.
    - The step exits with an error only when no issue was created and at least one creation failed.
    - With `dry_run`, it prints each title, its labels and the body length instead.
12. **Upload artifacts** (always, see below).
13. **Write a job summary** with the last 20 lines of `analysis.log`.

## Expected model output

The prompt asks for JSON only, without Markdown fences:

```json
{
  "suggestions": [
    {
      "title": "Brief, specific title",
      "body": "Detailed description with context and rationale.",
      "labels": ["suggestion", "additional-label"]
    }
  ]
}
```

## Duplicates and labels

The workflow does not compare titles with existing issues. It avoids duplicates only by including the open issues in the prompt and telling the model not to repeat them, so a duplicate can still be filed.

Issues receive only labels that already exist in the repository. The label list comes from `gh label list` at run time, and any other label the model proposes is dropped before `gh issue create` runs.

## Artifacts

Each run uploads `feature-suggester-analysis-<run id>`, kept for 30 days.

| File | Content |
|---|---|
| `analysis_summary.json` | Condensed analysis results used in the prompt |
| `suggestion_output.json` | Raw model response |
| `llm_prompt.txt` | The full prompt sent to the model |
| `analysis.log` | Progress log of the analysis steps |
| `analysis_output/` | `ruff_results.json`/`.txt`, `bandit_results.json`/`.txt`, `mypy_results.txt`, `mypy_report/`, `coverage.json`, `test_results.txt`, `scc_results.json`/`.txt`, `todos.txt`, `test_files.txt`, `recent_commits.txt`, `codescene_delta.json`/`.txt`, `codescene_check.txt`, `codescene_reviews.json`, `codescene_reviews/`, `readme.txt`, `existing_issues.json`/`.txt`, `product_context.txt`, `labels.txt` |

The `codescene_reviews/` directory exists only when `CS_ACCESS_TOKEN` is set.

## Customising the workflow

| Change | Where |
|---|---|
| Schedule | The `cron` expression under `on.schedule` |
| Prompt wording | The "Prepare LLM prompt" step |
| Analysis tools | The "Run repository analysis" step. A new tool's output reaches the prompt only if its file is also added to `json_files` or `text_files` in the "Consolidate analysis results" step. |
| Model | The `model` input of the "Run AI inference for suggestions" step |

## Testing changes

Run the workflow from the Actions tab with `dry_run` enabled. It then runs the analysis, prompt, inference, JSON parsing and label filtering, but creates no issues. In the Run workflow dialog, select the branch that contains your change.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| `Error: LLM response is not valid JSON` | The step prints the response; it is also in `suggestion_output.json`. Adjust the prompt if the model adds prose or code fences. |
| No issues created | The step log lists skipped suggestions, `Dropping labels not in this repo`, `Retrying without labels` and `Failed:` messages. Check that the job still has `issues: write`. |
| CodeScene files contain `CodeScene CLI not available or CS_ACCESS_TOKEN not set` | Add the `CS_ACCESS_TOKEN` secret, or ignore it: the analysis runs without CodeScene. |
| Code-structure metrics are missing | The `scc` download failed; the run shows a warning annotation. |

## Related workflows

| Workflow | File |
|---|---|
| CI | `.github/workflows/cdci.yml` |
| Enhance new issues | `.github/workflows/enhanceIssue.yml` |
| Summarize new issues | `.github/workflows/summary.yml` |
| Weekly Benchmarks | `.github/workflows/benchmark.yml` |

See also the [CI and release workflow](ci-and-release-workflow.md) page.
