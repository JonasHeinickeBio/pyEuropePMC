# FullTextClient API Reference

The `FullTextClient` provides access to full-text content from Europe PMC articles in various formats (PDF, XML, HTML).

## Important: Europe PMC Endpoint Architecture

Europe PMC has different endpoint architectures for different content types:

### XML Full Text

- **Primary Endpoint**: Direct REST API (`/PMC{id}/fullTextXML`)
- **Fallback Endpoint**: Europe PMC FTP OA bulk archives (`https://europepmc.org/ftp/oa/`)
- **Archive Format**: Gzipped XML files organized by PMC ID ranges (e.g., `PMC1000000_PMC1099999.xml.gz`)
- **Availability Check**: Via HEAD/GET request to REST endpoint
- **Download**:
  1. First tries REST API for individual articles
  2. Falls back to bulk FTP archives when REST API fails
  3. Automatically determines correct archive based on PMC ID
  4. Unpacks gzipped archives and extracts specific article XML
- **Reliability**: High - officially supported with robust fallback mechanism

### PDF Full Text

- **Endpoints**: Multiple fallback endpoints
  1. Render endpoint: `https://europepmc.org/articles/PMC{id}?pdf=render`
  2. Backend service: `https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{id}&blobtype=pdf`
  3. ZIP archive: `https://europepmc.org/pub/databases/pmc/pdf/OA/{dir}/PMC{id}.zip`
- **Availability Check**: Via GET request to render endpoint (checks content-type)
- **Download**: Tries endpoints in order until successful
- **Reliability**: Medium - depends on article availability and server status

### HTML Full Text

- **Endpoint**: Web interface (`https://europepmc.org/article/MED/{medid}#free-full-text`)
- **Availability Check**: Cannot be checked via PMC ID alone (requires MED ID)
- **Download**: Via web scraping (not currently implemented)
- **Reliability**: Low - requires additional metadata and web scraping

## Class Reference

```python
from pyeuropepmc import FullTextClient
```

### Constructor

```python
FullTextClient(rate_limit_delay: float = 1.0)
```

**Parameters:**

- `rate_limit_delay`: Delay between requests to respect API limits

### Methods

#### check_fulltext_availability()

```python
check_fulltext_availability(pmcid: str) -> Dict[str, bool]
```

Check availability of full text formats for a given PMC ID.

**Parameters:**

- `pmcid`: PMC ID (with or without 'PMC' prefix)

**Returns:**

- Dictionary with format availability: `{"pdf": bool, "xml": bool, "html": bool}`

**Note:** HTML always returns `False` as it requires MED ID for checking.

#### download_pdf_by_pmcid()

```python
download_pdf_by_pmcid(pmcid: str, output_path: Optional[Path] = None) -> Optional[Path]
```

Download PDF using multiple fallback endpoints.

**Parameters:**

- `pmcid`: PMC ID (with or without 'PMC' prefix)
- `output_path`: Where to save the PDF (optional)

**Returns:**

- Path to downloaded file if successful, None if failed

**Download Strategy:**

1. Try render endpoint (`?pdf=render`)
2. Try backend service (`ptpmcrender.fcgi`)
3. Try ZIP archive from OA collection

#### download_xml_by_pmcid()

```python
download_xml_by_pmcid(pmcid: str, output_path: Optional[Path] = None) -> Optional[Path]
```

Download XML full text with automatic fallback to bulk FTP archives.

This method first tries the REST API endpoint, and if that fails (404, 403, or network errors),
it automatically falls back to bulk download from Europe PMC FTP OA archives.

**Parameters:**

- `pmcid`: PMC ID (with or without 'PMC' prefix)
- `output_path`: Where to save the XML (optional)

**Returns:**

- Path to downloaded file if successful, None if failed

#### download_xml_by_pmcid_bulk()

```python
download_xml_by_pmcid_bulk(pmcid: str, output_path: Optional[Path] = None) -> Optional[Path]
```

Download XML full text directly from Europe PMC FTP OA bulk archives only.

This method downloads from the Europe PMC FTP OA archives (.xml.gz files) without trying
the REST API first. Useful when you specifically want to use the bulk download method or
when the REST API is unavailable.

**Parameters:**

- `pmcid`: PMC ID (with or without 'PMC' prefix)
- `output_path`: Where to save the XML (optional)

**Returns:**

- Path to downloaded file if successful, None if failed

**Note:** Archives are organized by PMC ID ranges (e.g., PMC1000000_PMC1099999.xml.gz).
The method automatically determines the correct archive and unpacks the gzipped content.

#### get_fulltext_content()

```python
get_fulltext_content(pmcid: str, format_type: str = "xml") -> str
```

Get full text content as string (XML only).

**Parameters:**

- `pmcid`: PMC ID
- `format_type`: Must be "xml" (HTML not supported via PMC ID)

**Returns:**

- Full text content as string

#### download_fulltext_batch()

```python
download_fulltext_batch(
    pmcids: List[str],
    format_type: str = "pdf",
    output_dir: Optional[Path] = None,
    skip_errors: bool = True
) -> Dict[str, Optional[Path]]
```

Batch download multiple articles.

**Parameters:**

- `pmcids`: List of PMC IDs
- `format_type`: "pdf" or "xml"
- `output_dir`: Directory to save files
- `skip_errors`: Continue on individual failures

**Returns:**

- Dictionary mapping PMC IDs to file paths (or None if failed)

## Error Handling

The client raises `FullTextError` for:

- Invalid PMC IDs
- Network failures
- Access restrictions
- File system errors

## Usage Examples

### Basic Usage

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    # Check availability
    availability = client.check_fulltext_availability("3312970")
    print(availability)  # {"pdf": True, "xml": True, "html": False}

    # Download PDF (tries multiple endpoints)
    pdf_path = client.download_pdf_by_pmcid("3312970", "article.pdf")

    # Download XML (via REST API)
    xml_path = client.download_xml_by_pmcid("3312970", "article.xml")
```

### Error Handling Fulltext

```python
from pyeuropepmc import FullTextClient, FullTextError

with FullTextClient() as client:
    try:
        pdf_path = client.download_pdf_by_pmcid("123456")
        if pdf_path:
            print(f"Downloaded: {pdf_path}")
        else:
            print("PDF not available via any endpoint")
    except FullTextError as e:
        print(f"Error: {e}")
```

### Batch Downloads

```python
from pathlib import Path

pmcids = ["3312970", "4123456", "5789012"]

with FullTextClient() as client:
    results = client.download_fulltext_batch(
        pmcids,
        format_type="pdf",
        output_dir=Path("downloads"),
        skip_errors=True
    )

    for pmcid, path in results.items():
        if path:
            print(f"✓ {pmcid}: {path}")
        else:
            print(f"✗ {pmcid}: Download failed")
```

## Limitations and Considerations

1. **PDF Availability**: Not all articles have PDFs available through any endpoint
2. **HTML Content**: Requires MED ID and web scraping (not implemented)
3. **Rate Limiting**: Respect API limits with appropriate delays
4. **Error Tolerance**: Always handle potential failures gracefully
5. **Network Timeouts**: Large files may require longer timeout settings

## Best Practices

1. **Always use context managers** (`with` statement) for proper cleanup
2. **Handle errors gracefully** - not all content is available
3. **Use batch operations** for multiple downloads
4. **Check availability first** for better user feedback
5. **Respect rate limits** to avoid being blocked
