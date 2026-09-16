# Enrichment skill

Use `PaperEnricher` to combine a paper's metadata from Europe PMC, CrossRef, OpenAlex, Semantic Scholar and NIH iCite into one record. The full guide is [Metadata enrichment](../enrichment.md).

```python
from pyeuropepmc import EnrichmentConfig, PaperEnricher

config = EnrichmentConfig(crossref_email="you@example.org")

with PaperEnricher(config) as enricher:
    result = enricher.enrich_paper("10.1371/journal.pone.0308090")

merged = result["merged"]
print(f"Sources: {result['sources']}")
print(f"Title: {merged.get('title')}")
print(f"Citations: {merged.get('citation_count')}")
```

Key tips:
- Pass a DOI, DOI URL, PMID or PMCID as the first argument, or as `doi=`, `pmid=` or `pmcid=`.
- Europe PMC, CrossRef, OpenAlex, Semantic Scholar, iCite and ROR are enabled by default. Unpaywall needs `enable_unpaywall=True` plus `unpaywall_email` (or the `UNPAYWALL_EMAIL` environment variable); without an email the config raises `ValueError`.
- `result["sources"]` lists the sources that returned data. `merged["citation_count"]` is the highest count, and `merged["citation_counts"]` has the per-source values.
- For several papers, use `enricher.enrich_papers_batch(identifiers, save_responses=False)`. The default `save_responses=True` writes JSON files to `./enrichment_responses`.
- Semantic Scholar needs `pip install "pyeuropepmc[enrichment]"`; without it that source is skipped and the others still run.
