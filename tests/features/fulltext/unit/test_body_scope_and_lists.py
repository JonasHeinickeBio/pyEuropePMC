"""Body scoping and list rendering, found by auditing 124 real documents.

Three defects that only showed up at corpus scale:

* ``.//body`` also matches the <body> of every <sub-article>, so peer-review
  reports were returned as article sections. 9 of 124 documents carried
  sub-articles, 377,847 characters of foreign text between them.
* ``_process_list_plaintext`` rendered only the first <p> of each list item,
  and matched nested items twice.
* Content under <body> but outside any <sec> was found with ``./p``, which
  misses a <p> wrapped in <boxed-text>.
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit

PEER_REVIEWED = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>T</article-title>
</title-group></article-meta></front>
<body><sec><title>Results</title><p>ARTICLE BODY TEXT.</p></sec></body>
<sub-article article-type="reviewer-report">
  <body><sec><title>Review</title><p>REVIEWER COMMENTS.</p></sec></body>
</sub-article>
</article>"""

BOXED_AND_LISTS = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>T</article-title>
</title-group></article-meta></front><body>
<boxed-text><p>BOXED body-level text outside any section.</p></boxed-text>
<sec><title>Methods</title>
  <p>Intro sentence.
    <list list-type="bullet">
      <list-item><p>ITEM ONE paragraph.</p><p>ITEM ONE second paragraph.</p></list-item>
      <list-item>ITEM TWO with no paragraph wrapper.</list-item>
    </list>
  </p>
</sec>
</body></article>"""


class TestSubArticleBodiesExcluded:
    @pytest.fixture
    def parser(self):
        return FullTextXMLParser(PEER_REVIEWED)

    def test_sections_exclude_reviewer_text(self, parser):
        joined = "\n".join(s["content"] for s in parser.get_full_text_sections())
        assert "ARTICLE BODY TEXT." in joined
        assert "REVIEWER COMMENTS." not in joined

    def test_plaintext_excludes_reviewer_text(self, parser):
        out = parser.to_plaintext()
        assert "ARTICLE BODY TEXT." in out
        assert "REVIEWER COMMENTS." not in out

    def test_markdown_excludes_reviewer_text(self, parser):
        out = parser.to_markdown()
        assert "ARTICLE BODY TEXT." in out
        assert "REVIEWER COMMENTS." not in out


class TestBodyLevelBoxedText:
    def test_boxed_text_outside_a_section_is_kept(self):
        """`./p` missed it; the walk stops at <sec> but enters wrappers."""
        p = FullTextXMLParser(BOXED_AND_LISTS)
        joined = "\n".join(s["content"] for s in p.get_full_text_sections())
        assert "BOXED body-level text" in joined
        assert "BOXED body-level text" in p.to_plaintext()


class TestListRendering:
    @pytest.fixture
    def plain(self):
        return FullTextXMLParser(BOXED_AND_LISTS).to_plaintext()

    def test_second_paragraph_of_an_item_survives(self, plain):
        """Only `item_text[0]` was rendered, so this was dropped."""
        assert plain.count("ITEM ONE second paragraph.") == 1

    def test_item_without_a_paragraph_wrapper_survives(self, plain):
        """An item holding text directly produced nothing at all."""
        assert plain.count("ITEM TWO with no paragraph wrapper.") == 1

    def test_list_text_is_not_also_emitted_by_its_wrapping_paragraph(self, plain):
        assert plain.count("ITEM ONE paragraph.") == 1

    def test_wrapping_paragraph_keeps_its_own_text(self, plain):
        assert plain.count("Intro sentence.") == 1


TABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>T</article-title>
</title-group></article-meta></front><body>
<sec><title>Results</title>
  <p>Ordinary paragraph.</p>
  <table-wrap id="t1">
    <caption><p>CAPTION of the table.</p></caption>
    <table><tbody>
      <tr><td><p>CELL first paragraph.</p><p>CELL second paragraph.</p></td></tr>
    </tbody></table>
    <table-wrap-foot><fn><p>FOOTNOTE explaining the abbreviations.</p></fn></table-wrap-foot>
  </table-wrap>
</sec>
</body></article>"""


class TestTableRendering:
    """<caption> and <table-wrap-foot> are siblings of <table>, not children."""

    @pytest.fixture
    def plain(self):
        return FullTextXMLParser(TABLE_XML).to_plaintext()

    def test_caption_is_rendered(self, plain):
        """Selecting the inner <table> put the caption out of reach."""
        assert "CAPTION of the table." in plain

    def test_footer_is_rendered(self, plain):
        """The footer carries the table's notes and abbreviation keys."""
        assert "FOOTNOTE explaining the abbreviations." in plain

    def test_whole_cell_is_rendered(self, plain):
        """Only the first extracted string per cell was kept."""
        assert "CELL second paragraph." in plain

    def test_table_content_is_not_also_emitted_as_paragraphs(self, plain):
        """The paragraph walk descends into <table-wrap> unless stopped.

        Cells and captions would otherwise be collected as section paragraphs
        as well as rendered by the table renderer.
        """
        for text in ("CAPTION of the table.", "CELL first paragraph.",
                     "FOOTNOTE explaining the abbreviations."):
            assert plain.count(text) == 1, f"{text!r} appears {plain.count(text)}x"

    def test_ordinary_paragraph_unaffected(self, plain):
        assert plain.count("Ordinary paragraph.") == 1
