"""JATSNormalizer does what its configuration and docstrings say.

Each case is a shape taken from a real Europe PMC document:

* numeric character references for "<" and "&" were decoded before parsing,
  which broke the XML (PMC3258128 writes ``P&#x02009;&#x0003c;&#x02009;0.05``);
* the DOI and the authors came from peer-review <sub-article> elements, and
  authorship declared on the <contrib-group> gave no authors;
* sections were neither in document order nor reversed;
* ``strip_display_markup`` and ``flatten_xrefs`` only ever acted together;
* MathML was dropped with its text, and the text after it;
* ``bytes`` were decoded as UTF-8 whatever the XML declaration said.
"""

from __future__ import annotations

import codecs

import pytest

from pyeuropepmc.features.fulltext.jats_normalizer import JATSNormalizer

pytestmark = pytest.mark.unit

MML = 'xmlns:mml="http://www.w3.org/1998/Math/MathML"'


def _body(inner: str) -> str:
    return f"<article><body><sec><title>Results</title>{inner}</sec></body></article>"


class TestNumericCharacterReferences:
    def test_escaped_less_than_and_ampersand_parse(self):
        xml = _body("<p>P&#x02009;&#x0003c;&#x02009;0.05 in R &#x00026; D &#60; &#38;</p>")
        text = JATSNormalizer().normalize_xml(xml)["body_text"]
        assert "P < 0.05 in R & D < &" in text

    def test_named_entities_are_still_resolved(self):
        xml = _body("<p>&alpha; at 37&deg;C</p>")
        assert "α at 37°C" in JATSNormalizer().normalize_xml(xml)["body_text"]


PEER_REVIEWED = """<article article-type="research-article"><front><article-meta>
  <article-id pub-id-type="doi">10.1371/journal.pcbi.1011761</article-id>
  <contrib-group>
    <contrib contrib-type="author"><name><surname>Gast</surname><given-names>R</given-names></name></contrib>
  </contrib-group>
</article-meta></front>
<body><sec><title>Introduction</title><p>Text.</p></sec></body>
<sub-article article-type="aggregated-review-documents"><front-stub>
  <article-id pub-id-type="doi">10.1371/journal.pcbi.1011761.r001</article-id>
  <contrib-group>
    <contrib contrib-type="author"><name><surname>Reviewer</surname><given-names>A</given-names></name></contrib>
  </contrib-group>
</front-stub><body><p>Review.</p></body></sub-article>
</article>"""

GROUP_DIALECT = """<article><front><article-meta>
  <contrib-group content-type="author">
    <contrib><name><surname>Tong</surname><given-names>Joo Chuan</given-names></name></contrib>
    <contrib><name><surname>Tan</surname><given-names>Tin Wee</given-names></name></contrib>
  </contrib-group>
  <contrib-group content-type="editor">
    <contrib><name><surname>Editor</surname><given-names>E</given-names></name></contrib>
  </contrib-group>
</article-meta></front><body><sec><title>Background</title><p>Text.</p></sec></body></article>"""


class TestMetadataScope:
    def test_doi_is_the_articles_own(self):
        metadata = JATSNormalizer().normalize_xml(PEER_REVIEWED)["metadata"]
        assert metadata["doi"] == "10.1371/journal.pcbi.1011761"

    def test_reviewers_are_not_authors(self):
        metadata = JATSNormalizer().normalize_xml(PEER_REVIEWED)["metadata"]
        assert [a["name"] for a in metadata["authors"]] == ["R Gast"]

    def test_group_level_authorship(self):
        metadata = JATSNormalizer().normalize_xml(GROUP_DIALECT)["metadata"]
        assert [a["name"] for a in metadata["authors"]] == ["Joo Chuan Tong", "Tin Wee Tan"]


class TestSectionOrder:
    def test_document_order_with_subsections_after_their_parent(self):
        xml = """<article><body>
          <sec><title>1. Introduction</title><p>a</p></sec>
          <sec><title>2. Methods</title><p>b</p>
            <sec><title>2.1 Animals</title><p>c</p></sec>
            <sec><title>2.2 Drugs</title><p>d</p>
              <sec><title>2.2.1 Doses</title><p>e</p></sec>
            </sec>
          </sec>
          <sec><title>3. Results</title><p>f</p></sec>
        </body></article>"""
        sections = JATSNormalizer().normalize_xml(xml)["sections"]
        assert [(s["title"], s["level"]) for s in sections] == [
            ("1. Introduction", 0),
            ("2. Methods", 0),
            ("2.1 Animals", 1),
            ("2.2 Drugs", 1),
            ("2.2.1 Doses", 2),
            ("3. Results", 0),
        ]
        assert [s["text"] for s in sections] == ["a", "b", "c", "d", "e", "f"]


MARKUP = _body('<p>Some <bold>bold <xref rid="f1">Fig 1</xref></bold> here.</p>')


class TestMarkupFlags:
    @staticmethod
    def _counts(**flags):
        root = JATSNormalizer(**flags).normalize_xml(MARKUP)["normalized_root"]
        return len(list(root.iter("bold"))), len(list(root.iter("xref")))

    def test_both_on(self):
        assert self._counts() == (0, 0)

    def test_markup_kept_xrefs_flattened(self):
        """The CLI's --no-markup; it used to change nothing."""
        assert self._counts(strip_display_markup=False) == (1, 0)

    def test_markup_stripped_xrefs_kept(self):
        """An <xref> inside a stripped <bold> used to vanish with it."""
        assert self._counts(flatten_xrefs=False) == (0, 1)

    def test_both_off(self):
        assert self._counts(strip_display_markup=False, flatten_xrefs=False) == (1, 1)

    def test_unwrapping_keeps_the_text_in_order(self):
        text = JATSNormalizer().normalize_xml(MARKUP)["sections"][0]["text"]
        assert text == "Some bold Fig 1 here."


class TestMathML:
    def test_formula_text_is_kept_in_place(self):
        xml = _body(
            f"<p>where <inline-formula><mml:math {MML}><mml:msup><mml:mi>x</mml:mi>"
            "<mml:mn>2</mml:mn></mml:msup><mml:mo>+</mml:mo><mml:mi>y</mml:mi></mml:math>"
            "</inline-formula> is positive.</p>"
        )
        section = JATSNormalizer().normalize_xml(xml)["sections"][0]
        assert section["text"] == "where x2+y is positive."

    def test_text_after_a_formula_is_kept(self):
        xml = _body(f"<p>so <mml:math {MML}><mml:mi>k</mml:mi></mml:math> and more text.</p>")
        assert "and more text." in JATSNormalizer().normalize_xml(xml)["body_text"]

    def test_tex_alternative_is_not_duplicated(self):
        xml = _body(
            "<p>so <inline-formula><alternatives><tex-math>x^2</tex-math>"
            f"<mml:math {MML}><mml:msup><mml:mi>x</mml:mi><mml:mn>2</mml:mn></mml:msup>"
            "</mml:math></alternatives></inline-formula> holds</p>"
        )
        text = JATSNormalizer().normalize_xml(xml)["sections"][0]["text"]
        assert text == "so x^2 holds"

    def test_drop_mathml_off_keeps_the_element(self):
        xml = _body(f"<p><mml:math {MML}><mml:mi>k</mml:mi></mml:math></p>")
        root = JATSNormalizer(drop_mathml=False).normalize_xml(xml)["normalized_root"]
        assert len(list(root.iter("math"))) == 1


class TestBytesInput:
    DOCUMENT = (
        '<?xml version="1.0" encoding="{encoding}"?>'
        "<article><body><sec><title>T</title><p>Café über</p></sec></body></article>"
    )

    @pytest.mark.parametrize("encoding", ["ISO-8859-1", "windows-1252", "UTF-8"])
    def test_the_declared_encoding_is_used(self, encoding):
        data = self.DOCUMENT.format(encoding=encoding).encode(encoding)
        assert "Café über" in JATSNormalizer().normalize_xml(data)["body_text"]

    def test_utf16_with_byte_order_mark(self):
        data = self.DOCUMENT.format(encoding="UTF-16").encode("utf-16")
        assert "Café über" in JATSNormalizer().normalize_xml(data)["body_text"]

    def test_utf8_byte_order_mark_without_declaration(self):
        data = codecs.BOM_UTF8 + _body("<p>Café</p>").encode("utf-8")
        assert "Café" in JATSNormalizer().normalize_xml(data)["body_text"]

    def test_an_unknown_declared_encoding_is_read_as_utf8(self):
        data = self.DOCUMENT.format(encoding="X-NO-SUCH-CODEC").encode("utf-8")
        assert "Café über" in JATSNormalizer().normalize_xml(data)["body_text"]

    def test_no_declaration_means_utf8(self):
        data = _body("<p>Café</p>").encode("utf-8")
        assert "Café" in JATSNormalizer().normalize_xml(data)["body_text"]
