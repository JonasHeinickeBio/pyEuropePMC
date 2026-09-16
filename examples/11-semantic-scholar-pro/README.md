# Semantic Scholar library wrapper

This directory contains examples for `ProfessionalSemanticScholarClient`, the wrapper around the [danielnsilva/semanticscholar](https://github.com/danielnsilva/semanticscholar) library that `SemanticScholarClient` uses internally. It needs `pip install "pyeuropepmc[semanticscholar]"`.

The wrapper converts the library's typed `Paper` and `Author` objects to plain dicts, so read values with `[]` or `.get()`; keys whose value is missing are left out. It is not exported from `pyeuropepmc.features.enrich`, does not cache responses, and is not a context manager.

## Quick start

```python
from pyeuropepmc.features.enrich.sources.semanticscholar_pro import (
    ProfessionalSemanticScholarClient,
)

# An API key is optional but raises the rate limit
client = ProfessionalSemanticScholarClient(api_key=None, rate_limit_delay=1.0)

paper = client.get_paper("DOI:10.1038/nature12373")
if paper:
    print(f"Title: {paper['title']}")
    print(f"Authors: {len(paper.get('authors', []))}")

# Bulk search (no relevance ranking)
papers = client.search_paper("cancer", bulk=True, limit=50)

# Relevance-ranked search
papers = client.search_paper("machine learning", bulk=False, limit=100)
```

## Examples

| Script | Shows |
|---|---|
| `typed_responses.py` | The keys of paper and author results |
| `bulk_search.py` | Bulk search, relevance search and filters |
| `rate_limiting.py` | How `rate_limit_delay` spaces requests, and bulk search to save API calls |
| `integration.py` | `PaperEnricher` combining Semantic Scholar with CrossRef, OpenAlex and Unpaywall |

### Paper and author lookups

```python
from pyeuropepmc.features.enrich.sources.semanticscholar_pro import (
    ProfessionalSemanticScholarClient,
)

client = ProfessionalSemanticScholarClient()

paper = client.get_paper("DOI:10.1038/nature12373")
if paper:
    print(f"Title: {paper['title']}")
    print(f"DOI: {paper.get('external_ids', {}).get('DOI')}")
    print(f"Citation count: {paper.get('citation_count')}")
    print(f"Year: {paper.get('year')}")
    print(f"Fields of study: {paper.get('fields_of_study')}")
    for author in paper.get("authors", []):
        print(f"  - {author.get('name')} ({author.get('author_id')})")

author = client.get_author("1724609")
if author:
    print(f"Author: {author.get('name')}")
    print(f"Paper count: {author.get('paper_count')}")
    print(f"H-index: {author.get('h_index')}")
```

Paper dicts have `s2_paper_id`, `title`, `abstract`, `year`, `publication_date`, `venue`, `journal` (a dict with `name`, `volume`, `pages`), `citation_count`, `influential_citation_count`, `reference_count`, `fields_of_study`, `publication_types`, `external_ids`, `open_access_pdf_url`, `tldr` and `authors`. Author dicts have `author_id`, `name`, `affiliations`, `citation_count`, `h_index`, `paper_count`, `homepage` and `url`.

### Search with filters

```python
from pyeuropepmc.features.enrich.sources.semanticscholar_pro import (
    ProfessionalSemanticScholarClient,
)

client = ProfessionalSemanticScholarClient()

papers = client.search_paper(
    query="cancer",
    year="2023",
    publication_types=["JournalArticle"],
    min_citation_count=10,
    limit=100,
)
print(f"Found {len(papers)} papers")
for paper in papers[:10]:
    print(paper.get("title"), paper.get("citation_count"))
```

Publication types use Semantic Scholar's names, such as `JournalArticle`, `Review`, `ClinicalTrial` and `MetaAnalysis`.

### Enrichment with several APIs

```python
from pyeuropepmc import EnrichmentConfig, PaperEnricher

config = EnrichmentConfig(
    enable_crossref=True,
    enable_semantic_scholar=True,
    enable_openalex=True,
    enable_unpaywall=True,
    unpaywall_email="you@example.org",
    rate_limit_delay=1.0,
)

with PaperEnricher(config) as enricher:
    result = enricher.enrich_paper("10.1038/nature12373")

merged = result["merged"]
print(f"Title: {merged.get('title')}")
print(f"Citation count (max): {merged.get('citation_count')}")
print(f"Open access: {merged.get('oa_status', 'N/A')}")
```

## Method reference

| Method | Returns |
|---|---|
| `get_paper(paper_id, fields=None)` | `dict` or `None`; `paper_id` is a Semantic Scholar ID or a prefixed ID such as `DOI:10.1038/nature12373` |
| `get_papers(paper_ids, fields=None)` | `list[dict]` for up to 500 IDs |
| `search_paper(query, bulk=False, limit=100, year=None, publication_types=None, min_citation_count=None, ...)` | `list[dict]` |
| `get_author(author_id, fields=None)` | `dict` or `None` |
| `search_author(query, ...)` | `list[dict]` |
| `get_paper_authors(paper_id, ...)` | `list[dict]` |
| `get_recommendations(...)`, `get_recommendations_from_lists(...)` | `list[dict]` |

See the [enrichment guide](../../docs/guides/enrichment.md) for `SemanticScholarClient` and `PaperEnricher`.

## Best practices

1. **Use an API key** for higher rate limits.
2. **Use `bulk=True`** for large searches to minimise API calls.
3. **Handle missing data**: keys without a value are left out of the dicts.
