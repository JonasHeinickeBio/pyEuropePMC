# Citation Networks & Work Cooccurrences - Advisory Summary

> **Date**: 2025-11-11  
> **Status**: Advisory Documentation Completed  
> **Purpose**: Provide strategic guidance on implementing comprehensive network analysis features

---

## 🎯 Core Recommendation

**Implement citation networks and work cooccurrences as NEW MODULES within the current PyEuropePMC repository.**

❌ Do NOT create a separate repository  
❌ Do NOT fork the project  
✅ DO extend the existing codebase with a new `networks` submodule

---

## 📊 Decision Rationale

### Why Same Repository?

| Advantage | Impact |
|-----------|--------|
| **Reuse Infrastructure** | Leverage existing ArticleClient, caching, rate limiting, error handling |
| **Single Package** | Users install one package, not multiple dependencies |
| **Unified Maintenance** | One CI/CD pipeline, one test suite, one release process |
| **Consistent API** | Follow established patterns throughout |
| **Manageable Scope** | Network module ~2,000 LOC vs 10,000 LOC core - only 20% increase |

### Dependencies Made Optional

Keep core lightweight by making network analysis dependencies optional:

```bash
# Core package (no change for existing users)
pip install pyeuropepmc

# With network features (opt-in)
pip install pyeuropepmc[networks]
```

---

## 🏗️ Proposed Structure

```python
src/pyeuropepmc/
├── networks/                    # NEW MODULE
│   ├── __init__.py
│   ├── citation_network.py     # CitationNetworkBuilder
│   ├── cooccurrence.py          # CooccurrenceAnalyzer
│   ├── metrics.py               # NetworkMetrics
│   └── exporters.py             # Export utilities
```

### Example Usage (Proposed)

```python
from pyeuropepmc.networks import CitationNetworkBuilder
from pyeuropepmc import ArticleClient, CacheConfig

# Build citation network with caching (recommended)
builder = CitationNetworkBuilder(
    article_client=ArticleClient(
        cache_config=CacheConfig(enabled=True)
    ),
    max_depth=2,
    max_nodes=1000,
)

# Create forward citation network
network = builder.build_forward_network("MED", "29867326", depth=2)

# Export for visualization
builder.export_network(network, format="graphml", path="citations.graphml")

# Analyze network
from pyeuropepmc.networks import NetworkMetrics
metrics = NetworkMetrics()
hubs = metrics.identify_hubs(network, top_n=10)
```

---

## 📅 Implementation Timeline

### Phase 1: Core Citation Networks (2-3 weeks)
- ✅ CitationNetworkBuilder class
- ✅ Forward/backward/bidirectional traversal
- ✅ Depth limiting and cycle detection
- ✅ Basic export (GraphML, JSON)
- ✅ Comprehensive tests

### Phase 2: Network Metrics (1-2 weeks)
- ✅ NetworkMetrics class
- ✅ Centrality calculations
- ✅ Hub identification
- ✅ Clustering coefficients

### Phase 3: Cooccurrence Analysis (2-3 weeks)
- ✅ CooccurrenceAnalyzer class
- ✅ MeSH term cooccurrence
- ✅ Author collaboration networks
- ✅ Keyword analysis

### Phase 4: Advanced Features (2-3 weeks)
- ✅ Temporal network analysis
- ✅ Community detection
- ✅ Network comparison tools
- ✅ Performance optimizations

**Total Estimated Time**: 7-11 weeks

---

## 🔑 Critical Success Factors

### 1. Aggressive Caching
- Network traversal can trigger hundreds of API calls
- Caching reduces repeated work by 80-90%
- **Action**: Make caching the default for network operations

### 2. Resource Limits
- Set `max_depth` (default: 2) to prevent infinite recursion
- Set `max_nodes` (default: 1000) to prevent memory issues
- **Action**: Clear documentation on resource requirements

### 3. Error Handling
- Europe PMC data has gaps (missing citations, incomplete metadata)
- **Action**: Robust error handling, skip gracefully, log issues

### 4. Documentation & Examples
- Network analysis is complex
- **Action**: Comprehensive Jupyter notebook examples

### 5. Performance Monitoring
- Document API call counts and memory usage
- **Action**: Include estimates in docstrings and user guide

---

## 📈 Complexity Assessment

### Citation Networks: Medium-High
- **Complexity**: Multi-hop traversal, graph construction
- **API Calls**: 50-1000+ depending on depth
- **Memory**: 10-200 MB for typical networks
- **Time**: 1-15 minutes with caching

### Work Cooccurrences: High
- **Complexity**: Statistical analysis, combinatorial comparisons
- **API Calls**: Depends on query size (100-1000+ papers)
- **Memory**: Varies with analysis type
- **Time**: Minutes to hours for large analyses

---

## 🚦 When to Reconsider Separate Repository

Create `pyeuropepmc-networks` as separate package if:

1. Network module grows beyond **5,000 lines of code**
2. Dependency conflicts emerge (e.g., NetworkX version issues)
3. You want to support **non-Europe PMC data sources**
4. User base clearly **segments** (API users vs network analysts)
5. Development cycles need to be **fully independent**

**Current Assessment**: None of these conditions apply. Start in same repo.

---

## 📚 Documentation Delivered

### Complete Advisory Package

1. **[Full Implementation Advisory](docs/development/citation-networks-implementation-advisory.md)** (20 pages)
   - Current state analysis
   - Feature scope breakdown
   - Three options compared (same repo, new repo, fork)
   - Complete module structure with examples
   - 4-phase implementation plan
   - Key considerations and trade-offs

2. **[Quick Reference Guide](docs/development/citation-networks-quick-reference.md)** (7 pages)
   - TL;DR decision matrix
   - Proposed API examples
   - Implementation timeline
   - Critical considerations

3. **[Architecture Diagrams](docs/development/citation-networks-architecture.md)** (17 pages)
   - Visual architecture (current and proposed)
   - Citation network building flow
   - Cooccurrence analysis flow
   - Memory and performance estimates

4. **[Documentation Index](docs/development/CITATION_NETWORKS_README.md)** (9 pages)
   - Navigation guide
   - FAQ section
   - Next steps

### Updated Files

- **[Development README](docs/development/README.md)**: Added links to new advisory documents

---

## 🎓 What Already Exists

PyEuropePMC provides the foundation for network analysis:

### ArticleClient (Existing)
```python
from pyeuropepmc.article import ArticleClient

client = ArticleClient()

# Forward citations (papers citing this paper)
citations = client.get_citations("MED", "29867326")

# Backward citations (papers referenced by this paper)
references = client.get_references("MED", "29867326")

# Citation counts
count = client.get_citation_count("MED", "29867326")
```

### SearchClient (Existing)
```python
from pyeuropepmc import SearchClient, QueryBuilder

# Advanced query building
qb = QueryBuilder()
query = qb.keyword("cancer").and_().citation_count(min_count=10).build()

# Search with caching
client = SearchClient(cache_config=CacheConfig(enabled=True))
results = client.search(query, pageSize=100)
```

### Infrastructure (Existing)
- ✅ Rate limiting with configurable delays
- ✅ Retry logic with exponential backoff
- ✅ Optional caching (diskcache-based)
- ✅ Comprehensive error handling
- ✅ Type-safe API with full type hints
- ✅ 200+ tests, 90%+ coverage

---

## 🛠️ Dependencies to Add

```toml
[tool.poetry.dependencies]
# Network analysis (optional)
networkx = { version = ">=3.0", optional = true }
matplotlib = { version = ">=3.5", optional = true }
plotly = { version = ">=5.0", optional = true }

# Alternative backend for performance
igraph = { version = ">=0.10", optional = true }

[tool.poetry.extras]
networks = ["networkx", "matplotlib", "plotly"]
networks-fast = ["igraph"]  # Alternative
```

---

## ✅ Next Steps for Implementation

### Immediate (Days 1-2)
1. Review all advisory documentation
2. Build prototype CitationNetworkBuilder with 10-paper test
3. Validate caching and rate limiting approach

### Short-term (Week 1)
1. Write detailed API specification
2. Define test coverage requirements
3. Plan example notebooks
4. Set up `networks` module structure

### Medium-term (Weeks 2-4)
1. Implement Phase 1 (core citation networks)
2. Achieve 90%+ test coverage
3. Create basic example notebook
4. Gather early user feedback

### Long-term (Weeks 5-11)
1. Implement Phases 2-4
2. Comprehensive documentation
3. Performance optimization
4. Production release

---

## 💡 Key Insights

### Strength of Current Codebase
- Well-structured, modular design
- Production-ready infrastructure
- Active maintenance (v1.10.1 released recently)
- Strong test coverage and documentation culture

### Natural Extension Point
- ArticleClient already provides citation/reference APIs
- Adding multi-hop traversal is logical next step
- Cooccurrence analysis complements existing search features

### Ecosystem Coherence
- Users expect one package for Europe PMC operations
- Splitting would fragment the ecosystem
- Single repository maintains conceptual unity

### Risk Mitigation
- Optional dependencies keep core lightweight
- Clear module boundaries prevent scope creep
- 4-phase approach allows incremental validation

---

## 🎉 Conclusion

**The path forward is clear**: Extend PyEuropePMC with a new `networks` submodule. This approach:

- ✅ Leverages existing infrastructure
- ✅ Maintains ecosystem unity
- ✅ Keeps core package lightweight (optional dependencies)
- ✅ Provides clear implementation path (4 phases)
- ✅ Balances feature richness with maintainability

**The documentation is complete.** Implementation can begin with confidence that the architectural foundation is sound.

---

## 📞 Questions or Feedback?

- **GitHub Issues**: [Report or discuss](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)
- **Email**: jonas.heinicke@helmholtz-hzi.de
- **Documentation**: See `docs/development/CITATION_NETWORKS_README.md` for full index

---

**Advisory Status**: ✅ Complete and ready for implementation decision
