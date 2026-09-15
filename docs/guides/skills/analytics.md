# Analytics skill

Summarise and plot Europe PMC search results with the analytics and visualization functions. The full reference is [Analytics and visualization](../../api/analytics-visualization.md).

```python
from pyeuropepmc import (
    SearchClient,
    citation_statistics,
    plot_citation_distribution,
    publication_year_distribution,
    to_dataframe,
)

with SearchClient() as client:
    response = client.search("cancer", pageSize=100)

papers = response["resultList"]["result"]
papers_df = to_dataframe(papers)

stats = citation_statistics(papers_df)
print(f"Mean citations: {stats['mean_citations']:.2f}")
print(f"Max citations: {stats['max_citations']}")

print(publication_year_distribution(papers_df))

fig = plot_citation_distribution(papers_df, save_path="citations.png")
```

Key tips:
- Install `pyeuropepmc[analytics]` (pandas) for the statistics, or `pyeuropepmc[visualization]` (adds matplotlib and seaborn) for the plots.
- `to_dataframe()` takes the list in `response["resultList"]["result"]`, not the response dict. The other functions accept that list or the DataFrame.
- `citation_statistics()` keys end in `_citations` (`mean_citations`, `median_citations`, `max_citations`, ...).
- `quality_metrics()` reports the share of papers that are open access, have an abstract, a DOI, a PMC copy or a PDF, plus an estimated peer-reviewed share. For licences, use `access_distribution()` or `plot_license_distribution()` from `pyeuropepmc.features.analytics`.
- `detect_duplicates(papers, method="doi")` returns lists of row indices; `method` is `title`, `doi`, `pmid` or `pmcid`.
- Every `plot_*` function returns a `matplotlib.figure.Figure`; pass `save_path` to write the image.
