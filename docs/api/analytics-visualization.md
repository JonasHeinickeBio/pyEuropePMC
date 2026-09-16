# Analytics and visualization

The analytics functions summarise Europe PMC search results: publication years, citations, duplicates, data quality, publication types, journals, authors and affiliations. The visualization functions draw these summaries with matplotlib and seaborn. This page lists the functions with their parameters and return values.

## Installation

| Extra | Installs | Needed for |
|---|---|---|
| `pyeuropepmc[analytics]` | numpy, pandas | The statistics functions |
| `pyeuropepmc[visualization]` | matplotlib, numpy, pandas, seaborn | The `plot_*` functions and `create_summary_dashboard` |
| `pyeuropepmc[export]` | pandas, tabulate, xlsxwriter | `DataFrame.to_excel()` in [Working with DataFrames](#working-with-dataframes) |

```bash
pip install "pyeuropepmc[visualization]"
```

The functions are imported lazily, so `import pyeuropepmc` works without these extras. A function whose dependencies are missing raises `ModuleNotFoundError` when you use it.

## Input data

Every function takes the result records of a Europe PMC search, `response["resultList"]["result"]`. All functions except `to_dataframe()` also accept the DataFrame that `to_dataframe()` returns.

Search with `resultType="core"` when you need abstracts, affiliations, MeSH terms, grants or publisher names. `lite` results do not contain these fields, so the corresponding columns stay empty and the analyses that use them report nothing.

## Converting to a DataFrame

```python
from pyeuropepmc import SearchClient, to_dataframe

with SearchClient() as client:
    response = client.search("CRISPR gene editing", pageSize=100, resultType="core")

papers = response["resultList"]["result"]
df = to_dataframe(papers)
print(df.columns.tolist())
```

`to_dataframe(papers: list[dict]) -> pandas.DataFrame` returns one row per paper, or an empty DataFrame for an empty list. Passing the response dict or a DataFrame raises an error.

| Column | Type | Content |
|---|---|---|
| `id`, `source`, `title`, `authorString`, `doi`, `pmid`, `pmcid`, `language`, `pageInfo`, `firstPublicationDate` | `str` | The field of the same name |
| `journalTitle` | `str` | `journalTitle`, or `journalInfo.journal.title` in core results |
| `pubYear` | `str` | `pubYear`, not converted to a number |
| `pubType` | `str` | Publication types from `pubType` and `pubTypeList` |
| `isOpenAccess` | `str` | `"Y"` or `"N"` |
| `citedByCount` | `int` | `citedByCount` (0 when missing) |
| `abstractText`, `affiliation`, `publisher` | `str` | Core results only |
| `meshTerms`, `grants` | `str` | Values joined with `"; "`, core results only |
| `hasAbstract`, `hasPDF`, `inPMC`, `inEPMC`, `hasReferences`, `hasTextMinedTerms`, `hasDbCrossReferences` | `bool` | Flags derived from the record |

## Statistics

### Publication years

```python
from pyeuropepmc import publication_year_distribution

years = publication_year_distribution(papers)
print(years)
```

`publication_year_distribution(papers)` returns a `pandas.Series` with the year (`int`) as index and the number of papers as values, sorted by year.

### Citations

```python
from pyeuropepmc import citation_statistics

stats = citation_statistics(papers)
print(f"Mean citations: {stats['mean_citations']:.2f}")
print(f"Median citations: {stats['median_citations']:.0f}")
print(f"Papers with citations: {stats['papers_with_citations']}")
for percentile, value in stats["citation_distribution"].items():
    print(f"  {percentile}: {value:.1f}")
```

`citation_statistics(papers)` returns a `dict`:

| Key | Content |
|---|---|
| `total_papers` | Number of papers |
| `mean_citations`, `median_citations`, `std_citations` | Mean, median and standard deviation of `citedByCount` |
| `min_citations`, `max_citations`, `total_citations` | Minimum, maximum and sum |
| `papers_with_citations`, `papers_without_citations` | Papers with at least one citation, and with none |
| `citation_distribution` | `{"25th_percentile": ..., "50th_percentile": ..., "75th_percentile": ..., "90th_percentile": ..., "95th_percentile": ...}` |

### Duplicates

```python
from pyeuropepmc import detect_duplicates, remove_duplicates

groups = detect_duplicates(papers, method="doi")
print(f"Found {len(groups)} groups of duplicates")

unique_df = remove_duplicates(papers, method="title", keep="most_cited")
```

| Function | Parameters | Returns |
|---|---|---|
| `detect_duplicates(papers, method="title")` | `method`: `"title"` (case-insensitive exact match), `"doi"`, `"pmid"` or `"pmcid"`; other values raise `ValueError` | `list[list[int]]`: the row positions of each group of duplicates |
| `remove_duplicates(papers, method="title", keep="first")` | `method` as above; `keep`: `"first"`, `"last"` or `"most_cited"` | `pandas.DataFrame` without the duplicates |

### Data quality

```python
from pyeuropepmc import quality_metrics

metrics = quality_metrics(papers)
print(f"Open access: {metrics['open_access_percentage']:.1f}%")
print(f"With abstract: {metrics['with_abstract_percentage']:.1f}%")
print(f"With DOI: {metrics['with_doi_percentage']:.1f}%")
print(f"In PMC: {metrics['in_pmc_percentage']:.1f}%")
print(f"With PDF: {metrics['with_pdf_percentage']:.1f}%")
print(f"Peer reviewed (estimate): {metrics['peer_reviewed_percentage']:.1f}%")
```

`quality_metrics(papers)` returns a `dict` with `total_papers` and, for each indicator, a count and a percentage: `open_access_count`/`open_access_percentage`, `with_abstract_count`/`with_abstract_percentage`, `with_doi_count`/`with_doi_percentage`, `in_pmc_count`/`in_pmc_percentage`, `with_pdf_count`/`with_pdf_percentage`, and `peer_reviewed_estimate`/`peer_reviewed_percentage`. The peer-review figure is estimated from the publication types.

### Publication types and journals

```python
from pyeuropepmc import journal_distribution, publication_type_distribution

print(publication_type_distribution(papers).head(10))
print(journal_distribution(papers, top_n=15))
```

| Function | Returns |
|---|---|
| `publication_type_distribution(papers)` | `pandas.Series`: publication type to number of papers. A paper with several types is counted once for each type. |
| `journal_distribution(papers, top_n=10)` | `pandas.Series`: the `top_n` journals and their number of papers |

### Authors and affiliations

```python
from pyeuropepmc import author_statistics, geographic_analysis

authors = author_statistics(papers, top_n=10)
print(f"Unique authors: {authors['total_authors']}")
print(authors["top_authors"])

geography = geographic_analysis(papers, top_n=10)
print(geography["top_countries"])
```

| Function | Returns (dict keys) |
|---|---|
| `author_statistics(papers, top_n=10)` | `total_authors`, `total_author_mentions`, `avg_authors_per_paper`, `max_authors_per_paper`, `min_authors_per_paper`, `single_author_papers`, `multi_author_papers`, `top_authors` (`pandas.Series`), `author_collaboration_patterns` |
| `geographic_analysis(papers, top_n=10)` | `total_papers`, `papers_with_affiliation`, `country_distribution`, `institution_distribution`, `top_countries`, `top_institutions`, `international_collaboration_rate`. Needs the `affiliation` field of core results. |

### Further analyses

These functions are exported from `pyeuropepmc.features.analytics`, not from `pyeuropepmc`:

| Function | Returns (dict keys) |
|---|---|
| `access_distribution(papers, top_n_licenses=10)` | `total_papers`, `open_access_count`/`_percentage`, `closed_access_count`/`_percentage`, `has_fulltext_api_count`/`_percentage`, `no_fulltext_api_count`/`_percentage`, `license_distribution`, `license_top_n`, `fulltext_availability_breakdown` |
| `citation_by_access_type(papers)` | `open_access`, `closed_access` (statistics per group), `effect_size` (Cohen's d), `is_significant`, `citation_impact_score` |
| `disease_comparison_trends(papers, disease_terms)` | One entry per key of `disease_terms` (a dict of name to list of search terms), plus `comparison` |
| `author_collaboration_network(papers, top_n=10)` | `network_stats`, `top_authors`, `collaboration_matrix`, `centrality_metrics`, `core_researchers`, `research_groups` |
| `funding_source_analysis(papers, top_n=10)` | `total_funded_papers`, `funding_source_distribution`, `top_funders`, `concentration_index`, `multi_funder_papers`, `funding_by_year` |

```python
from pyeuropepmc.features.analytics import access_distribution, funding_source_analysis

access = access_distribution(papers)
print(f"Open access: {access['open_access_percentage']:.1f}%")

funding = funding_source_analysis(papers, top_n=5)
print(funding["top_funders"])
```

## Visualization

Every plotting function returns a `matplotlib.figure.Figure`. Pass `save_path` to also write the figure to an image file.

| Function (defaults) | Figure |
|---|---|
| `plot_publication_years(papers, title="Publications by Year", figsize=(12, 6), save_path=None)` | Bar chart of papers per year |
| `plot_citation_distribution(papers, title="Citation Distribution", figsize=(12, 6), log_scale=False, save_path=None)` | Histogram of citation counts |
| `plot_quality_metrics(papers, title="Paper Quality Metrics", figsize=(10, 6), save_path=None)` | Bars for Open Access, With Abstract, With DOI, In PMC, With PDF and Peer Reviewed |
| `plot_publication_types(papers, title="Publication Type Distribution", top_n=10, figsize=(10, 6), save_path=None)` | Bar chart of the most common publication types |
| `plot_journals(papers, title="Top Journals", top_n=10, figsize=(10, 6), save_path=None)` | Bar chart of the most common journals |
| `plot_trend_analysis(papers, title="Publication and Citation Trends", figsize=(14, 6), save_path=None)` | Two panels: publications over time, and citations per paper over time |
| `create_summary_dashboard(papers, title="Literature Analysis Dashboard", figsize=(16, 10), save_path=None)` | Six panels: publications over time, citation distribution, quality metrics, top publication types, top journals, and a summary panel |

`pyeuropepmc.features.analytics` also provides `plot_access_distribution`, `plot_license_distribution` (`top_n=10`), `plot_fulltext_availability`, `plot_citation_by_access_type`, `plot_disease_comparison_trends` (requires `disease_terms`), `plot_author_collaboration_network` (`top_n=20`) and `plot_funding_sources` (`top_n=10`). They take `title`, `figsize` and `save_path` in the same way.

```python
from pyeuropepmc import (
    create_summary_dashboard,
    plot_citation_distribution,
    plot_journals,
    plot_publication_types,
    plot_publication_years,
    plot_quality_metrics,
    plot_trend_analysis,
)

plot_publication_years(papers, save_path="pub_years.png")
plot_citation_distribution(papers, log_scale=True, save_path="citations.png")
plot_quality_metrics(papers, save_path="quality.png")
plot_publication_types(papers, top_n=10, save_path="pub_types.png")
plot_journals(papers, top_n=15, save_path="journals.png")
plot_trend_analysis(papers, save_path="trends.png")
fig = create_summary_dashboard(papers, save_path="dashboard.png")
```

## Complete example

```python
from pyeuropepmc import (
    SearchClient,
    citation_statistics,
    create_summary_dashboard,
    plot_citation_distribution,
    plot_publication_years,
    quality_metrics,
    remove_duplicates,
    to_dataframe,
)

with SearchClient() as client:
    response = client.search("machine learning healthcare", pageSize=100, resultType="core")

df = to_dataframe(response["resultList"]["result"])
print(f"Retrieved {len(df)} papers")

df = remove_duplicates(df, method="title", keep="most_cited")
print(f"After deduplication: {len(df)} papers")

print(f"Mean citations: {citation_statistics(df)['mean_citations']:.2f}")
print(f"Open access: {quality_metrics(df)['open_access_percentage']:.1f}%")

plot_publication_years(df, save_path="years.png")
plot_citation_distribution(df, save_path="citations.png")
create_summary_dashboard(df, save_path="dashboard.png")
```

## Working with DataFrames

The DataFrame from `to_dataframe()` works with all pandas operations. `pubYear` is a string, so convert it before comparing years:

```python
import pandas as pd

highly_cited = df[df["citedByCount"] > df["citedByCount"].quantile(0.75)]

years = pd.to_numeric(df["pubYear"], errors="coerce")
recent_open_access = df[(years >= 2020) & (df["isOpenAccess"] == "Y")]

yearly = df.groupby("pubYear").agg(
    papers=("id", "count"),
    mean_citations=("citedByCount", "mean"),
)

df.to_csv("papers.csv", index=False)
df.to_json("papers.json", orient="records")
df.to_excel("papers.xlsx", index=False)  # needs xlsxwriter or openpyxl
```

## See also

- [SearchClient](search-client.md)
- [Analytics skill card](../guides/skills/analytics.md)
- [Analytics example notebook](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/examples/07-advanced-analytics/04-analytics-demo.ipynb)
