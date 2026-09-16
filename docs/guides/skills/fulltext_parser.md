# Full-text parser skill

Parse Europe PMC full-text XML and extract metadata, sections, tables, figures and references.

## Core parser

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(Path("PMC3258128.xml").read_text(encoding="utf-8"))

metadata = parser.extract_metadata()
print(metadata["title"])
print(", ".join(metadata["authors"][:3]))

plaintext = parser.to_plaintext()
markdown = parser.to_markdown()
tables = parser.extract_tables()
figures = parser.extract_figures()
references = parser.extract_references()

body = [s for s in parser.get_full_text_sections_structured() if s["section_type"] == "body"]
print(len(figures), len(references), body[0]["title"])
```

Output:

```text
Hepato-specific microRNA-122 facilitates accumulation of newly synthesized miRNA through regulating PRKRA
Shuai Li, Juanjuan Zhu, Hanjiang Fu
5 47 INTRODUCTION
```

Key tips:

- Download the XML with `FullTextClient().download_xml_by_pmcid("PMC3258128")`, or get it as a string with `get_fulltext_content()`.
- `authors` is a list of name strings; `extract_authors_detailed()` gives dicts with ORCIDs and affiliation IDs.
- Table dicts have `headers` and `rows`; `headers` is `[]` when the header cells are not `<th>`.
- Reference dicts use `source` for the journal and a single `authors` string.
- `get_full_text_sections()` returns flat `{title, content}` dicts; `get_full_text_sections_structured()` returns typed blocks and starts with two `front` sections (title and abstract), so filter on `section_type == "body"`.
- Errors raise `ParsingError` from `pyeuropepmc.core.exceptions`, not `xml.etree.ElementTree.ParseError`.

## Extension modules

```python
from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.features.fulltext.extensions import (
    BatchProcessor,
    ContentBlockExtractor,
    ImageFetcher,
    JATS4RValidator,
    MathMLConverter,
    PeerReviewExtractor,
    parse_xml_file,
)

parser = parse_xml_file("PMC13567752.xml")
sections = ContentBlockExtractor(parser.root).extract_sections()      # StructuredSection objects
report = JATS4RValidator(parser.root).validate()                      # report.score, report.findings
reviews = PeerReviewExtractor(parser.root).extract_peer_reviews()     # one PeerReviewSet
assets = ImageFetcher(parser.root, article_id="PMC13567752").extract_asset_refs()

math_parser = parse_xml_file("PMC12738713.xml")
math = math_parser.root.find(".//mml:math", FullTextXMLParser.NAMESPACES)
latex = MathMLConverter().convert(math)                               # takes an Element

batch = BatchProcessor(rate_limit=5).process_files(["PMC3258128.xml", "PMC13567752.xml"])
print(len(sections) > 0, round(report.score, 2), len(reviews.reviews), batch.success_rate)
```

Output:

```text
True 0.2 7 1.0
```

Key tips:

- All extensions are importable from `pyeuropepmc.features.fulltext.extensions`.
- `BatchProcessor` also has `process_xml_strings([(identifier, xml), ...])` and `process_directories([...])`.
- `ReferenceResolver().resolve_batch(parser.extract_references())` looks references up in Europe PMC (network).
- `FigureExtractor` finds no figures in Europe PMC XML; use `parser.extract_figures()`.
- See [XML parsing](../../features/parsing/README.md) and the [extensions reference](../../api/xml-parser-extensions.md).
