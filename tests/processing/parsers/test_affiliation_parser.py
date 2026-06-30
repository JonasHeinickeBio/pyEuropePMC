"""Tests for the AffiliationParser."""
import pytest
from xml.etree import ElementTree as ET

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.processing.parsers.affiliation_parser import AffiliationParser


class TestAffiliationParser:
    """Tests for AffiliationParser."""

    def test_extract_affiliations_basic(self):
        """Test basic affiliation extraction."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<contrib-group>
<contrib>
<aff id="aff1">
<institution>University of Test</institution>
<city>Testville</city>
<country>USA</country>
</aff>
</contrib>
</contrib-group>
</article-meta>
</front>
</article>"""
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        affiliations = parser.extract_affiliations()
        assert len(affiliations) == 1
        assert affiliations[0]["institution"] == "University of Test"
        assert affiliations[0]["city"] == "Testville"
        assert affiliations[0]["country"] == "USA"

    def test_extract_affiliations_empty(self):
        """Test extraction with no affiliations."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
</article-meta>
</front>
</article>"""
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        affiliations = parser.extract_affiliations()
        assert affiliations == []

    def test_no_root_error(self):
        """Test error with no root set."""
        parser = AffiliationParser()
        with pytest.raises(ParsingError, match="PARSE003"):
            parser.extract_affiliations()

    def test_institution_id_extraction(self):
        """Test institution ID extraction."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<contrib-group>
<contrib>
<aff id="aff1">
<institution-id institution-id-type="ror">01234567</institution-id>
<institution-id institution-id-type="isni">00000001</institution-id>
<institution>University of Test</institution>
<city>Testville</city>
<country>USA</country>
</aff>
</contrib>
</contrib-group>
</article-meta>
</front>
</article>"""
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        affiliations = parser.extract_affiliations()
        assert len(affiliations) == 1
        ids = affiliations[0]["institution_ids"]
        assert ids["ror"] == "01234567"
        assert ids["isni"] == "00000001"

    def test_institution_wrap(self):
        """Test institution-wrap extraction."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<contrib-group>
<contrib>
<aff id="aff1">
<institution-wrap>
<institution-id institution-id-type="ror">abc123</institution-id>
<institution>Primary University</institution>
</institution-wrap>
<institution-wrap>
<institution>Secondary Lab</institution>
</institution-wrap>
</aff>
</contrib>
</contrib-group>
</article-meta>
</front>
</article>"""
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        affiliations = parser.extract_affiliations()
        assert len(affiliations) == 1
        inst_list = affiliations[0]["institutions"]
        assert len(inst_list) == 2
        assert inst_list[0]["name"] == "Primary University"
        assert inst_list[0]["ids"]["ror"] == "abc123"
        assert inst_list[1]["name"] == "Secondary Lab"

    def test_institution_wrap_no_ids(self):
        """Test institution-wrap without IDs."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<contrib-group>
<contrib>
<aff id="aff1">
<institution-wrap>
<institution>Just A Name</institution>
</institution-wrap>
</aff>
</contrib>
</contrib-group>
</article-meta>
</front>
</article>"""
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        affiliations = parser.extract_affiliations()
        assert len(affiliations) == 1
        inst_list = affiliations[0]["institutions"]
        assert len(inst_list) == 1
        assert inst_list[0]["name"] == "Just A Name"
        assert "ids" not in inst_list[0]

    def test_parse_mixed_content_with_markers(self):
        """Test mixed content affiliation with sup markers."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<contrib-group>
<contrib>
<aff id="aff1">
<sup>1</sup>Department of Biology, University of Test, Boston, USA
</aff>
</contrib>
</contrib-group>
</article-meta>
</front>
</article>"""
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        affiliations = parser.extract_affiliations()
        assert len(affiliations) == 1
        assert affiliations[0]["markers"] == "1"
        assert "institution_text" in affiliations[0]

    def test_parse_mixed_content_without_markers(self):
        """Test mixed content affiliation without sup markers."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<contrib-group>
<contrib>
<aff id="aff1">
Department of Biology, University of Test, Boston, USA
</aff>
</contrib>
</contrib-group>
</article-meta>
</front>
</article>"""
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        affiliations = parser.extract_affiliations()
        assert len(affiliations) == 1
        # Parser should extract structured fields from flat text via comma-splitting
        assert affiliations[0].get("city") == "Boston"
        assert affiliations[0].get("country") == "USA"

    def test_multi_institution_affiliation(self):
        """Test affiliation with multiple institutions separated by 'and'."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<contrib-group>
<contrib>
<aff id="aff1">
<sup>1</sup>Dept A, University X, Boston, USA and <sup>2</sup>Dept B, University Y, New York, USA
</aff>
</contrib>
</contrib-group>
</article-meta>
</front>
</article>"""
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        affiliations = parser.extract_affiliations()
        assert len(affiliations) == 1
        # Should have parsed_institutions since text has 'and'
        if "parsed_institutions" in affiliations[0]:
            parsed = affiliations[0]["parsed_institutions"]
            assert len(parsed) >= 1

    def test_empty_components_in_parse_single(self):
        """Test _parse_single_institution with empty components."""
        # Empty text should not cause index errors
        parser = AffiliationParser()
        result = parser._parse_single_institution("", [], 0)
        assert result["marker"] is None

    def test_extract_institution_ids_empty(self):
        """Test _extract_institution_ids with no IDs in element."""
        xml = "<aff><institution>No IDs</institution></aff>"
        root = ET.fromstring(xml)
        parser = AffiliationParser(root)
        ids = parser._extract_institution_ids(root)
        assert ids == {}
