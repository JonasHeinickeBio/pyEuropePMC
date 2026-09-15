# EuropePMCParser API reference

`EuropePMCParser` turns Europe PMC search responses into lists of plain dicts and builds the package's entity models from search records. All methods are static; `SearchClient.search_and_parse()` calls the format parsers for you.

```python
from pyeuropepmc import EuropePMCParser
```

The class is defined in `pyeuropepmc.features.literature.search_parser`; `pyeuropepmc.Parser` is an alias. It handles search responses only. Full-text article XML is parsed by [FullTextXMLParser](xml-parser.md).

## Format parsers

| Method | Input | Returns |
|---|---|---|
| `parse_json(data)` | A JSON search response (`dict`) or its list of records | `list[dict]` |
| `parse_xml(xml_str)` | The text of a `format="xml"` search response | `list[dict]` |
| `parse_dc(dc_str)` | The text of a `format="dc"` (Dublin Core) search response | `list[dict]` |
| `parse_csv(csv_str)` | CSV text with a header row | `list[dict]` |

### parse_json

Returns the records from `resultList.result` unchanged, with Europe PMC's keys and value types: for example `pubYear` is a string and `citedByCount` an integer. A list of records is accepted as well. Items that are not dicts are dropped and logged.

Raises `ParsingError` for `None` or an empty string (`PARSE003`) and for input that is neither a dict nor a list (`PARSE001`).

```python
from pyeuropepmc import EuropePMCParser, SearchClient

with SearchClient() as client:
    response = client.search("malaria", resultType="core")

records = EuropePMCParser.parse_json(response)
for record in records[:3]:
    print(record["source"], record["id"], record.get("pubYear"), record["title"])
```

### parse_xml

Each `<result>` element becomes a dict that maps its child element names to their text. Nested elements such as `authorList` are not expanded. Raises `ParsingError` if the text is not well-formed XML (`PARSE002`) or contains no `resultList/result` elements (`PARSE004`).

### parse_dc

Each `rdf:Description` element becomes a dict keyed by Dublin Core element name without namespace, for example `title`, `creator`, `contributor`, `description`, `date`, `identifier`, `language` and `bibliographicCitation`. An element that occurs more than once, such as `creator`, becomes a list of strings. A missing `title` is set to `""`.

```python
from pyeuropepmc import EuropePMCParser, SearchClient

with SearchClient() as client:
    dc_text = client.search("malaria", format="dc")

records = EuropePMCParser.parse_dc(dc_text)
print(records[0]["title"])
print(records[0]["creator"])
```

### parse_csv

Reads the text with `csv.DictReader` and returns one dict per row.

## Entity builders

### parse_search_results_with_entities

`parse_search_results_with_entities(search_results) -> list[dict]`

Builds a `PaperEntity` and its related author and institution entities for each record. Each item of the returned list is:

```text
{"entity": PaperEntity, "related_entities": {"authors": [AuthorEntity, ...], "institutions": [InstitutionEntity, ...]}}
```

Pass the list of records, `response["resultList"]["result"]`. A single dict is treated as one record, so passing the whole response produces one meaningless entity. Records that fail to convert are skipped with a logged warning. Use `resultType="core"` records to populate authors, affiliations, MeSH-based keywords and grants.

```python
from pyeuropepmc import EuropePMCParser, SearchClient

with SearchClient() as client:
    response = client.search("malaria", resultType="core")

items = EuropePMCParser.parse_search_results_with_entities(response["resultList"]["result"])
paper = items[0]["entity"]
print(paper.title, paper.publication_year, paper.cited_by_count)
print(len(items[0]["related_entities"]["authors"]), "authors")
```

### create_paper_entity_from_result

`create_paper_entity_from_result(result) -> tuple[PaperEntity, dict]`

Converts one record. Returns the `PaperEntity` and `{"authors": list[AuthorEntity], "institutions": list[InstitutionEntity]}`. The entity receives the identifiers, title, abstract, journal (as a `JournalEntity`), volume, issue, pages, `publication_year` as an `int`, author dicts, keywords, open-access flags and URL, `cited_by_count`, publication type, grants and licence. The entity classes are described in [Data models](../reference/models.md).

## Field extractors

Each takes one search record. Most of the fields they read are only present in `resultType="core"` records.

| Method | Returns |
|---|---|
| `extract_authors_and_entities(result)` | `(authors, author_entities, institution_entities)`. `authors` is a list of dicts with `full_name`, `first_name`, `last_name`, `initials`, `orcid` and, when available, `affiliations` |
| `extract_keywords_and_mesh(result)` | `list[str]`: the `keywordList` entries followed by `"MeSH:<descriptor>"` for each major-topic MeSH heading |
| `extract_mesh_headings(result)` | `list[MeSHHeadingEntity]`; see [MeSH models](../features/mesh-pico.md#mesh-data-models) |
| `extract_open_access_info(result)` | `(is_open_access, in_epmc, in_pmc, has_pdf, oa_url)`; `oa_url` is the first `fullTextUrlList` entry with availability code `OA`, or `None` |
| `extract_citation_info(result)` | `(cited_by_count, has_references, has_text_mined_terms, has_db_cross_references, has_labs_links, has_tm_accession_numbers)` |
| `extract_publication_metadata(result)` | `(pub_type, funders, license)`; `funders` is a list of `{"agency", "grant_id", "acronym"}` dicts |
| `parse_affiliation_string(affiliation_text)` | `InstitutionEntity`; splits the text on commas and guesses department, city and country |

```python
from pyeuropepmc import EuropePMCParser

institution = EuropePMCParser.parse_affiliation_string(
    "Department of Oncology, University of Oxford, Oxford, UK"
)
print(institution.display_name, institution.city, institution.country, institution.institution_type)
# University of Oxford Oxford UK Department of Oncology
```

## Errors

The format parsers raise `ParsingError` from `pyeuropepmc.core.exceptions`. The extractors do not validate their input; a record missing a field yields `None`, `False` or an empty list for it.

DOI and author-name normalization are not part of this class; see [Normalization utilities](../features/multi-source-search.md#normalization-utilities).

## Related pages

- [SearchClient](search-client.md)
- [FullTextXMLParser](xml-parser.md) for full-text XML
- [Data models](../reference/models.md)
