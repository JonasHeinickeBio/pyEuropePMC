# EuropePMCParser API Reference

The `EuropePMCParser` handles parsing and normalization of Europe PMC API responses.

## Class Overview

```python
from pyeuropepmc.processing.search_parser import EuropePMCParser

class EuropePMCParser:
    """Parser for Europe PMC API responses."""
```

## Constructor

### `EuropePMCParser()`

Create a new EuropePMCParser instance.

## Methods

### `parse_search_results(response_data)`

Parse raw search API response into structured data.

**Parameters:**
- `response_data` (dict): Raw API response from search endpoint

**Returns:**
- List of normalized paper dictionaries

**Example:**
```python
from pyeuropepmc.processing.search_parser import EuropePMCParser

parser = EuropePMCParser()
raw_response = client.search("cancer", format="json")
papers = parser.parse_search_results(raw_response)

for paper in papers:
    print(f"Title: {paper.get('title')}")
    print(f"DOI: {paper.get('doi')}")
```

### `normalize_paper_data(paper_dict)`

Normalize a single paper's data structure.

**Parameters:**
- `paper_dict` (dict): Raw paper data from API

**Returns:**
- Normalized paper dictionary

### `extract_authors(paper_dict)`

Extract and normalize author information.

**Parameters:**
- `paper_dict` (dict): Paper data containing author information

**Returns:**
- List of author dictionaries

### `extract_journal_info(paper_dict)`

Extract journal and publication information.

**Parameters:**
- `paper_dict` (dict): Paper data containing journal information

**Returns:**
- Dictionary with journal metadata including 'title', 'volume', and 'issue' keys

## Static Methods

### `normalize_doi(doi_string)`

Normalize DOI format.

**Parameters:**
- `doi_string` (str): Raw DOI string

**Returns:**
- Normalized DOI string

**Example:**
```python
normalized = EuropePMCParser.normalize_doi("HTTPS://DOI.ORG/10.1234/TEST")
print(normalized)  # "10.1234/test"
```

### `parse_date(date_string)`

Parse various date formats into standardized format.

**Parameters:**
- `date_string` (str): Date string from API

**Returns:**
- ISO format date string or None

## Usage Examples

### Parse Search Results

```python
from pyeuropepmc.search import SearchClient
from pyeuropepmc.processing.search_parser import EuropePMCParser

with SearchClient() as client:
    # Get raw response
    response = client.search("machine learning", pageSize=50)

    # Parse results
    parser = EuropePMCParser()
    papers = parser.parse_search_results(response)

    # Process parsed data
    for paper in papers:
        print(f"Title: {paper.get('title')}")
        print(f"Year: {paper.get('pub_year')}")
        print(f"Citations: {paper.get('citedByCount', 0)}")
```

### Manual Data Normalization

```python
# Raw paper data from API
raw_paper = {
    "title": "Example Paper",
    "doi": "HTTPS://DOI.ORG/10.1234/EXAMPLE",
    "pubYear": "2023",
    "authorString": "Smith J, Doe J"
}

parser = EuropePMCParser()
normalized = parser.normalize_paper_data(raw_paper)

print(f"DOI: {normalized.get('doi')}")  # "10.1234/example"
```

### Author Extraction

```python
paper_data = {
    "authorString": "Smith John, Doe Jane, Brown Bob",
    "authorList": {
        "author": [
            {"fullName": "Smith John", "firstName": "John", "lastName": "Smith"},
            {"fullName": "Doe Jane", "firstName": "Jane", "lastName": "Doe"}
        ]
    }
}

authors = parser.extract_authors(paper_data)
for author in authors:
    print(f"Name: {author.get('full_name')}")
    print(f"First: {author.get('first_name')}")
    print(f"Last: {author.get('last_name')}")
```

## Data Structure

### Normalized Paper Dictionary

```python
{
    "pmid": "12345678",
    "pmcid": "PMC1234567",
    "doi": "10.1234/example",
    "title": "Example Paper Title",
    "abstract": "Abstract text...",
    "pub_year": 2023,
    "journal": "Nature",
    "authors": ["Smith J", "Doe J"],
    "citedByCount": 42,
    "isOpenAccess": "Y",
    # ... additional fields
}
```

### Author Dictionary

```python
{
    "full_name": "Smith John",
    "first_name": "John",
    "last_name": "Smith",
    "affiliation": "University of Example",
    "orcid": "0000-0001-2345-6789"
}
```

## Error Handling

The parser is designed to be robust and handle missing or malformed data:

```python
# Safe access patterns
title = paper.get('title', 'No title available')
year = paper.get('pub_year', 'Unknown year')
citations = paper.get('citedByCount', 0)
```

## Performance Notes

- **Memory Efficient**: Processes data in-place where possible
- **Type Coercion**: Automatically converts strings to appropriate types
- **Validation**: Includes basic data validation and cleaning
- **Extensible**: Easy to add new normalization rules

## Related Classes

- [`SearchClient`](../search-client.md) - For retrieving data to parse
- [`FullTextXMLParser`](../parser-quick-reference.md) - For parsing XML content
