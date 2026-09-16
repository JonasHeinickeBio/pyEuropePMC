"""to_plaintext(), to_markdown() and get_full_text_sections() on hand-written JATS.

Each renderer collected a section's <p> elements and little else, so what was
not a paragraph reached it only through a <p> nested inside: a figure lost its
label and caption title, a table its label and every cell outside a <p>, a code
listing everything. to_markdown() also escaped nothing, so "DRB1*0402 ...
DQB1*0503" opened an emphasis and "<node>" was passed through as HTML.
"""

from __future__ import annotations

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = [pytest.mark.unit]


def _article(body: str, back: str = "") -> str:
    return (
        '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
        "<title-group><article-title>A study</article-title></title-group>"
        f"</article-meta></front><body>{body}</body><back>{back}</back></article>"
    )


SECTION = (
    "<sec><title>Results</title>"
    "<p>Before the figure.</p>"
    "<fig><label>Figure 1</label><caption><title>Design.</title><p>The model.</p></caption></fig>"
    "<table-wrap><label>Table 1</label><caption><p>Doses.</p></caption><table>"
    "<thead><tr><th>Name</th><th>Dose</th></tr></thead>"
    "<tbody><tr><td>Drug A</td><td>10 mg</td></tr></tbody></table></table-wrap>"
    '<preformat xml:space="preserve">def f(x):\n    return x</preformat>'
    "<p>After the listing.</p></sec>"
)


def _parser(body: str = SECTION, back: str = "") -> FullTextXMLParser:
    return FullTextXMLParser(_article(body, back))


class TestPlaintext:
    def test_blocks_in_document_order(self):
        text = _parser().to_plaintext()
        order = [
            "Before the figure.",
            "Figure 1 Design. The model.",
            "Table 1 Doses.",
            "Drug A | 10 mg",
            "def f(x):\n    return x",
            "After the listing.",
        ]
        positions = [text.index(part) for part in order]
        assert positions == sorted(positions)

    def test_an_appendix_that_is_a_table_keeps_its_cells(self):
        """to_plaintext() rendered only an appendix's <p>: this came out as its title."""
        back = (
            "<app-group><app><title>Supplementary table</title><table-wrap><table>"
            "<tr><td>gene</td><td>score</td></tr></table></table-wrap></app></app-group>"
        )
        text = _parser("<sec><p>Body.</p></sec>", back).to_plaintext()
        assert "Appendix: Supplementary table" in text
        assert "gene | score" in text


class TestMarkdown:
    def test_figure_table_and_listing(self):
        markdown = _parser().to_markdown()
        assert "**Figure 1** Design. The model." in markdown
        assert "**Table 1** Doses." in markdown
        assert "| Name | Dose |\n| --- | --- |\n| Drug A | 10 mg |" in markdown
        assert "```\ndef f(x):\n    return x\n```" in markdown

    def test_text_is_escaped(self):
        body = (
            "<sec><title>DRB1*0402 model</title>"
            "<p>DRB1*0402 and DQB1*0503 bind; use <monospace>&lt;node&gt;/&lt;op&gt;</monospace>.</p>"
            "</sec>"
        )
        markdown = _parser(body).to_markdown()
        assert "## DRB1\\*0402 model" in markdown
        assert "DRB1\\*0402 and DQB1\\*0503 bind; use \\<node\\>/\\<op\\>." in markdown

    def test_a_listing_is_not_escaped(self):
        body = '<sec><preformat language="python">a_b = x * 2</preformat></sec>'
        assert "```python\na_b = x * 2\n```" in _parser(body).to_markdown()

    def test_a_list(self):
        body = (
            '<sec><list list-type="order"><list-item><p>first</p></list-item>'
            "<list-item><p>second_one</p></list-item></list></sec>"
        )
        assert "1. first\n2. second\\_one" in _parser(body).to_markdown()

    def test_an_appendix_is_laid_out_like_a_section(self):
        back = (
            "<app-group><app><title>Extra</title><table-wrap><table>"
            "<tr><td>a</td><td>b</td></tr></table></table-wrap></app></app-group>"
        )
        markdown = _parser("<sec><p>Body.</p></sec>", back).to_markdown()
        assert "## Appendix: Extra" in markdown
        assert "| a | b |" in markdown


class TestSections:
    def test_content_carries_every_block(self):
        content = _parser().get_full_text_sections()[0]["content"]
        assert content.split("\n\n") == [
            "Before the figure.",
            "Figure 1 Design. The model.",
            "Table 1 Doses.\nName | Dose\nDrug A | 10 mg",
            "def f(x):\n    return x",
            "After the listing.",
        ]

    def test_bare_body_content(self):
        sections = _parser(
            "<p>Opening.</p><disp-formula><label>(1)</label>x=1</disp-formula>"
        ).get_full_text_sections()
        assert sections[-1] == {"title": "", "content": "Opening.\n\nx=1 (1)"}


class TestStructuredCode:
    def test_a_code_block_keeps_its_line_breaks(self):
        blocks = [
            block
            for section in _parser().get_full_text_sections_structured()
            for block in section["content"]
            if block["type"] == "code"
        ]
        assert blocks[0]["text"] == "def f(x):\n    return x"


class TestFloatsGroup:
    """Figures and tables an NIH author manuscript keeps outside <body>."""

    ARTICLE = (
        '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
        "<title-group><article-title>A study</article-title></title-group></article-meta></front>"
        '<body><sec><title>Results</title><p>See <xref ref-type="fig" rid="F1">Figure 1</xref>.</p>'
        "</sec></body><back><ack><p>Thanks.</p></ack></back>"
        '<floats-group><fig id="F1"><label>Figure 1</label><caption><p>Dose response.</p></caption>'
        '</fig><table-wrap id="T1"><label>Table 1</label><caption><p>Doses.</p></caption><table>'
        "<tr><td>cocaine</td><td>3.0 mg/kg</td></tr></table></table-wrap></floats-group>"
        "<sub-article><floats-group><fig><label>Review figure</label></fig></floats-group>"
        "</sub-article></article>"
    )

    def _parser(self) -> FullTextXMLParser:
        return FullTextXMLParser(self.ARTICLE)

    def test_plaintext(self):
        text = self._parser().to_plaintext()
        floats = text.index(
            "Figures and Tables\nFigure 1 Dose response.\nTable 1 Doses.\ncocaine | 3.0 mg/kg"
        )
        assert text.index("See Figure 1.") < floats < text.index("Acknowledgments")

    def test_markdown(self):
        markdown = self._parser().to_markdown()
        assert (
            "## Figures and Tables\n\n**Figure 1** Dose response.\n\n**Table 1** Doses."
            in markdown
        )
        assert "| cocaine | 3.0 mg/kg |" in markdown

    def test_sections(self):
        sections = self._parser().get_full_text_sections()
        assert {
            "title": "Figures and Tables",
            "content": ("Figure 1 Dose response.\n\nTable 1 Doses.\ncocaine | 3.0 mg/kg"),
        } in sections

    def test_structured(self):
        sections = self._parser().get_full_text_sections_structured()
        floats = [s for s in sections if s["title"] == "Figures and Tables"]
        assert len(floats) == 1
        assert floats[0]["section_type"] == "body"
        assert [b["label"] for b in floats[0]["content"]] == ["Figure 1", "Table 1"]

    def test_a_sub_articles_floats_are_not_the_articles(self):
        parser = self._parser()
        assert "Review figure" not in parser.to_plaintext()
        assert "Review figure" not in str(parser.get_full_text_sections_structured())
