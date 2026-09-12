# Rhetorical PDF Highlighting

LLM-powered classification of text passages by their rhetorical role in scientific discourse.

## Overview

The `RhetoricalHighlighter` analyzes scientific text and labels sentences according to their rhetorical function:

| Role | Description |
|------|-------------|
| **Claim** | A statement of a new finding or position |
| **Method** | Description of experimental methods or procedures |
| **Result** | Presentation of experimental outcomes |
| **Limitation** | Acknowledgment of study limitations |
| **Conclusion** | Summary or interpretation of findings |

## Basic Usage

```python
from pyeuropepmc.features.fulltext import RhetoricalHighlighter

highlighter = RhetoricalHighlighter()

text = """
We conducted a randomized controlled trial of 500 patients with chronic fatigue syndrome.
Our results show a significant improvement in fatigue scores after 12 weeks of treatment.
This study was limited by the short follow-up period.
These findings suggest that cognitive behavioral therapy is effective for ME/CFS.
"""

result = highlighter.highlight(text)
# Returns HighlightedDocument with sentence-level annotations
```

## Annotated Document

```python
from pyeuropepmc.features.fulltext import RhetoricalHighlighter

highlighter = RhetoricalHighlighter()
doc = highlighter.highlight(text)

for sentence in doc.sentences:
    print(f"[{sentence.role.value:12s}] {sentence.text}")
```

## Group by Role

```python
# Group sentences by their rhetorical role
grouped = doc.group_by_role()
for role, sentences in grouped.items():
    print(f"\n=== {role.value}s ===")
    for s in sentences:
        print(f"  - {s.text}")
```

## Statistics

```python
stats = doc.statistics()
print(stats)
# {
#     "total_sentences": 10,
#     "distribution": {
#         "claim": 3,
#         "method": 2,
#         "result": 2,
#         "limitation": 1,
#         "conclusion": 2,
#     }
# }
```

## Summary

```python
summary = doc.summary()
print(summary)
# "3 claims, 2 methods, 2 results, 1 limitation, 2 conclusions"
```

## PDF Text Input

```python
from pyeuropepmc.features.fulltext import highlight_text, highlight_pdf_text

# Annotate any text
result = highlight_text(text)

# From PDF-extracted text (e.g., PyMuPDF, pdfplumber)
result = highlight_pdf_text("path/to/paper.pdf")
```

## LLM Requirements

The RhetoricalHighlighter uses OpenAI via LangChain. Requires:

```bash
pip install pyeuropepmc[llm]
export OPENAI_API_KEY="your-key"
```

## Use Cases

- **Systematic reviews**: Automatically identify methods and results sections
- **Literature mapping**: Classify claims vs limitations across papers
- **Reviewer aids**: Highlight key structural elements in manuscripts
- **Meta-analysis**: Extract results and limitations at scale
