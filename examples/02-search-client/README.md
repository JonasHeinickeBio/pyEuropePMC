# Search Client Examples

**Level**: ⭐⭐ Intermediate
**Examples**: 3 files (2 notebooks + 1 script)
**Time**: 20-30 minutes

## Overview

Master the powerful search features of PyEuropePMC. Learn to construct complex queries, optimize performance with caching, and debug with logging.

## 📓 Examples

### 01-search-basics.ipynb
**Comprehensive search tutorial**

Master search techniques:
- Simple keyword searches
- Boolean operators (AND, OR, NOT)
- Field-specific searches
- Date range filtering
- Result pagination
- Sorting and filtering

**What you'll build**: A flexible search tool with advanced filtering

**Key topics**:
- Query syntax and operators
- Pagination strategies
- Format conversion
- Result inspection

### 02-logging-features.ipynb
**Debug and monitor your searches**

Learn debugging techniques:
- Configuring logging levels
- Understanding API calls
- Tracking search progress
- Saving search logs
- Performance monitoring

**What you'll build**: A search tool with comprehensive logging

**Key topics**:
- Python logging integration
- Request/response inspection
- Performance metrics
- Error diagnosis

### 03-caching-demo.py
**Speed up repeated searches**

Optimize performance:
- Enabling cache for SearchClient
- Cache hit/miss monitoring
- Cache expiration strategies
- Performance comparison

**What you'll build**: A cached search system

**Key topics**:
- Cache configuration
- Performance gains
- Memory management
- Cache invalidation

## 🚀 Quick Examples

### Basic Search
```python
from pyeuropepmc.search import SearchClient

with SearchClient() as client:
    results = client.search("machine learning healthcare")
```

### Advanced Query
```python
# Boolean operators and field searches
query = '(cancer OR tumor) AND (treatment OR therapy) AND PUB_YEAR:[2020 TO 2025]'
results = client.search(query, page_size=100)
```

### With Caching
```python
from pyeuropepmc.search import SearchClient

# Enable caching for faster repeated searches
with SearchClient(enable_cache=True, cache_ttl=3600) as client:
    results = client.search("covid-19 vaccine")
```

## 🎯 Learning Path

1. **Start**: `01-search-basics.ipynb` - Master query syntax
2. **Debug**: `02-logging-features.ipynb` - Add logging
3. **Optimize**: `03-caching-demo.py` - Speed up with caching

## 💡 Pro Tips

### Query Construction
- Use field-specific searches: `AUTH:"Smith J" AND JOURNAL:"Nature"`
- Combine with dates: `PUB_YEAR:[2020 TO 2025]`
- Use wildcards: `gene*` matches "gene", "genes", "genetic"

### Performance Optimization
- Enable caching for repeated searches
- Use appropriate page sizes (10-100)
- Implement rate limiting for bulk operations

### Debugging
- Always check `hitCount` vs actual results
- Log queries for reproducibility
- Monitor API response times

## 🔍 Advanced Query Examples

### By Publication Date
```python
query = "CRISPR AND PUB_YEAR:2024"
```

### By Journal
```python
query = 'JOURNAL:"Nature" AND cancer'
```

### By Author
```python
query = 'AUTH:"Smith J" AND keyword'
```

### Complex Boolean
```python
query = '((cancer OR tumor) AND treatment) NOT review'
```

### Date Range
```python
query = 'covid-19 AND PUB_YEAR:[2020 TO 2023]'
```

## 📊 Search Result Fields

Common fields in results:
- `id` - Unique article identifier
- `title` - Article title
- `authorString` - Formatted author list
- `journalTitle` - Journal name
- `pubYear` - Publication year
- `doi` - Digital Object Identifier
- `pmid` / `pmcid` - PubMed identifiers
- `abstractText` - Article abstract

## 🆘 Troubleshooting

**No results returned?**
- Check query syntax
- Verify field names
- Try simpler queries first

**Too many results?**
- Add more specific terms
- Use field-specific searches
- Narrow date ranges

**Slow performance?**
- Enable caching
- Reduce page size
- Use more specific queries

## 🔗 Resources

- [Europe PMC Search Syntax](https://europepmc.org/Help#mostofsearch)
- [Advanced Query Guide](https://europepmc.org/AdvancedSearch)
- [API Documentation](https://europepmc.org/RestfulWebService)
