# CodeScene CLI Setup for pyEuropePMC

## Installation Complete

CodeScene CLI has been successfully installed and configured for your project!

## What's Been Set Up

### 1. CodeScene CLI Installation
- CodeScene CLI installed at `~/.local/bin/cs`
- Access token configured (`CS_ACCESS_TOKEN`)
- CLI is functional and tested

### 2. Custom Configuration
- `.codescene-rules.json` - Custom rules for different file types
- Stricter rules for source code, relaxed for tests and examples

### 3. Development Integration
- **Pre-commit hook** added for automatic code health checks
- **Makefile targets**:
  - `make codescene` - Full analysis
  - `make codescene-delta` - Delta analysis
  - `make quality-full` - All quality checks including CodeScene
- **Analysis script** at `scripts/codescene_analysis.sh`

### 4. CI/CD Integration
- **GitHub Actions workflows** (`.github/workflows/cdci.yml` and `analyze_repo.yml`)
- Automatic CodeScene CLI installation in CI
- Environment variable loading from `.env` file
- Comprehensive analysis with check, review, and delta commands

### 5. Environment Management
- **`.env` file** for secure token storage
- **`.env.example`** template for team setup
- Automatic loading in scripts and workflows

## Environment Setup

### CodeScene Access Token
1. **Copy the template:**
   ```bash
   cp .env.example .env
   ```

2. **Get your CodeScene token:**
   - Contact your CodeScene administrator
   - Or check your CodeScene project settings

3. **Configure the token:**
   ```bash
   # Edit .env file
   CS_ACCESS_TOKEN=your_actual_token_here
   ```

### Security Notes
- `.env` is in `.gitignore` (won't be committed)
- Token is loaded automatically by scripts and CI/CD
- No hardcoded secrets in code

### Command Line Usage
```bash
# Check a single file
cs check src/pyeuropepmc/article.py

# Review with detailed output
cs review src/pyeuropepmc/article.py

# Delta analysis (compare with main branch)
cs delta main

# Check staged changes only
cs delta --staged

# Interactive mode (prompts for fixes)
cs delta --interactive
```

### Make Commands
```bash
# Run full CodeScene analysis
make codescene

# Run delta analysis only
make codescene-delta

# Run all quality checks (ruff, mypy, bandit, codescene)
make quality-full
```

### Script Usage
```bash
# Full analysis (check + review + delta)
./scripts/codescene_analysis.sh

# Check analysis only
./scripts/codescene_analysis.sh check

# Review analysis only
./scripts/codescene_analysis.sh review

# Delta analysis only
./scripts/codescene_analysis.sh delta

# Help
./scripts/codescene_analysis.sh help
```

## Current Code Health Status

### `src/pyeuropepmc/article.py` - Score: 7.55/10
**Issues Found:**
- Code duplication in multiple locations
- Functions with 5-7 arguments (threshold: 4)
- Complex conditional expressions
- Overall code complexity

### `src/pyeuropepmc/search.py` - Score: 7.31/10
**Issues Found:**
- Complex methods (cyclomatic complexity up to 18!)
- Bumpy road patterns
- Multiple complex conditionals

## Improvement Recommendations

### High Priority (search.py)
1. **Break down complex methods** (cc > 10)
   - `_advanced_search()` method (cc=18) needs refactoring
   - Consider splitting into smaller, focused functions

2. **Simplify conditional logic**
   - Extract complex conditions into well-named boolean functions
   - Use early returns to reduce nesting

### Medium Priority (article.py)
1. **Reduce function arguments**
   - Use data classes or configuration objects
   - Group related parameters into dictionaries

2. **Eliminate code duplication**
   - Extract common patterns into utility functions
   - Consider using inheritance or composition

### General Improvements
1. **Method length** - Keep methods under 20 lines
2. **Single responsibility** - Each function should do one thing
3. **Descriptive naming** - Use clear, intention-revealing names

## Integration with Git Workflow

### CI/CD Pipelines
CodeScene analysis runs automatically in:
- **Main CI/CD pipeline** (`.github/workflows/cdci.yml`)
- **Repository analysis workflow** (`.github/workflows/analyze_repo.yml`)

Both workflows:
- Install CodeScene CLI automatically
- Load environment variables from `.env`
- Run comprehensive analysis (check + review + delta)
- Report results in CI logs

### Pre-commit Hook
- Automatically runs on `git commit`
- Checks all staged Python files
- Prevents commits with severe code health issues

## Monitoring Code Health

### Regular Analysis
```bash
# Weekly full analysis
make codescene

# Before each PR
make codescene-delta
```

### Custom Thresholds
Edit `.codescene-rules.json` to adjust:
- Complexity thresholds
- Argument count limits
- File-specific rules

## Next Steps

1. **Set up your environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your CodeScene token
   ```

2. **Test the integration:**
   ```bash
   make codescene  # Full analysis
   make quality-full  # All quality checks
   ```

3. **Monitor CI/CD runs** to ensure CodeScene analysis works in automated pipelines

4. **Address high-priority issues** identified by CodeScene analysis

5. **Set up regular code health monitoring** in your development workflow

## Resources

- [CodeScene CLI Documentation](https://codescene.io/docs/cli/)
- [Code Health Metrics Guide](https://codescene.io/docs/guides/code-health/)
- [Refactoring Patterns](https://refactoring.guru/)
