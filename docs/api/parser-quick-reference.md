# FullTextXMLParser Quick Reference

## Generic Base Functions Reference

### Text Extraction

#### `_extract_nested_texts(parent, outer_pattern, inner_patterns, join=" ")`
Extract and combine nested text fields.
```python
# Example: Extract author names
authors = self._extract_nested_texts(
    self.root,
    ".//contrib[@contrib-type='author']/name",
    ["given-names", "surname"],
    join=" "
)
# Result: ["John Smith", "Jane Doe"]
```

#### `_extract_flat_texts(parent, pattern, filter_empty=True, use_full_text=False)`
Extract text from flat element lists.
```python
# Example: Extract keywords
keywords = self._extract_flat_texts(self.root, ".//kwd")
# Result: ["keyword1", "keyword2", "keyword3"]

# Example: Extract paragraphs with full text
paragraphs = self._extract_flat_texts(
    section, ".//p", use_full_text=True
)
```

#### `_extract_structured_fields(parent, field_patterns, first_only=True)`
Extract multiple fields as a structured dict.
```python
# Example: Extract reference metadata
fields = self._extract_structured_fields(
    citation,
    {
        "title": "article-title",
        "source": "source",
        "year": "year",
        "volume": "volume",
    }
)
# Result: {"title": "...", "source": "...", "year": "...", "volume": "..."}
```

### Data Transformation

#### `_combine_page_range(fpage, lpage)`
Format page range.
```python
# Examples:
_combine_page_range("10", "15")  # → "10-15"
_combine_page_range("10", None)  # → "10"
_combine_page_range(None, None)  # → None
```

#### `_extract_section_structure(section)`
Extract section title and content.
```python
section_data = self._extract_section_structure(section_elem)
# Result: {"title": "Introduction", "content": "paragraph1\n\nparagraph2"}
```

#### `_get_text_content(element)`
Deep text extraction (includes all descendants).
```python
text = self._get_text_content(abstract_elem)
# Extracts all text recursively, handling nested elements
```

## Decision Tree: Which Function to Use?

```
Need to extract text from XML?
│
├─ Multiple nested fields to combine?
│  └─ Use: _extract_nested_texts()
│     Example: author names, contributor info
│
├─ Simple list of text elements?
│  └─ Use: _extract_flat_texts()
│     Example: keywords, simple lists
│
├─ Multiple fields from same parent?
│  └─ Use: _extract_structured_fields()
│     Example: reference metadata, citation info
│
├─ Page range formatting?
│  └─ Use: _combine_page_range()
│
├─ Section with title + content?
│  └─ Use: _extract_section_structure()
│
└─ Custom complex pattern?
   └─ Use: extract_elements_by_patterns()
      or combine multiple base functions
```

## Common Patterns

### Pattern 1: Extract List of Simple Text
```python
def extract_something_list(self) -> list[str]:
    if self.root is None:
        raise ParsingError(...)
    items = self._extract_flat_texts(self.root, ".//item-tag")
    logger.debug(f"Extracted items: {items}")
    return items
```

### Pattern 2: Extract List of Nested Structures
```python
def extract_contributors(self) -> list[str]:
    if self.root is None:
        raise ParsingError(...)
    contributors = self._extract_nested_texts(
        self.root,
        ".//contrib",
        ["name", "role"],
        join=" - "
    )
    logger.debug(f"Extracted contributors: {contributors}")
    return contributors
```

### Pattern 3: Extract Complex Metadata
```python
def extract_citation_info(self) -> dict[str, Any]:
    if self.root is None:
        raise ParsingError(...)

    # Extract structured fields
    fields = self._extract_structured_fields(
        citation_elem,
        {
            "title": "title",
            "year": "year",
            "fpage": "fpage",
            "lpage": "lpage",
        }
    )

    # Combine pages
    fields["pages"] = self._combine_page_range(
        fields.pop("fpage"),
        fields.pop("lpage")
    )

    logger.debug(f"Extracted citation: {fields}")
    return fields
```

### Pattern 4: Extract Hierarchical Content
```python
def extract_sections(self) -> list[dict[str, str]]:
    if self.root is None:
        raise ParsingError(...)

    sections = []
    for section in self.root.findall(".//sec"):
        section_data = self._extract_section_structure(section)
        sections.append(section_data)

    logger.debug(f"Extracted {len(sections)} sections")
    return sections
```

## Best Practices

### 1. Always Check Root
```python
if self.root is None:
    raise ParsingError(
        ErrorCodes.PARSE003,
        {"message": "No XML content has been parsed. Call parse() first."},
    )
```

### 2. Always Log Results
```python
logger.debug(f"Extracted {len(items)} items: {items}")
```

### 3. Use Type Hints
```python
def extract_something(self) -> list[str]:
    ...

def extract_metadata(self) -> dict[str, Any]:
    ...
```

### 4. Document Parameters
```python
def _extract_custom(
    self,
    parent: ET.Element,
    pattern: str,
    transform: bool = False,
) -> list[str]:
    """
    Extract custom data from XML.

    Parameters
    ----------
    parent : ET.Element
        Parent element to search within
    pattern : str
        XPath pattern to find elements
    transform : bool
        If True, apply transformation
    """
```

### 5. Handle Edge Cases
```python
# Empty results
if not items:
    return []

# None values
if value is None:
    return None

# Filter empties
results = [r for r in raw_results if r]
```

## Performance Tips

1. **Reuse parsed root**: Don't parse multiple times
2. **Use specific patterns**: `.//sec/title` better than `.//title`
3. **Batch extractions**: Use `extract_elements_by_patterns()` for multiple fields
4. **Cache when possible**: Store frequently accessed elements

## Testing Your Extraction Function

```python
def test_extract_custom():
    xml = '''<article>
        <custom>value1</custom>
        <custom>value2</custom>
    </article>'''

    parser = FullTextXMLParser(xml)
    results = parser.extract_custom()

    assert len(results) == 2
    assert "value1" in results
    assert "value2" in results
```

## Troubleshooting

### Problem: No results returned
- Check XPath pattern syntax
- Verify XML structure matches pattern
- Use `list_element_types()` to see available elements
- Add logging to see what's being found

### Problem: Empty strings
- Use `use_full_text=True` for deep extraction
- Check `filter_empty` parameter
- Verify element actually has text content

### Problem: Wrong text extracted
- Check if you need `_get_text_content()` for nested text
- Verify pattern is specific enough
- Use element inspection to debug

## Additional Resources

- Full refactoring summary: `docs/parser-refactoring-summary.md`
- Parser implementation: `src/pyeuropepmc/fulltext_parser.py`
- Unit tests: `tests/parser/unit/test_fulltext_parser.py`
- Examples: `examples/fulltext_parser_demo.py`
