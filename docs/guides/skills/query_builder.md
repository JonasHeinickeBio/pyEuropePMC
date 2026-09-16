# Query builder skill card

Build Europe PMC query strings in code with `QueryBuilder`. This card summarises the [QueryBuilder API reference](../../api/query-builder.md).

```python
from pyeuropepmc import QueryBuilder

query = (
    QueryBuilder()
    .keyword("cancer", field="title")
    .and_()
    .keyword("immunotherapy")
    .and_()
    .date_range(start_year=2020, end_year=2023)
    .and_()
    .citation_count(min_count=10)
    .build()
)
print(query)
# TITLE:cancer AND immunotherapy AND (PUB_YEAR:[2020 TO 2023]) AND (CITED:[10 TO *])
```

Common calls:

- `.keyword("term", field="title")` adds a term, optionally in a field
- `.field("author", "Smith J")` adds `AUTH:"Smith J"`
- `.date_range(start_year=2020)` adds a publication-year range ending in the current year
- `.citation_count(min_count=10)` adds a citation filter
- `.and_()`, `.or_()`, `.not_()` add operators; `.group(other_builder)` and `.raw("...")` add sub-expressions

Tips:

- Put an operator between every two terms; none is added for you.
- Create a new `QueryBuilder()` for each query, because parts accumulate.
- Unknown field names raise `ValueError`. Leave `validate=False` (the default): `validate=True` rewrites the query in PubMed syntax and rejects ranges.
- The builder's field names are the keys of `FIELD_METADATA`; `get_available_fields()` fetches Europe PMC's live list of upper-case field names over the network.
- Save and reload a search string with `qb.save("q.json")` and `QueryBuilder.from_file("q.json")`. Both parse the string as PubMed syntax, so a query containing a range cannot be saved. See [Query builder](../../features/query-builder-load-save-translate.md).
- Record searches for a systematic review with `qb.log_to_search(log, results_returned=...)`; see [Systematic review search logging](../../features/systematic-review-tracking.md).
