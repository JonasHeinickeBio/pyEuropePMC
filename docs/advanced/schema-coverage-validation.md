# Schema Coverage Validation

## Overview

The `validate_schema_coverage()` method provides comprehensive analysis of XML document structure to identify which element types are recognized by the parser configuration versus which are unrecognized. This helps developers:

1. **Understand document structure** - See all unique element types in an XML document
2. **Identify coverage gaps** - Find elements not handled by current configuration
3. **Prioritize improvements** - Focus on frequently occurring unrecognized elements
4. **Validate configurations** - Ensure custom ElementPatterns cover necessary elements

## Method Signature

```python
def validate_schema_coverage(self) -> dict[str, Any]:
    """
    Validate schema coverage by analyzing recognized vs unrecognized element tags.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - total_elements: Total number of unique element types in document
        - recognized_elements: List of element types covered by config patterns
        - unrecognized_elements: List of element types not covered by config
        - recognized_count: Count of recognized element types
        - unrecognized_count: Count of unrecognized element types
        - coverage_percentage: Percentage of elements recognized (0-100)
        - element_frequency: Dict mapping each element to its occurrence count
    """
```

## Usage Examples

### Basic Usage

```python
from pyeuropepmc import FullTextXMLParser

# Parse XML content
parser = FullTextXMLParser(xml_content)

# Validate schema coverage
coverage = parser.validate_schema_coverage()

print(f"Coverage: {coverage['coverage_percentage']:.1f}%")
print(f"Unrecognized elements: {coverage['unrecognized_elements']}")
```

### Detailed Analysis

```python
# Get comprehensive analysis
coverage = parser.validate_schema_coverage()

# Display summary
print("=" * 80)
print("COVERAGE SUMMARY")
print("=" * 80)
print(f"Total element types:       {coverage['total_elements']}")
print(f"Recognized elements:       {coverage['recognized_count']}")
print(f"Unrecognized elements:     {coverage['unrecognized_count']}")
print(f"Coverage percentage:       {coverage['coverage_percentage']:.1f}%")

# Show unrecognized elements by frequency
if coverage['unrecognized_elements']:
    print("\nUNRECOGNIZED ELEMENTS (by frequency):")
    unrecognized_freq = [
        (elem, coverage['element_frequency'][elem])
        for elem in coverage['unrecognized_elements']
    ]
    unrecognized_freq.sort(key=lambda x: x[1], reverse=True)

    for elem, freq in unrecognized_freq[:10]:
        print(f"  {elem:40s} {freq:5d} occurrences")
```

### Identify High-Priority Elements

```python
# Find frequently occurring unrecognized elements
coverage = parser.validate_schema_coverage()

high_priority = [
    (elem, freq)
    for elem, freq in coverage['element_frequency'].items()
    if elem in coverage['unrecognized_elements'] and freq >= 10
]

if high_priority:
    print("HIGH-PRIORITY UNRECOGNIZED ELEMENTS:")
    for elem, freq in sorted(high_priority, key=lambda x: x[1], reverse=True):
        print(f"  • {elem} ({freq} occurrences)")
    print("\n💡 Consider adding patterns for these elements to ElementPatterns")
```

## Real-World Example

Running on PMC3258128.xml produces:

```
================================================================================
COVERAGE SUMMARY
================================================================================
Total element types:       72
Recognized elements:       43
Unrecognized elements:     29
Coverage percentage:       59.7%

================================================================================
UNRECOGNIZED ELEMENTS (with frequency)
================================================================================
  xref                                        80 occurrences
  person-group                                47 occurrences
  etal                                         7 occurrences
  month                                        7 occurrences
  award-id                                     6 occurrences
  day                                          5 occurrences
  funding-source                               4 occurrences
  media                                        4 occurrences
  journal-id                                   3 occurrences
  ...

================================================================================
RECOMMENDATIONS
================================================================================
Consider adding patterns for frequently occurring unrecognized elements:
  • xref (80 occurrences)
  • person-group (47 occurrences)
  • etal (7 occurrences)
  • month (7 occurrences)
  • award-id (6 occurrences)
```

## How Coverage is Calculated

The method:

1. **Scans all elements** - Iterates through the entire XML tree to collect unique element types
2. **Counts occurrences** - Tracks how many times each element appears
3. **Extracts configured patterns** - Parses all XPath patterns from ElementPatterns configuration
4. **Matches elements** - Compares document elements against configured patterns
5. **Adds structural elements** - Includes common JATS/PMC structural elements
6. **Calculates metrics** - Computes coverage percentage and categorizes elements

### Recognized Elements Include

Elements are considered "recognized" if they appear in:

- `citation_types` (e.g., element-citation, mixed-citation)
- `author_element_patterns` (e.g., contrib, name)
- `author_field_patterns` (e.g., surname, given-names)
- `journal_patterns` (e.g., journal-title, issn, volume)
- `article_patterns` (e.g., article-title, abstract, doi)
- `table_patterns` (e.g., table, thead, tbody, tr, td)
- `reference_patterns` (e.g., source, year, fpage)
- `inline_element_patterns` (e.g., sup, sub, italic, bold)
- Common structural elements (e.g., article, front, body, back, sec, p)

## Use Cases

### 1. Quality Assurance

Validate that your parser configuration covers all important elements in your XML documents:

```python
coverage = parser.validate_schema_coverage()

if coverage['coverage_percentage'] < 70:
    print("⚠️ Low coverage - review unrecognized elements")
elif coverage['coverage_percentage'] < 90:
    print("✓ Good coverage - consider adding high-frequency unrecognized elements")
else:
    print("✅ Excellent coverage!")
```

### 2. Configuration Optimization

Identify which elements to add to custom configurations:

```python
# Find top 5 unrecognized elements
coverage = parser.validate_schema_coverage()
unrecognized_freq = [
    (elem, coverage['element_frequency'][elem])
    for elem in coverage['unrecognized_elements']
]
unrecognized_freq.sort(key=lambda x: x[1], reverse=True)

print("Add these to ElementPatterns:")
for elem, freq in unrecognized_freq[:5]:
    print(f"  • {elem}")
```

### 3. Document Comparison

Compare schema coverage across different XML documents:

```python
from pathlib import Path

results = []
for xml_file in Path("xml_files").glob("*.xml"):
    parser = FullTextXMLParser(xml_file.read_text())
    coverage = parser.validate_schema_coverage()
    results.append({
        'file': xml_file.name,
        'coverage': coverage['coverage_percentage'],
        'unrecognized': coverage['unrecognized_count']
    })

# Find documents with lowest coverage
results.sort(key=lambda x: x['coverage'])
print("Documents needing attention:")
for r in results[:5]:
    print(f"  {r['file']}: {r['coverage']:.1f}% ({r['unrecognized']} unrecognized)")
```

## Demo Script

A complete demo script is available at `examples/schema_coverage_demo.py`:

```bash
python examples/schema_coverage_demo.py
```

This script:
- Loads a sample XML file
- Runs schema coverage analysis
- Displays comprehensive results
- Provides recommendations for improving coverage

## Integration with Tests

The schema coverage validation includes comprehensive unit tests:

```bash
pytest tests/test_flexible_parsing.py::TestSchemaCoverageValidation -v
```

Tests cover:
- Basic coverage analysis
- Unrecognized element detection
- Element frequency counting
- High coverage scenarios
- Table element recognition
- Error handling

## Best Practices

1. **Run regularly** - Check coverage when adding support for new XML sources
2. **Prioritize by frequency** - Focus on elements that appear often
3. **Consider use case** - Not all elements need patterns (e.g., formatting elements)
4. **Document decisions** - Note why certain elements are left unrecognized
5. **Update configurations** - Add patterns for important unrecognized elements

## Performance Notes

- Schema coverage analysis is fast (< 100ms for typical documents)
- Results are cached in `_schema` attribute during detect_schema()
- Element frequency counting adds minimal overhead
- Suitable for batch processing of multiple documents

## See Also

- [ElementPatterns Configuration](../docs/advanced/element-patterns.md)
- [Schema Detection](../docs/advanced/schema-detection.md)
- [Custom Configurations](../docs/advanced/custom-configs.md)
- [Advanced Examples Notebook](advanced_fulltext_example.ipynb)
