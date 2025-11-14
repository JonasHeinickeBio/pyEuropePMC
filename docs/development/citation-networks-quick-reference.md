# Citation Networks & Work Cooccurrences - Quick Reference

> **TL;DR**: Implement these features as **new modules in the current PyEuropePMC repository**, not as a separate package or fork.

## Quick Decision Matrix

| Option | Pros | Cons | Recommended? |
|--------|------|------|--------------|
| **Same Repository** | ✅ Reuse infrastructure<br>✅ Single package<br>✅ Easier maintenance | ⚠️ Increased complexity<br>⚠️ New dependencies | **✅ YES** |
| **New Repository** | ✅ Focused scope<br>✅ Independent releases | ❌ Code duplication<br>❌ Fragmented ecosystem | ❌ No |
| **Fork** | ✅ Full control | ❌ Loses updates<br>❌ Community split | ❌ No |

## What You Get Today (Already Built)

```python
from pyeuropepmc.article import ArticleClient

client = ArticleClient()

# Get forward citations (papers citing this paper)
citations = client.get_citations("MED", "29867326")

# Get backward citations (papers referenced by this paper)  
references = client.get_references("MED", "29867326")

# Get counts
citation_count = client.get_citation_count("MED", "29867326")
```

## What's Missing (To Be Built)

1. **Multi-hop traversal**: Following citations recursively
2. **Network construction**: Building graph data structures
3. **Network metrics**: Centrality, clustering, hubs
4. **Visualization export**: GraphML, GML, JSON formats
5. **Cooccurrence analysis**: MeSH terms, keywords, authors
6. **Collaboration networks**: Author and institution graphs

## Proposed Module Structure

```
src/pyeuropepmc/
├── networks/                        # NEW
│   ├── __init__.py
│   ├── citation_network.py         # CitationNetworkBuilder class
│   ├── cooccurrence.py              # CooccurrenceAnalyzer class
│   ├── metrics.py                   # NetworkMetrics class
│   └── exporters.py                 # Export utilities
```

## Quick Example (Proposed API)

```python
from pyeuropepmc.networks import CitationNetworkBuilder
from pyeuropepmc import ArticleClient, CacheConfig

# Initialize with caching (recommended for networks!)
cache_config = CacheConfig(enabled=True, ttl=86400)  # 24h cache
article_client = ArticleClient(cache_config=cache_config)

# Build citation network
builder = CitationNetworkBuilder(
    article_client=article_client,
    max_depth=2,        # Up to 2 hops from seed paper
    max_nodes=1000,     # Limit network size
)

# Build forward citation network (papers citing the seed)
network = builder.build_forward_network(
    source="MED",
    article_id="29867326",
    depth=2,
)

# Export to GraphML for visualization in Gephi/Cytoscape
builder.export_network(network, format="graphml", path="citations.graphml")

# Calculate network metrics
from pyeuropepmc.networks import NetworkMetrics

metrics = NetworkMetrics()
centrality = metrics.calculate_centrality(network)
hubs = metrics.identify_hubs(network, top_n=10)

print(f"Most influential papers: {hubs}")
```

## Installation (After Implementation)

```bash
# Core package (no network features)
pip install pyeuropepmc

# With network analysis features
pip install pyeuropepmc[networks]

# With fast graph processing (alternative)
pip install pyeuropepmc[networks-fast]
```

## Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1**: Core Citation Networks | 2-3 weeks | `CitationNetworkBuilder`, basic traversal, export |
| **Phase 2**: Network Metrics | 1-2 weeks | `NetworkMetrics`, centrality, hub detection |
| **Phase 3**: Cooccurrence Analysis | 2-3 weeks | `CooccurrenceAnalyzer`, MeSH/author/keyword |
| **Phase 4**: Advanced Features | 2-3 weeks | Temporal analysis, communities, optimization |
| **Total** | **7-11 weeks** | Full-featured network analysis module |

## Key Dependencies to Add

```toml
[tool.poetry.dependencies]
# Make these optional to keep core lightweight
networkx = { version = ">=3.0", optional = true }
matplotlib = { version = ">=3.5", optional = true }
plotly = { version = ">=5.0", optional = true }

[tool.poetry.extras]
networks = ["networkx", "matplotlib", "plotly"]
```

## Critical Implementation Considerations

### 1. Rate Limiting ⚠️
- Citation traversal = hundreds of API calls
- **Solution**: Use caching aggressively, implement batch processing

### 2. Memory Management ⚠️
- Large networks can use GBs of RAM
- **Solution**: Set max_nodes limits, provide streaming options

### 3. Reproducibility ⚠️
- Citation networks change over time
- **Solution**: Save snapshots with timestamps, version metadata

### 4. Data Quality ⚠️
- Missing citations, incomplete metadata
- **Solution**: Robust error handling, skip gracefully, log issues

## Why Not a Separate Repository?

| Concern | Why Same Repo Is Better |
|---------|-------------------------|
| "It's too complex" | ⚠️ Network module will be ~2,000 LOC vs 10,000 LOC core - still manageable |
| "New dependencies" | ✅ Make them optional - core users unaffected |
| "Maintenance burden" | ✅ Single CI/CD, one test suite, one release process |
| "Scope creep" | ✅ Clear module boundaries prevent this |

**Bottom Line**: Only split if module grows beyond 5,000 LOC or requires conflicting dependencies.

## Success Criteria

Before considering these features "done":

- ✅ Build 1,000-node citation network in <5 minutes
- ✅ Memory usage <1GB for typical networks (100-500 nodes)
- ✅ 90%+ test coverage maintained
- ✅ Comprehensive example notebooks
- ✅ Clear documentation on limitations and performance

## When to Reconsider Separate Repository

Split into `pyeuropepmc-networks` if:

1. Network module exceeds 5,000 lines of code
2. Dependency conflicts emerge (e.g., NetworkX version issues)
3. Want to support non-Europe PMC data sources
4. User base clearly segments (API users vs network analysts)
5. Development cycles need to be independent

**Current assessment**: None of these apply yet - stay in same repo.

## Next Steps

1. **Prototype** (1-2 days): Build basic `CitationNetworkBuilder` with 10-paper test
2. **Validate** (1 day): Ensure approach works with Europe PMC API limits
3. **Design** (2-3 days): Write detailed API specification
4. **Implement Phase 1** (2-3 weeks): Core citation networks
5. **Gather feedback** (ongoing): Adjust based on early user experience

## Questions?

See full advisory document: `docs/development/citation-networks-implementation-advisory.md`

Key sections:
- **Current State Analysis**: What's already built
- **Feature Scope Analysis**: Detailed breakdown of features
- **Detailed Recommendation**: Complete module structure
- **Implementation Phases**: Step-by-step plan
- **Key Considerations**: Performance, memory, rate limiting

## Related Documentation

- **Existing Features**: `examples/03-article-client/` - See current citation/reference retrieval
- **Caching Guide**: `docs/advanced/caching.md` - Critical for network operations
- **API Reference**: `docs/api/` - ArticleClient documentation
- **Development Guide**: `docs/development/README.md` - Contributing guidelines
