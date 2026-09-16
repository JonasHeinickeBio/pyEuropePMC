# QueryBuilder API reference

`QueryBuilder` assembles Europe PMC query strings from method calls, rejects unknown field names, and connects to the `search-query` package to save, load, translate and evaluate search strings. For a walkthrough see [Query builder](../features/query-builder-load-save-translate.md).

```python
from pyeuropepmc import QueryBuilder
```

The module `pyeuropepmc.features.literature.query_builder` also defines `QueryBuilderError`, `FIELD_METADATA`, `FieldType`, `get_field_info()`, `get_available_fields()` and `validate_field_coverage()`. `get_available_fields` and `validate_field_coverage` are exported by `pyeuropepmc` as well.

## How a query is built

Each method appends one part to the builder and returns the builder, so calls can be chained. `build()` joins the parts with single spaces. Operators are never added for you: `QueryBuilder().keyword("cancer").keyword("therapy", field="title").build()` returns `cancer TITLE:therapy`.

A builder keeps its parts after `build()`, so reusing it for a second query appends to the first. Create a new `QueryBuilder()` for each query.

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

String values are wrapped in double quotes when they contain a space, one of `: ( ) [ ] { }`, or the uppercase letters `AND`, `OR` or `NOT` anywhere in the value (so `CORE` becomes `"CORE"`). Double quotes inside a value are escaped. `field(..., escape=False)` and `raw()` send text unchanged.

## Constructor

`QueryBuilder(validate=False)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `validate` | `bool` | `False` | Parse the finished query with `search-query` in `build()` |

With `validate=True`, `build()` parses the string with `search-query` using PubMed rules and returns the PubMed rendering, for example `cancer[all] AND therapy[all]` for `cancer AND therapy`. Europe PMC constructs such as `(PUB_YEAR:[2020 TO 2023])` then raise `QueryBuilderError` with code `QUERY004`, and the parser prints warnings to standard output. Leave `validate` off for queries you send to Europe PMC; unknown field names are rejected in either mode.

## Terms

### keyword

`keyword(term, field=None) -> QueryBuilder`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `term` | `str` | required | Search term; quoted when needed |
| `field` | `FieldType` or `None` | `None` | A field name from [`FIELD_METADATA`](#field-names), such as `"title"` |

| Call | Part added |
|---|---|
| `keyword("cancer")` | `cancer` |
| `keyword("gene editing")` | `"gene editing"` |
| `keyword("CRISPR", field="title")` | `TITLE:CRISPR` |
| `keyword("CRISPR AND therapy")` | `"CRISPR AND therapy"` (one phrase, not a Boolean expression) |

Raises `QueryBuilderError` (`QUERY001`) for an empty term and `ValueError` for an unknown field. To add a Boolean sub-expression, use `raw()` or `group()`.

### field

`field(field_name, value, escape=True, transform=None) -> QueryBuilder`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `field_name` | `FieldType` | required | A name from `FIELD_METADATA`; case-insensitive |
| `value` | `str`, `int` or `bool` | required | `True` is sent as `y` and `False` as `n` |
| `escape` | `bool` | `True` | Quote string values when needed |
| `transform` | callable or `None` | `None` | Applied to `value` before formatting |

| Call | Part added |
|---|---|
| `field("author", "Smith J")` | `AUTH:"Smith J"` |
| `field("open_access", True)` | `OPEN_ACCESS:y` |
| `field("pub_year", 2023)` | `PUB_YEAR:2023` |
| `field("mesh", "Neoplasms")` | `MESH:Neoplasms` |
| `field("pub_type", "Clinical Trial")` | `PUB_TYPE:"Clinical Trial"` |
| `field("first_pdate", "[2020-01-01 TO 2023-12-31]", escape=False)` | `FIRST_PDATE:[2020-01-01 TO 2023-12-31]` |

Raises `ValueError` for an unknown field name and `QueryBuilderError` (`QUERY001`) for an empty string value.

### date_range

`date_range(start_year=None, end_year=None, start_date=None, end_date=None) -> QueryBuilder`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start_year` | `int` or `None` | `None` | First publication year, inclusive |
| `end_year` | `int` or `None` | `None` | Last publication year, inclusive |
| `start_date` | `str` or `None` | `None` | `YYYY-MM-DD`; when either date is given the years are ignored |
| `end_date` | `str` or `None` | `None` | `YYYY-MM-DD` |

| Call | Part added |
|---|---|
| `date_range(2020, 2023)` | `(PUB_YEAR:[2020 TO 2023])` |
| `date_range(start_year=2020)` | `(PUB_YEAR:[2020 TO <current year>])`, using the year at the time of the call |
| `date_range(end_year=2020)` | `(PUB_YEAR:[1000 TO 2020])` |
| `date_range(start_date="2020-01-01", end_date="2023-12-31")` | `(FIRST_PDATE:[2020-01-01 TO 2023-12-31])` |
| `date_range(start_date="2020-01-01")` | `(FIRST_PDATE:[2020-01-01 TO *])` |
| `date_range(end_date="2023-12-31")` | `(FIRST_PDATE:[* TO 2023-12-31])` |

Europe PMC's `PUB_YEAR` field holds years, so years produce a `PUB_YEAR` range and full dates a `FIRST_PDATE` range, the field that stores the first publication date. `field("first_pdate", "[2020-01-01 TO 2023-12-31]", escape=False)` builds the same part by hand.

Raises `QueryBuilderError` (`QUERY002`) for a year before 1000 or after next year, a start after the end, or a date not in `YYYY-MM-DD` form. With no arguments nothing is added.

### citation_count

`citation_count(min_count=None, max_count=None) -> QueryBuilder`

Adds `(CITED:[10 TO *])` for `min_count=10`, `(CITED:[* TO 5])` for `max_count=5` and `(CITED:[5 TO 50])` for both. Raises `QueryBuilderError` (`QUERY002`) for a negative count or `min_count` greater than `max_count`.

### pmcid, source, accession_type and cites

| Call | Part added | Notes |
|---|---|---|
| `pmcid("1234567")` | `PMCID:PMC1234567` | The `PMC` prefix is added when missing |
| `source("med")` | `SRC:MED` | Upper-cased |
| `accession_type("PDB")` | `ACCESSION_TYPE:pdb` | Lower-cased |
| `cites("8521067", source="med")` | `CITES:8521067_med` | Records that cite the given article |

Each raises `QueryBuilderError` (`QUERY001`) for an empty value.

## Operators and grouping

| Call | Result |
|---|---|
| `keyword("cancer").and_().keyword("therapy")` | `cancer AND therapy` |
| `keyword("cancer").or_().keyword("tumour")` | `cancer OR tumour` |
| `keyword("cancer").and_().not_().keyword("review")` | `cancer AND NOT review` |
| `keyword("cancer").not_().keyword("review")` | `cancer NOT review` |

`and_()`, `or_()` and `not_()` raise `QueryBuilderError` (`QUERY003`) when they are the first call or follow another operator; the one exception is `not_()` after `and_()`. `build()` raises the same error when the query ends with an operator.

`group(builder)` adds another builder's query in parentheses, and `raw(query_string)` adds a string unchanged:

```python
from pyeuropepmc import QueryBuilder

subquery = QueryBuilder().keyword("cancer").or_().keyword("tumour")
print(QueryBuilder().keyword("CRISPR").and_().group(subquery).build())
# CRISPR AND (cancer OR tumour)

print(QueryBuilder().raw("(cancer OR tumor) AND therapy").and_().date_range(2020, 2024).build())
# (cancer OR tumor) AND therapy AND (PUB_YEAR:[2020 TO 2024])
```

## build

`build(validate=True) -> str`

Returns the query string. The `validate` argument only has an effect on a builder created with `QueryBuilder(validate=True)`; see [Constructor](#constructor). Raises `QueryBuilderError` with `QUERY001` for an empty builder and `QUERY003` for a trailing operator.

## Saving, loading, translating and evaluating

These methods pass the query string to the `search-query` package, which is installed with pyeuropepmc. `search-query` reads a query in the syntax of one platform: `pubmed`, `wos` (Web of Science) or `ebscohost`; `translate()` also accepts `generic`. It has no Europe PMC syntax. A builder's own query is parsed as PubMed syntax, so a Europe PMC range such as `(PUB_YEAR:[2020 TO 2023])` makes `save()`, `translate()` and `to_query_object()` raise `QueryBuilderError` (`QUERY004`), and a Europe PMC field prefix such as `TITLE:` is not read as a field. Parser warnings are printed to standard output.

| Method | Returns | Description |
|---|---|---|
| `QueryBuilder.from_string(query_string, platform="pubmed", validate=False)` | `QueryBuilder` | Class method. Parses `query_string`; `build()` returns the string unchanged. `QUERY001` for an empty string, `QUERY004` if parsing fails |
| `QueryBuilder.from_file(file_path, validate=False)` | `QueryBuilder` | Class method. Loads a search file with at least `search_string` and `platform`. `FileNotFoundError` if the file is missing, `QUERY004` if it cannot be read |
| `save(file_path, platform="pubmed", authors=None, record_info=None, date_info=None, database=None, include_generic=False)` | `None` | Writes a search file; `QUERY004` if the query cannot be parsed |
| `translate(target_platform)` | `str` | The query in `"pubmed"`, `"wos"`, `"ebscohost"` or `"generic"` syntax; `QUERY004` otherwise |
| `to_query_object(platform="pubmed")` | `search_query` query object | Parsed query tree, cached on the builder, for example `search_query.query_and.AndQuery` |
| `evaluate(records, platform="pubmed")` | `dict` | Recall and precision against screened records |

`save()` parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | required | Output path |
| `platform` | `str` | `"pubmed"` | Platform written to the file and used to parse the query |
| `authors` | `list[dict]` or `None` | `None` | For example `[{"name": "Jane Smith", "ORCID": "0000-0000-0000-0002"}]` |
| `record_info` | `dict` or `None` | `None` | Free-form metadata |
| `date_info` | `dict` or `None` | `None` | For example `{"search_conducted": "2025-11-06"}`; stored as `date` |
| `database` | `list[str]` or `None` | `None` | Stored as `{"databases": [...]}` |
| `include_generic` | `bool` | `False` | Also store the generic rendering under `generic_query` |

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder.from_string("cancer[tiab] AND therapy[tiab]", platform="pubmed")
print(qb.translate("wos"))
# (AB=cancer OR TI=cancer) AND (AB=therapy OR TI=therapy)

print(QueryBuilder.from_string("TI=cancer", platform="wos").translate("pubmed"))
# cancer[ti]
```

`evaluate(records, platform="pubmed")` takes a dict of records keyed by ID, each with `title` and `colrev_status` (`"rev_included"` or `"rev_excluded"`). It returns `total_evaluated`, `selected`, `true_positives`, `false_positives`, `false_negatives`, `precision`, `recall` and `f1_score`. Terms without a field are matched against titles; a query with PubMed field tags such as `cancer[title]` raises `ValueError`, and a Europe PMC field prefix such as `TITLE:cancer` matches no records.

## log_to_search

`log_to_search(search_log, database="Europe PMC", filters=None, results_returned=None, notes=None, raw_results=None, raw_results_dir=None, platform=None, export_path=None) -> None`

Records `build(validate=False)` as a new entry in a `SearchLog`. The parameters are described in [Systematic review search logging](../features/systematic-review-tracking.md#log-a-querybuilder-query).

## Field names

`FIELD_METADATA` maps 158 lowercase field names to a tuple of the Europe PMC field name and a description, for example `"author": ("AUTH", "Author name (full or abbreviated form)")`. `FieldType` is a `typing.Literal` of the same names for static type checkers; at run time an unknown name raises `ValueError`. Names are matched case-insensitively.

Some names are aliases of the same Europe PMC field:

| Names | Europe PMC field |
|---|---|
| `author`, `auth` | `AUTH` |
| `affiliation`, `aff` | `AFF` |
| `language`, `lang` | `LANG` |
| `chemical`, `chem` | `CHEM` |
| `source`, `src` | `SRC` |
| `editor`, `ed` | `ED` |
| `citation_count`, `cited` | `CITED` |
| `pmid`, `ext_id` | `EXT_ID` |

Because `pmid` maps to `EXT_ID`, combine it with the source to search a PubMed ID: `QueryBuilder().field("pmid", "32791984").and_().source("MED").build()` returns `EXT_ID:32791984 AND SRC:MED`.

The names cover bibliographic fields (`title`, `abstract`, `journal`, `issn`, `doi`, `pub_year`, `pub_type`), dates (`first_pdate`, `e_pdate`, `p_pdate`, `update_date`), authors and funding (`auth_first`, `auth_last`, `authorid`, `investigator`, `grant_agency`, `grant_id`), subject terms (`mesh`, `keyword`, `disease`, `gene_protein`, `organism`, `goterm`, `chebiterm`), availability flags (`open_access`, `in_pmc`, `in_epmc`, `has_pdf`, `has_fulltext`, `has_abstract`), database links (`has_uniprot`, `has_pdb`, `accession_id`, `accession_type`), citations (`cites`, `reffed_by`), full-text sections (`intro`, `methods`, `results`, `discuss`, `concl`, `fig`, `table`, `ack_fund`) and a few internal fields (`_version_`, `text_hl`, `text_synonyms`, `shard`, `qn1`, `qn2`).

| Function | Returns | Network | Description |
|---|---|---|---|
| `get_field_info(field)` | `tuple[str, str]` | no | Europe PMC name and description; `ValueError` for an unknown name |
| `get_available_fields(api_url=None)` | `list[str]` | yes | Sorted upper-case field names from the Europe PMC `fields` endpoint; raises `APIClientError` on failure |
| `validate_field_coverage(verbose=False)` | `dict` | yes | Compares the live field list with `FIELD_METADATA` |

`validate_field_coverage()` returns `api_fields`, `defined_fields`, `missing_in_code`, `extra_in_code`, `coverage_percent`, `up_to_date`, `total_api_fields` and `total_defined_fields`. With `verbose=True` it also logs a report through the `logging` module. Fields such as `MESH`, `PAGE_INFO` and `SUBSET` are documented by Europe PMC but not returned by the `fields` endpoint, so they appear in `extra_in_code`.

```python
from pyeuropepmc import get_available_fields, validate_field_coverage
from pyeuropepmc.features.literature.query_builder import get_field_info

print(get_field_info("author"))  # ('AUTH', 'Author name (full or abbreviated form)')

fields = get_available_fields()
report = validate_field_coverage()
print(len(fields), report["up_to_date"], report["missing_in_code"])
```

In a source checkout, `python examples/scripts/check_fields.py` runs `validate_field_coverage(verbose=True)` and exits with status 0 when every live field is defined and 1 when some are missing. It takes no options.

## Errors

`QueryBuilderError` is defined in `pyeuropepmc.core.exceptions` and derives from `PyEuropePMCError`; `error.error_code` holds the code.

| Code | Cause |
|---|---|
| `QUERY001` | Empty term, value or query, or an empty sub-builder passed to `group()` |
| `QUERY002` | Invalid year, date or citation count, or a range whose start is after its end |
| `QUERY003` | An operator at the start, after another operator, or at the end of the query |
| `QUERY004` | `search-query` could not parse, validate, save or translate the query |

Unknown field names raise `ValueError`.

## Related pages

- [Query builder guide](../features/query-builder-load-save-translate.md)
- [Systematic review search logging](../features/systematic-review-tracking.md)
- [SearchClient](search-client.md)
