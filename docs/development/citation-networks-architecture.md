# Citation Networks & Cooccurrences - Architecture Diagram

## Current Architecture (Existing)

```
┌─────────────────────────────────────────────────────────────────┐
│                         PyEuropePMC                              │
│                        (Current v1.10.1)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ SearchClient │  │ArticleClient │  │FullTextClient│          │
│  │              │  │              │  │              │          │
│  │ • search()   │  │ • get_cita-  │  │ • download_  │          │
│  │ • search_    │  │   tions()    │  │   pdf()      │          │
│  │   and_parse()│  │ • get_refer- │  │ • download_  │          │
│  │              │  │   ences()    │  │   xml()      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                  │                  │                  │
│         └──────────────────┴──────────────────┘                 │
│                            │                                     │
│                  ┌─────────▼──────────┐                         │
│                  │   BaseAPIClient    │                         │
│                  │                    │                         │
│                  │ • Rate Limiting    │                         │
│                  │ • Retry Logic      │                         │
│                  │ • Error Handling   │                         │
│                  └─────────┬──────────┘                         │
│                            │                                     │
│                  ┌─────────▼──────────┐                         │
│                  │   CacheBackend     │                         │
│                  │                    │                         │
│                  │ • Optional Caching │                         │
│                  │ • TTL Management   │                         │
│                  └────────────────────┘                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Proposed Architecture (With Networks Module)

```
┌────────────────────────────────────────────────────────────────────────┐
│                            PyEuropePMC                                  │
│                         (Proposed v1.11+)                               │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ SearchClient │  │ArticleClient │  │FullTextClient│                 │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘                 │
│         │                  │                                            │
│         │                  │                                            │
│  ┌──────▼──────────────────▼────────────────────────────┐             │
│  │          Networks Module (NEW)                        │             │
│  │                                                        │             │
│  │  ┌───────────────────────────────────────────────┐   │             │
│  │  │     CitationNetworkBuilder                    │   │             │
│  │  │                                                │   │             │
│  │  │  • build_forward_network()                    │   │             │
│  │  │    └─> Recursively get_citations()           │   │             │
│  │  │                                                │   │             │
│  │  │  • build_backward_network()                   │   │             │
│  │  │    └─> Recursively get_references()          │   │             │
│  │  │                                                │   │             │
│  │  │  • build_bidirectional_network()             │   │             │
│  │  │                                                │   │             │
│  │  │  • export_network()                           │   │             │
│  │  │    └─> GraphML, GML, JSON, CSV               │   │             │
│  │  └───────────────────────────────────────────────┘   │             │
│  │                                                        │             │
│  │  ┌───────────────────────────────────────────────┐   │             │
│  │  │     CooccurrenceAnalyzer                      │   │             │
│  │  │                                                │   │             │
│  │  │  • analyze_mesh_cooccurrence()                │   │             │
│  │  │    └─> Extract MeSH terms, count pairs       │   │             │
│  │  │                                                │   │             │
│  │  │  • analyze_author_collaboration()             │   │             │
│  │  │    └─> Build author co-authorship network    │   │             │
│  │  │                                                │   │             │
│  │  │  • analyze_keyword_cooccurrence()             │   │             │
│  │  │    └─> Extract keywords, count pairs         │   │             │
│  │  └───────────────────────────────────────────────┘   │             │
│  │                                                        │             │
│  │  ┌───────────────────────────────────────────────┐   │             │
│  │  │     NetworkMetrics                            │   │             │
│  │  │                                                │   │             │
│  │  │  • calculate_centrality()                     │   │             │
│  │  │    └─> Degree, Betweenness, Eigenvector     │   │             │
│  │  │                                                │   │             │
│  │  │  • identify_hubs()                            │   │             │
│  │  │    └─> Top influential nodes                 │   │             │
│  │  │                                                │   │             │
│  │  │  • calculate_clustering()                     │   │             │
│  │  │    └─> Network clustering coefficient        │   │             │
│  │  └───────────────────────────────────────────────┘   │             │
│  │                                                        │             │
│  └────────────────────────────────────────────────────────┘            │
│                            │                                            │
│                  ┌─────────▼──────────┐                                │
│                  │   BaseAPIClient    │                                │
│                  │                    │                                │
│                  │ • Rate Limiting    │                                │
│                  │ • Retry Logic      │                                │
│                  │ • Error Handling   │                                │
│                  └─────────┬──────────┘                                │
│                            │                                            │
│                  ┌─────────▼──────────┐                                │
│                  │   CacheBackend     │  ◄─── CRITICAL for networks!  │
│                  │                    │                                │
│                  │ • Response Caching │                                │
│                  │ • TTL Management   │                                │
│                  └────────────────────┘                                │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                            │
                            │ Uses (Optional Dependencies)
                            ▼
        ┌─────────────────────────────────────────┐
        │   External Network Libraries            │
        │                                         │
        │   • NetworkX (graph data structures)    │
        │   • igraph (fast alternative)           │
        │   • matplotlib (visualization)          │
        │   • plotly (interactive viz)            │
        └─────────────────────────────────────────┘
```

## Citation Network Building Flow

```
                    ┌──────────────┐
                    │  Seed Paper  │
                    │ (MED:12345)  │
                    └──────┬───────┘
                           │
          ┌────────────────┴────────────────┐
          │                                  │
          ▼                                  ▼
   ┌────────────────┐              ┌────────────────┐
   │ Forward Cites  │              │ Backward Refs  │
   │ (who cites     │              │ (who is cited  │
   │  this paper?)  │              │  by this?)     │
   └────────┬───────┘              └────────┬───────┘
            │                               │
    ┌───────▼───────┐               ┌───────▼───────┐
    │ ArticleClient │               │ ArticleClient │
    │.get_citations()│               │.get_references│
    └───────┬───────┘               └───────┬───────┘
            │                               │
    ┌───────▼────────┐              ┌───────▼────────┐
    │ Paper 1        │              │ Paper A        │
    │ Paper 2        │              │ Paper B        │
    │ Paper 3        │              │ Paper C        │
    │ ...            │              │ ...            │
    └───────┬────────┘              └───────┬────────┘
            │                               │
            │ Depth < max_depth? ───────────┘
            │        │
            ▼        ▼
         Recurse   Stop
            │
            │
    ┌───────▼────────────────────┐
    │   NetworkX DiGraph         │
    │                            │
    │   Nodes: Papers            │
    │   Edges: Citations         │
    │   Attributes: Metadata     │
    └───────┬────────────────────┘
            │
    ┌───────▼────────────────────┐
    │   Export / Analyze         │
    │                            │
    │   • GraphML for Gephi      │
    │   • JSON for D3.js         │
    │   • Metrics calculation    │
    └────────────────────────────┘
```

## Cooccurrence Analysis Flow

```
                ┌────────────────────┐
                │  Query / Papers    │
                │  (e.g., "COVID-19")│
                └─────────┬──────────┘
                          │
              ┌───────────▼───────────┐
              │   SearchClient        │
              │   .search()           │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │   List of Papers      │
              │   (100-1000+ papers)  │
              └───────────┬───────────┘
                          │
         ┌────────────────┴─────────────────┐
         │                                   │
         ▼                                   ▼
┌─────────────────┐              ┌─────────────────┐
│ Extract MeSH    │              │ Extract Authors │
│ Terms           │              │                 │
└────────┬────────┘              └────────┬────────┘
         │                                 │
         ▼                                 ▼
┌─────────────────┐              ┌─────────────────┐
│ Count Pairs     │              │ Build Graph     │
│                 │              │                 │
│ (Term A, Term B)│              │ Node = Author   │
│   → count       │              │ Edge = Co-auth  │
└────────┬────────┘              └────────┬────────┘
         │                                 │
         ▼                                 ▼
┌─────────────────┐              ┌─────────────────┐
│ pandas DataFrame│              │ NetworkX Graph  │
│                 │              │                 │
│ term1 | term2   │              │ Undirected      │
│ cancer| therapy │              │ Weighted edges  │
│ ...   | ...     │              │                 │
└─────────────────┘              └─────────────────┘
```

## Data Flow & Dependencies

```
┌────────────────────────────────────────────────────────────┐
│                      User Application                       │
└────────────────────────────────┬───────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Citation        │  │ Cooccurrence    │  │ Network         │
│ NetworkBuilder  │  │ Analyzer        │  │ Metrics         │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                     │
         │  ┌─────────────────┴─────────────────┐  │
         │  │                                   │  │
         ▼  ▼                                   ▼  ▼
┌─────────────────┐                    ┌─────────────────┐
│ ArticleClient   │                    │ NetworkX        │
│ SearchClient    │                    │ (graph library) │
└────────┬────────┘                    └─────────────────┘
         │
         ▼
┌─────────────────┐
│ Europe PMC API  │
│                 │
│ • Citations     │
│ • References    │
│ • Metadata      │
└─────────────────┘
```

## Memory & Performance Considerations

```
Network Size Estimates:

┌──────────────┬────────────┬──────────────┬─────────────┐
│ Network Size │ API Calls  │ Memory Usage │ Build Time  │
├──────────────┼────────────┼──────────────┼─────────────┤
│ Small        │ < 50       │ < 10 MB      │ < 1 min     │
│ (50 nodes)   │            │              │             │
├──────────────┼────────────┼──────────────┼─────────────┤
│ Medium       │ 50-200     │ 10-50 MB     │ 1-5 min     │
│ (100-500)    │            │              │ (w/ cache)  │
├──────────────┼────────────┼──────────────┼─────────────┤
│ Large        │ 200-1000   │ 50-200 MB    │ 5-15 min    │
│ (500-1000)   │            │              │ (w/ cache)  │
├──────────────┼────────────┼──────────────┼─────────────┤
│ Very Large   │ > 1000     │ > 200 MB     │ > 15 min    │
│ (> 1000)     │            │              │             │
└──────────────┴────────────┴──────────────┴─────────────┘

With Caching: 80-90% reduction in API calls on repeated operations
Without Caching: Network rebuilds require full API traversal
```

## Module Import Structure

```python
# Top-level imports
from pyeuropepmc import (
    SearchClient,          # Existing
    ArticleClient,         # Existing
    FullTextClient,        # Existing
)

# Network analysis imports (NEW)
from pyeuropepmc.networks import (
    CitationNetworkBuilder,
    CooccurrenceAnalyzer,
    NetworkMetrics,
)

# Optional: Sub-module imports
from pyeuropepmc.networks.citation_network import CitationNetworkBuilder
from pyeuropepmc.networks.cooccurrence import CooccurrenceAnalyzer
from pyeuropepmc.networks.metrics import NetworkMetrics
from pyeuropepmc.networks.exporters import (
    export_to_graphml,
    export_to_gml,
    export_to_json,
)
```

## Alternative Architecture: Separate Repository (Not Recommended)

```
┌────────────────────────┐
│   pyeuropepmc          │  ← Core library
│                        │
│   • SearchClient       │
│   • ArticleClient      │
│   • FullTextClient     │
└───────────┬────────────┘
            │
            │ depends on
            ▼
┌────────────────────────┐
│ pyeuropepmc-networks   │  ← Separate package (NOT RECOMMENDED)
│                        │
│   • CitationNetwork    │
│     Builder            │
│   • Cooccurrence       │
│     Analyzer           │
└────────────────────────┘

Issues:
  ❌ Code duplication
  ❌ Version sync problems
  ❌ Fragmented documentation
  ❌ Two repos to maintain
```

## Recommended: Single Repository Architecture

```
pyEuropePMC/
├── src/pyeuropepmc/
│   ├── __init__.py              # Existing
│   ├── base.py                  # Existing
│   ├── search.py                # Existing
│   ├── article.py               # Existing
│   ├── fulltext.py              # Existing
│   ├── networks/                # NEW MODULE
│   │   ├── __init__.py
│   │   ├── citation_network.py
│   │   ├── cooccurrence.py
│   │   ├── metrics.py
│   │   └── exporters.py
│   └── utils/                   # Existing
│
├── tests/
│   ├── networks/                # NEW TESTS
│   │   ├── test_citation_network.py
│   │   ├── test_cooccurrence.py
│   │   └── test_metrics.py
│   └── ...
│
├── examples/
│   ├── 09-networks/             # NEW EXAMPLES
│   │   ├── 01-citation-network-basic.ipynb
│   │   ├── 02-cooccurrence-analysis.ipynb
│   │   └── 03-network-metrics.ipynb
│   └── ...
│
└── docs/
    ├── features/
    │   └── networks.md          # NEW DOCS
    └── ...
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single Repository** | Reuse infrastructure, easier maintenance |
| **Optional Dependencies** | Keep core lightweight, users opt-in |
| **NetworkX as Primary** | Standard, well-documented, widely used |
| **Caching Strongly Encouraged** | Networks = many API calls |
| **Max Depth/Nodes Limits** | Prevent runaway resource usage |
| **Export First, Visualize Later** | Leverage existing tools (Gephi, Cytoscape) |

---

For detailed implementation guidance, see:
- Full advisory: `citation-networks-implementation-advisory.md`
- Quick reference: `citation-networks-quick-reference.md`
