"""A <mixed-citation> carrying structured children must be read structurally.

JATS allows <mixed-citation> to hold the same children as <element-citation>
- <person-group>, <article-title>, <source>, <year> - or to be a run of plain
text. The parser ran its regex over the flattened text first and only then
consulted the structure "for any missing fields"; since the regex fills title
and source on almost any input, the correct values were computed and thrown
away.

Over 124 real documents, of the 665 mixed-citations carrying an
<article-title> the extracted title matched it exactly 535 times before and
653 after; of the 149 carrying a <person-group>, a complete author list came
back 16 times before and 149 after.
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit


def _article(ref_body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><article><back><ref-list>'
        f'<ref id="r1">{ref_body}</ref>'
        "</ref-list></back></article>"
    )


STRUCTURED = _article(
    '<mixed-citation publication-type="journal">'
    '<person-group person-group-type="author">'
    "<name><surname>Albritton</surname><given-names>E.</given-names></name>"
    "<name><surname>Hernandez-Cancio</surname><given-names>S.</given-names></name>"
    "<name><surname>Lutz</surname><given-names>W.</given-names></name>"
    "</person-group> (<year>2016</year>). "
    "<article-title>How states can fund community health workers</article-title>. "
    "<source>Families USA</source>."
    "</mixed-citation>"
)

PLAIN_TEXT = _article(
    "<mixed-citation>Smith J. A study of things. Journal of Things, 2019.</mixed-citation>"
)


class TestStructuredMixedCitation:
    @pytest.fixture
    def ref(self):
        return FullTextXMLParser(STRUCTURED).extract_references()[0]

    def test_title_is_the_article_title(self, ref):
        """The regex used to put the second author here."""
        assert ref["title"] == "How states can fund community health workers"

    def test_source_is_the_journal(self, ref):
        """The regex used to put the third author here."""
        assert ref["source"] == "Families USA"

    def test_every_author_is_kept(self, ref):
        """Only the first author survived the text path."""
        for surname in ("Albritton", "Hernandez-Cancio", "Lutz"):
            assert surname in ref["authors"]

    def test_year(self, ref):
        assert ref["year"] == "2016"


class TestPlainTextMixedCitationStillParsed:
    """The text path remains the fallback when there is no structure."""

    @pytest.fixture
    def ref(self):
        return FullTextXMLParser(PLAIN_TEXT).extract_references()[0]

    def test_something_is_extracted(self, ref):
        assert ref["citation_type"] == "mixed-citation"
        assert any(ref.get(k) for k in ("title", "source", "authors", "raw_citation"))

    def test_year_found_in_free_text(self, ref):
        assert ref["year"] == "2019"
