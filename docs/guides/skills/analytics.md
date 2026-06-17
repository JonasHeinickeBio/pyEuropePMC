# Analytics Skill

Generate statistics and visualizations from search results.

```python
from pyeuropepmc import SearchClient, to_dataframe
from pyeuropepmc.processing.analytics import (
    citation_statistics,
    publication_year_distribution,
    plot_citation_distribution,
)

client = SearchClient()

# Search and convert to DataFrame
results = client.search("cancer", pageSize=100)
papers_df = to_dataframe(results)

# Calculate statistics
stats = citation_statistics(papers_df)
print(f"Mean citations: {stats['mean']}")
print(f"Max citations: {stats['max']}")

# Distribution analysis
years = publication_year_distribution(papers_df)
print(years)

# Visualizations
fig = plot_citation_distribution(papers_df)
fig.show()
```

Key tips:
- Use `quality_metrics()` for open access, license analysis
- `detect_duplicates()` finds duplicate DOIs/titles
- All plots use matplotlib/seaborn; return `matplotlib.figure.Figure`
