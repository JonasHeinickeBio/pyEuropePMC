# JATS XML Normalization

The `JATSNormalizer` applies a configurable pipeline of normalization layers to JATS XML documents, producing clean text suitable for NLP/ML pipelines while preserving structural information.

## Quick Start

```python
from pyeuropepmc.processing.jats_normalizer import JATSNormalizer

normalizer = JATSNormalizer()
result = normalizer.normalize_xml(xml_content)

# Clean plain text
print(result["body_text"])

# Structured sections with canonical types
for section in result["sections"]:
    print(f"{section['type']}: {section['title'][:50]}")
```

## Normalization Pipeline

The normalizer applies 11 layers in sequence:

| # | Layer | Description |
|---|-------|-------------|
| 1 | Entity pre-resolution | Resolves XML named entities (`&alpha;` to `α`) and numeric character references before parsing |
| 2 | Namespace stripping | Removes `{uri}` prefixes from element tags |
| 3 | Entity normalization | Resolves remaining entities in text/tail nodes |
| 4 | Display markup stripping | Strips `<bold>`, `<italic>`, `<sup>`, `<sub>`, etc. preserving text content |
| 5 | Structural element removal | Removes `<fig>`, `<table-wrap>`, `<supplementary-material>` from body |
| 6 | MathML dropping | Removes `<math>` / `<mml:math>` elements |
| 7 | Section type canonicalization | Maps ~30 heading patterns to canonical types (intro, methods, results, etc.) |
| 8 | Whitespace normalization | Replaces 20+ Unicode space characters, collapses multiples |
| 9 | Dash normalization | Replaces 10+ Unicode dash/hyphen/minus variants to ASCII hyphen |
| 10 | Identifier normalization | Normalizes ORCID, DOI, PMCID formats |
| 11 | BioC JSON output | Optional BioC format with section passages |

## Configuration

All layers are configurable via the constructor:

```python
normalizer = JATSNormalizer(
    normalize_entities=True,      # Resolve XML entities
    strip_display_markup=True,    # Strip bold/italic/sup/sub
    flatten_xrefs=True,           # Flatten xref to text/ID
    remove_structural=True,       # Remove fig/table-wrap from body
    section_types=True,           # Canonicalize section headings
    normalize_whitespace=True,    # Fix Unicode whitespace
    normalize_dashes=True,        # Normalize dashes to ASCII
    normalize_identifiers=True,   # Normalize ORCID/DOI/PMCID
    drop_mathml=True,             # Drop MathML elements
    bio_c_output=False,           # Generate BioC JSON
)
```

## Section Type Classification

The normalizer canonicalizes ~30 heading patterns to standard types:

| Type | Patterns Matched |
|------|-----------------|
| `intro` | Introduction, Background, Preface |
| `methods` | Methods, Materials and Methods, Methodology, Experimental |
| `results` | Results, Findings, Outcome |
| `discussion` | Discussion, Interpretation, Limitations |
| `conclusion` | Conclusion, Conclusions, Summary |
| `ack` | Acknowledgments, Acknowledgements |
| `funding` | Funding, Funding Source, Financial Support |
| `ethics` | Ethics, Ethical Approval, Conflict of Interest |
| `refs` | References, Bibliography, Literature Cited |

```python
from pyeuropepmc.processing.jats_normalizer import classify_section

print(classify_section("Materials and Methods"))  # "methods"
print(classify_section("Conclusions"))             # "conclusion"
print(classify_section("Data Availability"))        # "other"
```

## Module-Level Convenience Functions

```python
from pyeuropepmc.processing.jats_normalizer import (
    normalize_jats_xml,   # Full normalization
    normalize_jats_text,  # Plain text only
    classify_section,     # Heading classification
)

# Quick plain text
text = normalize_jats_text(xml_content)

# Full result dict
result = normalize_jats_xml(xml_content)
```

## CLI Usage

```bash
# Normalize to plain text
pyeuropepmc normalize text article.xml

# Extract sections as a table
pyeuropepmc normalize sections article.xml

# Convert to BioC JSON
pyeuropepmc normalize bioc article.xml -o output.json

# Classify a heading
pyeuropepmc normalize classify "Materials and Methods"

# Batch process a directory
pyeuropepmc normalize batch input_dir/ output_dir/ --output-format text
```

## Output Structure

`normalize_xml()` returns a dict with:

| Key | Type | Description |
|-----|------|-------------|
| `normalized_root` | `Element` | Cleaned XML element tree |
| `sections` | `list[dict]` | Sections with `type`, `title`, `text`, `level`, `passages` |
| `metadata` | `dict` | Normalized identifiers, authors, journal info |
| `body_text` | `str` | Full normalized body text |
| `bio_c` | `dict` | BioC JSON (if `bio_c_output=True`) |

## Use Cases

- **NLP/ML text mining** — Clean text for named entity recognition, relation extraction, sentiment analysis
- **ME/CFS knowledge graph** — Section-aware text for symptom-disease association extraction
- **Systematic reviews** — Standardized section classification for methods comparison
- **RAG pipelines** — Clean chunks with section provenance for LLM retrieval
- **BioC interoperability** — Exchange format compatible with PMC BioC API
