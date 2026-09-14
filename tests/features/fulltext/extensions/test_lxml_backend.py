"""Tests for the optional lxml parser backend."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

import pytest

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.features.fulltext.extensions.lxml_backend import (
    _HAS_LXML,
    LXMLParser,
    is_lxml_available,
)

pytestmark = pytest.mark.unit

# Skip all tests if lxml is not available
pytest.importorskip("lxml")


SIMPLE_XML = "<root><item id='1'>value</item></root>"


class TestLXMLParserInit:
    """Tests for LXMLParser.__init__."""

    def test_init_basic(self):
        """Test basic initialization."""
        parser = LXMLParser()
        assert parser.parser is not None

    def test_init_with_kwargs(self):
        """Test initialization with custom parameters."""
        parser = LXMLParser(recover=True, remove_blank_text=False)
        assert parser.parser is not None


class TestLXMLParserFromString:
    """Tests for LXMLParser.fromstring."""

    def test_fromstring_basic(self):
        """Test parsing a simple XML string."""
        root = LXMLParser.fromstring(SIMPLE_XML)
        assert root.tag.endswith("root")
        item = root.find(".//item")
        assert item is not None
        assert item.attrib.get("id") == "1"
        assert item.text == "value"

    def test_fromstring_malformed_xml(self):
        """Test that malformed XML raises ParsingError."""
        with pytest.raises(ParsingError, match="lxml XML parsing failed"):
            LXMLParser.fromstring("<root><broken></root>")

    def test_fromstring_empty_string(self):
        """Test that empty string raises ParsingError."""
        with pytest.raises(ParsingError):
            LXMLParser.fromstring("")

    def test_fromstring_xml_declaration(self):
        """Test parsing XML with declaration and namespace."""
        xml = '<?xml version="1.0"?><ns:root xmlns:ns="http://example.com"><ns:item>text</ns:item></ns:root>'
        root = LXMLParser.fromstring(xml)
        assert root.tag.endswith("root")

    @pytest.mark.parametrize(
        ("xml", "expected"),
        [
            pytest.param(
                '<?xml version="1.0" encoding="UTF-8"?><a>caf\u00e9</a>',
                "caf\u00e9",
                id="utf8-declared",
            ),
            pytest.param(
                '<?xml version="1.0" encoding="ISO-8859-1"?><a>caf\u00e9</a>',
                "caf\u00e9",
                id="latin1-declared",
            ),
            pytest.param(
                "<?xml version='1.0' encoding='latin-1'?><a>caf\u00e9</a>",
                "caf\u00e9",
                id="single-quoted-declaration",
            ),
            pytest.param(
                '<?xml version="1.0"?><a>caf\u00e9</a>', "caf\u00e9", id="no-encoding-attr"
            ),
            pytest.param("<a>caf\u00e9</a>", "caf\u00e9", id="no-declaration"),
            pytest.param(
                '\ufeff<?xml version="1.0" encoding="ISO-8859-1"?><a>caf\u00e9</a>',
                "caf\u00e9",
                id="bom-then-declaration",
            ),
        ],
    )
    def test_fromstring_accepts_declared_encodings(self, xml, expected):
        """A str with an encoding declaration parses, and text survives intact.

        lxml rejects a str carrying a declaration outright, and honours the
        declaration over supplied bytes - so a latin-1 declaration encoded to
        UTF-8 would silently yield 'caf\u00c3\u00a9'. Both are regressions worth
        holding: Europe PMC full text ships with these declarations.
        """
        assert LXMLParser.fromstring(xml).text == expected

    def test_fromstring_leaves_bytes_untouched(self):
        """bytes still mean what their declaration says; nothing is rewritten."""
        raw = '<?xml version="1.0" encoding="ISO-8859-1"?><a>caf\u00e9</a>'.encode("iso-8859-1")
        assert LXMLParser.fromstring(raw).text == "caf\u00e9"

    def test_fromstring_ignores_encoding_in_body_text(self):
        """Only a leading declaration is rewritten, never body content."""
        body = 'set encoding="ISO-8859-1" here'
        assert LXMLParser.fromstring(f"<a>{body}</a>").text == body

    @patch("pyeuropepmc.features.fulltext.extensions.lxml_backend.logger")
    def test_fromstring_logs_error(self, mock_logger):
        """Test that parsing errors are logged."""
        with pytest.raises(ParsingError):
            LXMLParser.fromstring("<root><broken></root>")
        mock_logger.error.assert_called_once()


class TestLXMLParserFromFile:
    """Tests for LXMLParser.fromfile."""

    def test_fromfile_basic(self, tmp_path: Path):
        """Test parsing an XML file."""
        filepath = tmp_path / "test.xml"
        filepath.write_text(SIMPLE_XML)
        root = LXMLParser.fromfile(str(filepath))
        assert root.tag.endswith("root")

    def test_fromfile_not_found(self):
        """Test that missing file raises ParsingError."""
        with pytest.raises(ParsingError, match="lxml file parsing failed"):
            LXMLParser.fromfile("/nonexistent/path.xml")

    @patch("pyeuropepmc.features.fulltext.extensions.lxml_backend.logger")
    def test_fromfile_logs_error(self, mock_logger):
        """Test that file errors are logged."""
        with pytest.raises(ParsingError):
            LXMLParser.fromfile("/nonexistent/path.xml")
        mock_logger.error.assert_called_once()


class TestLXMLParserEnableFor:
    """Tests for LXMLParser.enable_for."""

    def test_enable_for_replaces_parse_method(self):
        """Test that enable_for replaces the parse method."""
        mock_parser = MagicMock()
        original_parse = mock_parser.parse

        LXMLParser.enable_for(mock_parser)
        assert mock_parser.parse is not original_parse

    def test_enable_for_with_xml_content(self):
        """Test enable_for with immediate XML parsing."""
        mock_parser = MagicMock()
        mock_parser.xml_content = None
        mock_parser.root = None

        LXMLParser.enable_for(mock_parser, SIMPLE_XML)
        assert mock_parser.xml_content is not None
        assert mock_parser.root is not None
        mock_parser._reset_parsers.assert_called_once()

    def test_enable_for_with_et_element(self):
        """Test enable_for with an already-parsed ET.Element."""
        mock_parser = MagicMock()
        existing_root = ET.fromstring(SIMPLE_XML)

        LXMLParser.enable_for(mock_parser)
        # Calling the new parse method with an ET.Element should fall back
        # to the original parse method
        result = mock_parser.parse(existing_root)
        assert result is not None

    def test_enable_for_passes_kwargs(self):
        """Test that enable_for passes kwargs to LXMLParser."""
        mock_parser = MagicMock()
        LXMLParser.enable_for(mock_parser, recover=True)
        # Should succeed (recover=True is a valid lxml kwarg)
        result = mock_parser.parse(SIMPLE_XML)
        assert result is not None


class TestLXMLParserEdgeCases:
    """Tests for edge cases."""

    def test_is_lxml_available(self):
        """Test that is_lxml_available returns True when lxml is installed."""
        assert is_lxml_available() is True
        assert _HAS_LXML is True

    def test_parser_property(self):
        """Test the parser property."""
        parser = LXMLParser()
        assert hasattr(parser, "parser")
        # Should return the lxml parser
        assert parser.parser is parser._parser  # noqa: SLF001

    def test_multiple_patches(self):
        """Test enable_for called multiple times on same parser."""
        mock_parser = MagicMock()
        LXMLParser.enable_for(mock_parser, SIMPLE_XML)
        parse_fn_1 = mock_parser.parse

        LXMLParser.enable_for(mock_parser, "<root>other</root>")
        parse_fn_2 = mock_parser.parse
        # Each call should create a new wrapper
        assert parse_fn_1 is not parse_fn_2
