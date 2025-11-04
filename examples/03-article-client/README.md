# Article Client Examples

**Level**: ⭐⭐ Intermediate
**Examples**: 1 notebook
**Time**: 15-20 minutes

## Overview

The ArticleClient provides fast access to detailed article metadata, citations, references, and supplementary materials. Perfect for citation analysis and article relationship mapping.

## 📓 Examples

### 01-article-basics.ipynb
**Complete article metadata tutorial**

Master article operations:
- Retrieving article details
- Analyzing citations (who cited this?)
- Exploring references (what does this cite?)
- Accessing supplementary files
- Cross-database links
- Error handling

**What you'll build**: An article analysis tool with citation network features

**Key topics**:
- Article identifiers (PMID, PMCID, DOI)
- Citation metrics
- Reference extraction
- Supplementary data access
- Database cross-references

## 🚀 Quick Start

```python
from pyeuropepmc.article import ArticleClient

client = ArticleClient()

# Get article details
article = client.get_article_details("MED", "34308300")
print(f"Title: {article['result']['title']}")

# Get citations (who cited this article?)
citations = client.get_citations("MED", "34308300")
print(f"Citations: {len(citations['citationList']['citation'])}")

# Get references (what this article cites)
references = client.get_references("MED", "34308300")
print(f"References: {len(references['referenceList']['reference'])}")
```

## 🎯 Key Features

### 1. Article Metadata
Get comprehensive article information:
- Title, authors, abstract
- Journal details
- Publication dates
- Identifiers (DOI, PMID, PMCID)
- Keywords and MeSH terms

### 2. Citation Analysis
Understand article impact:
- Papers that cited this work
- Citation counts and trends
- Citation context
- Related articles

### 3. Reference Extraction
Explore cited literature:
- Full reference list
- Structured citation data
- Cross-references
- Bibliography export

### 4. Supplementary Materials
Access additional resources:
- Supplementary files
- Data sets
- Code repositories
- Multimedia content

### 5. Database Links
Connect to external databases:
- UniProt (proteins)
- EMBL (nucleotides)
- PDB (structures)
- ArrayExpress (gene expression)

## 💡 Common Use Cases

### Citation Network Analysis
```python
# Build a citation network
article = client.get_article_details("MED", "34308300")
citations = client.get_citations("MED", "34308300")
references = client.get_references("MED", "34308300")

# Analyze impact
citation_count = len(citations.get('citationList', {}).get('citation', []))
reference_count = len(references.get('referenceList', {}).get('reference', []))
```

### Author Analysis
```python
# Get all papers by an author
article = client.get_article_details("MED", "34308300")
authors = article['result']['authorList']['author']

# Extract author details
for author in authors:
    print(f"{author.get('firstName', '')} {author.get('lastName', '')}")
    print(f"Affiliation: {author.get('affiliation', 'N/A')}")
```

### Journal Metrics
```python
# Get journal information
journal_info = article['result']['journalInfo']
print(f"Journal: {journal_info['journal']['title']}")
print(f"Volume: {journal_info.get('volume', 'N/A')}")
print(f"Issue: {journal_info.get('issue', 'N/A')}")
```

## 📊 Article Identifiers

PyEuropePMC supports multiple identifier types:

| Source | ID Type | Example | Description |
|--------|---------|---------|-------------|
| MED | PMID | 34308300 | PubMed ID |
| PMC | PMCID | PMC8313472 | PubMed Central ID |
| DOI | DOI | 10.1038/s41586-021-03819-2 | Digital Object Identifier |
| AGR | AGR ID | AGR:AGR-Reference-0000853717 | Alliance of Genome Resources |
| CTX | Clinical Trial | NCT04368728 | ClinicalTrials.gov |

**Note**: Use "MED" as source for most PubMed articles.

## 🔍 Advanced Patterns

### Batch Processing
```python
# Process multiple articles
article_ids = ["34308300", "33234567", "32123456"]

for pmid in article_ids:
    try:
        article = client.get_article_details("MED", pmid)
        # Process article...
    except Exception as e:
        print(f"Error processing {pmid}: {e}")
```

### Citation Timeline
```python
# Analyze citation growth over time
citations = client.get_citations("MED", "34308300")

# Group by year
from collections import defaultdict
by_year = defaultdict(int)

for citation in citations.get('citationList', {}).get('citation', []):
    year = citation.get('pubYear', 'Unknown')
    by_year[year] += 1
```

### Related Articles
```python
# Find related articles through citations
article = client.get_article_details("MED", "34308300")
citations = client.get_citations("MED", "34308300")

# Get details of citing articles
for citation in citations['citationList']['citation'][:5]:
    if 'id' in citation:
        citing_article = client.get_article_details(
            citation.get('source', 'MED'),
            citation['id']
        )
```

## 🆘 Troubleshooting

**"Article not found" error?**
- Verify the article ID is correct
- Check the source type (MED, PMC, etc.)
- Some articles may not be in Europe PMC

**No citations returned?**
- Article may be too new
- Article may not be widely cited yet
- Try with PMCID instead of PMID

**Missing supplementary files?**
- Not all articles have supplementary materials
- Check if the article is Open Access
- PMC articles more likely to have supplements

## 📈 Performance Tips

1. **Reuse the client**: Create once, use for multiple requests
2. **Enable caching**: For repeated lookups
3. **Batch requests**: Process multiple articles efficiently
4. **Error handling**: Always wrap in try-except blocks

## 🔗 Resources

- [Europe PMC Article API](https://europepmc.org/RestfulWebService#article)
- [Citation Network Guide](https://europepmc.org/Help#citations)
- [Identifier Types](https://europepmc.org/Help#idTypes)

## 🚀 Next Steps

- **Combine with search**: Use SearchClient to find articles, ArticleClient for details
- **Build networks**: Create citation graphs using citations and references
- **Export data**: Save article metadata for further analysis
