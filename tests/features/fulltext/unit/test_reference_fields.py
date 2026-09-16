"""Reference fields match what the citation tags, in each publisher's dialect.

Measured on five Europe PMC articles:

* PLOS writes a <mixed-citation>'s contributors as bare <name> children,
  with no <person-group>. Those were not read, and the text pass that took
  over ran surname and initials together: "NewtonSI", in 53 of 53
  references of PMC10775981.
* the text pass then assigned volume, pages, DOI and PMID whether or not
  the tagged elements had already given them, so "385-430" became "385" and
  a DOI followed by its PMID became "10.1098/rstb.2001.091011545699".
* BMC's text-only citations carry identifiers as
  <ext-link ext-link-type="pmid" xlink:href="9008308"/>, an empty element,
  so every PMID was lost (0 of 45 in PMC1764484); and "48:662–667" gave
  pages "662" because only an ASCII hyphen counted as a range.
* eLife titles software and datasets with <data-title> and names the
  repository in <source>; the title came back as "GitHub". A <collab>
  among the authors was dropped.
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit


def _reference(citation: str) -> dict:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<article xmlns:xlink="http://www.w3.org/1999/xlink"><back><ref-list>'
        f'<ref id="r1">{citation}</ref>'
        "</ref-list></back></article>"
    )
    return FullTextXMLParser(xml).extract_references()[0]


PLOS_BOOK = (
    '<mixed-citation publication-type="book">'
    '<name name-style="western"><surname>Newton</surname><given-names>SI</given-names></name>. '
    "<source>Philosophiae naturalis principia mathematica</source>. "
    "<publisher-name>G. Brookman</publisher-name>; <year>1833</year>.</mixed-citation>"
)

PLOS_CHAPTER = (
    '<mixed-citation publication-type="book">'
    "<name><surname>Hutt</surname><given-names>A</given-names></name>. "
    "<part-title>Synergetics: An Introduction</part-title>. In: "
    "<name><surname>Hutt</surname><given-names>A</given-names></name>, "
    "<name><surname>Haken</surname><given-names>H</given-names></name>, editors. "
    "<source>Encyclopedia of Complexity and Systems Science</source>. "
    "<year>2020</year>. p. <fpage>1</fpage>–<lpage>3</lpage>.</mixed-citation>"
)

PLOS_TAGGED = (
    '<mixed-citation publication-type="journal">'
    "<name><surname>Kötter</surname><given-names>R</given-names></name>. "
    "<article-title>Towards NeuroML</article-title>. <source>Phil Trans R Soc B</source>. "
    "<year>2001</year>;<volume>356</volume>:<fpage>385</fpage>–<lpage>430</lpage>. "
    '<comment>doi: </comment><pub-id pub-id-type="doi">10.1098/rstb.2001.0910</pub-id>'
    '<pub-id pub-id-type="pmid">11545699</pub-id></mixed-citation>'
)

BMC_TEXT_ONLY = (
    "<mixed-citation>"
    '<named-content content-type="citation-string">Carcassi C, Cottoni F, Contu L. '
    "HLA haplotypes in Sardinian patients. Tissue Antigens. 1996;48:662–667. "
    "doi: 10.1111/j.1399-0039.1996.tb02689.x.</named-content>"
    '<ext-link ext-link-type="doi" xlink:href="10.1111/j.1399-0039.1996.tb02689.x"/>'
    '<ext-link ext-link-type="pmid" xlink:href="9008308"/>'
    '<ext-link ext-link-type="pmcid" xlink:href="PMC280240"/>'
    '<ext-link ext-link-type="google-scholar" xlink:href="journal=Tissue Antigens"/>'
    "</mixed-citation>"
)

ELIFE_SOFTWARE = (
    '<element-citation publication-type="software">'
    '<person-group person-group-type="author">'
    "<name><surname>Diggins</surname><given-names>K</given-names></name>"
    "<name><surname>Irish</surname><given-names>J</given-names></name>"
    "</person-group><year>2017</year><data-title>MEM</data-title>"
    '<version designator="3">3</version><source>GitHub</source>'
    "</element-citation>"
)

ELIFE_COLLAB = (
    '<element-citation publication-type="journal">'
    '<person-group person-group-type="author">'
    "<name><surname>Johnson</surname><given-names>MB</given-names></name>"
    "<collab>International DS-PNDM Consortium</collab>"
    "<name><surname>Hattersley</surname><given-names>AT</given-names></name>"
    "</person-group>"
    '<person-group person-group-type="editor">'
    "<name><surname>Editor</surname><given-names>E</given-names></name>"
    "</person-group>"
    "<article-title>Trisomy 21 is a cause of permanent neonatal diabetes</article-title>"
    "<source>Diabetes</source><year>2019</year>"
    "</element-citation>"
)


class TestPlosBareNames:
    def test_surname_and_initials_are_kept_apart(self):
        assert _reference(PLOS_BOOK)["authors"] == "Newton, SI"

    def test_a_chapters_editors_are_not_its_authors(self):
        assert _reference(PLOS_CHAPTER)["authors"] == "Hutt, A"

    def test_a_chapter_is_titled_by_its_part_title(self):
        ref = _reference(PLOS_CHAPTER)
        assert ref["title"] == "Synergetics: An Introduction"
        assert ref["source"] == "Encyclopedia of Complexity and Systems Science"


class TestTaggedValuesSurviveTheTextPass:
    @pytest.fixture
    def ref(self):
        return _reference(PLOS_TAGGED)

    def test_tagged_page_range(self, ref):
        assert ref["pages"] == "385-430"

    def test_tagged_doi_is_not_run_into_the_pmid(self, ref):
        assert ref["doi"] == "10.1098/rstb.2001.0910"
        assert ref["pmid"] == "11545699"

    def test_tagged_volume(self, ref):
        assert ref["volume"] == "356"


class TestBmcTextOnlyCitations:
    @pytest.fixture
    def ref(self):
        return _reference(BMC_TEXT_ONLY)

    def test_identifiers_are_read_from_the_link_target(self, ref):
        assert (ref["pmid"], ref["pmcid"]) == ("9008308", "PMC280240")
        assert ref["doi"] == "10.1111/j.1399-0039.1996.tb02689.x"

    def test_an_en_dash_range_keeps_its_last_page(self, ref):
        assert (ref["volume"], ref["pages"]) == ("48", "662-667")

    def test_the_text_still_supplies_title_and_source(self, ref):
        assert ref["title"] == "HLA haplotypes in Sardinian patients"
        assert ref["source"] == "Tissue Antigens"


class TestElifeCitations:
    def test_software_is_titled_by_its_data_title(self):
        ref = _reference(ELIFE_SOFTWARE)
        assert (ref["title"], ref["source"]) == ("MEM", "GitHub")

    def test_a_collaboration_author_is_kept_in_place(self):
        assert _reference(ELIFE_COLLAB)["authors"] == (
            "Johnson, MB, International DS-PNDM Consortium, Hattersley, AT"
        )

    def test_editors_are_not_authors(self):
        assert "Editor" not in _reference(ELIFE_COLLAB)["authors"]


class TestStringName:
    def test_structured_string_name(self):
        ref = _reference(
            '<element-citation><person-group person-group-type="author">'
            "<string-name><surname>Bartel</surname><given-names>DP</given-names></string-name>"
            "</person-group><article-title>MicroRNAs</article-title></element-citation>"
        )
        assert ref["authors"] == "Bartel, DP"

    def test_unstructured_string_name(self):
        ref = _reference(
            '<element-citation><person-group person-group-type="author">'
            "<string-name>D. P. Bartel</string-name>"
            "</person-group><article-title>MicroRNAs</article-title></element-citation>"
        )
        assert ref["authors"] == "D. P. Bartel"
