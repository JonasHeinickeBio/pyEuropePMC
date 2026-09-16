# XML parser internals

This page is for contributors who change the full-text XML parser in `src/pyeuropepmc/features/fulltext/`. It covers how the modules fit together, how a document is parsed, and the helpers to build new extractions on. The public API is documented in [FullTextXMLParser](../api/xml-parser.md).

## Modules

| Path under `src/pyeuropepmc/features/fulltext/` | Contents |
|---|---|
| `fulltext_parser.py` | `FullTextXMLParser`: parses the XML and delegates each extraction |
| `parsers/base_parser.py` | `BaseParser`: shared root, configuration and helpers |
| `parsers/author_parser.py`, `affiliation_parser.py`, `metadata_parser.py`, `reference_parser.py`, `table_parser.py`, `figure_parser.py`, `section_parser.py` | One `BaseParser` subclass per extraction |
| `converters/plaintext_converter.py`, `converters/markdown_converter.py` | `to_plaintext()` and `to_markdown()` |
| `config/element_patterns.py`, `config/document_schema.py` | `ElementPatterns` and `DocumentSchema` |
| `utils/xml_helpers.py` | `XMLHelper` static text-extraction functions |
| `utils/text_cleaners.py`, `utils/geo_validators.py` | Text clean-up and affiliation location helpers |
| `extensions/` | Content blocks, peer review, MathML, JATS4R, batch and local processing, assets, reference resolution, Pydantic and LinkML models |
| `jats_normalizer.py` | `JATSNormalizer`, which does not use `FullTextXMLParser` |

## How a document is parsed

1. `FullTextXMLParser(xml_content, config)` calls `parse()` when content is given.
2. A string is parsed with `defusedxml.ElementTree.fromstring`. `_strip_default_namespace()` then removes the root's own default namespace from every tag, so the unprefixed patterns (`.//article-meta`) also match schema-based JATS. Prefixed vocabularies such as `xlink` and `ali` keep their namespaces. An `Element` is stored without this step.
3. `ET.ParseError` becomes `ParsingError(ErrorCodes.PARSE002)`; any other exception, including defusedxml's `EntitiesForbidden`, becomes `ParsingError(ErrorCodes.PARSE003)`. The original exception is the `__cause__`.
4. `_reset_parsers()` drops all cached components.

Components are created on first access through properties (`author_parser`, `metadata_parser`, …, `content_block_extractor`), each with the same `root` and `config`. `content_block_extractor` imports the extensions package lazily to avoid a circular import. The public methods call `_require_root()`; `extract_metadata`, `extract_references`, `extract_tables`, `extract_figures`, the two section methods and the two converters also wrap unexpected exceptions in `ParsingError(PARSE003)`.

## Parse XML only with defusedxml

All XML in the package is parsed with defusedxml. Ruff enforces this on `src/` and `tests/`: rules S313–S319 flag the standard-library parsers, and `flake8-tidy-imports.banned-api` bans `lxml` (see `pyproject.toml`). The rules do not catch every spelling, for example `xml.etree.ElementTree.XML`, `XMLPullParser`, `xml.parsers.expat` or defusedxml calls with its protections switched off, so check new parser calls in review. Import `xml.etree.ElementTree` only for type hints and `ET.ParseError`, with `# nosec B405`.

## XMLHelper

`XMLHelper` in `utils/xml_helpers.py` holds static methods that every parser uses.

| Method | Returns | Behaviour |
|---|---|---|
| `get_text_content(element, exclude_tags=frozenset())` | `str` | All text of the element and its descendants with whitespace collapsed. Inline elements keep the document's spacing; block-level elements (`p`, `title`, `td`, `caption`, …) are separated by a space. Subtrees of `exclude_tags` are skipped, their tails kept. `None` gives `""` |
| `extract_flat_texts(parent, pattern, filter_empty=True, use_full_text=False)` | `list[str]` | For each `findall(pattern)` match: its stripped `.text`, or `get_text_content()` with `use_full_text=True` |
| `extract_nested_texts(parent, outer_pattern, inner_patterns, join=" ", filter_empty=True)` | `list[str]` | For each outer match, the `.text` of the first match of each inner pattern, joined |
| `extract_structured_fields(parent, field_patterns, first_only=True)` | `dict` | Field name to the first `.text` match (or `None`), or to a list of all matches |
| `extract_with_fallbacks(element, patterns, use_full_text=False)` | `str \| None` | The text of the first pattern that matches |
| `combine_page_range(fpage, lpage)` | `str \| None` | `"10-15"`, `"10"` or `None` |
| `extract_inline_elements(element, inline_patterns=None, filter_empty=True)` | `list[str]` | Texts of the inline elements; default pattern `.//sup` |
| `get_text_without_inline_elements(element, inline_patterns=None)` | `str` | The element's text with the texts of those inline elements removed |

```python
import defusedxml.ElementTree as DefusedET

from pyeuropepmc.features.fulltext.utils.xml_helpers import XMLHelper

root = DefusedET.fromstring(
    "<article><front><article-meta>"
    "<contrib-group><contrib contrib-type='author'><name><surname>Smith</surname>"
    "<given-names>Jane</given-names></name></contrib></contrib-group>"
    "<fpage>10</fpage><lpage>15</lpage>"
    "</article-meta></front><body><sec><p>Water is H<sub>2</sub>O.</p></sec></body></article>"
)
print(XMLHelper.extract_nested_texts(root, ".//contrib[@contrib-type='author']/name", ["given-names", "surname"]))
pages = XMLHelper.extract_structured_fields(root, {"fpage": ".//fpage", "lpage": ".//lpage"})
print(XMLHelper.combine_page_range(pages["fpage"], pages["lpage"]))
print(XMLHelper.extract_flat_texts(root, ".//p"), XMLHelper.get_text_content(root.find(".//p")))
```

Output:

```text
['Jane Smith']
10-15
['Water is H'] Water is H2O.
```

`FullTextXMLParser` still has private wrappers that delegate to `XMLHelper` (`_get_text_content`, `_extract_flat_texts`, `_extract_nested_texts`, `_extract_with_fallbacks`, `_extract_structured_fields`, `_combine_page_range`, `_extract_inline_elements`, `_get_text_without_inline_elements`, `_extract_reference_authors`, `_extract_section_structure`). They are kept for backward compatibility; new code should call `XMLHelper` or work inside a `BaseParser` subclass.

## BaseParser

`BaseParser(root=None, config=None)` stores `root` and `config` (`ElementPatterns()` by default) and provides:

| Member | Description |
|---|---|
| `_require_root()` | Raises `ParsingError(PARSE003)` when `root` is `None` |
| `extract_elements_by_patterns(...)` | Same as the public parser method |
| `_own_bodies(root)` | The `<body>` elements of the article itself, not of `<sub-article>`s |
| `_child_sections(parent)` | The outermost `<sec>` elements below `parent` |
| `_section_own_elements(section, *tags, stop_at=())` | Descendants with the given tags that no nested `<sec>` (or `stop_at` element) owns |
| `_text_excluding(element, *skip_tags)` | Full text without the named subtrees |
| `_get_text_content`, `_extract_flat_texts`, `_extract_structured_fields`, `_extract_with_fallbacks` | Wrappers around `XMLHelper` |

Use `_own_bodies()` and `_section_own_elements()` rather than `.//body` and `.//p`: the shortcuts pick up sub-article bodies and duplicate the text of subsections.

Two modules in `utils/` lay out what the renderings share:

| Function | Description |
|---|---|
| `table_grid.build_table_grid(table, cell_text=None)` | Places the cells of a `<table>` by their `colspan` and `rowspan`; `extract_tables()`, the structured `table` block and the flat renderings all read the result |
| `flat_blocks.iter_flat_blocks(container)` | The blocks a section, `<body>` or `<app>` owns, in document order: paragraphs (cut where a table, figure, formula, list or listing sits inside a `<p>`), lists, definition lists, tables, figures, supplementary items, formulas and code. `to_plaintext()`, `to_markdown()` and `get_full_text_sections()` render from it, so each element is rendered once and by the block that owns it |
| `flat_blocks.escape_markdown(text)` | Escapes the characters that change what a Markdown renderer does with text |

## Add an extraction

1. If the XPath patterns should be configurable, add them to a group in `ElementPatterns` (each field is a `dict[str, list[str]]` with a default factory).
2. Implement the extraction in the matching `BaseParser` subclass, or a new one in `parsers/`, using `XMLHelper`; call `self._require_root()` first.
3. Expose it on `FullTextXMLParser` through a lazy property and a public method that calls `_require_root()` and, like `extract_tables()`, wraps unexpected errors in `ParsingError(ErrorCodes.PARSE003, {...})`.
4. Add unit tests under `tests/features/fulltext/unit/` or `tests/features/fulltext/parsers/`, and checks against real documents in `tests/features/fulltext/real_data/`, which use the articles in `tests/fixtures/fulltext_downloads/`.
5. Document the method and its return shape in `docs/api/xml-parser.md`.

## Tests

`pytest` deselects tests marked `slow`, `functional`, `network`, `benchmark` and `e2e` by default (`addopts` in `pyproject.toml`). The real-XML extension tests in `tests/extensions/test_functional_real_xml.py` are marked `functional`; run them with `pytest -m functional tests/extensions/test_functional_real_xml.py`.
