# XML parser extensions

The `pyeuropepmc.features.fulltext.extensions` package adds nine modules to `FullTextXMLParser`: content blocks, peer review, MathML conversion, JATS4R validation, batch processing, assets, reference resolution, local processing and Pydantic helpers. Everything on this page except `InlineElement` and the LinkML models is importable from `pyeuropepmc.features.fulltext.extensions`.

The examples read fixture articles from files named after their PMC ID; download them with `FullTextClient().download_xml_by_pmcid(...)` (see [Full-text retrieval](../features/fulltext/README.md)).

## Content blocks

`ContentBlockExtractor` produces the typed sections behind `FullTextXMLParser.get_full_text_sections_structured()`, as objects instead of dicts.

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.features.fulltext.extensions import ContentBlockExtractor

parser = FullTextXMLParser(Path("PMC3258128.xml").read_text(encoding="utf-8"))
sections = ContentBlockExtractor(parser.root).extract_sections()

introduction = next(s for s in sections if s.section_type == "body")
print(introduction.title, len(introduction.content), introduction.content[0].type.value)

chunks = introduction.to_chunks(max_tokens=200, overlap=20)
print(len(chunks), sorted(chunks[0]))
documents = introduction.to_langchain_documents(metadata={"pmcid": "PMC3258128"})
print(documents[0]["metadata"])
```

Output:

```text
INTRODUCTION 3 paragraph
5 ['chunk_index', 'estimated_tokens', 'section_path', 'section_type', 'text']
{'pmcid': 'PMC3258128', 'section_title': 'INTRODUCTION', 'section_type': 'body', 'block_type': 'paragraph', 'block_index': 0}
```

`ContentBlockExtractor(root=None, config=None)`; `extract_sections() -> list[StructuredSection]`. The section order and splitting rules are described in [Structured sections](../features/parsing/README.md#structured-sections).

### StructuredSection

| Field | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | required | Section title |
| `content` | `list[ContentBlock]` | `[]` | Blocks in document order |
| `section_type` | `str` | `"body"` | `"front"`, `"body"`, `"back"` or `"appendix"` |
| `section_path` | `str` | `""` | Titles from the top level down, joined by `/` |

| Method | Returns | Description |
|---|---|---|
| `to_dict()` | `dict` | `title`, `content` (block dicts), `section_type`, `schema_version` (`"0.2.0"`), and `section_path` when not empty |
| `to_chunks(max_tokens=512, overlap=50, approx_chars_per_token=4)` | `list[dict]` | Block texts joined, in document order, into chunks of at most `max_tokens` tokens (estimated as characters divided by `approx_chars_per_token`); the trailing blocks of one chunk, up to `overlap` tokens, begin the next. Each chunk has `text`, `section_path` (the section's path, or its title when it has none), `section_type`, `chunk_index` and `estimated_tokens`. A block longer than `max_tokens` is split at sentence ends, and a sentence longer than that at spaces |
| `to_langchain_documents(metadata=None)` | `list[dict]` | One `{"page_content", "metadata"}` dict per block with text; metadata holds your `metadata` plus `section_title`, `section_type`, `block_type`, `block_index` and, when set, `label` |

### ContentBlock

| Field | Type | Default | Used by |
|---|---|---|---|
| `type` | `ContentBlockType` | required | all |
| `text` | `str` | `""` | paragraph, heading, code, quote, boxed text, table (flattened), unknown |
| `items`, `list_type` | `list[str]`, `str` | `[]`, `""` | list |
| `label`, `caption` | `str` | `""` | figure, table, formula |
| `uri`, `target_id` | `str` | `""` | figure, figure and table references |
| `rows` | `list[list[str]]` | `[]` | table |
| `tex`, `mathml` | `str` | `""` | formula |
| `uri` | `str` | `""` | figure, formula (the publisher's rendered image) |
| `language` | `str` | `""` | code |
| `definition_terms` | `list[dict[str, str]]` | `[]` | definition list: `{"term", "def"}` dicts |
| `jats_tag` | `str` | `""` | unknown block |
| `inlines` | `list[InlineElement]` | `[]` | paragraph, figure, table |
| `metadata` | `dict` | `{}` | type-specific extras |
| `parse_status` | `str` | `"success"` | `"success"`, `"partial"` or `"error"` |
| `quality_score` | `float` | `1.0` | completeness from 0 to 1 |
| `parser_notes` | `list[str]` | `[]` | diagnostics |
| `schema_version` | `str` | `"0.2.0"` | all |

`to_dict()` always writes `type` and `schema_version` and leaves out empty fields, `parse_status` when it is `"success"`, and `quality_score` when it is 1.0. The class attributes `LIST_TYPES`, `DEF_LIST_TYPES` and `RICH_TYPES` group the block types (`{LIST}`, `{DEFINITION_LIST}`, `{FIGURE, TABLE, FORMULA}`).

Factory class methods: `paragraph(text)`, `paragraph_with_inlines(text, inlines=None)`, `heading(text)`, `list_block(items, list_type="unordered")`, `definition_list(terms)`, `formula(tex, label="")`, `figure(label, caption, uri="", target_id="")`, `figure_ref(target_id, label="")`, `table_block(label, caption, text="", rows=None)`, `table_ref(target_id, label="")`, `code(text, language="")`, `boxed_text(text)`, `quote(text, inlines=None)` and `unknown_block(jats_tag, text="")`.

`ContentBlockType` values: `paragraph`, `list`, `formula`, `figure_ref`, `table_ref`, `code`, `boxed_text`, `heading`, `figure`, `table`, `quote`, `mathml`, `peer_review`, `definition_list`, `unknown_block`.

`InlineElement` (in `pyeuropepmc.features.fulltext.extensions.content_blocks`) has `type` (an `InlineElementType`: `xref`, `inline_formula`, `bold`, `italic`, `superscript`, `subscript`, `chemical_structure`, `named_content`, `strikethrough`, `underline`, `monospace`, `small_caps`, `roman`, `sans_serif`, `styled_content`, `unknown_inline`), `text`, `ref_type`, `target_id`, `position` and `length`, `formula_latex`, `language` and `metadata`. `position` and `length` are the character span in the block's `text`; for a block without `text`, such as a figure, in its `caption`; and in a list or definition list, in the item that `metadata` names: `{"item": i}` indexes `items`, `{"term": i}` and `{"definition": i}` the term and the definition of `definition_terms[i]`.

## Peer review

`PeerReviewExtractor` reads the `<sub-article>` elements that carry review materials.

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.features.fulltext.extensions import PeerReviewExtractor

parser = FullTextXMLParser(Path("PMC13567752.xml").read_text(encoding="utf-8"))
review_set = PeerReviewExtractor(parser.root).extract_peer_reviews()

print(len(review_set.reviews), sorted(review_set.revision_rounds))
for review in review_set.reviews[:3]:
    names = ", ".join(contributor["name"] for contributor in review.contributors) or "no names"
    print(review.revision_round, review.review_type.value, names)
```

`PeerReviewExtractor(root=None, config=None)`; `extract_peer_reviews() -> PeerReviewSet`.

- Only sub-articles whose `article-type` is `decision-letter`, `referee-report`, `editor-report`, `reviewer-report`, `author-comment`, `community-comment`, `aggregated-review-documents` (how PLOS publishes each round's decision letter with its reviews) or `reply` are read; others are skipped.
- The title comes from the sub-article's `<front-stub>`, `<front>` or `<article-meta>`.
- `sections` are read from the sub-article's own `<body>` as the article's body is: one section per `<sec>` at any depth, with its `section_path`, plus an untitled section for the content outside any `<sec>`, in document order. Every section has `section_type` `"peer_review"`.
- The revision round comes from a version number in the sub-article, or from a numbered footnote label, and is 1 otherwise.

| Class | Fields |
|---|---|
| `PeerReviewSet` | `article_id` (`str`), `reviews` (`list[PeerReviewMaterial]`), `revision_rounds` (`dict[int, list[PeerReviewMaterial]]`, sorted by round); `to_dict()` |
| `PeerReviewMaterial` | `review_type` (`PeerReviewType`), `title` (`str`), `contributors` (`list[dict]` with `name` and `type`), `sections` (`list[StructuredSection]`), `revision_round` (`int`, default 1), `metadata` (`dict`); `to_dict()` |
| `PeerReviewType` | `DECISION_LETTER`, `REFEREE_REPORT`, `EDITOR_REPORT`, `REVIEWER_REPORT`, `AUTHOR_COMMENT`, `COMMUNITY_COMMENT`, `AGGREGATED_REVIEW_DOCUMENTS`, `REPLY`, `UNKNOWN`; values are the JATS `article-type` strings |

## MathML to LaTeX

```python
from pathlib import Path

import defusedxml.ElementTree as DefusedET

from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.features.fulltext.extensions import MathMLConverter

converter = MathMLConverter()
element = DefusedET.fromstring(
    '<math xmlns="http://www.w3.org/1998/Math/MathML"><msub><mi>x</mi><mn>1</mn></msub></math>'
)
print(converter.convert(element), converter.convert_to_latex(element), MathMLConverter.convert_display_mathml(element))

parser = FullTextXMLParser(Path("PMC12738713.xml").read_text(encoding="utf-8"))
formula = parser.root.find(".//disp-formula")
math = formula.find(".//mml:math", FullTextXMLParser.NAMESPACES)
print(converter.convert(math)[:40])
```

Output:

```text
$x_{1}$ x_{1} $$x_{1}$$
$$\mathcal{L}_{P - T} = - \frac{1}{2N}\s
```

| Member | Returns | Description |
|---|---|---|
| `MathMLConverter(inline=None)` | – | `inline=True` or `False` forces `$` or `$$` delimiters; `None` decides per element |
| `convert(mathml_element)` | `str` | LaTeX wrapped in `$…$` when the element's `display` attribute is `"inline"` or missing, otherwise `$$…$$` |
| `convert_to_latex(mathml_element)` | `str` | LaTeX without delimiters |
| `convert_mathml(mathml_element)` | `str` | Class method: `convert()` with inline delimiters |
| `convert_display_mathml(mathml_element)` | `str` | Class method: `convert()` with display delimiters |
| `to_html(mathml_element)` | `str` | A `<span>` holding MathJax-style LaTeX, for example `<span class="math-inline">\({x}_{1}\)</span>` |
| `to_svg(mathml_element)` | `str` | SVG rendered with a system LaTeX installation and `dvisvgm` |

Every method takes an `Element`; a string raises `AttributeError`. Parse strings with `defusedxml.ElementTree.fromstring` first.

## JATS4R validation

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.features.fulltext.extensions import JATS4RValidator

parser = FullTextXMLParser(Path("PMC3258128.xml").read_text(encoding="utf-8"))
report = JATS4RValidator(parser.root).validate()

print(f"score {report.score:.2f}, {len(report.findings)} findings in {sorted(report.categories)}")
finding = report.findings[0]
print(finding.rule_id, finding.severity, finding.category)
```

Output:

```text
score 0.80, 16 findings in ['affiliations', 'authors', 'data_availability', 'funding']
AUTH-02 info authors
```

`JATS4RValidator(root=None, config=None)`; `validate() -> ValidationReport`. The validator checks authors, affiliations, the abstract, funding, citations, data availability, ORCID identifiers and peer review against [JATS4R](https://jats4r.org/) recommendations.

| Class | Fields and methods |
|---|---|
| `ValidationReport` | `findings` (`list[ValidationFinding]`), `score` (`float`), `categories` (`dict[str, list[ValidationFinding]]`); `add_finding(finding)`; `to_dict()` with `score`, `total_findings`, `errors`, `warnings`, `infos`, `categories` |
| `ValidationFinding` | `rule_id` (for example `"AUTH-02"`), `severity` (`"error"`, `"warning"` or `"info"`), `message`, `category` (`authors`, `affiliations`, `abstract`, `funding`, `citations`, `data_availability`, `orcid`, `peer_review`), `element_path`, `suggestion`; `to_dict()` |

`score` is 1.0 minus one tenth of the summed finding weights (error 1.0, warning 0.5, info 0.1), and never below 0.0. It counts findings rather than measuring a proportion: an article with many authors without ORCIDs collects one `info` finding per author and can reach 0.0.

## Batch processing

```python
from pathlib import Path

from pyeuropepmc.features.fulltext.extensions import BatchProcessor

processor = BatchProcessor(
    max_workers=2,
    rate_limit=50,
    progress_callback=lambda done, total, identifier: None,
)
result = processor.process_xml_strings(
    [("PMC3258128", Path("PMC3258128.xml").read_text(encoding="utf-8")), ("broken", "<article>")],
    extraction_fn=lambda parser: {"title": parser.extract_metadata()["title"]},
)
for item in sorted(result.results, key=lambda r: r.identifier):
    print(item.identifier, item.success, item.data or item.error[:8])
print(result.success_rate, sorted(result.to_dict()))
```

Output:

```text
PMC3258128 True {'title': 'Hepato-specific microRNA-122 facilitates accumulation of newly synthesized miRNA through regulating PRKRA'}
broken False [PARSE00
0.5 ['failures', 'results', 'success_rate', 'successes', 'total', 'total_duration']
```

`BatchProcessor(max_workers=4, rate_limit=3.0, progress_callback=None, error_callback=None)`:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_workers` | `int` | `4` | Threads |
| `rate_limit` | `float` | `3.0` | Each item waits `1 / rate_limit` seconds before it starts, in its own thread; values below 0.1 are raised to 0.1 |
| `progress_callback` | `Callable[[int, int, str], None] \| None` | `None` | Called with `(completed, total, identifier)` after each item |
| `error_callback` | `Callable[[str, Exception], None] \| None` | `None` | Called with `(identifier, exception)` when an item fails |

| Method | Input |
|---|---|
| `process_xml_strings(items, extraction_fn=None)` | `list[tuple[str, str]]` of `(identifier, xml)` |
| `process_files(file_paths, extraction_fn=None)` | `list[str]`; the identifier is the path |
| `process_directories(directories, glob_pattern="*.xml", extraction_fn=None)` | `list[str]` of directories, not searched recursively |

Each method returns a `BatchResult`. `extraction_fn` receives a `FullTextXMLParser` and returns a dict. Without it, each item's `data` holds `metadata`, `authors`, `sections` (flat), `references`, `figures`, `tables` and `funding`; a part that raises is left out.

| Class | Fields |
|---|---|
| `BatchResult` | `results` (`list[ProcessingResult]`, in completion order, not input order), `total_duration` (seconds); properties `successes`, `failures`, `success_rate`; `to_dict()` |
| `ProcessingResult` | `identifier`, `success`, `data` (`dict` or `None`), `error` (`str`), `duration` (seconds); `to_dict()` |

## Assets

`ImageFetcher` lists the files an article references and can download them.

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.features.fulltext.extensions import AssetFetchPolicy, ImageFetcher

parser = FullTextXMLParser(Path("PMC3258128.xml").read_text(encoding="utf-8"))
fetcher = ImageFetcher(parser.root, article_id="PMC3258128", download_dir="assets",
                       policy=AssetFetchPolicy.METADATA_ONLY)
refs = fetcher.extract_asset_refs()
print(len(refs), refs[0].to_dict()["asset_type"], refs[0].label)
print(refs[0].uri)
print(ImageFetcher.resolve_figure_uris(parser.extract_figures()[:1], "PMC3258128")[0]["graphic_uri"])
```

Output:

```text
9 figure Figure 1.
https://europepmc.org/api/fulltextRepo?pmcId=PMC3258128&type=FILE&fileName=gkr715f1.jpg&mimeType=image%2Fjpeg&version=1
https://europepmc.org/api/fulltextRepo?pmcId=PMC3258128&type=FILE&fileName=gkr715f1.jpg&mimeType=image%2Fjpeg&version=1
```

`ImageFetcher(root=None, article_id="", download_dir="", policy=AssetFetchPolicy.METADATA_ONLY)`:

| Method | Returns | Description |
|---|---|---|
| `extract_asset_refs()` | `list[AssetRef]` | One reference per file, in document order: every `<graphic>`, `<inline-graphic>` and `<media>`, typed and labelled by the block that owns it. A `<supplementary-material>` without such a child is read from its own `xlink:href`, or else from an `<object-id>` that holds a file name (never one typed as a DOI). A file declared twice is returned once. With a PMCID as `article_id`, `uri` is the Europe PMC download URL; otherwise it stays the file name from the XML |
| `download_assets(asset_refs)` | `list[AssetRef]` | Only with policy `DOWNLOAD` or `DOWNLOAD_MISSING` and a `download_dir`: downloads each `http` or `https` URI into `download_dir` under its file name and sets `local_path`. `DOWNLOAD_MISSING` skips assets whose `local_path` exists. Failures are logged. Returns the same list |
| `resolve_figure_uris(figures, article_id)` | `list[dict]` | Class method: rewrites relative `graphic_uri` values of `extract_figures()` results in place, to Europe PMC download URLs. Needs a PMCID; anything else leaves the file names alone |

| Class | Values or fields |
|---|---|
| `AssetRef` | `asset_type`, `uri`, `local_path`, `label`, `caption`, `id`, `mime_type`, `metadata`; `to_dict()`. `metadata` holds `file_name` and `jats_tag`, plus `alternative` for the second and later representations of one figure and `parent_id`/`parent_label` for a figure supplement |
| `AssetType` | `FIGURE`, `TABLE`, `SUPPLEMENTARY`, `FORMULA`, `VIDEO`, `AUDIO`, `UNKNOWN`. The block that owns the file decides: a `<fig>` gives `FIGURE`, a `<table-wrap>` `TABLE`, a `<supplementary-material>` `SUPPLEMENTARY`, an inline or display formula `FORMULA`. A `<graphic>` no block owns is a `FIGURE`, an `<inline-graphic>` is `UNKNOWN`, and a `<media>` is `VIDEO` or `AUDIO` by MIME type |
| `AssetFetchPolicy` | `SKIP`, `METADATA_ONLY`, `DOWNLOAD`, `DOWNLOAD_MISSING` |

## Reference resolution

`ReferenceResolver` looks up cited works in Europe PMC by DOI, then PMID, then title.

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.features.fulltext.extensions import ReferenceResolver

parser = FullTextXMLParser(Path("PMC3258128.xml").read_text(encoding="utf-8"))
resolver = ReferenceResolver(rate_limit=3.0)
resolved = resolver.resolve_batch(parser.extract_references()[:1])

reference = resolved[0]
print(reference.source_ref["label"], reference.resolved_pmid, reference.journal, reference.citations)
print(resolver.stats)
```

`ReferenceResolver(rate_limit=3.0, api_key=None)`:

| Member | Returns | Description |
|---|---|---|
| `resolve_reference(ref)` | `ResolvedReference \| None` | Takes a dict from `extract_references()`. Queries `https://www.ebi.ac.uk/europepmc/api/search` with `DOI:"…"`, then `PMID:"…"`, then `TITLE:"…"` (titles of at least 20 characters), and returns the first hit, or `None`. Results are cached per DOI, PMID or title; requests wait to stay under `rate_limit` per second; request errors are logged and give `None` |
| `resolve_batch(references, progress_callback=None)` | `list[ResolvedReference]` | One result per reference; an unresolved one only copies `pmid` and `doi` from the input. `progress_callback(done, total)` is called after each |
| `stats` | `dict` | `lookups`, `cache_hits`, `cache_size` |

`ResolvedReference` fields: `source_ref` (the input dict), `resolved_pmid`, `resolved_pmcid`, `resolved_doi`, `title`, `authors`, `year` (from the first publication date), `journal`, `citations` (`int`), `is_open_access` (`bool`); `to_dict()`.

## Local processing

```python
from pyeuropepmc.features.fulltext.extensions import (
    LocalXMLProcessor,
    extract_article_id_from_xml,
    parse_xml_directory,
    parse_xml_file,
)

parser = parse_xml_file("PMC3258128.xml")
parsers = parse_xml_directory(".", glob_pattern="PMC3*.xml", recursive=False)
print(parser.extract_metadata()["doi"], sorted(parsers))

summary = LocalXMLProcessor().process_single("PMC3359999.xml")
print(sorted(summary))
print(extract_article_id_from_xml(parser.xml_content))
```

Output:

```text
10.1093/nar/gkr715 ['PMC3258128.xml', 'PMC3359999.xml']
['authors', 'figures', 'funding', 'keywords', 'metadata', 'references', 'sections', 'source', 'tables']
3258128
```

| Function or method | Returns | Description |
|---|---|---|
| `parse_xml_file(file_path, config=None)` | `FullTextXMLParser` | Reads a UTF-8 file; `FileNotFoundError` if it does not exist, `ValueError` if it is not a file |
| `parse_xml_directory(directory, glob_pattern="*.xml", config=None, recursive=True)` | `dict[str, FullTextXMLParser]` | File path to parser; files that fail to parse are logged and left out |
| `extract_article_id_from_xml(xml_content)` | `str \| None` | The first PMCID, else DOI, else PMID `<article-id>`, as written; `None` for unparseable input |
| `LocalXMLProcessor(config=None).process_single(file_path, extract_fn=None)` | `dict` | `extract_fn(parser)`, or by default `source` (the first 100 characters), `metadata`, `authors`, `sections`, `references`, `figures`, `tables`, `funding`, `keywords` |
| `LocalXMLProcessor(config=None).process_directory(directory, glob_pattern="*.xml", extract_fn=None)` | `dict[str, dict]` | File path to the result of `process_single`, searching subdirectories; `{"error": ...}` for a file that fails |
| `process_single_pmc(pmcid, max_retries=3, timeout=30)` | `FullTextXMLParser` | Downloads `PMC{id}/fullTextXML` from the Europe PMC REST API with `urllib`, retrying after 2, 4, … seconds; raises `ConnectionError` after the last attempt or on HTTP 404 |
| `process_biorxiv_manifest(manifest_path, **kwargs)` | `list[FullTextXMLParser]` | Reads DOIs from a manifest's `<article>` or `<record>` elements, looks each up in Europe PMC and downloads the articles that have a PMC ID with `process_single_pmc(pmcid, **kwargs)`; articles without one are skipped |
| `parse_bits_book(filepath_or_xml, **kwargs)` | `FullTextXMLParser` | Parses XML text (a string starting with `<`) or the file at a path, with book-specific patterns when the root is `<book>` |

## Pydantic helpers

```python
from pyeuropepmc.features.fulltext.extensions import (
    ContentBlock,
    PydanticModelGenerator,
    dataclass_to_pydantic,
)

BlockModel = dataclass_to_pydantic(ContentBlock, include_fields=["type", "text"])
print(BlockModel(type="paragraph", text="Hello").model_dump())

Summary = PydanticModelGenerator.generate_model("ArticleSummary", sample_data={"title": "T", "year": 2012})
print(Summary(title="A title").model_dump())
```

Output:

```text
{'type': <ContentBlockType.PARAGRAPH: 'paragraph'>, 'text': 'Hello'}
{'title': 'A title', 'year': None}
```

| Function | Returns | Description |
|---|---|---|
| `dataclass_to_pydantic(dc, model_name=None, include_fields=None, exclude_fields=None)` | Pydantic model class | A model with the dataclass's fields; `model_name` defaults to the dataclass name |
| `PydanticModelGenerator.from_dataclass(dc, model_name=None, include_fields=None, exclude_fields=None)` | Pydantic model class | Class method, same as `dataclass_to_pydantic` |
| `PydanticModelGenerator.generate_model(model_name, sample_data=None, field_types=None, optional_defaults=True)` | Pydantic model class | Static method: field types from `field_types` or from the types of the `sample_data` values; with `optional_defaults=True` every field is optional with default `None` |

Pydantic is a dependency of pyeuropepmc, so these helpers are always available.

## LinkML models

`pyeuropepmc.features.fulltext.extensions.linkml_models` contains classes generated from the LinkML schema `schemas/linkml/article_content_schema.yaml` in the repository: `ArticleContent`, `ArticleMetadata`, `StructuredSection`, `ContentBlock`, `ContentBlockType`, `SectionType`, `ListStyle`, `PeerReview` and `AssetRef`. They are separate from the dataclasses above; import them from that module.

## Known limitations

- **MathML.** `MathMLConverter` covers presentation MathML only. Content MathML (`<apply>`, `<annotation-xml>`) is dropped, `<mmultiscripts>` loses its script positions, and an `<mtable>` always becomes a plain `array` — a `cases` or `aligned` environment is never produced. A character with no LaTeX command in its tables is kept as it stands (a letter inside `\text{}`), which a Unicode-aware engine or MathJax accepts and pdflatex does not; on a sample of 1,654 formulas from 32 papers, 4 failed to compile with pdflatex for that reason.
- **Assets.** `extract_asset_refs()` reports a file's MIME type from the `mimetype`/`mime-subtype` the XML states, or from the file extension; an extension the package does not know becomes `application/octet-stream`. A `<graphic>` reference written without a file type is assumed to be a JPEG, which is what every such file in the corpus is.
- **Peer review.** `contributors` are collected from the whole sub-article, including any sub-article nested inside it. The revision round is not read from PLOS's titles ("Decision Letter 1"), so every PLOS review is in round 1.
- **Reference resolution.** `is_open_access` is `True` whenever Europe PMC returns any value, including `"N"`.
