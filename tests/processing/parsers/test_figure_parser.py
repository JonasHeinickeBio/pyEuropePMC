"""Tests for figure parser."""
import pytest
from xml.etree import ElementTree as ET

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.processing.parsers.figure_parser import FigureParser

SAMPLE_XML = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<body>
<sec>
<p>Some text</p>
<fig id="F1">
<label>Fig 1.</label>
<caption>
<p>A sample figure caption with <bold>bold</bold> text.</p>
</caption>
<graphic xlink:href="F1.jpg"/>
</fig>
<fig id="F2">
<label>Fig 2.</label>
<caption>
<p>Second figure.</p>
</caption>
<graphic xlink:href="F2.png"/>
</fig>
</sec>
</body>
</article>
"""

SAMPLE_XML_NO_GRAPHIC = """<?xml version="1.0"?>
<article>
<body>
<fig id="F1">
<label>Fig 1.</label>
<caption><p>Caption text.</p></caption>
</fig>
</body>
</article>
"""

SAMPLE_XML_NO_FIGS = """<?xml version="1.0"?>
<article>
<body>
<sec><p>No figures here.</p></sec>
</body>
</article>
"""


class TestFigureParser:
    """Tests for FigureParser."""

    def test_extract_figures_basic(self):
        """Test extracting figures from XML."""
        root = ET.fromstring(SAMPLE_XML)
        parser = FigureParser(root)
        figures = parser.extract_figures()

        assert len(figures) == 2
        assert figures[0]["id"] == "F1"
        assert figures[0]["label"] == "Fig 1."
        assert "sample figure caption" in (figures[0]["caption"] or "")
        assert figures[0]["graphic_uri"] == "F1.jpg"

        assert figures[1]["id"] == "F2"
        assert figures[1]["label"] == "Fig 2."
        assert figures[1]["graphic_uri"] == "F2.png"

    def test_extract_figures_no_figures(self):
        """Test extracting figures when no figures exist."""
        root = ET.fromstring(SAMPLE_XML_NO_FIGS)
        parser = FigureParser(root)
        figures = parser.extract_figures()
        assert figures == []

    def test_extract_figures_no_graphic(self):
        """Test extracting a figure without a graphic element."""
        root = ET.fromstring(SAMPLE_XML_NO_GRAPHIC)
        parser = FigureParser(root)
        figures = parser.extract_figures()

        assert len(figures) == 1
        assert figures[0]["id"] == "F1"
        assert figures[0]["label"] == "Fig 1."
        assert figures[0].get("graphic_uri") is None

    def test_require_root_raises(self):
        """Test that extracting without root raises error."""
        parser = FigureParser()
        with pytest.raises(ParsingError, match="PARSE003"):
            parser.extract_figures()

    def test_extract_first_text_from_element_no_match(self):
        """Test _extract_first_text_from_element returns None when no match."""
        root = ET.fromstring(SAMPLE_XML)
        parser = FigureParser(root)
        # Call with no matching element
        elem = root.find(".//fig")
        result = parser._extract_first_text_from_element(elem, {"nonexistent": "nonexistent"})
        assert result is None

    def test_with_config(self):
        """Test FigureParser with custom config."""
        from pyeuropepmc.processing.config.element_patterns import ElementPatterns

        config = ElementPatterns()
        root = ET.fromstring(SAMPLE_XML)
        parser = FigureParser(root, config)
        figures = parser.extract_figures()
        assert len(figures) == 2
