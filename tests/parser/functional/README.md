# FullTextXMLParser Functional Tests

## Overview

This directory contains comprehensive functional tests for the `FullTextXMLParser` class, which parses full text XML from Europe PMC articles.

## Test Coverage

The functional test suite (`test_fulltext_parser_functional.py`) validates real-world usage of the FullTextXMLParser with actual Europe PMC XML fixtures.

### Test Categories

#### 1. **Basic Parsing Tests**
- `test_parse_real_xml_file` - Validates parser initialization with real XML files
- Ensures XML content is properly loaded and root element is accessible

#### 2. **Metadata Extraction Tests**
- `test_extract_metadata_from_real_files` - Tests metadata extraction (title, authors, abstract, journal, publication date)
- `test_extract_authors_from_real_files` - Tests author name extraction
- Validates metadata structure and field presence

#### 3. **Reference Extraction Tests**
- `test_extract_references_from_real_files` - Tests bibliography/citation extraction
- Validates reference structure (authors, title, source, year, volume, pages)

#### 4. **Table Extraction Tests**
- `test_extract_tables_from_real_files` - Tests table data extraction
- Validates table structure (label, caption, headers, rows)

#### 5. **Schema Detection Tests**
- `test_detect_schema_from_real_files` - Tests XML schema capability detection
- Checks for: tables, figures, supplementary materials, acknowledgments, funding info

#### 6. **Format Conversion Tests**
- `test_to_plaintext_from_real_files` - Tests XML → plaintext conversion
- `test_to_markdown_from_real_files` - Tests XML → markdown conversion
- Validates output format and content preservation

#### 7. **Configuration Tests**
- `test_custom_config_with_real_files` - Tests custom ElementPatterns configuration
- Validates that custom citation types are applied correctly

#### 8. **Integration Tests**
- `test_integration_workflow_complete` - End-to-end workflow test
  - Initialize parser
  - Detect schema capabilities
  - Extract metadata, authors, references, tables
  - Convert to plaintext and markdown
  - Validate all steps complete successfully

#### 9. **Error Handling Tests**
- `test_error_handling_malformed_xml` - Tests behavior with invalid XML
- Validates appropriate ParsingError exceptions are raised

#### 10. **Consistency Tests**
- `test_roundtrip_consistency` - Tests that multiple parses produce consistent results
- `test_output_format_compatibility` - Tests that title appears in output formats

### Fixtures

The tests use real Europe PMC XML files from `tests/fixtures/fulltext_downloads/`:
- **PMC3258128.xml** - Full text article XML
- **PMC3359999.xml** - Full text article XML

These fixtures contain actual article data with:
- Complete metadata (title, authors, journal info)
- Abstract and full text sections
- Bibliography/references
- Tables and figures (where present)
- Multiple XML schema variations (JATS, NLM)

## Running the Tests

### Run All Functional Tests
```bash
pytest tests/parser/functional/test_fulltext_parser_functional.py -v
```

### Run with Detailed Output
```bash
pytest tests/parser/functional/test_fulltext_parser_functional.py -v -s
```

### Run Specific Test Category
```bash
# Run only integration test
pytest tests/parser/functional/test_fulltext_parser_functional.py::TestFullTextXMLParserFunctional::test_integration_workflow_complete -v

# Run only metadata extraction tests
pytest tests/parser/functional/test_fulltext_parser_functional.py::TestFullTextXMLParserFunctional::test_extract_metadata_from_real_files -v

# Run only format conversion tests
pytest tests/parser/functional/test_fulltext_parser_functional.py -k "plaintext or markdown" -v
```

### Run with Coverage
```bash
pytest tests/parser/functional/test_fulltext_parser_functional.py --cov=pyeuropepmc.fulltext_parser --cov-report=html
```

## Test Statistics

- **Total Tests**: 28
- **Test Classes**: 2 (TestFullTextXMLParserFunctional, TestParserFixtures)
- **Parametrized Tests**: Most tests run against 2 XML fixtures (56 test executions)
- **Coverage Areas**:
  - ✅ Parser initialization
  - ✅ Metadata extraction (title, authors, journal, dates)
  - ✅ Author extraction
  - ✅ Reference/bibliography extraction
  - ✅ Table extraction
  - ✅ Schema detection
  - ✅ Plaintext conversion
  - ✅ Markdown conversion
  - ✅ Custom configuration
  - ✅ Error handling
  - ✅ Roundtrip consistency
  - ✅ Format compatibility

## Comparison with Unit Tests

**Unit Tests** (`tests/parser/unit/test_fulltext_parser.py`):
- Use synthetic SAMPLE_ARTICLE_XML for controlled testing
- Test individual methods in isolation
- Focus on code paths and edge cases
- 783 lines, 23+ tests

**Functional Tests** (`tests/parser/functional/test_fulltext_parser_functional.py`):
- Use real Europe PMC XML fixtures
- Test end-to-end workflows
- Focus on real-world usage validation
- 540+ lines, 28 tests

**Together**, these test suites provide comprehensive coverage:
- Unit tests ensure correctness of individual components
- Functional tests validate real-world applicability

## Key Features Tested

### 1. **Flexible XML Schema Handling**
The parser handles multiple XML schema variations:
- JATS (Journal Article Tag Suite)
- NLM (National Library of Medicine) DTD
- Custom Europe PMC schemas

### 2. **Fallback Pattern System**
Tests validate the ElementPatterns configuration system that provides:
- Multiple fallback element patterns
- Different citation type support
- Flexible author/journal/article metadata patterns

### 3. **Output Format Fidelity**
Tests ensure:
- Plaintext preserves structure and content
- Markdown uses proper formatting (headers, bold, links)
- Metadata appears consistently across formats

### 4. **Error Resilience**
Tests validate:
- Graceful handling of malformed XML
- Informative error messages
- Proper exception types (ParsingError)

## Adding New Tests

To add new functional tests:

1. **Add new XML fixtures** to `tests/fixtures/fulltext_downloads/`
2. **Create parametrized test** using `@pytest.mark.parametrize("filename", get_fulltext_xml_files())`
3. **Follow existing pattern**:
   ```python
   def test_new_feature(self, filename):
       xml_path = FIXTURE_DIR / filename
       with open(xml_path, 'r', encoding='utf-8') as f:
           xml_content = f.read()
       parser = FullTextXMLParser(xml_content)
       # Test your feature
   ```

## CI/CD Integration

These functional tests are:
- ✅ Included in CI/CD pipeline (`.github/workflows/cdci.yml`)
- ✅ Run on every push and pull request
- ✅ Required to pass for merging
- ✅ Contribute to coverage metrics (75% minimum required)

## Troubleshooting

**Tests fail with "No XML fixtures available"**:
- Ensure `tests/fixtures/fulltext_downloads/` contains XML files
- Run `scripts/download_fixtures.py` to fetch fixtures

**Tests timeout or hang**:
- Check for large XML files (>5MB)
- Consider adding timeout markers: `@pytest.mark.timeout(30)`

**Inconsistent results**:
- Check for race conditions in parallel test execution
- Verify fixture files haven't been modified

## Future Enhancements

Potential additions to the functional test suite:

- [ ] **Performance benchmarking** - Track parsing speed for large documents
- [ ] **Memory profiling** - Ensure efficient memory usage
- [ ] **Multi-format fixtures** - Add more XML schema variations
- [ ] **Comparative testing** - Compare output against expected reference files
- [ ] **Regression tests** - Add specific tests for reported bugs
- [ ] **Fuzzing** - Generate random/malformed XML for robustness testing

## Resources

- **FullTextXMLParser Source**: `src/pyeuropepmc/fulltext_parser.py`
- **Unit Tests**: `tests/parser/unit/test_fulltext_parser.py`
- **Demo Scripts**: `examples/fulltext_parser_demo.py`, `examples/fulltext_parser_simple_demo.py`
- **Documentation**: `docs/features/fulltext-parsing.md`
- **Europe PMC API**: https://europepmc.org/RestfulWebService

## Contributing

When adding functional tests:
1. ✅ Use real XML fixtures (not synthetic)
2. ✅ Test end-to-end workflows (not just individual methods)
3. ✅ Add logging with `logger.info()` for debugging
4. ✅ Validate data types and structure
5. ✅ Include error cases
6. ✅ Document expected behavior
7. ✅ Run full test suite before committing

---

**Last Updated**: 2025
**Test Suite Version**: 1.0
**Total Coverage**: 28 functional tests + 23 unit tests = 51 total FullTextXMLParser tests
