# FullTextXMLParser

`FullTextXMLParser` parses Europe PMC full-text XML (JATS) and extracts metadata, tables, figures, references and sections, or renders the article as plain text or Markdown. This page lists its public methods and the exact shape of what they return; [XML parsing](../features/parsing/README.md) shows them in use.

```python
from pyeuropepmc import FullTextXMLParser
```

`ElementPatterns` and `DocumentSchema` are importable from `pyeuropepmc` too. All three are defined under `pyeuropepmc.features.fulltext`.

## Constructor

`FullTextXMLParser(xml_content=None, config=None)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `xml_content` | `str \| xml.etree.ElementTree.Element \| None` | `None` | Parsed immediately when given |
| `config` | `ElementPatterns \| None` | `None` | Element patterns; `None` uses `ElementPatterns()` |

| Attribute | Type | Description |
|---|---|---|
| `root` | `Element \| None` | Root of the parsed document |
| `xml_content` | `str \| None` | The parsed string; `None` when an `Element` was passed |
| `config` | `ElementPatterns` | The pattern configuration |
| `NAMESPACES` | `dict[str, str]` | Class attribute: `{"xlink": "http://www.w3.org/1999/xlink", "mml": "http://www.w3.org/1998/Math/MathML"}`, for `find(".//mml:math", FullTextXMLParser.NAMESPACES)` |

## parse

`parse(xml_content) -> xml.etree.ElementTree.Element`

Parses a string with `defusedxml.ElementTree.fromstring`, removes the root's default namespace (if any) from all tags, stores and returns the root, and resets cached results. An `Element` is stored as it is. A DOCTYPE without entity declarations is accepted; a document that declares an entity is refused.

| Failure | Raises |
|---|---|
| Malformed XML | `ParsingError`, `error_code` `PARSE002`, cause `xml.etree.ElementTree.ParseError` |
| Entity declaration | `ParsingError`, `PARSE003`, cause `defusedxml.EntitiesForbidden` |
| `None`, empty string, `bytes` or other type | `ParsingError`, `PARSE003` |

## Methods

Every method raises `ParsingError` (`PARSE003`) when nothing has been parsed. The methods marked "wrapped" also turn any other exception into `ParsingError` (`PARSE003`), with the original exception as `__cause__`; the others let it propagate.

| Method | Returns | Errors |
|---|---|---|
| `extract_metadata()` | `dict[str, Any]`, see [extract_metadata](#extract_metadata) | wrapped |
| `extract_authors()` | `list[str]`: `"Given Surname"` for each author in the front matter | – |
| `extract_authors_detailed()` | `list[dict]` with `given_names`, `surname`, `full_name`, `affiliation_refs` (list of affiliation IDs), `orcid` (`str` or `None`) | – |
| `extract_affiliations()` | `list[dict]`, see [Affiliations](#affiliations) | – |
| `extract_pub_date()` | `str \| None`: `YYYY`, `YYYY-MM` or `YYYY-MM-DD` | – |
| `extract_keywords()` | `list[str]` | – |
| `extract_funding()` | `list[dict]` with `source`, and when present `fundref_doi`, `award_id`, `recipients` (list of name dicts), `recipient_full` | – |
| `extract_license()` | `dict` with `url`, `text` and, when present, `type`; `{}` when there is no licence | – |
| `extract_publisher()` | `dict` with `name` and, when present, `location`; `{}` when absent | – |
| `extract_article_categories()` | `dict`: `{"subject_groups": [{"subjects": [...], "type": ...}]}`; `{}` when absent | – |
| `extract_tables()` | `list[dict]`, see [Tables](#tables) | wrapped |
| `extract_figures()` | `list[dict]`, see [Figures](#figures) | wrapped |
| `extract_references()` | `list[dict]`, see [References](#references) | wrapped |
| `get_full_text_sections()` | `list[dict]`, see [Flat sections](#flat-sections) | wrapped |
| `get_full_text_sections_structured()` | `list[dict]`, see [Structured sections](#structured-sections) | wrapped |
| `to_plaintext()` | `str` | wrapped |
| `to_markdown()` | `str` | wrapped |
| `detect_schema()` | `DocumentSchema`, see [DocumentSchema](#documentschema) | – |
| `list_element_types()` | `list[str]`: sorted distinct tag names, namespace URIs removed | – |
| `validate_schema_coverage()` | `dict`, see [Coverage report](#coverage-report) | – |
| `extract_elements_by_patterns(patterns, return_type="text", first_only=False, get_attribute=None)` | `dict[str, list]`, see [extract_elements_by_patterns](#extract_elements_by_patterns) | – |

`to_plaintext()` and `to_markdown()` are described in [Plain text and Markdown](../features/parsing/README.md#plain-text-and-markdown).

## extract_metadata

Always present, with `None` or an empty value when not found:

| Key | Type | Description |
|---|---|---|
| `title` | `str \| None` | Article title |
| `abstract` | `str \| None` | Text of the first `<abstract>` |
| `authors` | `list[str]` | Same as `extract_authors()` |
| `journal` | `dict` | `title`, `volume`, `issue`; when present also `issn_print`, `issn_electronic`, `publisher`, `nlm_ta`, `iso_abbrev`, `journal_ids`, `country` |
| `pub_date` | `str \| None` | Same as `extract_pub_date()` |
| `doi` | `str \| None` | Article DOI |
| `pmcid` | `str \| None` | As written in the XML: `"PMC3258128"` or `"3258128"` |
| `volume`, `issue` | `str \| None` | Volume and issue |
| `pages` | `str \| None` | `"fpage-lpage"` or `"fpage"` |
| `keywords` | `list[str]` | Same as `extract_keywords()` |

Present only when the article has the information:

| Key | Type | Description |
|---|---|---|
| `pmid` | `str` | PubMed ID |
| `identifiers` | `dict[str, str]` | Every article ID by `pub-id-type`, for example `pmcid`, `pmid`, `doi`, `publisher-id` |
| `license` | `dict` | Same as `extract_license()` |
| `copyright` | `dict` | `statement` and, when present, `year` |
| `publisher` | `dict` | Same as `extract_publisher()` |
| `funding` | `list[dict]` | Same as `extract_funding()` |
| `categories` | `dict` | Same as `extract_article_categories()` |
| `history` | `list[dict]` | Editorial dates: `{"type": "received", "date": "2010-12-13"}` |
| `correspondence` | `list[dict]` | `id`, `email`, `text` of `<corresp>` elements |
| `self_uri` | `str` | The first `<self-uri>` link |
| `counts` | `dict[str, int]` | From `<counts>`, for example `{"pages": 8}` |
| `extended_metadata` | `dict` | Further values such as `alternative_title` and `article_version` |

## Affiliations

`extract_affiliations()` returns one dict per `<aff>` element. Keys depend on the markup:

| Key | Present for | Description |
|---|---|---|
| `id`, `text` | all | Element ID and full text |
| `institution`, `city`, `country` | tagged or heuristically split affiliations | Parts of the address; missing parts are left out or `None` |
| `institutions`, `institution_ids` | affiliations with `<institution-wrap>` | All institution names; identifiers such as `ROR` and `GRID` |
| `markers`, `institution_text`, `parsed_institutions` | one `<aff>` holding several numbered institutions | Marker numbers, the text without markers, and one dict per institution |

## Tables

| Key | Type | Description |
|---|---|---|
| `id` | `str \| None` | `id` attribute of `<table-wrap>` |
| `label` | `str \| None` | For example `"Table 1"` |
| `caption` | `str \| None` | Caption text |
| `footer` | `str \| None` | Text of `<table-wrap-foot>` |
| `headers` | `list[str]` | `<th>` cells of the first `<thead>` row; `[]` when there is no `<thead>` or its cells are `<td>` |
| `rows` | `list[list[str]]` | `<td>` cells of each `<tbody>` row |
| `column_groups` | `list[dict]` | Only when the table has `<colgroup>`: `{"columns": [{"span": ..., "width": ...}], "span": ...}` |

## Figures

| Key | Type | Description |
|---|---|---|
| `id` | `str \| None` | `id` attribute of `<fig>` |
| `label` | `str \| None` | For example `"Figure 1."` |
| `caption` | `str \| None` | Caption text, including its title |
| `graphic_uri` | `str` | Only when the figure contains a `<graphic>`: the `xlink:href` of the first one, a file name such as `"gkr715f1"` |

## References

| Key | Type | Description |
|---|---|---|
| `id`, `label` | `str \| None` | `id` attribute and label of `<ref>` |
| `citation_type` | `str \| None` | `element-citation` or `mixed-citation` |
| `authors` | `str \| None` | All author names in one string, for example `"Bartel, DP"` |
| `title` | `str \| None` | Title of the cited work; falls back to `source` when there is none |
| `source` | `str \| None` | Journal or book title |
| `year`, `volume`, `pages` | `str \| None` | Year, volume, page range |
| `doi`, `pmid`, `pmcid` | `str \| None` | Identifiers |
| `raw_citation` | `str` | Only for some untagged citations: the citation text |

## Flat sections

`get_full_text_sections()` returns `{"title": str, "content": str}` dicts: one per `<sec>` in the article's own body (not sub-articles), in document order, with `content` holding that section's own paragraphs joined by blank lines. Then an untitled entry for paragraphs directly in `<body>`, if there are any. Then back matter with an extra `type` key: `author_notes` (title `"Author Notes"`), `acknowledgments`, `appendix` (the appendix title) and `glossary`.

## Structured sections

`get_full_text_sections_structured()` returns `StructuredSection.to_dict()` results:

| Key | Type | Description |
|---|---|---|
| `title` | `str` | `"Article Title"` and `"Abstract"` for the first two sections; otherwise the section title, possibly `""` |
| `content` | `list[dict]` | Content blocks, see [ContentBlock](xml-parser-extensions.md#contentblock) |
| `section_type` | `str` | `"front"`, `"body"`, `"back"` or `"appendix"` |
| `schema_version` | `str` | `"0.2.0"` |
| `section_path` | `str` | Present when not empty: section titles from the top level down, joined by `/` |

The order of sections, the block types and how paragraphs are split around nested tables and figures are described in [Structured sections](../features/parsing/README.md#structured-sections). `parser.content_block_extractor.extract_sections()` returns the same sections as objects.

## DocumentSchema

`detect_schema()` returns this dataclass, computed once per parsed document:

| Field | Type | Description |
|---|---|---|
| `has_tables` | `bool` | The document contains a table |
| `table_structure` | `str` | `"jats"` for `<table-wrap>`, `"html"` for a bare `<table>` only |
| `has_figures` | `bool` | Contains `<fig>` |
| `has_supplementary` | `bool` | Contains `<supplementary-material>` |
| `has_acknowledgments` | `bool` | Contains `<ack>` |
| `has_funding` | `bool` | Contains `<funding-group>` |
| `citation_types` | `list[str]` | Citation element names found, in the order of `config.citation_types` |

## Coverage report

`validate_schema_coverage()` returns:

| Key | Type | Description |
|---|---|---|
| `total_elements` | `int` | Number of distinct tag names in the document |
| `recognized_elements` | `list[str]` | Sorted tag names that occur in the pattern configuration or in the parser's list of common structural elements |
| `unrecognized_elements` | `list[str]` | Sorted remaining tag names |
| `recognized_count`, `unrecognized_count` | `int` | Lengths of the two lists |
| `coverage_percentage` | `float` | `recognized_count / total_elements * 100` |
| `element_frequency` | `dict[str, int]` | Occurrences of each tag name |

## extract_elements_by_patterns

`extract_elements_by_patterns(patterns, return_type="text", first_only=False, get_attribute=None) -> dict[str, list]`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `patterns` | `dict[str, str]` | required | Output name to ElementTree XPath, evaluated with `root.findall()` |
| `return_type` | `str` | `"text"` | `"text"`: full text of each match; `"element"`: the elements; `"attribute"`: the attribute named in `get_attribute` |
| `first_only` | `bool` | `False` | Keep only the first match per name |
| `get_attribute` | `dict[str, str] \| None` | `None` | Output name to attribute name, required for `"attribute"`; namespaced attributes are written `{uri}name` |

Each name maps to a list, `[]` when nothing matches. An unknown `return_type`, or a missing attribute name, raises `ValueError`.

## ElementPatterns

`ElementPatterns` is a dataclass whose 17 fields are `dict[str, list[str]]` groups of XPath patterns with defaults: `citation_types`, `author_element_patterns`, `author_field_patterns`, `journal_patterns`, `article_patterns`, `table_patterns`, `reference_patterns`, `inline_element_patterns`, `xref_patterns`, `media_patterns`, `object_id_patterns`, `math_patterns`, `formatting_patterns`, `extended_metadata_patterns`, `content_structure_patterns`, `award_patterns` and `appendix_patterns`. A field passed to the constructor replaces the whole default group, so keep every key the parser reads; print `ElementPatterns()` to see the defaults.

```python
from pyeuropepmc import ElementPatterns

defaults = ElementPatterns()
print(defaults.citation_types)
print(sorted(defaults.article_patterns)[:4])
```

Output:

```text
{'types': ['element-citation', 'mixed-citation', 'nlm-citation', 'citation']}
['abstract', 'doi', 'issue', 'keywords']
```

## Lazily created components

The parser delegates to helper objects that it creates on first use and discards when a new document is parsed: `author_parser`, `affiliation_parser`, `metadata_parser`, `reference_parser`, `table_parser`, `figure_parser`, `section_parser`, `plaintext_converter`, `markdown_converter` and `content_block_extractor`. They are properties; [XML parser internals](../development/xml-parser-internals.md) describes them.

## See also

- [XML parsing](../features/parsing/README.md): examples and known limitations
- [XML parser extensions](xml-parser-extensions.md)
- [JATS normalization](../features/parsing/jats-normalization.md)
