# Examples

This section contains practical examples of using PyEuropePMC for various tasks.

## Table of Contents

- [Basic Examples](#basic-examples)
- [Query Builder Examples](#query-builder-examples)
- [Search Examples](#search-examples)
- [Data Processing Examples](#data-processing-examples)
- [Advanced Use Cases](#advanced-use-cases)

## Query Builder Examples

### Basic Query Building

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder()

# Simple keyword search
query1 = qb.keyword("machine learning").build()
print(query1)  # "machine learning"

# Field-specific search
query2 = qb.field("author", "Smith J").build()
print(query2)  # "AUTH:Smith J"

# Boolean operators
query3 = qb.keyword("cancer").and_().keyword("therapy").build()
print(query3)  # "cancer AND therapy"
```

### Advanced Query Patterns

```python
# Complex query with multiple conditions
complex_query = (qb
    .keyword("CRISPR", field="title")
    .and_()
    .keyword("gene editing")
    .and_()
    .date_range(start_year=2018, end_year=2023)
    .and_()
    .citation_count(min_count=50)
    .build())

print(complex_query)
# "(TITLE:CRISPR) AND gene editing AND (PUB_YEAR:[2018 TO 2023]) AND (CITED:[50 TO *])"
```

### Citation and Date Filtering

```python
# High-impact papers from specific period
high_impact_query = (qb
    .keyword("artificial intelligence")
    .and_()
    .citation_count(min_count=100, max_count=1000)
    .and_()
    .date_range(start_year=2020)
    .build())

# Recent papers with open access
recent_oa_query = (qb
    .keyword("COVID-19")
    .and_()
    .field("open_access", True)
    .and_()
    .date_range(start_year=2020)
    .build())
```

### OR Logic and Grouping

```python
# OR logic for synonyms
synonym_query = (qb
    .keyword("machine learning")
    .or_()
    .keyword("artificial intelligence")
    .or_()
    .keyword("deep learning")
    .build())

# Grouped sub-queries
diseases = QueryBuilder().keyword("cancer").or_().keyword("tumor").or_().keyword("neoplasm")
therapies = QueryBuilder().keyword("therapy").or_().keyword("treatment").or_().keyword("intervention")

combined_query = (qb
    .group(diseases)
    .and_()
    .group(therapies)
    .and_()
    .field("pub_year", 2023)
    .build())
```

### Field-Specific Searches

```python
# Author and affiliation searches
author_query = qb.field("author", "John Smith").build()
affiliation_query = qb.field("affiliation", "Harvard University").build()

# Journal and publication type
journal_query = qb.field("journal", "Nature").build()
review_query = qb.field("pub_type", "review").build()

# MeSH terms and keywords
mesh_query = qb.field("mesh", "Gene Therapy").build()
keyword_query = qb.field("keyword", "CRISPR").build()
```

### PMC and DOI Searches

```python
# PMC ID search (automatically adds PMC prefix)
pmc_query = qb.pmcid("1234567").build()  # "PMCID:PMC1234567"

# DOI search
doi_query = qb.field("doi", "10.1038/nature12345").build()

# Accession type search (automatically lowercased)
accession_query = qb.accession_type("PDB").build()  # "ACCESSION_TYPE:pdb"
```

### Citation Network Queries

```python
# Find papers that cite a specific article
citing_query = qb.cites("8521067", source="med").build()

# Find highly cited papers
highly_cited = (qb
    .keyword("neural networks")
    .and_()
    .citation_count(min_count=500)
    .build())
```

### Query Persistence and Translation

```python
# Save query to file
qb.save("my_search.json",
        platform="pubmed",
        authors=[{"name": "Researcher Name", "ORCID": "0000-0000-0000-0001"}])

# Load query from file
loaded_qb = QueryBuilder.from_file("my_search.json")

# Translate to different platforms
pubmed_query = loaded_qb.build()
wos_query = loaded_qb.translate("wos")  # Web of Science syntax
ebsco_query = loaded_qb.translate("ebsco")  # EBSCO syntax
```

### Systematic Review Integration

```python
from pyeuropepmc.utils.search_logging import start_search

# Start systematic review log
log = start_search("AI in Healthcare Review", executed_by="Dr. Smith")

# Build comprehensive search
comprehensive_search = (qb
    .keyword("artificial intelligence")
    .and_()
    .keyword("healthcare")
    .and_()
    .date_range(start_year=2018)
    .and_()
    .field("open_access", True)
    .build())

# Log the search for systematic review
qb.log_to_search(
    search_log=log,
    database="Europe PMC",
    filters={
        "date_range": "2018+",
        "open_access": True,
        "keywords": ["artificial intelligence", "healthcare"]
    },
    results_returned=250,
    notes="Comprehensive search for AI in healthcare literature"
)

# Save the review log
log.save("systematic_review_searches.json")
```

### Query Evaluation and Optimization

```python
# Evaluate search effectiveness
test_records = {
    "r1": {"title": "AI in cancer diagnosis", "colrev_status": "rev_included"},
    "r2": {"title": "Machine learning for drug discovery", "colrev_status": "rev_included"},
    "r3": {"title": "Weather prediction models", "colrev_status": "rev_excluded"}
}

evaluation = qb.evaluate(test_records)
print(f"Recall: {evaluation['recall']:.2f}")
print(f"Precision: {evaluation['precision']:.2f}")
print(f"F1 Score: {evaluation['f1_score']:.2f}")
```

### Custom Field Transformations

```python
# Use transform parameter for custom value processing
custom_query = (qb
    .field("pmcid", "1234567", transform=lambda x: f"PMC{x}" if not str(x).startswith("PMC") else str(x))
    .and_()
    .field("accession_type", "GENBANK", transform=str.lower)
    .build())

print(custom_query)  # "PMCID:PMC1234567 AND ACCESSION_TYPE:genbank"
```

### Fetching Article by ID

```python
# Fetch by PubMed ID
article = client.fetch_by_id(pmid="12345678")
print(f"Title: {article.title}")
print(f"Abstract: {article.abstract}")

# Fetch by PMC ID
article = client.fetch_by_id(pmcid="PMC1234567")

# Fetch by DOI
article = client.fetch_by_id(doi="10.1038/nature12345")
```

## Search Examples

### Advanced Search Queries

```python
# Search with Boolean operators
results = client.search("(cancer OR tumor) AND therapy", limit=20)

# Search in specific fields
results = client.search("AUTH:\"Smith J\" AND JOURNAL:\"Nature\"")

# Search with date range
results = client.search("CRISPR AND PUB_YEAR:[2020 TO 2023]")

# Search by MeSH terms
results = client.search("MESH:\"Gene Therapy\"")
```

### Filtering and Sorting

```python
# Filter by source
results = client.search(
    "machine learning",
    source="PMC",  # Only PMC articles
    limit=15
)

# Sort by date (newest first)
results = client.search(
    "artificial intelligence",
    sort="date",
    limit=10
)

# Sort by citation count
results = client.search(
    "deep learning",
    sort="cited",
    limit=5
)
```

### Pagination

```python
# Get first page
page1 = client.search("cancer", limit=25, offset=0)

# Get second page
page2 = client.search("cancer", limit=25, offset=25)

# Iterate through all results
def get_all_results(query, batch_size=100):
    offset = 0
    all_results = []

    while True:
        results = client.search(
            query,
            limit=batch_size,
            offset=offset
        )

        if not results:
            break

        all_results.extend(results)
        offset += batch_size

        # Optional: add delay to respect rate limits
        time.sleep(1)

    return all_results

# Get all articles about "bioinformatics"
all_articles = get_all_results("bioinformatics")
print(f"Found {len(all_articles)} articles")
```

## Data Processing Examples

### Extracting Author Networks

```python
import collections
from itertools import combinations

def build_author_network(articles):
    """Build co-authorship network from articles."""
    collaborations = collections.defaultdict(int)

    for article in articles:
        if len(article.authors) > 1:
            # Create pairs of co-authors
            for author1, author2 in combinations(article.authors, 2):
                pair = tuple(sorted([author1, author2]))
                collaborations[pair] += 1

    return collaborations

# Search for articles in a specific field
articles = client.search("computational biology", limit=100)

# Build collaboration network
network = build_author_network(articles)

# Find most frequent collaborations
top_collaborations = sorted(
    network.items(),
    key=lambda x: x[1],
    reverse=True
)[:10]

print("Top collaborations:")
for (author1, author2), count in top_collaborations:
    print(f"{author1} <-> {author2}: {count} papers")
```

### Journal Impact Analysis

```python
import collections

def analyze_journals(articles):
    """Analyze journal publication patterns."""
    journal_stats = collections.defaultdict(lambda: {
        'count': 0,
        'years': set(),
        'articles': []
    })

    for article in articles:
        journal = article.journal
        journal_stats[journal]['count'] += 1
        journal_stats[journal]['years'].add(article.pub_year)
        journal_stats[journal]['articles'].append(article)

    return journal_stats

# Analyze AI research journals
ai_articles = client.search("artificial intelligence", limit=200)
journal_analysis = analyze_journals(ai_articles)

# Sort by publication count
sorted_journals = sorted(
    journal_analysis.items(),
    key=lambda x: x[1]['count'],
    reverse=True
)

print("Top journals for AI research:")
for journal, stats in sorted_journals[:10]:
    year_range = f"{min(stats['years'])}-{max(stats['years'])}"
    print(f"{journal}: {stats['count']} articles ({year_range})")
```

### Citation Analysis

```python
def analyze_citations(pmid_list):
    """Analyze citation patterns for a list of articles."""
    citation_data = {}

    for pmid in pmid_list:
        try:
            # Get citations for this article
            citations = client.fetch_citations(pmid=pmid, limit=100)

            # Get references from this article
            references = client.fetch_references(pmid=pmid, limit=100)

            citation_data[pmid] = {
                'cited_by_count': len(citations),
                'references_count': len(references),
                'citations': citations,
                'references': references
            }

        except Exception as e:
            print(f"Error processing {pmid}: {e}")
            continue

    return citation_data

# Example: Analyze top papers in a field
top_papers = client.search("machine learning", sort="cited", limit=10)
pmid_list = [article.pmid for article in top_papers if article.pmid]

citation_analysis = analyze_citations(pmid_list)

# Print citation statistics
for pmid, data in citation_analysis.items():
    print(f"PMID {pmid}:")
    print(f"  Cited by: {data['cited_by_count']} articles")
    print(f"  References: {data['references_count']} articles")
    print()
```

## Advanced Use Cases

### Research Trend Analysis

```python
import matplotlib.pyplot as plt
from collections import defaultdict

def analyze_research_trends(keywords, years):
    """Analyze research trends over time for given keywords."""
    trend_data = defaultdict(lambda: defaultdict(int))

    for keyword in keywords:
        for year in years:
            query = f"{keyword} AND PUB_YEAR:{year}"
            try:
                results = client.search(query, limit=1000)
                trend_data[keyword][year] = len(results)
            except Exception as e:
                print(f"Error for {keyword} in {year}: {e}")
                trend_data[keyword][year] = 0

    return trend_data

# Analyze AI/ML trends
keywords = ["artificial intelligence", "machine learning", "deep learning"]
years = range(2015, 2024)

trends = analyze_research_trends(keywords, years)

# Plot trends
plt.figure(figsize=(12, 6))
for keyword in keywords:
    years_list = sorted(trends[keyword].keys())
    counts = [trends[keyword][year] for year in years_list]
    plt.plot(years_list, counts, marker='o', label=keyword)

plt.xlabel("Year")
plt.ylabel("Number of Publications")
plt.title("AI/ML Research Trends")
plt.legend()
plt.grid(True)
plt.show()
```

### Multi-source Data Integration

```python
def comprehensive_search(query, max_results=1000):
    """Search across multiple Europe PMC sources."""
    sources = ["MED", "PMC", "AGR", "CBA"]
    all_results = []

    for source in sources:
        try:
            results = client.search(
                query,
                source=source,
                limit=min(max_results // len(sources), 250)
            )

            # Add source information to each result
            for article in results:
                article.source = source

            all_results.extend(results)

        except Exception as e:
            print(f"Error searching {source}: {e}")
            continue

    return all_results

# Search across all sources
comprehensive_results = comprehensive_search("COVID-19 treatment")

# Analyze by source
source_counts = {}
for article in comprehensive_results:
    source = getattr(article, 'source', 'Unknown')
    source_counts[source] = source_counts.get(source, 0) + 1

print("Results by source:")
for source, count in source_counts.items():
    print(f"{source}: {count} articles")
```

### Export to Different Formats

```python
import json
import csv
import pandas as pd

def export_results(articles, format='json', filename=None):
    """Export search results to various formats."""

    if format == 'json':
        data = []
        for article in articles:
            data.append({
                'title': article.title,
                'authors': article.authors,
                'journal': article.journal,
                'year': article.pub_year,
                'pmid': article.pmid,
                'doi': article.doi,
                'abstract': article.abstract
            })

        if filename:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        return data

    elif format == 'csv':
        if filename:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Title', 'Authors', 'Journal', 'Year', 'PMID', 'DOI'])

                for article in articles:
                    writer.writerow([
                        article.title,
                        '; '.join(article.authors) if article.authors else '',
                        article.journal,
                        article.pub_year,
                        article.pmid,
                        article.doi
                    ])

    elif format == 'dataframe':
        data = []
        for article in articles:
            data.append({
                'title': article.title,
                'authors': '; '.join(article.authors) if article.authors else '',
                'journal': article.journal,
                'year': article.pub_year,
                'pmid': article.pmid,
                'doi': article.doi
            })

        return pd.DataFrame(data)

# Example usage
results = client.search("bioinformatics", limit=50)

# Export to JSON
export_results(results, format='json', filename='bioinformatics_articles.json')

# Export to CSV
export_results(results, format='csv', filename='bioinformatics_articles.csv')

# Create DataFrame for analysis
df = export_results(results, format='dataframe')
print(df.head())
```

## Error Handling Examples

```python
from pyeuropepmc import EuropePMC, APIError, RateLimitError

def robust_search(query, max_retries=3):
    """Search with robust error handling."""
    client = EuropePMC()

    for attempt in range(max_retries):
        try:
            results = client.search(query, limit=100)
            return results

        except RateLimitError:
            print(f"Rate limit hit, waiting before retry {attempt + 1}")
            time.sleep(2 ** attempt)  # Exponential backoff

        except APIError as e:
            print(f"API error: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(1)

        except Exception as e:
            print(f"Unexpected error: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(1)

    return []

# Use robust search
try:
    results = robust_search("complex query here")
    print(f"Successfully retrieved {len(results)} articles")
except Exception as e:
    print(f"Failed after all retries: {e}")
```

For more examples, check out the [examples directory](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples) in the repository.
