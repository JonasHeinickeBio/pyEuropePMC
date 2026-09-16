# XML parsing

`FullTextXMLParser` reads a Europe PMC full-text article in JATS XML and extracts its metadata, authors, tables, figures, references and sections, or renders it as plain text or Markdown. This page shows the common tasks; the [FullTextXMLParser reference](../../api/xml-parser.md) lists every method and every returned key.

## Get the XML

The examples on this page read the full text of article PMC3258128 from a file. Download it once:

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    path = client.download_xml_by_pmcid("PMC3258128", output_path="PMC3258128.xml")
print(path)
```

Output:

```text
PMC3258128.xml
```

`client.get_fulltext_content("PMC3258128")` returns the same XML as a string instead. See [Full-text retrieval](../fulltext/README.md).

## Parse a document

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser

xml_content = Path("PMC3258128.xml").read_text(encoding="utf-8")
parser = FullTextXMLParser(xml_content)
print(parser.root.tag)
```

Output:

```text
article
```

The examples below continue with this `parser`.

- `FullTextXMLParser(xml_content=None, config=None)` accepts a string or an `xml.etree.ElementTree.Element`. Without content, call `parser.parse(xml_content)` before extracting anything. The parser does not read files; pass the file's text, or use `parse_xml_file()` from the [extensions](../../api/xml-parser-extensions.md#local-processing).
- Strings are parsed with [defusedxml](https://pypi.org/project/defusedxml/). A `<!DOCTYPE>` is accepted as long as it declares no entities; the external DTD that Europe PMC documents reference is not loaded. A document that declares an entity, internal or external, is refused.
- If the root element declares a default namespace, as schema-based JATS does, that namespace is removed from the tags so the same lookups work. Prefixed namespaces such as `xlink:` and `mml:` are kept. An `Element` you pass in is used as it is, without this step.
- Parsing the same text again creates a new tree; reuse one parser for all extractions on a document.

### Parse errors

Every failure raises `ParsingError` from `pyeuropepmc.core.exceptions`:

```python
from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.core.exceptions import ParsingError

for document in ["<article><p>", '<!DOCTYPE article [<!ENTITY x "y">]><article/>', b"<article/>"]:
    try:
        FullTextXMLParser(document)
    except ParsingError as error:
        cause = type(error.__cause__).__name__ if error.__cause__ else None
        print(error.error_code.value, cause)
```

Output:

```text
PARSE002 ParseError
PARSE005 EntitiesForbidden
PARSE003 None
```

| Input | Error code | `__cause__` |
|---|---|---|
| Malformed XML, including an undeclared named entity such as `&alpha;` | `PARSE002` | `xml.etree.ElementTree.ParseError` |
| A DOCTYPE that declares an entity | `PARSE005` | `defusedxml.EntitiesForbidden` |
| `None`, an empty string, `bytes` or another type | `PARSE003` | none |
| Calling an extraction method before anything was parsed | `PARSE003` | none |

`ParsingError` derives from `PyEuropePMCError`, not from `xml.etree.ElementTree.ParseError`, so `except ParseError` does not catch it; catch `ParsingError` instead. Every entry point that parses XML raises it the same way, and the message names the cause: which entity a refused document declares, or the line and column of a malformed one. Numeric character references such as `&#x0003c;` parse normally.

## Metadata, authors and affiliations

```python
metadata = parser.extract_metadata()
print(metadata["title"])
print(metadata["authors"][:2], metadata["journal"]["title"], metadata["pub_date"])
print(metadata["doi"], metadata["pmcid"], metadata.get("pmid"))
```

Output:

```text
Hepato-specific microRNA-122 facilitates accumulation of newly synthesized miRNA through regulating PRKRA
['Shuai Li', 'Juanjuan Zhu'] Nucleic Acids Research 2012-01
10.1093/nar/gkr715 3258128 None
```

`extract_metadata()` returns a dict. These keys are always present, with `None` or an empty value when the article lacks them: `title`, `abstract`, `authors` (a list of name strings), `journal` (a dict with `title`, `volume`, `issue` and, when present, ISSNs, publisher and journal IDs), `pub_date` (a string such as `"2012-01"`), `doi`, `pmcid` (as written in the XML, with or without the `PMC` prefix), `volume`, `issue`, `pages`, `elocation_id` and `keywords`. Other keys, such as `pmid`, `identifiers`, `license`, `copyright`, `publisher`, `funding`, `categories`, `history`, `correspondence`, `self_uri`, `counts` and `extended_metadata`, appear only for some articles, so read them with `.get()`. The [reference](../../api/xml-parser.md#extract_metadata) describes every key.

Separate methods return single parts of the front matter:

```python
print(parser.extract_authors_detailed()[0])
print(sorted(parser.extract_affiliations()[0]))
print(parser.extract_pub_date(), parser.extract_license()["url"], parser.extract_publisher())
```

Output:

```text
{'given_names': 'Shuai', 'surname': 'Li', 'full_name': 'Shuai Li', 'affiliation_refs': ['gkr715-AFF1'], 'orcid': None}
['id', 'institution_text', 'markers', 'parsed_institutions', 'text']
2012-01 http://creativecommons.org/licenses/by-nc/3.0 {'name': 'Oxford University Press'}
```

The keys of an affiliation depend on how it is tagged: tagged affiliations have `institution`, `city`, `country` and sometimes `institutions` and `institution_ids`; untagged ones, like these, have `markers`, `institution_text` and `parsed_institutions`. `extract_keywords()`, `extract_funding()` and `extract_article_categories()` return the corresponding metadata values.

Front matter is read from the article's own `<front>`, never from the whole document: a peer-review `<sub-article>` has authors, affiliations and keywords of its own, a `<related-article>` in `<article-meta>` carries the companion paper's pagination, and every reference has a `<volume>`, an `<fpage>` and an `<lpage>`. `extract_affiliations()` additionally leaves out the affiliations of the editors, which are told apart by which `<contrib>` elements cite them.

## Tables

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser

plos = FullTextXMLParser(Path("PMC13567752.xml").read_text(encoding="utf-8"))
table = plos.extract_tables()[0]
print(table["id"], table["label"], table["caption"])
print(table["headers"], len(table["rows"]), table["rows"][0])
```

Output:

```text
pone.0357759.t001 Table 1 Powder metallurgy steps employed.
['Steps', 'Details'] 9 ['Milling Method', 'Ball milling (RETSCH PM400)']
```

Each table is a dict with `id`, `label`, `caption`, `footer` (text of the table footnotes, or `None`), `headers`, `header_rows`, `rows`, `spans` and `cell_graphics`, plus `column_groups` when the table has `<colgroup>` markup.

- `headers` has one label per column. A header of several rows is combined top to bottom, and a header cell spanning several columns labels each of them. It is `[]` when the table has no header row. Header cells tagged `<td>`, which many journals use, count.
- `header_rows` and `rows` hold the header rows and the body rows as strings, every row as wide as the table. A cell spanning several positions has its text at the top-left one and `""` at the others, so each value stays under its own header.
- `spans` lists the cells that span, as `{"row", "column", "rowspan", "colspan"}` with `row` counting the header rows first; `cell_graphics` lists images inside cells. A cell holding nothing but an image reads `"[graphic: <file>]"`.

A table with a three-row header:

```python
table = plos.extract_tables()[2]
print(table["headers"][:3])
print(table["header_rows"][1][:3], table["spans"][0])
```

Output:

```text
['Std', 'Run', 'Inputparameter 1 / A: Composition / wt.%']
['', '', 'A: Composition'] {'row': 0, 'column': 0, 'rowspan': 3, 'colspan': 1}
```

To load a table into pandas, allow for empty headers:

```python
import pandas as pd

for table in plos.extract_tables()[:2]:
    frame = pd.DataFrame(table["rows"], columns=table["headers"] or None)
    print(table["label"], frame.shape)
```

Output:

```text
Table 1 (9, 2)
Table 2 (3, 6)
```

## Figures and assets

```python
figures = parser.extract_figures()
print(len(figures), figures[0]["id"], figures[0]["label"], figures[0]["graphic_uri"])
print(figures[0]["caption"][:60])
```

Output:

```text
5 gkr715-F1 Figure 1. gkr715f1
Affinity purification with biotin-tagged miR-122 from human
```

Each figure is a dict with `id`, `label`, `caption` and, when the figure has a `<graphic>`, `graphic_uri`: the file name from the XML, not a URL. `graphic_uri` is the figure's own graphic - the one it carries directly, or in an `<alternatives>` of its own - not the first image anywhere beneath it, which can be an inline formula inside the caption. A figure supplement, a `<fig>` nested in another, also carries `parent_id` and `parent_label`.

`ImageFetcher` from the extensions turns those file references into Europe PMC download URLs, and can download them:

```python
from collections import Counter

from pyeuropepmc.features.fulltext.extensions import ImageFetcher

assets = ImageFetcher(parser.root, article_id="PMC3258128").extract_asset_refs()
print(len(assets), Counter(a.asset_type.value for a in assets))
print(assets[0].label, assets[0].uri)
```

Output:

```text
9 Counter({'figure': 5, 'supplementary': 4})
Figure 1. https://europepmc.org/api/fulltextRepo?pmcId=PMC3258128&type=FILE&fileName=gkr715f1.jpg&mimeType=image%2Fjpeg&version=1
```

There is one `AssetRef` per file, in document order, typed by the block that owns it (`figure`, `table`, `supplementary`, `formula`, `video`, `audio`, `unknown`) and carrying that block's label and caption. `metadata["file_name"]` is the file as Europe PMC stores it, `metadata["alternative"]` marks the second and later representations of one figure, and a figure supplement's asset carries `metadata["parent_id"]` and `metadata["parent_label"]`. The URL is the one Europe PMC's own article pages load; `article_id` must be a PMCID, and with anything else `uri` stays the file name from the XML.

`FigureExtractor` in `pyeuropepmc.features.fulltext` reads the same blocks straight from an XML string or from Europe PMC:

```python
from pyeuropepmc.features.fulltext import FigureExtractor

items = FigureExtractor().extract_from_xml(xml_content, pmcid="PMC3258128")
print(len(items), Counter(i.figure_type for i in items))
print(items[0].label, items[0].file_name, items[0].mime_type)
```

Output:

```text
6 Counter({'figure': 5, 'supplement': 1})
Figure 1. gkr715f1.jpg image/jpeg
```

Each `FigureInfo` has `id`, `label`, `caption`, `alt_text`, `figure_type` (`figure`, `table` or `supplement`), `file_name`, `mime_type`, `image_url`, and `parent_id`/`parent_label` for a figure supplement. `extract(pmcid=...)`, `extract(pmid=...)` or `extract(doi=...)` fetches the XML first. Without a PMCID there is no `image_url`, since the download endpoint is addressed by PMCID.

## References

```python
references = parser.extract_references()
print(len(references))
print(references[0])
```

Output:

```text
47
{'id': 'gkr715-B1', 'label': '1', 'citation_type': 'element-citation', 'authors': 'Bartel, DP', 'title': 'MicroRNAs: genomics, biogenesis, mechanism, and function', 'source': 'Cell', 'year': '2004', 'volume': '116', 'pages': '281-297', 'doi': None, 'pmid': '14744438', 'pmcid': None}
```

Each reference has `id`, `label`, `citation_type` (`element-citation` or `mixed-citation`), `authors`, `title`, `source` (journal or book), `year`, `volume`, `pages`, `doi`, `pmid` and `pmcid`; missing values are `None`. Some references also carry `raw_citation`. `authors` is a single string, not a list.

## Sections

`get_full_text_sections()` returns the body as a flat list of `{"title", "content"}` dicts, where `content` is the section's own blocks as plain text, in document order, joined by blank lines:

```python
sections = parser.get_full_text_sections()
print(len(sections), [s["title"] for s in sections[:4]])
print(sections[0]["content"][:70])
print([s["type"] for s in sections if "type" in s])
```

Output:

```text
23 ['INTRODUCTION', 'MATERIALS AND METHODS', 'Cell lines and cultures', 'Affinity purification experiments']
MicroRNAs (miRNAs) are small conserved RNAs of ∼22 nt which negatively
['author_notes']
```

- There is one entry per `<sec>` in the article's own body, in document order; a subsection is a separate entry, and a section that only contains subsections has empty `content`. The list gives no nesting information.
- Content that sits directly in `<body>`, outside any `<sec>`, forms one untitled entry placed after all sections.
- Figures and tables kept in `<floats-group>` form an entry titled `Figures and Tables` after that, with no `type` key.
- Back matter follows, with a third key `type`: `author_notes`, `acknowledgments`, `appendix` or `glossary`.
- A block is rendered as in `to_plaintext()`: a figure as its label and caption on one line, a table as its label and caption followed by one line per row, a display formula followed by its label, a code listing with its line breaks, and a list or definition list one item per line. A table, figure, formula, list or listing inside a `<p>` splits that paragraph where it stands.

### Structured sections

`get_full_text_sections_structured()` keeps the document structure: each section holds typed content blocks.

```python
structured = parser.get_full_text_sections_structured()
for section in structured[:3]:
    print(section["section_type"], "|", section["title"], "|", section.get("section_path"),
          [block["type"] for block in section["content"]][:3])

body = [section for section in structured if section["section_type"] == "body"]
first_paragraph = body[0]["content"][0]
print(sorted(first_paragraph))
```

Output:

```text
front | Article Title | Article Title ['heading']
front | Abstract | Abstract ['paragraph']
body | INTRODUCTION | INTRODUCTION ['paragraph', 'paragraph', 'paragraph']
['inlines', 'schema_version', 'text', 'type']
```

The method returns a list of dicts (`StructuredSection.to_dict()`), in this order:

1. A section titled `Article Title` with `section_type` `"front"`, holding the title as a `heading` block.
2. A section titled `Abstract` with `section_type` `"front"`.
3. One section per `<sec>` in the body, with `section_type` `"body"`. Nested sections are separate entries; `section_path` joins the titles with `/`, for example `"Results/Gene mutation prediction"`. Paragraphs directly in `<body>` form an untitled section with `section_path` `"body"`.
4. When the article keeps figures and tables in `<floats-group>`, outside `<body>` - every NIH author manuscript does - a section titled `Figures and Tables`, also with `section_type` `"body"`, holding a block for each.
5. Back matter such as footnotes, notes and references, with `section_type` `"back"`, and appendices with `"appendix"`. A reference list placed inside `<body>`, as some BioMed Central articles do, is given here once, as References, and not in the body section that holds it.

Filter on `section_type == "body"` to get the main text only.

Each block is a dict with `type` and `schema_version`, plus the fields that apply and are not empty:

| Block `type` | Fields |
|---|---|
| `heading` | `text` |
| `paragraph` | `text`; `inlines`, a list of `{type, text, position, length}` dicts for cross-references and formatting, with `ref_type` and `target_id` for cross-references. A reference in the References section is one paragraph - its label, then its citation (the `<mixed-citation>` when there is one) - with `target_id` set to the `<ref>`'s `id`, so a cross-reference's `target_id` finds it |
| `list` | `items`, `list_type`; `inlines` whose `metadata["item"]` names the item their position indexes |
| `table` | `label`, `caption`, `rows` (header rows first, laid out as in `extract_tables()`), `text` (label, caption, cells and footer in one string), `inlines` (positions in `text`), `metadata` (`header_rows`, the number of header rows; `footer`; and when present `spans`, `cell_graphics` and `cell_inlines`, the inline elements of each cell as `{row, column, inlines}`) |
| `figure` | `label`, `caption`, `uri`, `target_id`, `inlines` |
| `formula` | `text` (the expression as plain text), `tex` (LaTeX), `label`, `mathml`, `uri` |
| `code`, `quote`, `boxed_text` | `text` |
| `definition_list` | `definition_terms` |
| `unknown_block` | `jats_tag`, `text` for elements without a dedicated block type |

A `<table-wrap>`, `<table>`, `<fig>` or `<disp-formula>` inside a `<p>` becomes its own block: the paragraph is split into a paragraph block with the text before it, the table, figure or formula block, and a paragraph block with the text after it. In PMC12311175, for example, the section "Tumor-induced immune suppression" contains a paragraph, then a `figure` block labelled `Fig. 1`, then the rest of the paragraph.

A `formula` block carries the expression three ways: `text` is the plain text as a reader sees it, `tex` is LaTeX converted from the MathML (or the document's own `<tex-math>` when it ships one), and `mathml` is the MathML itself, serialized in the MathML namespace. `label` holds the equation number, which is kept out of `text`. `to_plaintext()`, `to_markdown()` and `get_full_text_sections()` render a display formula on a line of its own, after the section's paragraphs, as the expression followed by its label.

For `StructuredSection` and `ContentBlock` objects instead of dicts, with methods to split sections into chunks for retrieval, use `ContentBlockExtractor`; see [Content blocks](../../api/xml-parser-extensions.md#content-blocks).

## Plain text and Markdown

```python
text = parser.to_plaintext()
print(text[:150])

markdown = parser.to_markdown()
print([line for line in markdown.splitlines() if line.startswith("#")][:4])
```

Output:

```text
Hepato-specific microRNA-122 facilitates accumulation of newly synthesized miRNA through regulating PRKRA

Authors: Shuai Li, Juanjuan Zhu, Hanjiang F
['# Hepato-specific microRNA-122 facilitates accumulation of newly synthesized miRNA through regulating PRKRA', '## Abstract', '## INTRODUCTION', '## MATERIALS AND METHODS']
```

`to_plaintext()` returns, separated by blank lines: the title; `Authors: ...`; `Abstract` and its text; each body section's title and its blocks in document order; the content outside any section; `Figures and Tables` followed by the figures and tables of `<floats-group>`; then `Acknowledgments`, `Author Notes`, `Appendix: <title>` (with the appendix's blocks and sections) and `Glossary` blocks. Blocks are written as follows:

- a paragraph as its text; a table, figure, formula, list or listing inside it splits it where it stands;
- a list one item per line, prefixed with `• `, or `1. ` for `list-type="order"`; an item with its own label gets no prefix;
- a table as its label and caption (`Table: <caption>` when it has no label), one line per row with the non-empty cells joined by ` | `, then its footnotes;
- a figure or supplementary item as its label, caption and any other text on one line;
- a display formula as its text followed by its label, and a code listing with its line breaks and indentation.

`to_markdown()` returns the title as `#`, `**Authors:**`, `**Journal:**` and `**DOI:**` lines, `## Abstract`, the content outside any section, the body sections as `##` headings with subsections one level deeper, `## Figures and Tables` for `<floats-group>`, and `## Acknowledgments`, `## Author Notes`, `## Appendix: <title>` and `## Glossary` sections. Within a section the blocks come in document order: a table as a `**label** caption` line and a GitHub-style pipe table (with an empty header row when the table has none), a figure as `**label** caption`, a list as `- ` or `1. ` items, and a code listing as a fenced block tagged with its `language`. All text taken from the document is escaped with a backslash wherever a character would change how Markdown renders it: the backslash, the backtick, `*`, `_`, `[`, `]`, `<`, `>`, `~`, `|` and `$` anywhere, and `#`, `+`, `-` or a number followed by `.` or `)` at the start of a paragraph. Code listings are not escaped.

## Inspect the document structure

```python
print(parser.detect_schema())
print(len(parser.list_element_types()))
coverage = parser.validate_schema_coverage()
print(coverage["total_elements"], coverage["recognized_count"], round(coverage["coverage_percentage"], 1))
print(coverage["unrecognized_elements"][:3], coverage["element_frequency"]["p"])
```

Output:

```text
DocumentSchema(has_tables=False, has_figures=True, has_supplementary=True, has_acknowledgments=False, has_funding=False, citation_types=['element-citation'], table_structure='jats')
72
72 62 86.1
['article-meta', 'fax', 'fn'] 38
```

- `detect_schema()` returns a `DocumentSchema` describing which structures the document contains.
- `list_element_types()` returns the sorted tag names used in the document.
- `validate_schema_coverage()` compares those tag names with the parser's pattern configuration. `total_elements` counts distinct tag names, not elements; `recognized_elements` and `unrecognized_elements` are sorted lists of tag names; `element_frequency` maps each tag name to its number of occurrences. A tag counts as recognized if it appears in the configuration, which does not guarantee its content is extracted.

The [XML element types](../../reference/xml_element_types_documentation.md) page explains the elements of a typical Europe PMC article.

## Custom element patterns

The parser finds elements through the XPath patterns in an `ElementPatterns` configuration. Each field is a `dict[str, list[str]]`; a field you pass replaces that whole group of defaults.

```python
from pyeuropepmc import ElementPatterns, FullTextXMLParser

print(ElementPatterns().citation_types)
config = ElementPatterns(citation_types={"types": ["element-citation", "mixed-citation"]})
custom = FullTextXMLParser(xml_content, config=config)
print(len(custom.extract_references()))
```

Output:

```text
{'types': ['element-citation', 'mixed-citation', 'nlm-citation', 'citation']}
47
```

For one-off lookups, `extract_elements_by_patterns()` takes a dict of names and ElementTree XPath expressions and returns a dict of lists:

```python
found = parser.extract_elements_by_patterns(
    {"doi": ".//article-id[@pub-id-type='doi']", "supplementary": ".//supplementary-material//title"},
    first_only=True,
)
print(found)
graphics = parser.extract_elements_by_patterns(
    {"graphic": ".//fig/graphic"},
    return_type="attribute",
    get_attribute={"graphic": "{http://www.w3.org/1999/xlink}href"},
)
print(graphics["graphic"][:2])
```

Output:

```text
{'doi': ['10.1093/nar/gkr715'], 'supplementary': ['Supplementary Data']}
['gkr715f1', 'gkr715f2']
```

## Parse many files

`parse_xml_directory()` from the extensions returns a parser for each XML file in a directory, and `BatchProcessor` parses files concurrently:

```python
from pathlib import Path

from pyeuropepmc.features.fulltext.extensions import BatchProcessor

paths = sorted(str(path) for path in Path(".").glob("PMC*.xml"))
result = BatchProcessor(max_workers=4).process_files(
    paths, extraction_fn=lambda p: {"title": p.extract_metadata()["title"]}
)
print(len(result.successes), len(result.failures))
```

Output:

```text
6 0
```

See [Batch processing](../../api/xml-parser-extensions.md#batch-processing) and [Local processing](../../api/xml-parser-extensions.md#local-processing).

## Extensions

The `pyeuropepmc.features.fulltext.extensions` package adds nine modules; the [extensions reference](../../api/xml-parser-extensions.md) documents them.

| Module | Main classes and functions | Purpose |
|---|---|---|
| Content blocks | `ContentBlockExtractor`, `StructuredSection`, `ContentBlock` | Typed blocks behind `get_full_text_sections_structured()`, with chunking for retrieval |
| Peer review | `PeerReviewExtractor` | Review reports and author responses from `<sub-article>` elements |
| MathML | `MathMLConverter` | MathML elements to LaTeX |
| JATS4R | `JATS4RValidator` | Checks against JATS4R recommendations, with a score |
| Batch processing | `BatchProcessor` | Parse many files or strings in threads |
| Assets | `ImageFetcher` | Figure, supplementary and media file references; downloads |
| Reference resolution | `ReferenceResolver` | Look up cited works in Europe PMC |
| Local processing | `parse_xml_file`, `parse_xml_directory`, `LocalXMLProcessor` | Parse files and directories |
| Pydantic helpers | `dataclass_to_pydantic`, `PydanticModelGenerator` | Pydantic models from dataclasses or sample data |

For normalized text for text mining, with canonical section types and BioC output, see [JATS normalization](jats-normalization.md).

## Known limitations

These were found by checking the parser's output against the source XML of real Europe PMC articles.

- **Floats outside the body.** Figures and tables in `<floats-group>` are gathered under `Figures and Tables` after the body, not placed where the text first cites them.
- **Display formulas.** The `text` of a formula block is the flattened MathML, so subscripts and superscripts become plain characters (x² reads "x2"); `tex` carries the structure. `to_plaintext()`, `to_markdown()` and `get_full_text_sections()` render that flattened text, not the LaTeX.
- **Tables.** A spanning cell's text appears once, at its top-left position; the positions it covers are `""`, not filled with its value, so fill them yourself where a value applies to every row it spans. A Markdown pipe table cannot express a span, so there a spanning cell stands in its first column only.
- **Figures.** A figure whose graphic sits neither directly under the `<fig>` nor in an `<alternatives>` of its own - inside a `<disp-formula>`, say - has no `graphic_uri`, rather than the wrong one.
- **Metadata.**
  - Only the first `<abstract>` is used, so author summaries and digests are missing.
  - `extract_funding()` reports one recipient as `recipient_full`; the rest are in `recipients`.
  - An affiliation's address is split by heuristics, so `city`, `postal_code` and `country` are often wrong for markup that does not tag them.
- **References.**
  - `authors` is one string that cannot always be split into people; PLOS references run surname and initials together ("NewtonSI"), and collaboration authors are dropped.
  - `title` falls back to `source` for software and some books.
  - A pass over the flattened citation text can overwrite correctly tagged pages or DOIs.
- **Structured sections.**
  - Front-matter `<notes>` are typed `back`. The `peer_review` section type is produced only by `PeerReviewExtractor`; `get_full_text_sections_structured()` leaves sub-articles out.
  - Appendix sections have no `section_path`, and a path is ambiguous when a title contains `/`.
- **Text renderings.** `to_plaintext()`, `to_markdown()` and `get_full_text_sections()` render the title of a `<boxed-text>` or `<disp-quote>` and the `<label>` of a section or footnote as nothing, and a `<ref-list>` placed inside `<body>` not at all. `to_markdown()` renders a display formula as its flattened text rather than LaTeX, and emphasis, sub- and superscripts as plain text.
- **Size and depth.** There are no size or depth limits; a document nested a few thousand levels deep fails in section extraction with `ParsingError`.

## See also

- [FullTextXMLParser reference](../../api/xml-parser.md)
- [XML parser extensions](../../api/xml-parser-extensions.md)
- [JATS normalization](jats-normalization.md)
- [Full-text retrieval](../fulltext/README.md)
- [Full-text index](../fulltext-index.md): search parsed articles locally
