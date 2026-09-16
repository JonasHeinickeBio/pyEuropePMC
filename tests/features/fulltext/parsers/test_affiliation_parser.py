"""Tests for the AffiliationParser."""

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.features.fulltext.parsers.affiliation_parser import AffiliationParser


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
        root = DefusedET.fromstring(xml)
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
        root = DefusedET.fromstring(xml)
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
        root = DefusedET.fromstring(xml)
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
        root = DefusedET.fromstring(xml)
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
        root = DefusedET.fromstring(xml)
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
        root = DefusedET.fromstring(xml)
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
        root = DefusedET.fromstring(xml)
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
        root = DefusedET.fromstring(xml)
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
        root = DefusedET.fromstring(xml)
        parser = AffiliationParser(root)
        ids = parser._extract_institution_ids(root)
        assert ids == {}


EDITOR_AND_REVIEWERS = """<?xml version="1.0"?>
<article><front><article-meta>
<contrib-group>
  <contrib contrib-type="author"><name><surname>Rachubinski</surname></name>
    <xref ref-type="aff" rid="aff1">1</xref></contrib>
  <aff id="aff1"><label>1</label>
    <institution-id institution-id-type="ror">https://ror.org/03wmf1y16</institution-id>
    <institution>Linda Crnic Institute</institution>
    <city>Aurora</city></aff>
</contrib-group>
<contrib-group>
  <contrib contrib-type="editor"><name><surname>Marinazzo</surname></name></contrib>
  <aff><institution>Ghent University</institution></aff>
</contrib-group>
<contrib-group>
  <contrib contrib-type="editor"><name><surname>Scala</surname></name>
    <xref ref-type="aff" rid="edit1">1</xref></contrib>
</contrib-group>
<aff id="edit1"><institution>Sapienza University</institution></aff>
<aff id="aff9"><institution>Uncited Institute</institution></aff>
</article-meta></front>
<body><sec><p>Body.</p></sec></body>
<sub-article article-type="referee-report"><front-stub><contrib-group>
  <contrib contrib-type="author"><name><surname>Osorio</surname></name>
    <xref ref-type="aff" rid="sa1">1</xref></contrib>
  <aff id="sa1"><institution>Reviewer Institute</institution></aff>
</contrib-group></front-stub><body><p>Review.</p></body></sub-article>
</article>"""

GROUP_DIALECT = """<?xml version="1.0"?>
<article><front><article-meta>
<contrib-group content-type="author">
  <contrib><name><surname>Tong</surname></name>
    <xref ref-type="aff" rid="I1">1</xref></contrib>
</contrib-group>
<aff id="I1"><sup>1</sup>Department of Biochemistry, 8 Medical Drive, Singapore 117597</aff>
</article-meta></front><body><sec><p>Body.</p></sec></body></article>"""


class TestAffiliationScope:
    """Whose affiliations come back, and what their text says.

    `.//aff` matched the editors' affiliations and every peer-review
    <sub-article>'s: PMC11687933 has 8 author affiliations and returned 33.
    The text ran the <label> marker and each <institution-id> - a ROR URL, a
    GRID code, an ISNI - straight into the institution name, because the
    markup puts no whitespace between them (#248).
    """

    @pytest.fixture
    def affiliations(self):
        root = DefusedET.fromstring(EDITOR_AND_REVIEWERS)
        return AffiliationParser(root).extract_affiliations()

    def test_author_affiliations_in_document_order(self, affiliations):
        assert [a["id"] for a in affiliations] == ["aff1", "aff9"]

    def test_editor_affiliations_are_left_out(self, affiliations):
        text = " ".join(a["text"] for a in affiliations)
        assert "Ghent" not in text and "Sapienza" not in text

    def test_reviewer_affiliations_are_left_out(self, affiliations):
        assert "Reviewer Institute" not in " ".join(a["text"] for a in affiliations)

    def test_text_drops_the_label_and_the_institution_ids(self, affiliations):
        assert affiliations[0]["text"] == "Linda Crnic Institute Aurora"

    def test_institution_ids_are_still_reported_separately(self, affiliations):
        assert affiliations[0]["institution_ids"] == {"ror": "https://ror.org/03wmf1y16"}

    def test_a_superscript_marker_does_not_strip_digits_from_the_address(self):
        """The marker used to be removed by text, taking a street number."""
        root = DefusedET.fromstring(GROUP_DIALECT)
        affiliation = AffiliationParser(root).extract_affiliations()[0]
        assert affiliation["markers"] == "1"
        assert affiliation["institution_text"] == (
            "Department of Biochemistry, 8 Medical Drive, Singapore 117597"
        )
