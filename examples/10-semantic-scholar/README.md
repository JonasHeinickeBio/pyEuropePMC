# Semantic Scholar Demo

This directory contains examples for using the Semantic Scholar enrichment client with pyEuropePMC.

## Files

- `demo_semantic_scholar.py` - Python script demonstrating all enrichment methods
- `semantic_scholar_demo.ipynb` - Jupyter notebook version of the demo
- `test_rate_limit.py` - Test script to measure API rate limits
- `.env` - Environment file with API key (not included in repo)

## Setup

1. Install dependencies:
```bash
pip install pyeuropepmc python-dotenv
```

2. Configure API key (optional but recommended):
```bash
echo "SEMANTIC_SCHOLAR_API_KEY=your_api_key_here" > .env
```

3. Run the demo:
```bash
python3 demo_semantic_scholar.py
```

## Usage

### Basic Enrichment
```python
from pyeuropepmc import SemanticScholarClient
client = SemanticScholarClient()
result = client.enrich(identifier="10.1038/nature12373")
print(result['title'])
```

### Author Enrichment
```python
author = client.enrich_author(author_id="2226359")
print(author['name'], author['paper_count'])
```

### Get Recommendations
```python
recs = client.get_recommendations_for_paper(paper_id="649def34f8be52c8b66281af98ae884c09aef38b")
for paper in recs:
    print(paper['title'])
```

### Test Rate Limits
```bash
python3 test_rate_limit.py
```

## API Key

### Rate Limit Measurements (with API key)
- **Rapid requests**: ~1.69 req/s (20/20 success)
- **With 0.1s delay**: ~1.87 req/s (20/20 success)
- **With 0.5s delay**: ~1.56 req/s (10/10 success)

### Expected vs Actual

| Scenario | Expected | Actual |
|----------|----------|--------|
| Without key | ~1 req/s | ~1.5-1.9 req/s |
| With API key | ~10 req/s | ~1.6-1.9 req/s |

**Note**: Actual rate is lower than documented.

### Get API Key

- **Free (no key)**: 25k requests/month
- **With API key**: 100k requests/month

Get your API key at: https://api.semanticscholar.org/api-key-form
