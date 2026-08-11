# Additional Source Clients

PyEuropePMC integrates with several additional free literature sources beyond the main multi-source search.

## CORE

Open access aggregator with 200M+ papers (requires free API key):

```python
from pyeuropepmc.features.search import COREClient

with COREClient(api_key="your_key") as client:
    papers = client.search("machine learning", limit=10)
```

## NIH iCite

NIH Office of Portfolio Analysis citation metrics, including the Relative Citation Ratio (RCR):

```python
from pyeuropepmc.features.enrich import ICiteClient

client = ICiteClient()

# Get citation metrics for a paper
metrics = client.get_metrics(pmids=["32791984", "32882182"])
for metric in metrics:
    print(f"PMID: {metric['pmid']}")
    print(f"  Citations: {metric['citations']}")
    print(f"  RCR: {metric.get('rcr', 'N/A')}")  # Relative Citation Ratio
    print(f"  Percentile: {metric.get('percentile', 'N/A')}")
```

### ICiteMetrics Model

```python
from pyeuropepmc.models import ICiteMetrics

metrics = ICiteMetrics(
    pmid="32791984",
    citations=42,
    relative_citation_ratio=1.5,
    percentile_by_year=85.0,
    expected_citations=28,
)
```

## ORCID

Researcher profile and publication lookups:

```python
client = OrcidClient()
profile = client.get_profile("0000-0002-1825-0097")
works = client.get_works("0000-0002-1825-0097")
```

## Source Matrix

| Source | Type | Key Required | Records |
|--------|------|--------------|---------|
| CORE | Open access papers | Yes (free) | 200M+ |
| iCite | Citation metrics | No | NIH papers |
| ORCID | Researcher profiles | No | 10M+ |
| Zenodo | Datasets & software | No | 3M+ |
| DOAJ | Open access journals | No | 20K journals |
| DBLP | Computer science | No | 6M+ papers |
| HAL | French open archive | No | 1M+ papers |
