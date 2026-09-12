# Multi-Source Search

PyEuropePMC provides a unified interface for searching across **15+ external literature sources** with automatic deduplication.

## UnifiedSearch

The `UnifiedSearch` orchestrator lets you query multiple sources with a single call:

```python
from pyeuropepmc.features.search import UnifiedSearch

searcher = UnifiedSearch()

# Search default sources (Europe PMC, PubMed, arXiv), in parallel
results, report = searcher.search("chronic fatigue syndrome", limit=25)

print(f"Found {len(results)} unique papers ({report.duplicates_removed} removed)")
print(report.metadata["source_times"])    # per-source wall time
print(report.metadata["source_errors"])   # {source: "<error>"} for any that failed
```

Sources run **concurrently** on a thread pool (`max_workers`, default one per
source), and the single query string is **translated into each source's
dialect** before dispatch (`translate=False` to disable) — e.g. arXiv gets
`all:"..."`, OpenAlex/Semantic Scholar get a plain free-text string, PubMed and
Europe PMC keep their field syntax.

### Available Sources

Sources come from a pluggable registry
(`pyeuropepmc.features.search.registry`).  List them, with the ones whose
optional dependency is actually installed:

```python
from pyeuropepmc.features.search import registry

registry.available_sources()                     # every registered source
registry.available_sources(installed_only=True)  # only what you can use now
registry.source_capabilities("europepmc")        # {'search', 'get_paper', 'fulltext', 'date_filter'}
```

| Source key | Class | Type | Extra needed |
|---|---|---|---|
| `europepmc` | `EuropePMCLiteratureAdapter` | Europe PMC (home API) | — |
| `pubmed` | `PubMedClient` | Biomedical literature | — |
| `arxiv` | `ArxivClient` | Preprints | — |
| `semantic_scholar` | `SemanticScholarLiteratureAdapter` | AI-powered citations | `pyeuropepmc[semanticscholar]` |
| `openalex` | `OpenAlexLiteratureAdapter` | Open scholarly catalog | — |
| `clinicaltrials` | `ClinicalTrialsClient` | Clinical trial protocols | — |
| `zenodo` | `ZenodoClient` | Datasets & software | — |
| `doaj` | `DOAJClient` | Open access journals | — |
| `dblp` | `DBLPClient` | Computer science | — |
| `hal` | `HALClient` | French open archive | — |
| `core` | `COREClient` | Open access aggregator | — |

Selecting a source whose extra is missing raises `OptionalDependencyError` with
the exact `pip install` command.

### Credentials

```python
searcher = UnifiedSearch(
    sources=["europepmc", "pubmed", "semantic_scholar", "openalex"],
    credentials={"api_key": "S2_KEY", "email": "you@example.org"},
)
```

Each source declares which credentials it accepts (`SourceSpec.credential_kwargs`):
`api_key` → Semantic Scholar / CORE; `email` → PubMed & OpenAlex polite pools.
`UnifiedSearch(api_key=...)` still works as a shortcut.

### Registering your own source

```python
from pyeuropepmc.features.search import registry

registry.register_source(registry.SourceSpec(
    name="my_repo",
    target="my_package.clients:MyRepoClient",   # resolved lazily
    extras=("my_sdk",),
    capabilities=frozenset({"search", "get_paper"}),
))
```

Packages can also register automatically via a `pyeuropepmc.sources` entry point
(a zero-arg callable that performs the `register_source` calls);
`registry.load_entry_point_sources()` loads them.

### Custom Source Selection

```python
# Explicit source list
searcher = UnifiedSearch(sources=["pubmed", "arxiv", "clinicaltrials"])

# Also available with author/institution lookups
searcher = UnifiedSearch(sources=["pubmed", "arxiv", "orcid"])
```

### Per-Source Results (No Dedup)

```python
# Get results grouped by source without deduplication
per_source = searcher.search_all("biomarkers")
for source, results in per_source.items():
    print(f"{source}: {len(results)} papers")
```

## Individual Source Clients

Each source can also be used independently:

### PubMed

```python
from pyeuropepmc.features.search import PubMedClient

with PubMedClient(api_key="your_key") as client:
    papers = client.search("ME/CFS", limit=10)
    paper = client.get_paper("32791984")  # by PMID
```

### arXiv

```python
from pyeuropepmc.features.search import ArxivClient

with ArxivClient() as client:
    papers = client.search("chronic fatigue", limit=10, sort="relevance")
    paper = client.get_paper("2101.12345")  # by arXiv ID
```

### Semantic Scholar

```python
from pyeuropepmc.features.literature.adapters import SemanticScholarLiteratureAdapter

with SemanticScholarLiteratureAdapter() as client:
    papers = client.search("machine learning", limit=10)
```

### OpenAlex

```python
from pyeuropepmc.features.literature.adapters import OpenAlexLiteratureAdapter

with OpenAlexLiteratureAdapter() as client:
    papers = client.search("CRISPR", limit=10)
```

### Zenodo

```python
from pyeuropepmc.features.search import ZenodoClient

with ZenodoClient() as client:
    papers = client.search("metabolomics", limit=10)
```

### DOAJ

```python
from pyeuropepmc.features.search import DOAJClient

with DOAJClient() as client:
    papers = client.search("open access journals", limit=10)
```

### DBLP

```python
from pyeuropepmc.features.search import DBLPClient

with DBLPClient() as client:
    papers = client.search("knowledge graph", limit=10)
```

### HAL

```python
from pyeuropepmc.features.search import HALClient

with HALClient() as client:
    papers = client.search("neuroscience", limit=10)
```

## LiteratureResult Model

All search methods return `LiteratureResult` Pydantic objects with consistent fields:

```python
from pyeuropepmc.models import LiteratureResult

# Fields:
# - title, doi, pmid, pmcid, authors, publication_year
# - journal, abstract, citation_count, source, source_id
# - extra_metadata (source-specific data)

paper = results[0]
print(f"{paper.title} ({paper.source})")
print(f"DOI: {paper.doi}")
print(f"Year: {paper.publication_year}")
```

## Rate Limiting

Each source has polite default rate limits:

| Source | Default Delay | With API Key |
|--------|--------------|--------------|
| PubMed | 1.0s | 0.3s |
| arXiv | 3.0s | N/A |
| Semantic Scholar | 1.0s | 0.1s |
| ClinicalTrials.gov | 0.5s | N/A |
| Others | 1.0s | Varies |

## Normalization Utilities

The package includes normalization utilities for consistent data cleaning:

```python
from pyeuropepmc.features.search import (
    normalize_doi,           # DOI validation + URL stripping
    normalize_author_name,   # "SMITH, John" → "Smith, John"
    normalize_paper_title,   # Lowercase + unicode NFKC
    normalize_abstract,      # Whitespace normalization
    normalize_mesh_terms,    # MeSH term normalization
    is_valid_doi,            # DOI format validation
)
```
