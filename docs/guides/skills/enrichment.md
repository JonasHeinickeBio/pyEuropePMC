# Enrichment Skill

Use `PaperEnricher` to enrich paper metadata with external sources (CrossRef, Semantic Scholar, OpenAlex, Unpaywall).

```python
from pyeuropepmc import PaperEnricher, EnrichmentConfig

# Configure sources
config = EnrichmentConfig(
    enable_crossref=True,
    enable_semantic_scholar=True,
    enable_openalex=True,
    enable_unpaywall=False,  # requires email
)

with PaperEnricher(config) as enricher:
    result = enricher.enrich_paper(doi="10.1371/journal.pone.0308090")

    # Merged metadata from all sources
    merged = result["merged"]
    print(f"Title: {merged.get('title')}")
    print(f"Citations: {merged.get('citation_count')}")
```

Key tips:
- Unpaywall requires `crossref_email` in config for some features
- Results include `sources` list showing which APIs contributed
- Use `enrich_paper_batch()` for multiple DOIs
