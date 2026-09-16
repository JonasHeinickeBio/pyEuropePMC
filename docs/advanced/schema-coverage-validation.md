# Schema coverage validation

`FullTextXMLParser.validate_schema_coverage()` lists the element types that occur in a parsed XML document and splits them into those that the parser's `ElementPatterns` configuration recognises and those it does not. Use it to find document structures the parser ignores and to check a custom configuration.

## Check a document

```python
from pyeuropepmc import FullTextXMLParser

xml = """<article>
  <front><article-meta><title-group><article-title>Example</article-title></title-group></article-meta></front>
  <body><sec><title>Methods</title><p>Text with <named-content content-type="gene">BRCA1</named-content>.</p></sec></body>
</article>"""

parser = FullTextXMLParser(xml)
coverage = parser.validate_schema_coverage()

print(f"{coverage['coverage_percentage']:.1f}% of {coverage['total_elements']} element types recognised")
print(coverage["unrecognized_elements"])
```

Output:

```text
80.0% of 10 element types recognised
['article-meta', 'title-group']
```

The parser must hold a document, passed to the constructor or to `parse()`; otherwise the method raises `ParsingError`.

## Return value

| Key | Type | Meaning |
|---|---|---|
| `total_elements` | `int` | Number of distinct element names in the document, not occurrences. |
| `recognized_elements` | `list[str]` | Sorted names that the configuration recognises. |
| `unrecognized_elements` | `list[str]` | Sorted names that it does not recognise. |
| `recognized_count` | `int` | Length of `recognized_elements`. |
| `unrecognized_count` | `int` | Length of `unrecognized_elements`. |
| `coverage_percentage` | `float` | `recognized_count / total_elements * 100`. |
| `element_frequency` | `dict[str, int]` | Occurrences of each element name. |

Namespace URIs are removed from tag names before counting. The result is computed again on every call; `detect_schema()` caches its own `DocumentSchema`, which this method does not use.

## Rank unrecognised elements

This block continues from the previous example:

```python
unrecognized = sorted(
    ((name, coverage["element_frequency"][name]) for name in coverage["unrecognized_elements"]),
    key=lambda item: item[1],
    reverse=True,
)
for name, count in unrecognized[:10]:
    print(f"{name:30s} {count:5d}")
```

## A real document

For `tests/fixtures/fulltext_downloads/PMC3258128.xml`, the current configuration recognises 62 of 72 element types (86.1%). The unrecognised types are:

| Element | Occurrences |
|---|---:|
| `funding-source` | 4 |
| `article-meta`, `fax`, `fn`, `journal-meta`, `journal-title-group`, `license`, `license-p`, `phone`, `title-group` | 1 each |

These numbers change whenever the patterns change.

## What counts as recognised

An element is recognised if its name appears in one of these `ElementPatterns` groups or in a fixed list of structural elements:

- every pattern group of the configuration: `citation_types`, `author_element_patterns`, `author_field_patterns`, `journal_patterns`, `article_patterns`, `table_patterns`, `reference_patterns`, `inline_element_patterns`, `xref_patterns`, `media_patterns`, `object_id_patterns`, `math_patterns`, `formatting_patterns`, `extended_metadata_patterns`, `content_structure_patterns`, `award_patterns` and `appendix_patterns`;
- the structural elements `article`, `front`, `body`, `back`, `sec`, `p`, `title`, `ref-list`, `ref`, `fig`, `graphic`, `label`, `caption`, `supplementary-material`, `ack`, `funding-group`, `aff`, `name`, `contrib`, `contrib-group`, `author-notes`, `pub-date`, `addr-line`, `xref`, `person-group`, `etal`, `media`, `underline`, `month`, `day`, `object-id`, `disp-quote`, `notes`, `history`, `pub-history`, `copyright-statement`, `copyright-year`, `corresp`, `self-uri`, `kwd-group`, `institution-wrap`, `page-count`, `figure-count`, `table-count`, `equation-count`, `word-count`, `counts` and `email`.

A pattern written with a namespace prefix, such as `.//mml:math` in `math_patterns`, contributes the local name (`math`), because tag names are compared with their namespace removed.

## Add a pattern

`ElementPatterns` is a dataclass, and each instance has its own pattern lists. This block continues from the first example:

```python
from pyeuropepmc import ElementPatterns, FullTextXMLParser

config = ElementPatterns()
config.inline_element_patterns["patterns"].append(".//named-content")

parser = FullTextXMLParser(xml, config=config)
print(parser.validate_schema_coverage()["unrecognized_elements"])  # ['article-meta', 'title-group']
```

`named-content` is already covered by `extended_metadata_patterns`, so this particular addition changes nothing; adding a pattern for an element no group mentions does move it into `recognized_elements`.

## Compare several documents

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser

rows = []
for path in sorted(Path("xml_files").glob("*.xml")):
    coverage = FullTextXMLParser(path.read_text(encoding="utf-8")).validate_schema_coverage()
    rows.append((path.name, coverage["coverage_percentage"], coverage["unrecognized_count"]))

for name, percentage, unrecognized_count in sorted(rows, key=lambda row: row[1])[:5]:
    print(f"{name}: {percentage:.1f}% ({unrecognized_count} unrecognised)")
```

## Example script and tests

[`examples/07-advanced-parsing/03-schema-coverage.py`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/examples/07-advanced-parsing/03-schema-coverage.py) runs the analysis on `examples/downloads/PMC3258128.xml` and prints recommendations. The tests are in `tests/test_flexible_parsing.py`:

```bash
pytest tests/test_flexible_parsing.py::TestSchemaCoverageValidation -v
```

## Related pages

- [XML parsing](../features/parsing/README.md)
