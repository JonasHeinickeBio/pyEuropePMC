"""Text extraction must not invent spacing the document does not have.

`get_text_content` stripped every text fragment and joined the results with a
space, which separates an inline element from the text it sits against:

    PM<sub>2.5</sub>                ->  "PM 2.5"
    (<xref>Kumar, 2021</xref>; ...) ->  "( Kumar, 2021 ; ...)"

Both are wrong for a reader and for anything tokenising the text. Taking the
fragments bare fixes them but goes too far: "<title>G</title>text" is two
blocks that need a gap, and the markup is not obliged to supply one. So
inline runs keep the source's spacing and block-level children are padded.

Across 124 real documents this took exact article titles from 122 to 124;
`PM2.5` had been coming back as `PM 2.5`.
"""

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.utils.xml_helpers import XMLHelper

pytestmark = pytest.mark.unit


def text_of(xml: str) -> str:
    return XMLHelper.get_text_content(DefusedET.fromstring(xml))


class TestInlineElementsKeepSourceSpacing:
    @pytest.mark.parametrize(
        ("xml", "expected"),
        [
            pytest.param("<p>PM<sub>2.5</sub> levels</p>", "PM2.5 levels", id="subscript-midword"),
            pytest.param("<p>H<sub>2</sub>O and CO<sub>2</sub></p>", "H2O and CO2", id="formulae"),
            pytest.param("<p>x<sup>2</sup>+1</p>", "x2+1", id="superscript"),
            pytest.param(
                "<p>see (<xref>Kumar, 2021</xref>; <xref>Lee, 2022</xref>) here</p>",
                "see (Kumar, 2021; Lee, 2022) here",
                id="citations-in-parentheses",
            ),
            pytest.param("<p>a <italic>word</italic> b</p>", "a word b", id="spaced-italic"),
            pytest.param("<p>pre<bold>mid</bold>post</p>", "premidpost", id="no-spaces-at-all"),
        ],
    )
    def test_spacing_is_taken_from_the_document(self, xml, expected):
        assert text_of(xml) == expected

    def test_runs_of_whitespace_are_collapsed(self):
        assert text_of("<p>  spaced   \n out  </p>") == "spaced out"


class TestBlockElementsAreSeparated:
    def test_title_followed_by_bare_text(self):
        """The markup supplies no gap here, and the two are distinct blocks."""
        assert text_of("<glossary><title>G</title>text here</glossary>") == "G text here"

    def test_adjacent_paragraphs(self):
        assert text_of("<sec><title>T</title><p>One.</p><p>Two.</p></sec>") == "T One. Two."

    def test_table_cells_do_not_run_together(self):
        xml = "<tr><td>left</td><td>right</td></tr>"
        assert text_of(xml) == "left right"


class TestEdgeCases:
    def test_none_element(self):
        assert XMLHelper.get_text_content(None) == ""

    def test_empty_element(self):
        assert text_of("<p/>") == ""

    def test_whitespace_only(self):
        assert text_of("<p>   </p>") == ""
