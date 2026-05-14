# Query Builder Skill

Use `QueryBuilder` for fluent, type-safe search queries against Europe PMC.

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder()

# Build complex queries
query = (
    qb.keyword("cancer", field="title")
    .and_()
    .keyword("immunotherapy")
    .and_()
    .date_range(start_year=2020, end_year=2023)
    .and_()
    .citation_count(min_count=10)
    .build()
)

# Output: (TITLE:cancer) AND immunotherapy AND (PUB_YEAR:[2020 TO 2023]) AND (CITED:[10 TO *])
```

Common helpers:
- `.keyword("term", field="title")` — keyword search in field
- `.field("author", "Smith")` — field-specific search
- `.date_range(start_year=2020)` — year range
- `.citation_count(min_count=10)` — citation filter
- Boolean: `.and_()`, `.or_()`, `.not_()`

Key tips:
- Use `validate=True` for field name validation
- Call `get_available_fields()` to see searchable fields
- Save/restore queries with `.save()` and `.load()`
