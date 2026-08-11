# arXiv Integration

Search and retrieve preprints from arXiv.org across all subject areas.

## Basic Usage

```python
from pyeuropepmc.features.search import ArxivClient

with ArxivClient() as client:
    papers = client.search("machine learning", limit=10)
    for paper in papers:
        print(f"{paper.title} ({paper.source_id})")
```

## Searching by Subject

arXiv supports searching by subject category:

```python
papers = client.search(
    query="quantum computing",
    limit=20,
    categories="cs.AI,cs.LG",  # Computer Science categories
)
```

## Sorting

```python
from pyeuropepmc.features.search import ArxivClient

with ArxivClient() as client:
    # By relevance (default)
    papers = client.search("transformer architecture", sort="relevance")

    # By date (newest first)
    papers = client.search("transformer architecture", sort="date")
```

## Get Paper by ID

```python
# By arXiv ID
paper = client.get_paper("2101.12345")

# By DOI
paper = client.get_paper("10.48550/arXiv.2101.12345")
```

## No API Key Needed

arXiv is a free, open API. No registration or API key is required. The client includes a polite 3-second rate limit by default.

## Features

- ✅ Free, no API key required
- ✅ All arXiv subject areas (CS, physics, math, bio, finance, statistics)
- ✅ Atom XML parsing with proper metadata extraction
- ✅ Author name normalization
- ✅ Rate-limited (3s by default)
- ✅ Standardized `LiteratureResult` output
