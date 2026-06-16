# Feature Suggester GitHub Action

## Overview

The Feature Suggester is an automated GitHub Action that analyzes the pyEuropePMC repository and uses AI to suggest improvements, missing features, and potential refactoring opportunities. It runs weekly and can be triggered manually.

## How It Works

### 1. Repository Analysis
The workflow performs comprehensive code analysis:
- **Linting**: Runs Ruff to detect code quality issues
- **Security**: Uses Bandit to identify security vulnerabilities
- **Type Checking**: Executes mypy for type safety analysis
- **Test Coverage**: Generates coverage reports using pytest
- **Code Metrics**: Uses `scc` to analyze code structure and complexity
- **TODO Tracking**: Scans for TODO, FIXME, and similar comments
- **Git History**: Reviews recent commits for patterns

### 2. AI-Powered Suggestions
The analysis results are fed to GitHub's AI inference action, which:
- Reviews all collected metrics and reports
- Identifies high-priority improvement opportunities
- Generates actionable suggestions as GitHub issues
- Provides specific file names, functions, and contexts

### 3. Issue Creation
A Python script (`scripts/create_suggestions.py`):
- Parses the AI-generated suggestions
- Checks for duplicate issues to avoid spam
- Creates new issues with appropriate labels
- Logs all operations for transparency

## Schedule

- **Automatic**: Every Monday at 3:00 AM UTC
- **Manual**: Can be triggered via the Actions tab → Feature Suggester → Run workflow

## Configuration

### Required Secrets
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions (no setup needed)

### Environment Variables
The workflow uses the following internal variables:
- `SUGGESTIONS_FILE`: Path to LLM output (default: `suggestion_output.json`)
- `LOG_FILE`: Path to execution log (default: `action.log`)

## Artifacts

Each run produces the following artifacts (retained for 30 days):

1. **analysis_summary.json**: Complete repository analysis data
2. **suggestion_output.json**: Raw AI-generated suggestions
3. **action.log**: Detailed execution log showing what was created/skipped
4. **analysis_output/**: Directory containing individual analysis reports
   - `ruff_results.json/txt`: Linting results
   - `bandit_results.json/txt`: Security scan results
   - `coverage.json`: Test coverage data
   - `scc_results.json/txt`: Code structure metrics
   - `todos.txt`: List of TODO comments
   - `test_files.txt`: List of test files

## Labels Applied

Created issues are automatically labeled:
- `suggestion`: All AI-generated suggestions
- Additional context-specific labels: `enhancement`, `bug`, `security`, `documentation`, `testing`, `refactoring`, `performance`

## Deduplication

The script compares suggested issue titles against existing open issues to prevent duplicates. If a similar issue already exists, the suggestion is skipped and logged.

## Monitoring

Check the workflow execution:
1. Go to the **Actions** tab in GitHub
2. Select **Feature Suggester** workflow
3. View run history and logs
4. Download artifacts for detailed analysis

## Customization

### Modify Analysis Scope
Edit `.github/workflows/analyze_repo.yml` to:
- Add/remove analysis tools
- Change the analysis depth
- Adjust the AI prompt for different focus areas

### Adjust Schedule
Change the `cron` expression in the workflow file:
```yaml
on:
  schedule:
    - cron: "0 3 * * 1"  # Current: Weekly on Monday at 3 AM UTC
```

Examples:
- Daily: `"0 3 * * *"`
- Bi-weekly: `"0 3 1,15 * *"`
- Monthly: `"0 3 1 * *"`

### Customize AI Prompt
Edit the prompt in the "Prepare LLM prompt" step to:
- Focus on specific aspects (e.g., only security, only tests)
- Change the tone or detail level
- Add project-specific context

## Troubleshooting

### No issues created
1. Check if the AI response was valid JSON (download artifacts)
2. Review `action.log` for skipped duplicates
3. Verify the `GITHUB_TOKEN` has issues write permissions

### Invalid JSON errors
- The AI response may not be properly formatted
- Check `suggestion_output.json` artifact
- The prompt may need adjustment for clearer JSON output

### Rate limiting
- If running too frequently, GitHub API rate limits may apply
- Space out runs or reduce the number of suggestions

## Future Enhancements

Potential improvements to consider:
- Multi-provider LLM support (OpenAI, Claude, Cohere)
- Confidence thresholds for filtering suggestions
- PR-level comment bot for real-time feedback
- Integration with GitHub Projects for auto-triage
- Organization-level analysis across multiple repositories
- Fine-tuned prompts for domain-specific patterns (bioinformatics)

## Related Workflows

- **CDCI Pipeline**: Main CI/CD workflow for testing and quality checks
- **Enhance Issues**: AI-powered issue reformatting for clarity

## Contributing

To improve the Feature Suggester:
1. Test changes locally using `workflow_dispatch` trigger
2. Review generated artifacts for quality
3. Monitor false positives and adjust deduplication logic
4. Update the AI prompt based on suggestion quality
