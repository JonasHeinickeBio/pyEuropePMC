# Query builder

This page shows how to build Europe PMC queries with `QueryBuilder` and how to save, load, translate and evaluate search strings through its `search-query` integration. The [QueryBuilder API reference](../api/query-builder.md) lists every method, error code and field name.

## Build a query

```python
from pyeuropepmc import QueryBuilder, SearchClient

query = (
    QueryBuilder()
    .keyword("CRISPR", field="title")
    .and_()
    .field("open_access", True)
    .and_()
    .date_range(start_year=2020, end_year=2024)
    .build()
)
print(query)  # TITLE:CRISPR AND OPEN_ACCESS:y AND (PUB_YEAR:[2020 TO 2024])

with SearchClient() as client:
    results = client.search(query, pageSize=25)

print(results["hitCount"])
```

Put an operator between every two terms: the builder joins parts with spaces and does not insert `AND` itself. Use a new `QueryBuilder()` for each query, because a builder keeps its parts after `build()`.

| Call | Adds |
|---|---|
| `keyword("cancer")` | `cancer` |
| `keyword("gene editing", field="abstract")` | `ABSTRACT:"gene editing"` |
| `field("author", "Smith J")` | `AUTH:"Smith J"` |
| `field("mesh", "Neoplasms")` | `MESH:Neoplasms` |
| `date_range(start_year=2020)` | `(PUB_YEAR:[2020 TO <current year>])` |
| `citation_count(min_count=50)` | `(CITED:[50 TO *])` |
| `cites("8521067")` | `CITES:8521067_med` |
| `and_()`, `or_()`, `not_()` | `AND`, `OR`, `NOT` |
| `group(other_builder)` | `(<other query>)` |
| `raw("(cancer OR tumour)")` | the string unchanged |

Unknown field names raise `ValueError`. Field names are listed under [Field names](../api/query-builder.md#field-names).

## Save, load and translate search strings

`from_string()`, `from_file()`, `save()`, `translate()`, `to_query_object()` and `evaluate()` use the `search-query` package, which is installed with pyeuropepmc; no extra is needed.

`search-query` reads queries in the syntax of a specific platform, such as PubMed (`pubmed`), Web of Science (`wos`) or EBSCOhost (`ebscohost`). It has no Europe PMC syntax, so these methods are for search strings written for those platforms. A query built with `QueryBuilder` is parsed as PubMed syntax: simple strings such as `cancer AND treatment` work, a Europe PMC field prefix such as `TITLE:` is not recognised as a field, and a Europe PMC range such as `(PUB_YEAR:[2020 TO 2024])` makes the methods raise `QueryBuilderError` with code `QUERY004`.

`search-query` prints its parser messages, for example `Warning: field-implicit (FIELD_0004)`, to standard output.

### Load a query from a string

```python
from pyeuropepmc import QueryBuilder

pubmed = QueryBuilder.from_string("cancer AND treatment", platform="pubmed")
print(pubmed.build())  # cancer AND treatment

wos = QueryBuilder.from_string("TI=cancer", platform="wos")
print(wos.build())  # TI=cancer
```

`build()` returns the original string; the parsed form is kept for `translate()`, `save()` and `to_query_object()`.

### Save a query to a file

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder().keyword("cancer").and_().keyword("treatment")
qb.save(
    "my-search.json",
    platform="pubmed",
    authors=[{"name": "Jane Smith", "ORCID": "0000-0000-0000-0002"}],
    date_info={"search_conducted": "2025-11-06"},
    database=["PubMed", "PMC"],
    record_info={"project": "Cancer research review"},
)
```

`save()` writes this JSON:

```json
{
    "search_string": "cancer AND treatment",
    "platform": "pubmed",
    "authors": [{"name": "Jane Smith", "ORCID": "0000-0000-0000-0002"}],
    "record_info": {"project": "Cancer research review"},
    "date": {"search_conducted": "2025-11-06"},
    "field": "",
    "version": {"version": "1"},
    "database": {"databases": ["PubMed", "PMC"]},
    "generic_query": {}
}
```

With `include_generic=True`, `generic_query` holds the platform-independent form, for example `{"generic_query": "AND[cancer[all-fields], treatment[all-fields]]"}`. The file layout follows the search-reporting data structure proposed by Haddaway et al. (2022).

### Load a query from a file

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder.from_file("my-search.json")
print(qb.build())  # cancer AND treatment
```

`from_file()` also reads files in which `version` is a string and `database` a list, for example:

```json
{
    "search_string": "cancer AND treatment",
    "platform": "pubmed",
    "version": "1",
    "authors": [{"name": "John Doe", "ORCID": "0000-0000-0000-0001"}],
    "date": {"data_entry": "2025-01-01", "search_conducted": "2025-01-01"},
    "database": ["PubMed", "PMC"],
    "record_info": {}
}
```

A missing file raises `FileNotFoundError`.

### Translate to another platform

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder.from_string("cancer AND treatment", platform="pubmed")
print(qb.translate("wos"))        # ALL=(cancer AND treatment)
print(qb.translate("ebscohost"))  # TX (cancer AND treatment)
print(qb.translate("generic"))    # AND[cancer[all-fields], treatment[all-fields]]

fielded = QueryBuilder.from_string("cancer[tiab] AND therapy[tiab]", platform="pubmed")
print(fielded.translate("wos"))   # (AB=cancer OR TI=cancer) AND (AB=therapy OR TI=therapy)
```

Supported targets are `pubmed`, `wos`, `ebscohost` and `generic`. Any other value, and any field the target platform does not support, raises `QueryBuilderError` (`QUERY004`).

### Work with the parsed query

```python
from pyeuropepmc import QueryBuilder

query_object = QueryBuilder().keyword("cancer").and_().keyword("treatment").to_query_object()
print(type(query_object).__name__)  # AndQuery
print(query_object.to_string())     # cancer[all] AND treatment[all]
```

### Evaluate a query against screened records

```python
from pyeuropepmc import QueryBuilder

records = {
    "r1": {"title": "Cancer treatment research", "colrev_status": "rev_included"},
    "r2": {"title": "Cancer diagnosis methods", "colrev_status": "rev_included"},
    "r3": {"title": "Unrelated topic", "colrev_status": "rev_excluded"},
}

results = QueryBuilder().keyword("cancer").evaluate(records)
print(f"Recall: {results['recall']:.2f}")        # Recall: 1.00
print(f"Precision: {results['precision']:.2f}")  # Precision: 1.00
print(f"F1: {results['f1_score']:.2f}")          # F1: 1.00
```

`evaluate()` returns `total_evaluated`, `selected`, `true_positives`, `false_positives`, `false_negatives`, `precision`, `recall` and `f1_score`. It matches terms against record titles and supports unfielded terms only: a query with a PubMed field tag such as `cancer[title]` raises `ValueError`, and a Europe PMC field such as `TITLE:cancer` selects no records.

## Round trip: load, translate, save

```python
from pyeuropepmc import QueryBuilder

pubmed = QueryBuilder.from_string("cancer[tiab] AND immunotherapy[tiab]", platform="pubmed")
pubmed.save("pubmed-search.json", platform="pubmed")

wos_string = QueryBuilder.from_file("pubmed-search.json").translate("wos")
wos = QueryBuilder.from_string(wos_string, platform="wos")
wos.save("wos-search.json", platform="wos")
print(wos.build())
```

## Limitations

- Europe PMC query syntax is not a `search-query` platform. Ranges and Europe PMC field prefixes built with `QueryBuilder` cannot be saved, translated or evaluated; save or translate the platform-specific strings you run elsewhere.
- `evaluate()` works on titles and unfielded terms only.
- `QueryBuilder(validate=True)` rewrites queries in PubMed syntax and rejects ranges; leave it off for Europe PMC queries.

## References

- Haddaway, N. R., Rethlefsen, M. L., Davies, M., Glanville, J., McGowan, B., Nyhan, K., & Young, S. (2022). A suggested data structure for transparent and repeatable reporting of bibliographic searching. *Campbell Systematic Reviews*, 18(4), e1288. https://doi.org/10.1002/cl2.1288
- search-query: https://github.com/CoLRev-Environment/search-query

## See also

- [QueryBuilder API reference](../api/query-builder.md)
- [Systematic review search logging](systematic-review-tracking.md)
- [Searching Europe PMC](search/README.md)
