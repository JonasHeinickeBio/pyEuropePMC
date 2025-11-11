# Analytics and Visualization

PyEuropePMC provides comprehensive analytics and visualization tools for analyzing scientific literature retrieved from Europe PMC. These tools enable you to perform statistical analysis, detect patterns, and create visualizations of your search results.

## Overview

The analytics and visualization modules provide:

- **Data Conversion**: Convert API results to pandas DataFrames
- **Statistical Analysis**: Publication year distribution, citation statistics, quality metrics
- **Duplicate Detection**: Identify and remove duplicate papers
- **Visualizations**: Rich plots and dashboards using matplotlib and seaborn

## Installation

The analytics and visualization features require additional dependencies:

```bash
pip install pyeuropepmc[viz]
```

Or if you're using the base installation, these dependencies are already included:
- `pandas >= 1.4`
- `matplotlib >= 3.7.0`
- `seaborn >= 0.12.0`

## Analytics Module

### Converting to DataFrame

Convert search results to a pandas DataFrame for easier manipulation:

```python
from pyeuropepmc import SearchClient, to_dataframe

client = SearchClient()
response = client.search("CRISPR gene editing", pageSize=100)
papers = response.get("resultList", {}).get("result", [])

# Convert to DataFrame
df = to_dataframe(papers)
print(df.columns)
# Output: ['id', 'source', 'title', 'authorString', 'journalTitle',
#          'pubYear', 'pubType', 'isOpenAccess', 'citedByCount', ...]
```

### Publication Year Distribution

Analyze how publications are distributed across years:

```python
from pyeuropepmc import publication_year_distribution

# Get year distribution as pandas Series
year_dist = publication_year_distribution(papers)
print(year_dist)
# Output:
# 2018    5
# 2019    12
# 2020    23
# 2021    18
# 2022    15
# dtype: int64
```

### Citation Statistics

Calculate comprehensive citation statistics:

```python
from pyeuropepmc import citation_statistics

stats = citation_statistics(papers)
print(f"Mean citations: {stats['mean_citations']:.2f}")
print(f"Median citations: {stats['median_citations']:.0f}")
print(f"Papers with citations: {stats['papers_with_citations']}")
print(f"Citation distribution:")
for percentile, value in stats['citation_distribution'].items():
    print(f"  {percentile}: {value:.1f}")
```

**Output includes:**
- `total_papers`: Total number of papers
- `mean_citations`: Average citations per paper
- `median_citations`: Median citations
- `std_citations`: Standard deviation
- `min_citations` / `max_citations`: Range
- `total_citations`: Sum of all citations
- `papers_with_citations` / `papers_without_citations`: Citation status counts
- `citation_distribution`: Percentiles (25th, 50th, 75th, 90th, 95th)

### Duplicate Detection

Detect duplicate papers based on various criteria:

```python
from pyeuropepmc import detect_duplicates, remove_duplicates

# Detect duplicates by title
duplicates = detect_duplicates(papers, method="title")
print(f"Found {len(duplicates)} sets of duplicates")

# Methods: "title", "doi", "pmid", "pmcid"
doi_duplicates = detect_duplicates(papers, method="doi")

# Remove duplicates, keeping most cited version
unique_df = remove_duplicates(papers, method="title", keep="most_cited")
# Options for keep: "first", "last", "most_cited"
```

### Quality Metrics

Assess paper quality based on various criteria:

```python
from pyeuropepmc import quality_metrics

metrics = quality_metrics(papers)
print(f"Open access: {metrics['open_access_percentage']:.1f}%")
print(f"With abstract: {metrics['with_abstract_percentage']:.1f}%")
print(f"With DOI: {metrics['with_doi_percentage']:.1f}%")
print(f"In PMC: {metrics['in_pmc_percentage']:.1f}%")
print(f"With PDF: {metrics['with_pdf_percentage']:.1f}%")
print(f"Peer reviewed (est.): {metrics['peer_reviewed_percentage']:.1f}%")
```

**Quality indicators:**
- Open access availability
- Abstract presence
- DOI assignment
- PMC inclusion
- PDF availability
- Peer review status (estimated from publication type)

### Publication Type Distribution

Analyze distribution of publication types:

```python
from pyeuropepmc import publication_type_distribution

pub_types = publication_type_distribution(papers)
print(pub_types.head(10))
# Output:
# Journal Article      45
# Review              12
# Clinical Trial       8
# Case Reports         5
# ...
```

### Journal Distribution

Identify top journals:

```python
from pyeuropepmc import journal_distribution

journals = journal_distribution(papers, top_n=15)
print(journals)
# Output:
# Nature                    23
# Science                   18
# Cell                      15
# ...
```

## Visualization Module

### Publication Year Plot

Create a bar chart of publications by year:

```python
from pyeuropepmc import plot_publication_years

fig = plot_publication_years(
    papers,
    title="Publications by Year",
    save_path="pub_years.png"  # Optional: save to file
)
```

### Citation Distribution Plot

Visualize citation distribution with histogram:

```python
from pyeuropepmc import plot_citation_distribution

fig = plot_citation_distribution(
    papers,
    title="Citation Distribution",
    log_scale=True,  # Optional: use log scale
    save_path="citations.png"
)
```

### Quality Metrics Plot

Display quality metrics as horizontal bar chart:

```python
from pyeuropepmc import plot_quality_metrics

fig = plot_quality_metrics(
    papers,
    title="Paper Quality Metrics",
    save_path="quality.png"
)
```

### Publication Type Plot

Show distribution of publication types:

```python
from pyeuropepmc import plot_publication_types

fig = plot_publication_types(
    papers,
    title="Publication Type Distribution",
    top_n=10,  # Show top 10 types
    save_path="pub_types.png"
)
```

### Journal Plot

Display top journals:

```python
from pyeuropepmc import plot_journals

fig = plot_journals(
    papers,
    title="Top Journals",
    top_n=15,
    save_path="journals.png"
)
```

### Trend Analysis

Create multi-panel plot showing publication and citation trends:

```python
from pyeuropepmc import plot_trend_analysis

fig = plot_trend_analysis(
    papers,
    title="Publication and Citation Trends",
    save_path="trends.png"
)
```

This creates a figure with two panels:
- Left: Publication count over time
- Right: Average citations per paper over time (mean and median)

### Summary Dashboard

Create a comprehensive dashboard with all visualizations:

```python
from pyeuropepmc import create_summary_dashboard

fig = create_summary_dashboard(
    papers,
    title="Literature Analysis Dashboard",
    figsize=(16, 10),
    save_path="dashboard.png"
)
```

The dashboard includes:
- Publication year trend (line plot)
- Citation distribution (histogram)
- Quality metrics (bar chart)
- Top publication types (bar chart)
- Top journals (bar chart)
- Summary statistics (text box)

## Complete Example

Here's a complete example combining analytics and visualization:

```python
from pyeuropepmc import (
    SearchClient,
    to_dataframe,
    citation_statistics,
    quality_metrics,
    remove_duplicates,
    plot_publication_years,
    plot_citation_distribution,
    create_summary_dashboard,
)

# Search for papers
client = SearchClient()
response = client.search("machine learning healthcare", pageSize=100)
papers = response.get("resultList", {}).get("result", [])

# Convert to DataFrame
df = to_dataframe(papers)
print(f"Retrieved {len(df)} papers")

# Remove duplicates
df = remove_duplicates(df, method="title", keep="most_cited")
print(f"After deduplication: {len(df)} papers")

# Get statistics
cite_stats = citation_statistics(df)
print(f"Mean citations: {cite_stats['mean_citations']:.2f}")

metrics = quality_metrics(df)
print(f"Open access: {metrics['open_access_percentage']:.1f}%")

# Create visualizations
plot_publication_years(df, save_path="years.png")
plot_citation_distribution(df, save_path="citations.png")
create_summary_dashboard(df, save_path="dashboard.png")

print("Analysis complete!")
```

## Working with DataFrames

Once converted to a DataFrame, you can use all pandas functionality:

```python
# Filter highly cited papers
highly_cited = df[df['citedByCount'] > df['citedByCount'].quantile(0.75)]

# Filter recent open access papers
recent_oa = df[(df['pubYear'] >= '2020') & (df['isOpenAccess'] == 'Y')]

# Group by year and calculate statistics
yearly_stats = df.groupby('pubYear').agg({
    'citedByCount': ['mean', 'median', 'count'],
    'isOpenAccess': lambda x: (x == 'Y').sum()
})

# Export to various formats
df.to_csv('results.csv', index=False)
df.to_excel('results.xlsx', index=False)
df.to_json('results.json', orient='records')
```

## API Reference

### Analytics Functions

- `to_dataframe(papers)` - Convert papers to DataFrame
- `publication_year_distribution(papers)` - Get year distribution
- `citation_statistics(papers)` - Calculate citation statistics
- `detect_duplicates(papers, method)` - Detect duplicate papers
- `remove_duplicates(papers, method, keep)` - Remove duplicates
- `quality_metrics(papers)` - Calculate quality metrics
- `publication_type_distribution(papers)` - Get publication type distribution
- `journal_distribution(papers, top_n)` - Get journal distribution

### Visualization Functions

- `plot_publication_years(papers, title, figsize, save_path)` - Plot year distribution
- `plot_citation_distribution(papers, title, figsize, log_scale, save_path)` - Plot citations
- `plot_quality_metrics(papers, title, figsize, save_path)` - Plot quality metrics
- `plot_publication_types(papers, title, top_n, figsize, save_path)` - Plot publication types
- `plot_journals(papers, title, top_n, figsize, save_path)` - Plot journals
- `plot_trend_analysis(papers, title, figsize, save_path)` - Plot trends
- `create_summary_dashboard(papers, title, figsize, save_path)` - Create dashboard

All functions accept either a list of papers (from API) or a pandas DataFrame.

## Best Practices

1. **Deduplication**: Always check for and remove duplicates before analysis
2. **Data Quality**: Use quality metrics to assess result reliability
3. **Visualization**: Save plots with high DPI (300) for publications
4. **DataFrame Export**: Export processed DataFrames for reproducibility
5. **Large Datasets**: For large result sets, use pagination and batch processing

## Examples

See the [analytics demo notebook](../../examples/analytics_demo.ipynb) for a comprehensive walkthrough of all features.

## See Also

- [Search Client Documentation](./search-client.md)
- [Filtering Documentation](./filtering.md)
- [Examples](../examples/)
