"""Tests for section parser."""
import pytest
from xml.etree import ElementTree as ET

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.processing.parsers.section_parser import SectionParser

SAMPLE_XML = """<?xml version="1.0"?>
<article>
<body>
<sec>
<title>Introduction</title>
<p>Intro text.</p>
</sec>
<sec>
<title>Methods</title>
<p>Methods text.</p>
</sec>
</body>
</article>
"""

PLOS_STYLE_XML = """<?xml version="1.0"?>
<article>
<body>
<p>Paragraph 1 directly under body.</p>
<p>Paragraph 2 directly under body.</p>
</body>
</article>
"""

EMPTY_SECTION_XML = """<?xml version="1.0"?>
<article>
<body>
<sec>
<title />
</sec>
<sec>
<title>Has Content</title>
<p>Some text.</p>
</sec>
</body>
</article>
"""

APPENDIX_XML = """<?xml version="1.0"?>
<article>
<body>
<sec><title>Main</title><p>Main text.</p></sec>
</body>
<back>
<app>
<title>Appendix A</title>
<p>Appendix content.</p>
</app>
<author-notes>
<p>Author note content.</p>
</author-notes>
<glossary>
<p>Glossary content.</p>
</glossary>
</back>
</article>
"""


class TestSectionParser:
    """Tests for SectionParser."""

    def test_get_full_text_sections(self):
        """Extract sections with titles and content."""
        root = ET.fromstring(SAMPLE_XML)
        parser = SectionParser(root)
        sections = parser.get_full_text_sections()

        assert len(sections) == 2
        assert sections[0]["title"] == "Introduction"
        assert "Intro text" in sections[0]["content"]
        assert sections[1]["title"] == "Methods"
        assert "Methods text" in sections[1]["content"]

    def test_require_root_raises(self):
        """Extracting without root raises error."""
        parser = SectionParser()
        with pytest.raises(ParsingError, match="PARSE003"):
            parser.get_full_text_sections()

    def test_bare_p_elements(self):
        """Extract bare <p> elements directly under <body> (PLOS style)."""
        root = ET.fromstring(PLOS_STYLE_XML)
        parser = SectionParser(root)
        sections = parser.get_full_text_sections()

        assert len(sections) >= 1
        assert sections[0]["title"] == ""
        assert "Paragraph 1" in sections[0]["content"]
        assert "Paragraph 2" in sections[0]["content"]

    def test_empty_section_included(self):
        """Section with empty content is included but has empty fields."""
        root = ET.fromstring(EMPTY_SECTION_XML)
        parser = SectionParser(root)
        sections = parser.get_full_text_sections()

        # Both sections are included (empty section_data is a non-empty dict)
        assert len(sections) == 2
        assert sections[0]["title"] == ""
        assert sections[0]["content"] == ""
        assert sections[1]["title"] == "Has Content"

    def test_additional_content_structures(self):
        """Extract author-notes, appendices, and glossary."""
        root = ET.fromstring(APPENDIX_XML)
        parser = SectionParser(root)
        sections = parser.get_full_text_sections()

        # Check author notes
        notes = [s for s in sections if s.get("type") == "author_notes"]
        assert len(notes) == 1
        assert "Author note content" in notes[0]["content"]

        # Check appendix
        apps = [s for s in sections if s.get("type") == "appendix"]
        assert len(apps) >= 1
        assert "Appendix" in apps[0]["title"]

        # Check glossary
        gloss = [s for s in sections if s.get("type") == "glossary"]
        assert len(gloss) == 1
        assert "Glossary content" in gloss[0]["content"]

    def test_section_with_custom_config(self):
        """SectionParser with custom config."""
        root = ET.fromstring(SAMPLE_XML)
        config = type("Config", (), {"content_structure_patterns": {}, "appendix_patterns": {}})()
        parser = SectionParser(root, config)
        sections = parser.get_full_text_sections()
        assert len(sections) == 2
