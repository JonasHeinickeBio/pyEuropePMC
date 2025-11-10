# Query Builder Field Validation

This document describes the field validation capabilities added to the QueryBuilder module.

## Overview

The QueryBuilder now includes comprehensive field validation that automatically checks if all Europe PMC API fields are properly defined in the `FieldType` literal. This ensures that the query builder stays up-to-date with the latest API changes.

## Features

### 1. Complete Field Coverage

The `FieldType` literal now includes **all 142 fields** from the Europe PMC API (as of 2025-11-05), plus:
- Field aliases (e.g., `author`/`auth`, `affiliation`/`aff`)
- Documented fields not in API response (e.g., `mesh`, `pmid`, `subset`)
- Total: 156 fields defined

### 2. API Field Fetching

```python
from pyeuropepmc.query_builder import get_available_fields

# Fetch current fields from Europe PMC API
fields = get_available_fields()
print(f"Available fields: {len(fields)}")
```

### 3. Automatic Validation

```python
from pyeuropepmc.query_builder import validate_field_coverage

# Check if all API fields are covered
result = validate_field_coverage(verbose=True)

if result['up_to_date']:
    print("✅ All API fields are covered!")
else:
    print(f"❌ Missing {len(result['missing_in_code'])} fields")
```

### 4. Command-Line Tool

```bash
# Check field coverage from command line
python scripts/check_fields.py
```

## Field Categories

### Core Bibliographic Fields
- `title`, `abstract`, `author` (`auth`), `journal`, `issn`, `doi`, `pmid`, `pmcid`
- Publication metadata: `pub_year`, `pub_type`, `volume`, `issue`

### Date Fields
- Electronic: `e_pdate`, `first_pdate`, `p_pdate`
- System: `creation_date`, `update_date`, `index_date`, `embargo_date`

### Author & Affiliation
- `author` / `auth`, `affiliation` / `aff`, `investigator`
- `authorid`, `authorid_type`, `auth_first`, `auth_last`

### Scientific Metadata
- MeSH: `mesh` (not in API but works)
- Chemicals: `chemical` / `chem`, `chebiterm`, `chebiterm_id`
- Biology: `disease`, `gene_protein`, `organism`, `goterm`
- Methods: `experimental_method`, `experimental_method_id`

### Funding
- `grant_agency`, `grant_agency_id`, `grant_id`, `funder_initiative`

### Full Text Availability
- `has_abstract`, `has_pdf`, `has_fulltext`, `has_reflist`
- `has_tm` (text-mined), `has_suppl`, `has_data`
- `open_access`, `in_pmc`, `in_epmc`

### Database Cross-References
- Protein: `has_uniprot`, `uniprot_pubs`
- Nucleotide: `has_embl`, `embl_pubs`
- Structure: `has_pdb`, `pdb_pubs`
- Interaction: `has_intact`, `intact_pubs`
- Chemistry: `has_chebi`, `has_chembl`

### Citations
- `cites`, `cited`, `reffed_by`, `citation_count`

### Section-Level Search
- `title_abs`, `intro`, `methods`, `results`, `discuss`, `concl`
- `fig`, `table`, `suppl`, `ref`, `appendix`, `ack_fund`

## Field Aliases

Europe PMC supports both full and abbreviated field names:

| Full Name     | Abbreviated | Usage                          |
|---------------|-------------|--------------------------------|
| `author`      | `auth`      | Author names                   |
| `affiliation` | `aff`       | Author affiliations            |
| `language`    | `lang`      | Publication language           |
| `keyword`     | `kw`        | Keywords                       |
| `chemical`    | `chem`      | Chemical substances            |
| `source`      | `src`       | Data source (MED, PMC, etc.)   |
| `editor`      | `ed`        | Book editors                   |

Both forms are accepted by the API and included in `FieldType`.

## Examples

### Basic Usage

```python
from pyeuropepmc import QueryBuilder

# Use full field names
qb = QueryBuilder()
query = qb.keyword("Smith", field="author").build()
# Result: Smith:AUTHOR

# Or use abbreviations
qb = QueryBuilder()
query = qb.keyword("Smith", field="auth").build()
# Result: Smith:AUTH
```

### Validation in CI/CD

```bash
# Add to your CI pipeline to ensure fields stay up-to-date
python scripts/check_fields.py || exit 1
```

### Checking for Updates

```python
from pyeuropepmc.query_builder import validate_field_coverage

result = validate_field_coverage(verbose=False)

if not result['up_to_date']:
    print("⚠️  Field definitions need updating!")
    print(f"Missing fields: {result['missing_in_code']}")
```

## Maintenance

The field list is validated against the Europe PMC API:
- **API Endpoint**: `https://www.ebi.ac.uk/europepmc/webservices/rest/fields?format=json`
- **Last Updated**: 2025-11-05
- **Coverage**: 100% (142/142 API fields)

### Updating Fields

When the Europe PMC API adds new fields:

1. Run validation:
   ```bash
   python scripts/check_fields.py
   ```

2. If new fields are found, add them to `FieldType` in `src/pyeuropepmc/query_builder.py`

3. Update the "Last Updated" comment in the code

4. Re-run tests and validation

## API Reference

### `get_available_fields(api_url=None) -> list[str]`

Fetches the current list of searchable fields from Europe PMC API.

**Returns**: List of field names (lowercase, sorted)

**Raises**:
- `ImportError` if `requests` is not installed
- `RuntimeError` if API request fails

### `validate_field_coverage(verbose=False) -> dict`

Validates that `FieldType` includes all API fields.

**Returns**: Dictionary with:
- `api_fields`: Fields from API
- `defined_fields`: Fields in FieldType
- `missing_in_code`: API fields not in FieldType
- `extra_in_code`: FieldType fields not in API
- `coverage_percent`: Coverage percentage
- `up_to_date`: True if 100% coverage
- `total_api_fields`: Count of API fields
- `total_defined_fields`: Count of defined fields

**Parameters**:
- `verbose` (bool): Print detailed comparison

## Notes

### Documented but Not in API Response

Some fields are documented in the Europe PMC reference guide but don't appear in the `/fields` API endpoint:
- `mesh` - MeSH terms (works in queries)
- `pmid` - PubMed ID (works in queries)
- `subset` - Content set filters
- `page_info` - Page numbers
- `crd_links`, `has_crd` - Clinical trials
- `embargoed_man` - Embargoed manuscripts

These are intentionally kept in `FieldType` as they're documented and functional.

### System Fields

Some fields are for internal use and rarely needed in queries:
- `_version_`, `shard`, `qn1`, `qn2`
- `text_hl`, `text_synonyms`

These are included for completeness but typically not used in user queries.

## See Also

- [Europe PMC Web Service Reference](https://europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf)
- [QueryBuilder Documentation](../../docs/api/query-builder.md)
- [Field Validation Example](../../examples/field_validation_example.py)
