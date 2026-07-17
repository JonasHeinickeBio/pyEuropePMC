# Multi-Source Search

PyEuropePMC provides a unified interface for searching across **15+ external literature sources** with automatic deduplication.

## UnifiedSearch

The `UnifiedSearch` orchestrator lets you query multiple sources with a single call:

```python
from pyeuropepmc.literature import UnifiedSearch

searcher = UnifiedSearch()

# Search default sources (PubMed, arXiv, Semantic Scholar)
results, report = searcher.search("chronic fatigue syndrome", limit=25)

print(f"Found {len(results)} unique papers ({report.duplicates_removed} removed)")
```

### Available Sources

| Source key | Class | Type | Free? |
|---|---|---|---|
| `pubmed` | `PubMedClient` | Biomedical literature | Yes |
| `arxiv` | `ArxivClient` | Preprints | Yes |
| `semantic_scholar` | `SemanticScholarLiteratureAdapter` | AI-powered citations | Yes* |
| `openalex` | `OpenAlexLiteratureAdapter` | Open scholarly catalog | Yes |
| `clinicaltrials` | `ClinicalTrialsClient` | Clinical trial protocols | Yes |
| `zenodo` | `ZenodoClient` | Datasets & software | Yes |
| `doaj` | `DOAJClient` | Open access journals | Yes |
| `dblp` | `DBLPClient` | Computer science | Yes |
| `hal` | `HALClient` | French open archive | Yes |
| `core` | `COREClient` | Open access aggregator | Yes* |

*\* Optional API key recommended for higher rate limits*

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
from pyeuropepmc.literature import PubMedClient

with PubMedClient(api_key="your_key") as client:
    papers = client.search("ME/CFS", limit=10)
    paper = client.get_paper("32791984")  # by PMID
```

### arXiv

```python
from pyeuropepmc.literature import ArxivClient

with ArxivClient() as client:
    papers = client.search("chronic fatigue", limit=10, sort="relevance")
    paper = client.get_paper("2101.12345")  # by arXiv ID
```

### Semantic Scholar

```python
from pyeuropepmc.literature import SemanticScholarLiteratureAdapter

with SemanticScholarLiteratureAdapter() as client:
    papers = client.search("machine learning", limit=10)
```

### OpenAlex

```python
from pyeuropepmc.literature import OpenAlexLiteratureAdapter

with OpenAlexLiteratureAdapter() as client:
    papers = client.search("CRISPR", limit=10)
```

### Zenodo

```python
from pyeuropepmc.literature import ZenodoClient

with ZenodoClient() as client:
    papers = client.search("metabolomics", limit=10)
```

### DOAJ

```python
from pyeuropepmc.literature import DOAJClient

with DOAJClient() as client:
    papers = client.search("open access journals", limit=10)
```

### DBLP

```python
from pyeuropepmc.literature import DBLPClient

with DBLPClient() as client:
    papers = client.search("knowledge graph", limit=10)
```

### HAL

```python
from pyeuropepmc.literature import HALClient

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
from pyeuropepmc.literature import (
    normalize_doi,           # DOI validation + URL stripping
    normalize_author_name,   # "SMITH, John" → "Smith, John"
    normalize_paper_title,   # Lowercase + unicode NFKC
    normalize_abstract,      # Whitespace normalization
    normalize_mesh_terms,    # MeSH term normalization
    is_valid_doi,            # DOI format validation
)
```
