"""
Functional tests for FullTextXMLParser.

Tests the full text XML parser against real XML fixtures to ensure
end-to-end functionality for metadata extraction, format conversion,
table extraction, and schema detection.
"""

import pytest
import logging
from pathlib import Path

from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser, ElementPatterns, DocumentSchema
from pyeuropepmc.core.exceptions import ParsingError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fulltext_parser_functional_test")

# Test fixture directory
FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "fulltext_downloads"


def get_fulltext_xml_files():
    """Get all XML files from the fulltext downloads fixture directory."""
    if not FIXTURE_DIR.exists():
        logger.warning(f"Fixture directory does not exist: {FIXTURE_DIR}")
        return []
    return [f.name for f in FIXTURE_DIR.glob("*.xml")]


class TestFullTextXMLParserFunctional:
    """Functional tests for FullTextXMLParser with real fixtures."""

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_parse_real_xml_file(self, filename):
        """Test parsing real XML files from fixtures."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        try:
            parser = FullTextXMLParser(xml_content)
            logger.info(f"✅ Successfully parsed {filename}")

            # Verify parser was initialized
            assert parser.xml_content is not None
            assert parser.root is not None

        except ParsingError as e:
            logger.error(f"❌ ParsingError for {filename}: {e}")
            pytest.fail(f"Failed to parse {filename}: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error for {filename}: {e}")
            pytest.fail(f"Unexpected error parsing {filename}: {e}")

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_extract_metadata_from_real_files(self, filename):
        """Test metadata extraction from real XML files."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        metadata = parser.extract_metadata()

        logger.info(f"[{filename}] Extracted metadata keys: {list(metadata.keys())}")

        # Verify metadata structure
        assert isinstance(metadata, dict), "Metadata should be a dictionary"

        # Check for expected metadata fields
        expected_fields = ['title', 'authors', 'abstract', 'journal', 'publication_date']
        for field in expected_fields:
            if field in metadata:
                logger.info(f"  ✅ {field}: {type(metadata[field])}")
            else:
                logger.warning(f"  ⚠️ {field}: missing")

        # At least some metadata should be present
        assert len(metadata) > 0, f"No metadata extracted from {filename}"

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_extract_authors_from_real_files(self, filename):
        """Test author extraction from real XML files."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        authors = parser.extract_authors()

        logger.info(f"[{filename}] Extracted {len(authors)} authors")

        # Verify authors structure
        assert isinstance(authors, list), "Authors should be a list"

        if authors:
            # Check first author - extract_authors returns list[str]
            first_author = authors[0]
            assert isinstance(first_author, str), "Each author should be a string"

            # Log author information
            logger.info(f"  First author: {first_author}")
            if len(authors) > 1:
                logger.info(f"  All authors: {', '.join(authors[:3])}...")

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_extract_references_from_real_files(self, filename):
        """Test reference extraction from real XML files."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        references = parser.extract_references()

        logger.info(f"[{filename}] Extracted {len(references)} references")

        # Verify references structure
        assert isinstance(references, list), "References should be a list"

        if references:
            # Check first reference structure
            first_ref = references[0]
            assert isinstance(first_ref, dict), "Each reference should be a dictionary"

            # Log reference information
            logger.info(f"  First reference fields: {list(first_ref.keys())}")
            if 'authors' in first_ref and first_ref['authors']:
                if isinstance(first_ref['authors'], list):
                    logger.info(f"    Authors: {len(first_ref['authors'])} authors")
            if 'title' in first_ref and first_ref['title']:
                title_preview = str(first_ref['title'])[:50]
                logger.info(f"    Title: {title_preview}...")

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_extract_tables_from_real_files(self, filename):
        """Test table extraction from real XML files."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        tables = parser.extract_tables()

        logger.info(f"[{filename}] Extracted {len(tables)} tables")

        # Verify tables structure
        assert isinstance(tables, list), "Tables should be a list"

        if tables:
            # Check first table structure
            first_table = tables[0]
            assert isinstance(first_table, dict), "Each table should be a dictionary"

            # Log table information
            logger.info(f"  First table fields: {list(first_table.keys())}")
            if 'label' in first_table:
                logger.info(f"    Label: {first_table['label']}")
            if 'caption' in first_table:
                logger.info(f"    Caption: {first_table['caption'][:50]}...")
            if 'rows' in first_table and first_table['rows']:
                logger.info(f"    Rows: {len(first_table['rows'])}")
            if 'headers' in first_table and first_table['headers']:
                logger.info(f"    Headers: {len(first_table['headers'])}")

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_detect_schema_from_real_files(self, filename):
        """Test schema detection from real XML files."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        schema = parser.detect_schema()

        logger.info(f"[{filename}] Detected schema:")
        logger.info(f"  Has tables: {schema.has_tables}")
        logger.info(f"  Has figures: {schema.has_figures}")
        logger.info(f"  Has supplementary: {schema.has_supplementary}")
        logger.info(f"  Has acknowledgments: {schema.has_acknowledgments}")
        logger.info(f"  Has funding: {schema.has_funding}")
        logger.info(f"  Citation types: {schema.citation_types}")
        logger.info(f"  Table structure: {schema.table_structure}")

        # Verify schema structure
        assert isinstance(schema, DocumentSchema), "Schema should be DocumentSchema instance"
        assert isinstance(schema.has_tables, bool)
        assert isinstance(schema.has_figures, bool)

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_to_plaintext_from_real_files(self, filename):
        """Test conversion to plaintext from real XML files."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        plaintext = parser.to_plaintext()

        logger.info(f"[{filename}] Generated plaintext: {len(plaintext)} characters")

        # Verify plaintext generation
        assert isinstance(plaintext, str), "Plaintext should be a string"
        assert len(plaintext) > 0, f"Plaintext should not be empty for {filename}"

        # Log first 200 characters
        logger.info(f"  Preview: {plaintext[:200]}...")

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_to_markdown_from_real_files(self, filename):
        """Test conversion to markdown from real XML files."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        markdown = parser.to_markdown()

        logger.info(f"[{filename}] Generated markdown: {len(markdown)} characters")

        # Verify markdown generation
        assert isinstance(markdown, str), "Markdown should be a string"
        assert len(markdown) > 0, f"Markdown should not be empty for {filename}"

        # Check for markdown formatting
        has_headers = '#' in markdown
        has_bold_italic = '**' in markdown or '*' in markdown

        logger.info(f"  Has headers: {has_headers}")
        logger.info(f"  Has formatting: {has_bold_italic}")

        # Log first 200 characters
        logger.info(f"  Preview: {markdown[:200]}...")

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_custom_config_with_real_files(self, filename):
        """Test parser with custom ElementPatterns configuration."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        # Create custom configuration with additional citation types
        custom_config = ElementPatterns(
            citation_types={"types": ["element-citation", "mixed-citation", "nlm-citation", "citation", "ref"]}
        )

        parser = FullTextXMLParser(xml_content, config=custom_config)
        references = parser.extract_references()

        logger.info(f"[{filename}] With custom config: {len(references)} references")

        # Verify custom config was applied
        assert parser.config.citation_types == custom_config.citation_types
        assert isinstance(references, list)

    def test_integration_workflow_complete(self):
        """Test complete integration workflow: parse, extract all, convert all."""
        xml_files = get_fulltext_xml_files()

        if not xml_files:
            pytest.skip("No XML fixtures available for integration test")

        # Use first available XML file
        filename = xml_files[0]
        xml_path = FIXTURE_DIR / filename

        logger.info(f"\n{'='*60}")
        logger.info(f"INTEGRATION TEST: Complete workflow with {filename}")
        logger.info(f"{'='*60}\n")

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        # Step 1: Initialize parser
        logger.info("Step 1: Initialize parser")
        parser = FullTextXMLParser(xml_content)
        assert parser is not None
        logger.info("  ✅ Parser initialized")

        # Step 2: Detect schema
        logger.info("\nStep 2: Detect schema")
        schema = parser.detect_schema()
        logger.info(f"  Capabilities: tables={schema.has_tables}, "
                   f"figures={schema.has_figures}, supplementary={schema.has_supplementary}, "
                   f"acknowledgments={schema.has_acknowledgments}, funding={schema.has_funding}")
        logger.info(f"  Citation types: {schema.citation_types}")
        logger.info("  ✅ Schema detected")

        # Step 3: Extract metadata
        logger.info("\nStep 3: Extract metadata")
        metadata = parser.extract_metadata()
        logger.info(f"  Fields: {list(metadata.keys())}")
        if 'title' in metadata:
            logger.info(f"  Title: {metadata['title'][:80]}...")
        logger.info("  ✅ Metadata extracted")

        # Step 4: Extract authors
        logger.info("\nStep 4: Extract authors")
        authors = parser.extract_authors()
        logger.info(f"  Count: {len(authors)} authors")
        if authors:
            logger.info(f"  First author: {authors[0]}")
        logger.info("  ✅ Authors extracted")

        # Step 5: Extract references
        logger.info("\nStep 5: Extract references")
        references = parser.extract_references()
        logger.info(f"  Count: {len(references)} references")
        logger.info("  ✅ References extracted")

        # Step 6: Extract tables
        logger.info("\nStep 6: Extract tables")
        tables = parser.extract_tables()
        logger.info(f"  Count: {len(tables)} tables")
        logger.info("  ✅ Tables extracted")

        # Step 7: Convert to plaintext
        logger.info("\nStep 7: Convert to plaintext")
        plaintext = parser.to_plaintext()
        logger.info(f"  Length: {len(plaintext)} characters")
        logger.info("  ✅ Plaintext generated")

        # Step 8: Convert to markdown
        logger.info("\nStep 8: Convert to markdown")
        markdown = parser.to_markdown()
        logger.info(f"  Length: {len(markdown)} characters")
        logger.info("  ✅ Markdown generated")

        logger.info(f"\n{'='*60}")
        logger.info("INTEGRATION TEST: PASSED ✅")
        logger.info(f"{'='*60}\n")

        # Verify all steps completed
        assert metadata is not None
        assert isinstance(authors, list)
        assert isinstance(references, list)
        assert isinstance(tables, list)
        assert len(plaintext) > 0
        assert len(markdown) > 0

    def test_error_handling_malformed_xml(self):
        """Test error handling with malformed XML."""
        malformed_xml_samples = [
            "",  # Empty
            "<broken>",  # Unclosed tag
            "Not XML at all",  # Plain text
            "<?xml version='1.0'?><article>",  # Unclosed root
        ]

        for idx, xml_content in enumerate(malformed_xml_samples):
            logger.info(f"\nTesting malformed XML #{idx + 1}: {xml_content[:50]}...")

            with pytest.raises(ParsingError) as exc_info:
                FullTextXMLParser(xml_content)

            error_msg = str(exc_info.value)
            logger.info(f"  ✅ Raised ParsingError: {error_msg[:100]}...")

            # Verify error message is informative
            assert len(error_msg) > 10, "Error message should be informative"

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_roundtrip_consistency(self, filename):
        """Test that multiple parses of same file produce consistent results."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        # Parse twice
        parser1 = FullTextXMLParser(xml_content)
        parser2 = FullTextXMLParser(xml_content)

        # Extract metadata twice
        metadata1 = parser1.extract_metadata()
        metadata2 = parser2.extract_metadata()

        # Compare keys (values might differ slightly due to processing)
        assert set(metadata1.keys()) == set(metadata2.keys()), \
            "Multiple parses should produce same metadata keys"

        # Extract authors twice
        authors1 = parser1.extract_authors()
        authors2 = parser2.extract_authors()

        assert len(authors1) == len(authors2), \
            "Multiple parses should produce same number of authors"

        logger.info(f"[{filename}] Roundtrip consistency: ✅")

    @pytest.mark.parametrize("filename", get_fulltext_xml_files())
    def test_output_format_compatibility(self, filename):
        """Test that different output formats contain compatible information."""
        xml_path = FIXTURE_DIR / filename

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)

        # Get metadata
        metadata = parser.extract_metadata()

        # Get plaintext and markdown
        plaintext = parser.to_plaintext()
        markdown = parser.to_markdown()

        # If title exists in metadata, it should appear in both text formats
        if 'title' in metadata and metadata['title']:
            title = metadata['title'].strip()
            if len(title) > 10:  # Only check substantial titles
                # Title should appear in at least one of the text formats
                in_plaintext = title[:30] in plaintext
                in_markdown = title[:30] in markdown

                assert in_plaintext or in_markdown, \
                    f"Title should appear in plaintext or markdown: {title[:50]}"

                logger.info(f"[{filename}] Title appears in: "
                          f"plaintext={in_plaintext}, markdown={in_markdown}")


# Fixtures for test data
@pytest.fixture
def sample_xml_path():
    """Provide path to first available XML fixture."""
    xml_files = get_fulltext_xml_files()
    if not xml_files:
        pytest.skip("No XML fixtures available")
    return FIXTURE_DIR / xml_files[0]


@pytest.fixture
def sample_xml_content(sample_xml_path):
    """Provide content of first available XML fixture."""
    with open(sample_xml_path, 'r', encoding='utf-8') as f:
        return f.read()


@pytest.fixture
def sample_parser(sample_xml_content):
    """Provide initialized parser with sample XML."""
    return FullTextXMLParser(sample_xml_content)


class TestParserFixtures:
    """Tests using pytest fixtures for common scenarios."""

    def test_parser_initialization(self, sample_parser):
        """Test that parser initializes correctly."""
        assert sample_parser is not None
        assert sample_parser.xml_content is not None
        assert sample_parser.root is not None

    def test_metadata_extraction(self, sample_parser):
        """Test metadata extraction with fixture."""
        metadata = sample_parser.extract_metadata()
        assert isinstance(metadata, dict)
        assert len(metadata) > 0

    def test_schema_detection(self, sample_parser):
        """Test schema detection with fixture."""
        schema = sample_parser.detect_schema()
        assert isinstance(schema, DocumentSchema)

    def test_format_conversions(self, sample_parser):
        """Test all format conversions with fixture."""
        plaintext = sample_parser.to_plaintext()
        markdown = sample_parser.to_markdown()

        assert isinstance(plaintext, str)
        assert isinstance(markdown, str)
        assert len(plaintext) > 0
        assert len(markdown) > 0


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
