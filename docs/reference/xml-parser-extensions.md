# XML Parser Extensions Reference

The `pyeuropepmc.processing.extensions` package provides 10 extension modules that extend the `FullTextXMLParser` with advanced capabilities. All modules are designed to be modular, DRY, reusable, and backward compatible with the existing parser infrastructure.

## Installation

All extension modules are included with `pyeuropepmc`. Optional dependencies:

```bash
# For lxml backend support
pip install lxml

# For Pydantic model generation
pip install pydantic
```

## Module Reference

### 1. Content Block Model (`content_blocks`)

Typed content blocks that preserve document structure for RAG/LLM pipelines. Instead of flattening sections to `{title, content}` strings, each section contains ordered `ContentBlock` instances with explicit types.

**Key Classes:**

| Class | Description |
|-------|-------------|
| `ContentBlock` | Typed dataclass with factory methods for each block type |
| `ContentBlockType` | Enum: PARAGRAPH, LIST, FORMULA, FIGURE_REF, TABLE_REF, CODE, BOXED_TEXT, HEADING, FIGURE, TABLE, MATHML, PEER_REVIEW, UNKNOWN_BLOCK |
| `ContentBlockExtractor` | Walks `<sec>` children producing typed `ContentBlock` instances |
| `StructuredSection` | Section containing ordered typed content blocks |

**Integration:**

The `FullTextXMLParser.get_full_text_sections_structured()` method (added in this release) uses `ContentBlockExtractor` internally:

```python
parser = FullTextXMLParser(xml_content)
structured = parser.get_full_text_sections_structured()
for section in structured:
    print(f"Section: {section.title}")
    for block in section.content:
        print(f"  [{block.type.value}] {block.text[:100]}")
```

**Serialization:**

```python
# Each ContentBlock has a to_dict() method
for section in structured:
    data = section.to_dict()
    # {'title': 'Introduction', 'content': [{'type': 'paragraph', 'text': '...'}, ...]}
```

**Block Type Reference:**

| Block Type | Factory Method | Key Fields |
|-----------|---------------|------------|
| `PARAGRAPH` | `ContentBlock.paragraph(text)` | `text` |
| `HEADING` | `ContentBlock.heading(text)` | `text` |
| `LIST` | `ContentBlock.list_block(items, list_type)` | `items`, `list_type` |
| `FORMULA` | `ContentBlock.formula(tex, label)` | `tex`, `label`, `mathml` |
| `FIGURE` | `ContentBlock.figure(label, caption, uri, target_id)` | `label`, `caption`, `uri`, `target_id` |
| `TABLE` | `ContentBlock.table_block(label, caption, text)` | `label`, `caption`, `text` |
| `CODE` | `ContentBlock.code(text, language)` | `text`, `language` |
| `BOXED_TEXT` | `ContentBlock.boxed_text(text)` | `text` |
| `FIGURE_REF` | `ContentBlock.figure_ref(target_id, label)` | `target_id`, `label` |
| `TABLE_REF` | `ContentBlock.table_ref(target_id, label)` | `target_id`, `label` |
| `UNKNOWN_BLOCK` | `ContentBlock.unknown_block(jats_tag, text)` | `jats_tag`, `text` |

**Backward Compatibility:**

The original `get_full_text_sections()` method is unchanged. The new `get_full_text_sections_structured()` method returns `list[StructuredSection]`.

---

### 2. lxml Backend (`lxml_backend`)

High-performance XML parser backend using `lxml.etree` with secure configuration.

**Key Class:** `LXMLParser`

```python
from pyeuropepmc.processing.extensions import LXMLParser, is_lxml_available

if is_lxml_available():
    parser = LXMLParser()
    root = parser.parse(xml_content)

    # Swap FullTextXMLParser's backend to lxml
    ft_parser = FullTextXMLParser(xml_content)
    LXMLParser.enable_for(ft_parser)  # Replaces ft_parser.root with lxml-parsed tree
```

**Security:** Disables entity resolution (`resolve_entities=False`), enforces no-network access (`no_network=True`), and removes `DOCTYPE` with `remove_blank_text=True`.

**Graceful Degradation:** `is_lxml_available()` returns `False` if lxml is not installed; `LXMLParser` raises `ImportError` with a clear message.

---

### 3. Peer Review Extraction (`peer_review`)

Extract peer review materials from `<sub-article>` elements organized by revision round.

**Key Classes:**

| Class | Description |
|-------|-------------|
| `PeerReviewExtractor` | Extracts reviews from sub-article elements |
| `PeerReviewMaterial` | A single review with type, content, date, author |
| `PeerReviewSet` | Collection of reviews for one revision round |
| `PeerReviewType` | Enum: DECISION_LETTER, REFEREE_REPORT, EDITOR_REPORT, REVIEWER_REPORT, REBUTTAL, AUTHOR_RESPONSE, APPROVAL, OTHER |

```python
from pyeuropepmc.processing.extensions import PeerReviewExtractor

extractor = PeerReviewExtractor(parser.root)
review_sets = extractor.extract_all()

for review_set in review_sets:
    print(f"Round {review_set.revision_round}")
    for review in review_set.reviews:
        print(f"  Type: {review.review_type.value}")
        print(f"  Date: {review.date}")
        print(f"  By: {review.author}")
        print(f"  Content: {review.content[:200]}...")
```

**Supported article types:** `decision-letter`, `referee-report`, `editor-report`, `reviewer-report`, `rebuttal`, `author-response`, `approval`.

---

### 4. MathML Conversion (`mathml`)

Convert MathML to LaTeX string representation.

**Key Class:** `MathMLConverter`

```python
from pyeuropepmc.processing.extensions import MathMLConverter

converter = MathMLConverter()
latex = converter.convert(mathml_string)
# Example: converts <msub><mi>x</mi><mn>1</mn></msub> → x_{1}
```

**Supported Elements (15+):**

| MathML Element | LaTeX Output |
|---------------|-------------|
| `<mi>`, `<mn>`, `<mo>` | Direct text |
| `<msub>` | `x_{1}` |
| `<msup>` | `x^{2}` |
| `<msubsup>` | `x_{1}^{2}` |
| `<mfrac>` | `\frac{a}{b}` |
| `<msqrt>` | `\sqrt{x}` |
| `<mroot>` | `\sqrt[3]{x}` |
| `<mrow>` | Grouped expression |
| `<mi>` Greek letters | `\alpha`, `\beta`, etc. |
| `<mover>` | `\vec{x}`, `\dot{x}` |
| `<munder>` | `\sum_{i}` |
| `<munderover>` | `\sum_{i=1}^{n}` |
| `<mtable>` | `\begin{matrix}...\end{matrix}` |

**Entity Resolution:** Resolves 80+ common MathML entities (Greek letters, arrows, operators).

---

### 5. JATS4R Validation (`jats4r`)

Compliance checking against NISO JATS4R (Journal Article Tag Suite for Reproducibility) recommendations.

**Key Classes:**

| Class | Description |
|-------|-------------|
| `JATS4RValidator` | Main validator class |
| `ValidationReport` | Report with compliance score and findings |
| `ValidationFinding` | Individual finding with severity, category, message, element |

```python
from pyeuropepmc.processing.extensions import JATS4RValidator

validator = JATS4RValidator(parser.root)
report = validator.validate()

print(f"Compliance score: {report.compliance_score:.2f}")  # 0.0 to 1.0
print(f"Total findings: {len(report.findings)}")

for finding in report.findings:
    print(f"  [{finding.severity}] {finding.category}: {finding.message}")
    if finding.element is not None:
        print(f"    Element: {ET.tostring(finding.element, encoding='unicode')[:200]}")
```

**Validated Categories (6):**

| Category | What It Checks |
|----------|---------------|
| `AUTHORS` | ORCID presence, valid contributor types |
| `AFFILIATIONS` | Affiliation completeness, department/institution separation |
| `ABSTRACTS` | Abstract presence, structured abstract support |
| `FUNDING` | Funding statement, award IDs, funder identification |
| `CITATIONS` | DOI presence in references, publication type |
| `DATA_AVAILABILITY` | Data availability statement presence |

---

### 6. Batch Processing (`batch_processor`)

Concurrent XML parsing with rate limiting, progress callbacks, and error handling.

**Key Classes:**

| Class | Description |
|-------|-------------|
| `BatchProcessor` | Rate-limited batch processor |
| `BatchResult` | Summary of batch processing results |
| `ProcessingResult` | Result for a single XML document |

```python
from pyeuropepmc.processing.extensions import BatchProcessor

# Process a list of XML strings
processor = BatchProcessor(
    rate_per_second=5,           # API-friendly rate limiting
    on_progress=lambda i, t: print(f"Processing {i}/{t}"),
    on_error=lambda err: print(f"Error: {err}"),
)

xml_strings = [open(f).read() for f in ["paper1.xml", "paper2.xml"]]
results = processor.process(xml_strings)

# Process a directory of XML files
results = processor.process_directory("xml_files/", pattern="*.xml")

# Summary
print(f"Processed: {len(results.results)}")
print(f"Failed: {len(results.errors)}")
print(f"Total time: {results.total_time:.2f}s")
```

---

### 7. Image Fetcher (`image_fetcher`)

Extract asset references (figures, supplementary files, media) from XML and optionally download them.

**Key Classes:**

| Class | Description |
|-------|-------------|
| `ImageFetcher` | Main asset fetcher class |
| `AssetRef` | Single asset reference with type, URI, label |
| `AssetType` | Enum: FIGURE, GRAPHIC, SUPPLEMENTARY, MEDIA, TABLE |
| `AssetFetchPolicy` | Download policy configuration |

```python
from pyeuropepmc.processing.extensions import ImageFetcher, AssetFetchPolicy

fetcher = ImageFetcher(parser.root)

# Extract all assets
assets = fetcher.extract_assets()
for asset in assets:
    print(f"  [{asset.type.value}] {asset.label}: {asset.uri}")

# Download assets
policy = AssetFetchPolicy(output_dir="assets/", overwrite=False)
fetcher.download_assets(assets, policy)
```

---

### 8. Reference Resolver (`reference_resolver`)

Enrich references via the Europe PMC API with caching and rate limiting.

**Key Classes:**

| Class | Description |
|-------|-------------|
| `ReferenceResolver` | Resolves references by DOI, PMID, or title lookup |
| `ResolvedReference` | Resolved reference with enriched metadata |

```python
from pyeuropepmc.processing.extensions import ReferenceResolver

resolver = ReferenceResolver()
results = resolver.resolve_references(parser)

for ref in results:
    print(f"  [{ref.label}] {ref.title}")
    print(f"    DOI: {ref.doi}")
    print(f"    PMID: {ref.pmid}")
    print(f"    Citations: {ref.cited_by_count}")
```

**Lookup methods:** DOI-based lookup (fastest), PMID-based lookup, title-based lookup (fallback). Results are cached to avoid redundant API calls. Rate limiting respects Europe PMC API guidelines.

---

### 9. Pydantic Helpers (`pydantic_helpers`)

Convert dataclasses to Pydantic v2 models and dynamically generate models from sample data.

**Key Classes:**

| Class | Description |
|-------|-------------|
| `PydanticModelGenerator` | Dynamic Pydantic model generation from sample data |
| `dataclass_to_pydantic()` | Convert a dataclass to a Pydantic v2 model |

```python
from pyeuropepmc.processing.extensions import (
    dataclass_to_pydantic,
    PydanticModelGenerator,
)
from pyeuropepmc.processing.extensions.content_blocks import ContentBlock

# Convert existing dataclass to Pydantic model
PydanticContentBlock = dataclass_to_pydantic(ContentBlock)
model = PydanticContentBlock(type="paragraph", text="Hello World")

# Dynamic model generation from sample data
generator = PydanticModelGenerator()
DynamicModel = generator.generate_model("Article", sample_data)
```

**Requires:** `pydantic` (v2). Graceful `ImportError` if not installed.

---

### 10. Local Processing (`local_processing`)

Convenience utilities for parsing XML files and directories without managing `FullTextXMLParser` instances directly.

**Key Functions and Classes:**

| Function/Class | Description |
|---------------|-------------|
| `parse_xml_file(path)` | Parse a single XML file and return parser |
| `parse_xml_directory(path, pattern)` | Parse all XML files in a directory |
| `extract_article_id_from_xml(xml_content)` | Extract PMID/PMCID from XML metadata |
| `LocalXMLProcessor` | Class wrapping all local processing methods |

```python
from pyeuropepmc.processing.extensions import (
    LocalXMLProcessor,
    parse_xml_file,
    parse_xml_directory,
    extract_article_id_from_xml,
)

# Parse single file
parser = parse_xml_file("article.xml")
print(parser.extract_metadata()["title"])

# Parse all XML files in a directory
parsers = parse_xml_directory("xml_files/", pattern="*.xml")

# Extract ID without full parsing
article_id = extract_article_id_from_xml(xml_content)
print(f"PMCID: {article_id['pmcid']}, PMID: {article_id['pmid']}")

# Or use the class API
processor = LocalXMLProcessor()
parser = processor.parse_file("article.xml")
processor.write_markdown(xml_content, "output.md")
```

**Markdown Quick Export:**

```python
LocalXMLProcessor.write_markdown(xml_content, "output.md")
LocalXMLProcessor.write_plaintext(xml_content, "output.txt")
```

## LinkML Schema Integration

The extensions are linked to a LinkML schema at `schemas/linkml/article_content_schema.yaml` covering:

- `ContentBlock` - Typed content blocks (all types)
- `StructuredSection` - Sections with ordered content blocks
- `ArticleContent` - Complete article with metadata, sections, peer review, assets
- `PeerReview` - Review materials
- `AssetRef` - Asset references

Generated Python models are available at `src/pyeuropepmc/processing/extensions/linkml_models.py`. The schema connects to the `biomedical-knowledge-lookup` ontology where `EUROPEPMC` is defined as a `KnowledgeSource`.

```python
from pyeuropepmc.processing.extensions.linkml_models import (
    ArticleContent,
    StructuredSection as LinkMLSection,
    ContentBlock as LinkMLBlock,
)
```

## Testing

Extension tests are located in:

- `tests/extensions/test_all_extensions.py` — 41 unit tests covering all modules
- `tests/extensions/test_functional_real_xml.py` — 53 functional tests on 5 real XML papers

Run them with:

```bash
pytest tests/extensions/ -v
```

## See Also

- **[Features: XML Parsing](../features/parsing/)** — Feature overview with usage examples
- **[API Reference: XML Parser Extensions](../api/xml-parser-extensions.md)** — Full API reference
- **[API Reference: FullTextXMLParser](../api/xml-parser.md)** — Core parser API
- **[XML Element Types](xml_element_types_documentation.md)** — JATS element reference
- **[Local XML Fixtures](../../tests/fixtures/fulltext_downloads/)** — Test XML files
