# PyEuropePMC Dependency Groups

This document proposes a reorganization of dependencies into optional groups to reduce the overhead for users who only need basic functionality.

## Current Problem

The current `pyproject.toml` lists many dependencies as required, making installation heavy (~20+ packages). Users who only want basic search functionality shouldn't need to install visualization, RDF, LLM, and enrichment libraries.

## Proposed Solution

Split dependencies into 5 core groups:

1. **core** - Minimal required dependencies for basic search
2. **standard** - Common features (analytics, visualization, export, CLI)
3. **rdf** - Semantic web / RDF conversion features
4. **agentic** - LLM-powered citation analysis
5. **enrichment** - External API enrichment (Semantic Scholar, etc.)

## Detailed Grouping

### 1. Core (Required) - ~8 dependencies

These are the essential dependencies for basic Europe PMC search functionality.

| Dependency | Purpose | Used In |
|------------|---------|---------|
| `requests` | HTTP client for API calls | All clients |
| `backoff` | Retry mechanism | Core client |
| `defusedxml` | Safe XML parsing | Article, annotations clients |
| `tqdm` | Progress bars | Fulltext client |
| `diskcache` | File-based caching | Core cache system |
| `cachetools` | In-memory caching | Core cache system |
| `tabulate` | Table formatting (CLI) | CLI output |
| `python-dotenv` | Environment configuration | General use |

**Rationale:**
- These enable the core search functionality (basic PubMed/PMC queries)
- Minimal overhead (~2-3MB additional installation)
- Used by virtually all modules

### 2. Standard (Optional) - ~12 dependencies

Common features: analytics, visualization, export, CLI enhancements.

| Dependency | Purpose | Used In |
|------------|---------|---------|
| `pandas` | DataFrames, analytics | Analytics, visualization |
| `matplotlib` | Plotting | Visualization |
| `seaborn` | Enhanced plotting | Visualization |
| `xlsxwriter` | Excel export | Export utilities |
| `typer` | CLI framework | Command-line interface |
| `rich` | Enhanced terminal output | CLI, enrichment reporting |
| `requests-cache` | HTTP response caching | All HTTP operations |
| `beautifulsoup4` | HTML parsing | Optional utilities |
| `ipython` | Interactive shell | Optional Jupyter support |
| `ipykernel` | Jupyter kernels | Optional Jupyter support |
| `jupyterlab` | Jupyter environment | Optional Jupyter support |
| `notebook` | Jupyter notebooks | Optional Jupyter support |

**Rationale:**
- Users who want analytics/visualization need these
- Many users don't need rich CLI or Jupyter
- Separating from core allows minimal install

### 3. RDF/SEM (Optional) - ~3 dependencies

Semantic web and RDF conversion features.

| Dependency | Purpose | Used In |
|------------|---------|---------|
| `rdflib` | RDF graph manipulation | RDF mappers |
| `rdflib-jsonld` | JSON-LD serialization | RDF mappers |
| `rdfizer` | RML-based mapping | Advanced RDF conversion |

**Rationale:**
- Niche feature - only users doing semantic web work
- `rdfizer` is heavy and rarely used
- Can be installed separately if needed

### 4. Agentic (Optional) - ~4 dependencies

LLM-powered citation analysis features.

| Dependency | Purpose | Used In |
|------------|---------|---------|
| `langchain` | LLM framework | LLM client |
| `langchain-openai` | OpenAI integration | LLM client |
| `openai` | OpenAI SDK | LLM client |
| `rapidfuzz` | Fuzzy text matching | Citation analysis |

**Rationale:**
- LLM features are optional and expensive
- Many users won't use AI features
- `rapidfuzz` is also used by literature module - kept separate

### 5. Enrichment (Optional) - ~5 dependencies

External API enrichment (Semantic Scholar, Crossref, etc.).

| Dependency | Purpose | Used In |
|------------|---------|---------|
| `semanticscholar` | Semantic Scholar API | Enrichment |
| `cryptography` | Security features | Logging, signing |
| `search-query` | Query validation | Literature normalization |
| `tornado` | Web server (MCP) | MCP server |
| `flask` | Web server (MCP) | MCP server |

**Rationale:**
- Enrichment is optional feature
- MCP server only needed for API integration
- `cryptography` and `search-query` are small but not always needed

## Migration Plan

### Step 1: Update pyproject.toml

```toml
[project]
# Keep only core dependencies
dependencies = [
    "requests>=2.32",
    "backoff>=2.2",
    "defusedxml>=0.7",
    "tqdm>=4.67",
    "diskcache>=5.6",
    "cachetools>=6.2",
    "tabulate>=0.9",
    "python-dotenv>=0.19",
]

[project.optional-dependencies]
standard = [
    "pandas>=1.4",
    "matplotlib>=3.7",
    "seaborn>=0.12",
    "xlsxwriter>=3.2",
    "typer>=0.12",
    "rich>=13.0",
    "requests-cache>=1.2",
    "beautifulsoup4>=4.13",
    "ipython>=7.30",
    "ipykernel>=6.7",
    "jupyterlab>=3.2",
    "notebook>=6.4",
]

rdf = [
    "rdflib>=6.0",
    "rdflib-jsonld>=0.5",
    "rdfizer>=4.7.5,<5",
]

agentic = [
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "openai>=1.50",
    "rapidfuzz>=2.15",
]

enrichment = [
    "semanticscholar>=0.12",
    "cryptography>=46.0",
    "search-query>=0.13",
    "tornado>=6.5",
    "flask>=3.1",
]

# Combine groups for convenience
all = [
    "pandas>=1.4",
    "matplotlib>=3.7",
    "seaborn>=0.12",
    "xlsxwriter>=3.2",
    "typer>=0.12",
    "rich>=13.0",
    "requests-cache>=1.2",
    "beautifulsoup4>=4.13",
    "ipython>=7.30",
    "ipykernel>=6.7",
    "jupyterlab>=3.2",
    "notebook>=6.4",
    "rdflib>=6.0",
    "rdflib-jsonld>=0.5",
    "rdfizer>=4.7.5,<5",
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "openai>=1.50",
    "rapidfuzz>=2.15",
    "semanticscholar>=0.12",
    "cryptography>=46.0",
    "search-query>=0.13",
    "tornado>=6.5",
    "flask>=3.1",
]

dev = [
    "pytest>=8.4",
    "pytest-cov>=6.0",
    "pytest-xdist>=3.7",
    "pre-commit>=4.2",
    "black>=25.1",
    "mypy>=1.16",
    "types-PyYAML>=6.0",
    "types-requests>=2.31",
    "pytest-benchmark>=5.2",
    "coverage>=7.11",
    "bandit>=1.8",
    "ruff>=0.14",
    "typing-extensions>=4.14",
    "memory-profiler>=0.61",
]
```

### Step 2: Update installation documentation

```bash
# Minimal install (basic search only)
pip install pyeuropepmc

# Standard features (analytics, visualization, CLI)
pip install pyeuropepmc[standard]

# RDF features (semantic web)
pip install pyeuropepmc[rdf]

# Agentic features (LLM citation analysis)
pip install pyeuropepmc[agentic]

# Enrichment features (external APIs)
pip install pyeuropepmc[enrichment]

# All features
pip install pyeuropepmc[all]

# Development setup
pip install pyeuropepmc[dev]
```

### Step 3: Update code with lazy imports

Update modules to gracefully handle missing dependencies:

```python
# In src/pyeuropepmc/agentic/llm_client.py
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# In src/pyeuropepmc/processing/visualization.py
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    VIS_AVAILABLE = True
except ImportError:
    VIS_AVAILABLE = False
```

## Benefits

1. **Reduced install size**: Core install ~50MB vs current ~150MB+
2. **Faster CI/CD**: Minimal dependencies mean faster builds
3. **Lower conflict risk**: Fewer dependencies = fewer version conflicts
4. **Clear feature boundaries**: Users understand what each group provides
5. **Better maintainability**: Clearer module boundaries
6. **Flexible deployments**: Users install only what they need

## Migration Checklist

- [ ] Update `pyproject.toml` with new dependency groups
- [ ] Update all imports to use lazy loading for optional dependencies
- [ ] Add dependency check warnings in relevant modules
- [ ] Update README installation instructions
- [ ] Update documentation for each optional group
- [ ] Test minimal install (core only)
- [ ] Test each optional group independently
- [ ] Verify backward compatibility

## Backward Compatibility

- Existing code will continue to work
- Users installing via `pip install pyeuropepmc` will get minimal core
- Users wanting full features need to add extras: `pyeuropepmc[all]`
- Add clear migration path in release notes

## Next Steps

1. Review and approve the proposed groupings
2. Implement the changes in `pyproject.toml`
3. Add lazy imports throughout the codebase
4. Test each optional group
5. Update documentation
6. Release as minor version (backward compatible)
