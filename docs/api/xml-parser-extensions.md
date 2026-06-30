# XML Parser Extensions API Reference

## Module: `pyeuropepmc.processing.extensions`

```python
from pyeuropepmc.processing.extensions import *
```

### Conditional Imports

Pydantic helpers are available only when `pydantic` is installed:

```python
try:
    from pyeuropepmc.processing.extensions import (
        PydanticModelGenerator,
        dataclass_to_pydantic,
    )
except ImportError:
    # Pydantic not installed
    pass
```

---

## Content Block Model

### `ContentBlockType`

```python
class ContentBlockType(str, Enum):
    PARAGRAPH = "paragraph"
    LIST = "list"
    FORMULA = "formula"
    FIGURE_REF = "figure_ref"
    TABLE_REF = "table_ref"
    CODE = "code"
    BOXED_TEXT = "boxed_text"
    HEADING = "heading"
    FIGURE = "figure"
    TABLE = "table"
    MATHML = "mathml"
    PEER_REVIEW = "peer_review"
    UNKNOWN_BLOCK = "unknown_block"
```

### `ContentBlock`

```python
@dataclass
class ContentBlock:
    type: ContentBlockType
    text: str = ""
    items: list[str] = field(default_factory=list)
    list_type: str = ""
    label: str = ""
    target_id: str = ""
    language: str = ""
    tex: str = ""
    mathml: str = ""
    caption: str = ""
    uri: str = ""
    jats_tag: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
```

**Factory Methods:**

- `ContentBlock.paragraph(text: str) -> ContentBlock`
- `ContentBlock.heading(text: str) -> ContentBlock`
- `ContentBlock.list_block(items: list[str], list_type: str = "unordered") -> ContentBlock`
- `ContentBlock.formula(tex: str, label: str = "") -> ContentBlock`
- `ContentBlock.figure_ref(target_id: str, label: str = "") -> ContentBlock`
- `ContentBlock.table_ref(target_id: str, label: str = "") -> ContentBlock`
- `ContentBlock.code(text: str, language: str = "") -> ContentBlock`
- `ContentBlock.boxed_text(text: str) -> ContentBlock`
- `ContentBlock.figure(label: str, caption: str, uri: str = "", target_id: str = "") -> ContentBlock`
- `ContentBlock.table_block(label: str, caption: str, text: str = "") -> ContentBlock`
- `ContentBlock.unknown_block(jats_tag: str, text: str = "") -> ContentBlock`

**Class Variables:**

- `LIST_TYPES: ClassVar[set[ContentBlockType]]` — Block types with list-like structure
- `RICH_TYPES: ClassVar[set[ContentBlockType]]` — Block types with rich structured data

**Methods:**

- `to_dict() -> dict[str, Any]` — Serialize to dict, omitting empty fields

### `StructuredSection`

```python
@dataclass
class StructuredSection:
    title: str
    content: list[ContentBlock] = field(default_factory=list)
    section_type: str = "body"
```

**Methods:**

- `to_dict() -> dict[str, Any]` — Serialize to dict

### `ContentBlockExtractor`

```python
class ContentBlockExtractor(BaseParser):
    def __init__(
        self,
        root: ET.Element | None = None,
        config: ElementPatterns | None = None,
    )
    def extract_sections() -> list[StructuredSection]
```

---

## lxml Backend

### `LXMLParser`

```python
class LXMLParser:
    def __init__(self, **kwargs)
    def parse(xml_content: str) -> ET.Element
    @staticmethod
    def enable_for(parser: FullTextXMLParser) -> None
```

### `is_lxml_available`

```python
def is_lxml_available() -> bool
```

---

## Peer Review

### `PeerReviewType`

```python
class PeerReviewType(str, Enum):
    DECISION_LETTER = "decision-letter"
    REFEREE_REPORT = "referee-report"
    EDITOR_REPORT = "editor-report"
    REVIEWER_REPORT = "reviewer-report"
    REBUTTAL = "rebuttal"
    AUTHOR_RESPONSE = "author-response"
    APPROVAL = "approval"
    OTHER = "other"
```

### `PeerReviewMaterial`

```python
@dataclass
class PeerReviewMaterial:
    review_type: PeerReviewType
    content: str
    date: str = ""
    author: str = ""
    title: str = ""
```

### `PeerReviewSet`

```python
@dataclass
class PeerReviewSet:
    revision_round: int
    reviews: list[PeerReviewMaterial] = field(default_factory=list)
    article_type: str = ""
```

### `PeerReviewExtractor`

```python
class PeerReviewExtractor(BaseParser):
    def __init__(
        self,
        root: ET.Element | None = None,
        config: ElementPatterns | None = None,
    )
    def extract_all() -> list[PeerReviewSet]
    def extract_by_type(review_type: PeerReviewType) -> list[PeerReviewMaterial]
```

---

## MathML Conversion

### `MathMLConverter`

```python
class MathMLConverter:
    def __init__(self)
    def convert(mathml_str: str) -> str
    def convert_element(element: ET.Element) -> str

    # Namespace for MathML elements
    namespaces: dict[str, str]
    # Mapping of 80+ named entities
    ENTITY_MAP: ClassVar[dict[str, str]]
```

---

## JATS4R Validation

### `ValidationFinding`

```python
@dataclass
class ValidationFinding:
    severity: str  # "error", "warning", "info"
    category: str  # e.g., "AUTHORS", "FUNDING"
    message: str
    element: ET.Element | None = None
```

### `ValidationReport`

```python
@dataclass
class ValidationReport:
    compliance_score: float  # 0.0 to 1.0
    findings: list[ValidationFinding] = field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
```

### `JATS4RValidator`

```python
class JATS4RValidator(BaseParser):
    def __init__(
        self,
        root: ET.Element | None = None,
        config: ElementPatterns | None = None,
    )
    def validate() -> ValidationReport
```

**Validation Categories** (accessible via class attributes):

- `CHECK_AUTHORS`, `CHECK_AFFILIATIONS`, `CHECK_ABSTRACTS`
- `CHECK_FUNDING`, `CHECK_CITATIONS`, `CHECK_DATA_AVAILABILITY`

---

## Batch Processing

### `ProcessingResult`

```python
@dataclass
class ProcessingResult:
    index: int
    success: bool
    metadata: dict | None = None
    error: str | None = None
    duration: float = 0.0
```

### `BatchResult`

```python
@dataclass
class BatchResult:
    results: list[ProcessingResult]
    errors: list[str]
    total_time: float
    total_count: int
```

### `BatchProcessor`

```python
class BatchProcessor:
    def __init__(
        self,
        rate_per_second: float = 5.0,
        max_workers: int = 4,
        on_progress: Callable[[int, int], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    )
    def process(xml_strings: list[str]) -> BatchResult
    def process_files(file_paths: list[str]) -> BatchResult
    def process_directory(
        directory: str, pattern: str = "*.xml"
    ) -> BatchResult
```

---

## Image Fetcher

### `AssetType`

```python
class AssetType(str, Enum):
    FIGURE = "figure"
    GRAPHIC = "graphic"
    SUPPLEMENTARY = "supplementary"
    MEDIA = "media"
    TABLE = "table"
```

### `AssetRef`

```python
@dataclass
class AssetRef:
    type: AssetType
    uri: str
    label: str = ""
    caption: str = ""
    target_id: str = ""
```

### `AssetFetchPolicy`

```python
@dataclass
class AssetFetchPolicy:
    output_dir: str = "assets"
    overwrite: bool = False
    timeout: int = 30
```

### `ImageFetcher`

```python
class ImageFetcher(BaseParser):
    def __init__(
        self,
        root: ET.Element | None = None,
        config: ElementPatterns | None = None,
    )
    def extract_assets() -> list[AssetRef]
    def download_assets(
        assets: list[AssetRef],
        policy: AssetFetchPolicy | None = None,
    ) -> list[Path]
```

---

## Reference Resolver

### `ResolvedReference`

```python
@dataclass
class ResolvedReference:
    label: str
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    title: str = ""
    authors: str = ""
    source: str = ""
    year: str = ""
    volume: str = ""
    pages: str = ""
    cited_by_count: int = 0
    resolved: bool = False
```

### `ReferenceResolver`

```python
class ReferenceResolver:
    def __init__(
        self,
        cache_size: int = 1000,
        rate_per_second: float = 5.0,
    )
    def resolve_references(parser: FullTextXMLParser) -> list[ResolvedReference]
    def resolve_by_doi(doi: str) -> ResolvedReference | None
    def resolve_by_pmid(pmid: str) -> ResolvedReference | None
    def resolve_by_title(title: str) -> ResolvedReference | None
    def clear_cache()
```

---

## Pydantic Helpers

### `dataclass_to_pydantic`

```python
def dataclass_to_pydantic(
    dataclass: type,
    *,
    field_mapping: dict[str, str] | None = None,
    field_overrides: dict[str, Any] | None = None,
) -> type
```

### `PydanticModelGenerator`

```python
class PydanticModelGenerator:
    def __init__(self)
    def generate_model(name: str, sample_data: dict) -> type
    def add_validator(name: str, validator_func: Callable)
    def add_field_description(field: str, description: str)
```

---

## Local Processing

### `parse_xml_file`

```python
def parse_xml_file(path: str | Path) -> FullTextXMLParser
```

### `parse_xml_directory`

```python
def parse_xml_directory(
    path: str | Path,
    pattern: str = "*.xml",
) -> list[FullTextXMLParser]
```

### `extract_article_id_from_xml`

```python
def extract_article_id_from_xml(xml_content: str) -> dict[str, str]
# Returns: {"pmcid": "...", "pmid": "...", "doi": "..."}
```

### `LocalXMLProcessor`

```python
class LocalXMLProcessor:
    @staticmethod
    def parse_file(path: str | Path) -> FullTextXMLParser
    @staticmethod
    def parse_string(xml_content: str) -> FullTextXMLParser
    @staticmethod
    def write_markdown(xml_content: str, output_path: str | Path)
    @staticmethod
    def write_plaintext(xml_content: str, output_path: str | Path)
    @staticmethod
    def extract_id(xml_content: str) -> dict[str, str]
    @staticmethod
    def batch_process_files(
        file_paths: list[str | Path],
        rate_per_second: float = 5.0,
    ) -> BatchResult
```

---

## FullTextXMLParser Integration

New methods on `FullTextXMLParser`:

### `get_full_text_sections_structured`

```python
def get_full_text_sections_structured() -> list[StructuredSection]
```

Returns body sections as typed content blocks. Uses `ContentBlockExtractor` internally. Raises `ParsingError` if no content has been parsed.
