# Advisory: Implementing Citation Networks and Work Cooccurrences in PyEuropePMC

## Executive Summary

This document provides strategic advice on implementing comprehensive citation network analysis and work cooccurrence features in PyEuropePMC. After analyzing the current codebase, API capabilities, and project architecture, I recommend **extending the existing repository** with new specialized modules rather than creating a separate repository or fork.

**Key Recommendation**: Implement these features as **new modules within the current PyEuropePMC repository** to maintain ecosystem coherence while keeping the core library focused.

---

## Current State Analysis

### Existing Capabilities

PyEuropePMC already provides foundational building blocks for citation network analysis:

1. **ArticleClient** (`article.py`, 819 lines)
   - `get_citations()`: Retrieve papers citing a given article
   - `get_references()`: Retrieve papers referenced by an article
   - `get_citation_count()`: Get citation counts
   - `get_reference_count()`: Get reference counts
   - Pagination support for large citation/reference lists

2. **SearchClient** (`search.py`, 910 lines)
   - Advanced query capabilities via QueryBuilder
   - Citation count filtering (`citation_count()` method)
   - Batch searching capabilities

3. **Infrastructure**
   - Optional caching via `CacheBackend` (reduces API load for network traversal)
   - Rate limiting and retry logic
   - Type-safe API with comprehensive error handling
   - 200+ tests with 90%+ coverage

### Architecture Strengths

- **Modular design**: Clear separation of concerns (search, article, fulltext, parsing)
- **Well-documented**: Comprehensive docstrings, examples, and API docs
- **Production-ready**: Robust error handling, logging, caching
- **Active maintenance**: Recent updates (v1.10.1), CI/CD pipeline
- **Python 3.10+**: Modern type hints throughout

---

## Feature Scope Analysis

### 1. Citation Networks

**What it involves:**

- **Forward citations**: Papers that cite a seed paper (already available via `get_citations()`)
- **Backward citations**: Papers referenced by a seed paper (already available via `get_references()`)
- **Multi-hop traversal**: Building citation trees/graphs by following citations recursively
- **Network metrics**: Calculate centrality, clustering coefficients, PageRank-like metrics
- **Visualization**: Export networks to formats like GraphML, GML, or JSON for visualization tools
- **Network analysis**: Identify influential papers, citation patterns, research lineages

**Complexity**: **Medium-High**
- Requires recursive API calls with careful rate limiting
- Network data structures (graphs) not currently in the project
- Potential for very large datasets (thousands of nodes)
- Need for cycle detection and depth limiting
- Memory management for large networks

**API Dependencies**:
- Primarily uses existing `ArticleClient.get_citations()` and `get_references()`
- Europe PMC API fully supports this (no new endpoints needed)

### 2. Work Cooccurrences

**What it involves:**

- **Concept cooccurrence**: Track which MeSH terms, keywords, or concepts appear together in papers
- **Author collaboration**: Identify authors who frequently co-author papers
- **Institution networks**: Map research collaborations between institutions
- **Topic clustering**: Group papers by shared concepts or references
- **Temporal analysis**: Track how cooccurrences evolve over time

**Complexity**: **High**
- Requires aggregating and analyzing metadata from many papers
- Statistical analysis for significance testing
- Potential for combinatorial explosion (N² comparisons)
- Need for efficient data structures (sparse matrices, adjacency lists)
- More compute-intensive than citation networks

**API Dependencies**:
- Uses `SearchClient` for bulk paper retrieval
- Relies on metadata fields (MeSH terms, authors, keywords, affiliations)
- May require fulltext parsing for deeper analysis

---

## Implementation Options

### Option 1: Same Repository (Recommended) ✅

**Add new modules to `src/pyeuropepmc/`:**

```
src/pyeuropepmc/
├── networks/              # New module
│   ├── __init__.py
│   ├── citation_network.py    # Citation graph construction
│   ├── cooccurrence.py         # Cooccurrence analysis
│   ├── graph_metrics.py        # Network analysis metrics
│   └── exporters.py            # Export to various formats
```

**Advantages:**
- ✅ **Leverages existing infrastructure**: Reuse `ArticleClient`, caching, rate limiting, error handling
- ✅ **Single source of truth**: One package for all Europe PMC interactions
- ✅ **Easier maintenance**: One CI/CD pipeline, one test suite, one release process
- ✅ **Better discoverability**: Users find all features in one place
- ✅ **Shared dependencies**: Reuse `requests`, `pandas`, `numpy` already in the project
- ✅ **Consistent API design**: Follow established patterns in the codebase

**Disadvantages:**
- ⚠️ Increases package size and complexity
- ⚠️ New dependencies (e.g., `networkx`, `igraph`) impact all users
- ⚠️ Risk of scope creep if not carefully managed

**Mitigation:**
- Make network analysis dependencies **optional** (like `diskcache`)
- Use Python's optional imports pattern:
  ```python
  try:
      import networkx as nx
      NETWORKX_AVAILABLE = True
  except ImportError:
      NETWORKX_AVAILABLE = False
  ```
- Clear separation of concerns via submodules
- Comprehensive tests for new features

### Option 2: New Separate Repository

**Create `pyeuropepmc-networks` as a separate package**

**Advantages:**
- ✅ Focused scope (network analysis only)
- ✅ Independent versioning and release cycle
- ✅ Lighter weight for users who don't need networks
- ✅ Can use specialized dependencies without impacting core library

**Disadvantages:**
- ❌ **Code duplication**: Must reimplement or depend on pyeuropepmc
- ❌ **Dependency management**: Users must install two packages
- ❌ **Fragmented ecosystem**: Harder to discover and maintain
- ❌ **API inconsistency risk**: Different design patterns across packages
- ❌ **Doubled maintenance burden**: Two repos, two CI/CD pipelines, two documentation sites

**When this makes sense:**
- If the network features are **fundamentally different** from the core API wrapper functionality
- If you expect the network package to diverge significantly in purpose
- If you want to support multiple data sources (not just Europe PMC)

### Option 3: Fork the Repository

**Create a fork with network features built-in**

**Advantages:**
- ✅ Full control over codebase
- ✅ Can make breaking changes without affecting upstream
- ✅ Experimental features don't impact stable version

**Disadvantages:**
- ❌ **Loses upstream updates**: Must manually sync with original repo
- ❌ **Community fragmentation**: Splits the user base
- ❌ **Duplicated effort**: Two versions of the same codebase
- ❌ **Not scalable**: Forks should eventually merge or become separate projects

**When this makes sense:**
- If you fundamentally disagree with the project's direction
- If you need features the maintainers won't accept
- If you're prototyping and may not contribute back

---

## Detailed Recommendation: Extend Current Repository

### Proposed Module Structure

```python
# src/pyeuropepmc/networks/__init__.py
"""
Network analysis for Europe PMC data.

This module provides tools for building and analyzing citation networks
and investigating work cooccurrences.
"""

from pyeuropepmc.networks.citation_network import CitationNetworkBuilder
from pyeuropepmc.networks.cooccurrence import CooccurrenceAnalyzer
from pyeuropepmc.networks.metrics import NetworkMetrics

__all__ = [
    "CitationNetworkBuilder",
    "CooccurrenceAnalyzer", 
    "NetworkMetrics",
]


# src/pyeuropepmc/networks/citation_network.py
class CitationNetworkBuilder:
    """
    Build citation networks from Europe PMC data.
    
    Constructs directed graphs where nodes are papers and edges represent
    citation relationships. Supports both forward citations (papers citing
    a seed paper) and backward citations (papers referenced by a seed paper).
    """
    
    def __init__(
        self,
        article_client: ArticleClient | None = None,
        max_depth: int = 2,
        max_nodes: int = 1000,
        cache_config: CacheConfig | None = None,
    ):
        """
        Initialize citation network builder.
        
        Args:
            article_client: Existing ArticleClient (or create new one)
            max_depth: Maximum traversal depth to prevent infinite recursion
            max_nodes: Maximum nodes to prevent memory issues
            cache_config: Cache configuration (highly recommended for networks)
        """
        
    def build_forward_network(
        self, 
        source: str, 
        article_id: str,
        depth: int = 1,
    ) -> nx.DiGraph:
        """Build network of papers citing the seed paper."""
        
    def build_backward_network(
        self,
        source: str,
        article_id: str, 
        depth: int = 1,
    ) -> nx.DiGraph:
        """Build network of papers referenced by the seed paper."""
        
    def build_bidirectional_network(
        self,
        source: str,
        article_id: str,
        forward_depth: int = 1,
        backward_depth: int = 1,
    ) -> nx.DiGraph:
        """Build both forward and backward citation networks."""
        
    def export_network(
        self,
        network: nx.DiGraph,
        format: str = "graphml",
        path: str | None = None,
    ) -> str:
        """Export network to various formats (GraphML, GML, JSON, etc.)."""


# src/pyeuropepmc/networks/cooccurrence.py  
class CooccurrenceAnalyzer:
    """
    Analyze cooccurrences in Europe PMC literature.
    
    Supports analysis of:
    - MeSH term cooccurrences
    - Keyword cooccurrences  
    - Author collaboration networks
    - Institution collaboration networks
    - Citation overlap (papers citing multiple seed papers)
    """
    
    def __init__(
        self,
        search_client: SearchClient | None = None,
        article_client: ArticleClient | None = None,
    ):
        """Initialize cooccurrence analyzer."""
        
    def analyze_mesh_cooccurrence(
        self,
        papers: list[dict],
        min_count: int = 2,
    ) -> pd.DataFrame:
        """
        Find MeSH terms that frequently occur together.
        
        Returns DataFrame with term pairs and cooccurrence counts.
        """
        
    def analyze_author_collaboration(
        self,
        papers: list[dict],
        min_collaborations: int = 2,
    ) -> nx.Graph:
        """Build author collaboration network."""
        
    def analyze_keyword_cooccurrence(
        self,
        papers: list[dict],
        min_count: int = 2,
    ) -> pd.DataFrame:
        """Find keywords that frequently occur together."""


# src/pyeuropepmc/networks/metrics.py
class NetworkMetrics:
    """Calculate network analysis metrics."""
    
    @staticmethod
    def calculate_centrality(graph: nx.DiGraph) -> dict[str, float]:
        """Calculate various centrality measures (degree, betweenness, eigenvector)."""
        
    @staticmethod
    def identify_hubs(graph: nx.DiGraph, top_n: int = 10) -> list[tuple[str, float]]:
        """Identify most influential nodes in the network."""
        
    @staticmethod
    def calculate_clustering(graph: nx.Graph) -> float:
        """Calculate clustering coefficient."""
```

### Implementation Phases

**Phase 1: Core Citation Networks (2-3 weeks)**
1. Implement `CitationNetworkBuilder` with basic traversal
2. Add depth limiting and cycle detection
3. Implement network export (GraphML, JSON)
4. Add comprehensive tests
5. Create example notebooks

**Phase 2: Network Metrics (1-2 weeks)**
1. Implement `NetworkMetrics` class
2. Add centrality calculations
3. Add hub/authority identification
4. Add visualization helpers

**Phase 3: Cooccurrence Analysis (2-3 weeks)**
1. Implement `CooccurrenceAnalyzer`
2. Add MeSH term cooccurrence
3. Add author collaboration networks
4. Add keyword analysis

**Phase 4: Advanced Features (2-3 weeks)**
1. Temporal network analysis
2. Community detection
3. Network comparison tools
4. Performance optimizations

**Total Estimated Time**: 7-11 weeks for full implementation

### Dependencies to Add

```toml
[tool.poetry.dependencies]
# Existing dependencies remain...

# Network analysis (optional)
networkx = { version = ">=3.0", optional = true }
# Alternative: python-igraph for better performance on large graphs
igraph = { version = ">=0.10", optional = true }

# For visualization export
matplotlib = { version = ">=3.5", optional = true }
plotly = { version = ">=5.0", optional = true }

[tool.poetry.extras]
networks = ["networkx", "matplotlib", "plotly"]
networks-fast = ["igraph"]  # Alternative backend
```

Users would install with:
```bash
pip install pyeuropepmc[networks]
```

### Testing Strategy

1. **Unit tests**: Test each network method in isolation with mocked API responses
2. **Integration tests**: Test with small real datasets (10-20 papers)
3. **Performance tests**: Benchmark large networks (1000+ nodes)
4. **Example notebooks**: Jupyter notebooks demonstrating use cases

### Documentation Requirements

1. **API documentation**: Complete docstrings for all new classes/methods
2. **User guide**: High-level explanation of citation networks and cooccurrences
3. **Tutorial notebooks**: Step-by-step examples
4. **FAQ**: Common pitfalls and solutions
5. **Performance guide**: Tips for working with large networks

---

## Key Implementation Considerations

### 1. API Rate Limiting

**Challenge**: Citation network traversal can trigger hundreds of API calls.

**Solutions**:
- Leverage existing `rate_limit_delay` in `ArticleClient`
- **Strongly recommend caching**: `CacheConfig(enabled=True)` should be default for network operations
- Implement batch processing with progress callbacks
- Add early stopping criteria (max nodes, max depth)
- Provide resume capability for interrupted traversals

### 2. Memory Management

**Challenge**: Large networks can consume significant memory.

**Solutions**:
- Streaming/generator-based traversal where possible
- Option to save intermediate results to disk
- Use memory-efficient graph formats (adjacency lists)
- Clear documentation on memory requirements
- Add memory usage monitoring and warnings

### 3. Data Quality

**Challenge**: Europe PMC data quality varies; missing citations, incomplete metadata.

**Solutions**:
- Robust error handling for missing data
- Clear logging of skipped papers
- Validation methods to check network integrity
- Option to filter nodes by quality criteria (citation count, publication year)

### 4. Performance

**Challenge**: Network construction can be slow for large graphs.

**Solutions**:
- Parallel API calls where safe (respect rate limits)
- Efficient graph algorithms (use NetworkX or igraph)
- Caching at multiple levels (API responses, partial networks)
- Progress bars with `tqdm` (already a dependency)
- Provide "preview" mode for quick initial exploration

### 5. Reproducibility

**Challenge**: Citation networks evolve over time as new papers are published.

**Solutions**:
- Save snapshots of networks with timestamps
- Include query parameters in network metadata
- Export networks with version information
- Systematic review logging integration (already exists in QueryBuilder)

---

## Alternative: Separate Package Considerations

If you later decide a separate package is necessary, structure it as:

**Package name**: `pyeuropepmc-networks`

**Dependencies**:
```toml
dependencies = [
    "pyeuropepmc>=1.10.0",  # Core library
    "networkx>=3.0",
    "numpy>=1.21",
    "pandas>=1.4",
]
```

**Import structure**:
```python
from pyeuropepmc import ArticleClient, SearchClient
from pyeuropepmc_networks import CitationNetworkBuilder

# Seamless integration
client = ArticleClient()
builder = CitationNetworkBuilder(article_client=client)
network = builder.build_forward_network("MED", "12345678")
```

**When to consider this**:
- After implementing in main repo, if the network modules grow beyond ~5,000 LOC
- If network features require conflicting dependency versions
- If you want to support data sources beyond Europe PMC
- If the user base clearly segments into "basic API users" vs "network analysts"

---

## Comparison with Similar Projects

### 1. PubMed/NCBI Tooling
- **BioPython**: Provides PubMed API access but no citation networks
- **metapub**: Similar API wrapper, no network analysis
- **Your advantage**: Europe PMC has better open access coverage and citation APIs

### 2. Citation Network Tools
- **pybliometrics** (Scopus): Excellent network features but proprietary data
- **scholarly** (Google Scholar): Limited API, rate limiting issues
- **Your advantage**: Open data, stable API, better suited for research reproducibility

### 3. Network Analysis Libraries
- **NetworkX**: Standard Python graph library (use this!)
- **igraph**: Faster for large graphs, more complex API
- **graph-tool**: Fastest but harder to install
- **Recommendation**: Start with NetworkX for compatibility, optionally support igraph

---

## Final Recommendations

### Do's ✅

1. **Implement in the current repository** as a new `networks` module
2. **Make dependencies optional** to keep core library lightweight
3. **Leverage existing infrastructure** (caching, rate limiting, error handling)
4. **Follow existing code patterns** (type hints, docstrings, testing)
5. **Start with citation networks** (simpler, high value)
6. **Add comprehensive examples** (notebooks are critical for complex features)
7. **Document performance characteristics** clearly
8. **Provide memory and API call estimates** for different network sizes
9. **Integrate with existing features** (QueryBuilder for seed paper selection)
10. **Consider visualization helpers** but keep visualization libraries optional

### Don'ts ❌

1. **Don't create a separate repository** unless the module grows beyond 5,000 LOC
2. **Don't make network dependencies required** for core package users
3. **Don't implement custom graph data structures** - use NetworkX or igraph
4. **Don't skip rate limiting** - citation traversal can easily exceed API limits
5. **Don't ignore memory constraints** - document and test with large networks
6. **Don't reinvent the wheel** - reuse existing clients and utilities
7. **Don't neglect error handling** - network operations are inherently fragile
8. **Don't assume complete data** - Europe PMC has gaps in older literature

### Success Metrics

Track these to evaluate the feature's success:

- **Adoption**: Number of users installing with `[networks]` extra
- **Performance**: Network construction time and memory usage
- **Reliability**: Error rates and edge cases handled
- **Usability**: Time from install to first working network
- **Documentation quality**: User questions in issues/discussions

---

## Conclusion

**Recommended Approach**: Extend the existing PyEuropePMC repository with a new `networks` submodule.

**Key Principles**:
1. **Incremental implementation**: Start with core citation networks, add cooccurrence later
2. **Optional dependencies**: Keep the core library lightweight
3. **Leverage existing infrastructure**: Reuse clients, caching, and error handling
4. **Comprehensive testing and documentation**: These features are complex - invest in good examples
5. **Performance awareness**: Networks can be large - optimize early and document limitations

**Next Steps**:
1. Prototype a basic `CitationNetworkBuilder` class (1-2 days)
2. Test with small networks (10-20 papers) to validate approach
3. Write design document with detailed API specification
4. Implement Phase 1 (core citation networks) 
5. Gather user feedback before proceeding to Phase 2-4

This approach balances feature richness with maintainability, keeps the ecosystem unified, and provides clear paths for future expansion. The existing codebase is well-structured to support these additions without major refactoring.

---

## Questions to Consider Before Starting

1. **Target use cases**: Who will use this? Bibliometricians? Systematic reviewers? Data scientists?
2. **Performance requirements**: What's the largest network you expect users to build?
3. **Visualization scope**: Will you provide built-in visualization, or just export?
4. **Community input**: Are there existing users requesting these features?
5. **Maintenance capacity**: Can you support the ~30% increase in codebase size?

Feel free to discuss any of these points before beginning implementation.
