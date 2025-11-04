# CodeScene CLI Setup for pyEuropePMC

## ✅ Installation Complete

CodeScene CLI has been successfully installed and configured for your project!

## 🔧 What's Been Set Up

### 1. **CodeScene CLI Installation**
- ✅ CodeScene CLI installed at `~/.local/bin/cs`
- ✅ Access token configured (`CS_ACCESS_TOKEN`)
- ✅ CLI is functional and tested

### 2. **Custom Configuration**
- ✅ `.codescene-rules.json` - Custom rules for different file types
- ✅ Stricter rules for source code, relaxed for tests and examples

### 3. **Development Integration**
- ✅ **Pre-commit hook** added for automatic code health checks
- ✅ **Makefile targets**:
  - `make codescene` - Full analysis
  - `make codescene-delta` - Delta analysis
  - `make quality-full` - All quality checks including CodeScene
- ✅ **Analysis script** at `scripts/codescene_analysis.sh`

### 4. **CI/CD Integration**
- ✅ **GitHub Actions workflow** (`.github/workflows/codescene-analysis.yml`)
- ✅ Automatic PR analysis with comments
- ✅ Delta analysis on pull requests

## 🚀 How to Use

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
# Full analysis
./scripts/codescene_analysis.sh

# Delta analysis only
./scripts/codescene_analysis.sh delta

# Help
./scripts/codescene_analysis.sh help
```

## 📊 Current Code Health Status

### `src/pyeuropepmc/article.py` - Score: 7.55/10
**Issues Found:**
- ⚠️ Code duplication in multiple locations
- ⚠️ Functions with 5-7 arguments (threshold: 4)
- ⚠️ Complex conditional expressions
- ⚠️ Overall code complexity

### `src/pyeuropepmc/search.py` - Score: 7.31/10
**Issues Found:**
- ⚠️ Complex methods (cyclomatic complexity up to 18!)
- ⚠️ Bumpy road patterns
- ⚠️ Multiple complex conditionals

## 🎯 Improvement Recommendations

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

## 🔄 Integration with Git Workflow

### Pre-commit Hook
- Automatically runs on `git commit`
- Checks all staged Python files
- Prevents commits with severe code health issues

### Pull Request Analysis
- Automatic analysis on PR creation/updates
- Comments added to PR with findings
- Delta analysis shows impact of changes

## 📈 Monitoring Code Health

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

## 🔗 Next Steps

1. **Address high-priority issues** in `search.py`
2. **Set up regular code health monitoring**
3. **Train team** on CodeScene metrics and best practices
4. **Consider** CodeScene enterprise features for more insights

## 📚 Resources

- [CodeScene CLI Documentation](https://codescene.io/docs/cli/)
- [Code Health Metrics Guide](https://codescene.io/docs/guides/code-health/)
- [Refactoring Patterns](https://refactoring.guru/)

---

**CodeScene CLI is now fully integrated into your development workflow!** 🎉
