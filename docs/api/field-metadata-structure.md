# Field Metadata Structure

## Overview

The PyEuropePMC QueryBuilder now uses a structured metadata dictionary (`FIELD_METADATA`) that maps user-friendly field names to their API field names and human-readable descriptions.

## Structure

```python
FIELD_METADATA: dict[str, tuple[str, str]] = {
    "field_name": ("API_NAME", "Human-readable description"),
    ...
}
```

### Example Entries

```python
{
    "title": ("TITLE", "Article or book title"),
    "author": ("AUTH", "Author name (full or abbreviated form)"),
    "auth": ("AUTH", "Author name (API abbreviated form)"),
    "disease": ("DISEASE", "Disease or condition terms (text-mined)"),
    "open_access": ("OPEN_ACCESS", "Open access status (y/n)"),
}
```

## Key Features

### 1. **API Name Mapping**
Each field is mapped to its uppercase API field name (as returned by the Europe PMC API).

### 2. **Field Aliases**
Multiple user-friendly names can map to the same API field:
- `author` and `auth` both map to `AUTH`
- `affiliation` and `aff` both map to `AFF`
- `language` and `lang` both map to `LANG`
- `chemical` and `chem` both map to `CHEM`

### 3. **Human-Readable Descriptions**
Every field includes a description explaining its purpose, making it easier for developers to understand what each field does.

### 4. **Special Cases: Internal Fields**
Most API fields are uppercase (`TITLE`, `ABSTRACT`, `AUTH`), but three internal fields use lowercase:
- `_version_` - Document version (internal use)
- `text_hl` - Highlighted text snippets (internal use)
- `text_synonyms` - Text synonym expansion (internal use)

## API Functions

### `get_field_info(field: str) -> tuple[str, str]`

Get API field name and description for a given field.

```python
from pyeuropepmc.query_builder import get_field_info

# Get info for a field
api_name, description = get_field_info("author")
print(f"{api_name}: {description}")
# Output: AUTH: Author name (full or abbreviated form)
```

### `get_available_fields() -> list[str]`

Fetch the current list of searchable fields from the Europe PMC API.

```python
from pyeuropepmc.query_builder import get_available_fields

fields = get_available_fields()
print(f"Available fields: {len(fields)}")
# Output: Available fields: 142
```

### `validate_field_coverage(verbose: bool = False) -> dict`

Check if local field definitions cover all fields from the API.

```python
from pyeuropepmc.query_builder import validate_field_coverage

result = validate_field_coverage(verbose=True)
if result['up_to_date']:
    print("✅ All API fields are covered!")
```

## Field Categories

The metadata includes fields across multiple categories:

1. **Core Bibliographic** - title, abstract, journal, doi, etc.
2. **Authors & Contributors** - author, affiliation, ORCID, investigator, etc.
3. **Dates** - publication dates, embargo dates, indexing dates
4. **Identifiers** - DOI, PMID, PMCID, ISBN, accession IDs
5. **Content Features** - has_pdf, has_fulltext, open_access, etc.
6. **Subject Terms** - disease, organism, gene_protein, MeSH terms
7. **Citations & References** - citation_count, cites, cited, reffed_by
8. **Funding** - grant_id, grant_agency, funder_initiative
9. **Full-Text Sections** - introduction, methods, results, discussion

## Coverage

- **Total API Fields**: 142 (as of 2025)
- **Total Defined Fields**: 149 (includes aliases and documented fields)
- **Coverage**: 100% of API fields
- **Extra Fields**: 7 documented fields not currently in API (may be deprecated or version-specific)

## Validation

The field metadata is validated against the live Europe PMC API to ensure:
- All API fields are documented
- Field descriptions are accurate
- No missing fields

To check field coverage:

```bash
# Quick check
python scripts/check_fields.py

# Verbose output
python scripts/check_fields.py --verbose

# Quiet mode (exit code only)
python scripts/check_fields.py --quiet
```

## Migration Notes

### Before (Old Structure)

```python
FieldType = Literal["title", "abstract", "author", ...]
```

### After (New Structure)

```python
FIELD_METADATA: dict[str, tuple[str, str]] = {
    "title": ("TITLE", "Article or book title"),
    "abstract": ("ABSTRACT", "Article abstract text"),
    "author": ("AUTH", "Author name (full or abbreviated form)"),
    ...
}

# FieldType still exists for type hints
FieldType = Literal["title", "abstract", "author", ...]
```

## Benefits

1. **Better Documentation** - Each field has a clear description
2. **API Name Mapping** - Direct mapping to Europe PMC API field names
3. **Field Aliases** - Support for both full and abbreviated forms
4. **Live Validation** - Can check against API to ensure up-to-date
5. **Developer Experience** - Easier to discover and understand available fields
6. **Error Messages** - Can provide more informative validation errors

## See Also

- [Field Validation Guide](field-validation.md) - Complete field reference
- [QueryBuilder API](../api/README.md) - QueryBuilder documentation
- [Advanced Usage](../advanced/README.md) - Advanced query building patterns
