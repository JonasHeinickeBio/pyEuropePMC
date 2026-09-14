"""Content the structured extractor used to drop.

`get_full_text_sections_structured` is the RAG-facing API, and two containers
lost their text entirely - present in `get_full_text_sections()` and
`to_plaintext()`, absent from the structured blocks:

* a <fig> was rendered from its label, caption and graphic alone, so a
  <disp-quote> describing the figure was discarded
* <supplementary-material> was traversed with `findall("caption")`, direct
  children only, and the caption is often a child of a nested <media>

Across 124 real documents these accounted for 48 of the 19,964 body
sentences; one remains, in a shape not covered here.
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit


def _blocks(parser):
    return [b for s in parser.get_full_text_sections_structured() for b in s["content"]]


def _all_text(parser):
    out = []
    for b in _blocks(parser):
        out += [b.get("text") or "", b.get("caption") or ""]
        out += list(b.get("items") or [])
    return " ".join(x for x in out if x)


FIGURE_WITH_QUOTE = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>T</article-title>
</title-group></article-meta></front><body>
<sec><title>Results</title>
  <fig id="f1"><label>Fig. 1</label>
    <caption><p>CAPTION of the figure.</p></caption>
    <graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="f1.jpg"/>
    <disp-quote><p>QUOTE describing how the figure was produced.</p></disp-quote>
  </fig>
</sec></body></article>"""

SUPP_NESTED_CAPTION = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>T</article-title>
</title-group></article-meta></front><body>
<sec><title>Data</title>
  <supplementary-material>
    <media><caption><p>SUPPLEMENTARY description of the dataset.</p></caption></media>
  </supplementary-material>
</sec></body></article>"""


class TestFigureChildren:
    @pytest.fixture
    def parser(self):
        return FullTextXMLParser(FIGURE_WITH_QUOTE)

    def test_caption_still_present(self, parser):
        assert "CAPTION of the figure." in _all_text(parser)

    def test_disp_quote_inside_a_figure_survives(self, parser):
        """Dropped outright before: the figure block carried caption only."""
        assert "QUOTE describing how the figure was produced." in _all_text(parser)

    def test_figure_block_still_emitted(self, parser):
        assert any(b.get("type") == "figure" for b in _blocks(parser))

    def test_quote_becomes_its_own_block(self, parser):
        """Dispatched like any block-level child, not folded into the caption."""
        assert any(b.get("type") == "quote" for b in _blocks(parser))

    def test_flat_outputs_unchanged(self, parser):
        """These always had the text; the structured output was the odd one."""
        assert "QUOTE describing" in parser.to_plaintext()


class TestSupplementaryMaterial:
    @pytest.fixture
    def parser(self):
        return FullTextXMLParser(SUPP_NESTED_CAPTION)

    def test_caption_under_nested_media_is_found(self, parser):
        """`findall("caption")` took direct children only."""
        assert "SUPPLEMENTARY description of the dataset." in _all_text(parser)

    def test_supplementary_without_a_caption_keeps_its_text(self):
        xml = SUPP_NESTED_CAPTION.replace(
            "<media><caption><p>SUPPLEMENTARY description of the dataset.</p></caption></media>",
            "<p>BARE supplementary text with no caption element.</p>",
        )
        assert "BARE supplementary text" in _all_text(FullTextXMLParser(xml))


SUPP_CAPTION_AND_STRAY_P = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>T</article-title>
</title-group></article-meta></front><body>
<sec><title>Data</title>
  <supplementary-material id="s1" content-type="local-data">
    <caption><title>CAPTION TITLE of the supplement.</title></caption>
    <media xlink:href="s1.docx" xmlns:xlink="http://www.w3.org/1999/xlink"/>
    <p>STRAY paragraph describing the supplement, outside the caption.</p>
  </supplementary-material>
</sec>
</body></article>"""


class TestSupplementaryStrayParagraphs:
    """A <p> outside the <caption> was dropped when a caption was present.

    The no-caption fallback only fires when the element yields nothing at all,
    so an item carrying both kept the caption and lost the paragraph. Found on
    PMC12301511; it was the last body sentence missing from the structured
    output across a 124-document corpus.
    """

    @pytest.fixture
    def parser(self):
        return FullTextXMLParser(SUPP_CAPTION_AND_STRAY_P)

    def test_caption_title_is_kept(self, parser):
        assert "CAPTION TITLE of the supplement." in _all_text(parser)

    def test_stray_paragraph_is_kept(self, parser):
        assert "STRAY paragraph describing the supplement" in _all_text(parser)

    def test_each_appears_once(self, parser):
        text = _all_text(parser)
        assert text.count("CAPTION TITLE of the supplement.") == 1
        assert text.count("STRAY paragraph describing the supplement") == 1
