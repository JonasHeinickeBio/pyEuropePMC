"""JATS in a default XML namespace must parse like JATS without one.

Every search in this package is written unprefixed (`.//article-meta`,
`.//sec`), which matches the DTD-based JATS that Europe PMC serves. A
schema-based JATS document puts those elements in a default namespace, so
their tags read `{ns}article-meta` and every search silently returns nothing
- no title, no date, no sections, empty plain text, and no error raised.

Silent emptiness is a worse failure than an exception, which is why this is
tested rather than documented as a limitation.
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit

ALI = "http://www.niso.org/schemas/ali/1.0/"
XLINK = "http://www.w3.org/1999/xlink"

PLAIN = (
    "<article><front><article-meta>"
    "<title-group><article-title>Plain Title</article-title></title-group>"
    "<pub-date><year>2021</year><month>4</month></pub-date>"
    "<permissions><license>"
    f'<ali:license_ref xmlns:ali="{ALI}">https://cc.example/by/4.0/</ali:license_ref>'
    "<license-p>Open access.</license-p></license></permissions>"
    "</article-meta></front>"
    "<body><sec><title>Results</title><p>A body sentence that is long enough.</p>"
    f'<ext-link xmlns:xlink="{XLINK}" xlink:href="https://e.example/1">link</ext-link>'
    "</sec></body></article>"
)
NAMESPACED = PLAIN.replace("<article>", '<article xmlns="http://jats.nlm.nih.gov">', 1)


@pytest.fixture(params=["plain", "namespaced"])
def parser(request):
    return FullTextXMLParser(PLAIN if request.param == "plain" else NAMESPACED)


class TestNamespacedExtraction:
    def test_title(self, parser):
        assert parser.extract_metadata()["title"] == "Plain Title"

    def test_pub_date(self, parser):
        assert parser.extract_pub_date() == "2021-04"

    def test_sections(self, parser):
        sections = parser.get_full_text_sections()
        assert [s["title"] for s in sections] == ["Results"]
        assert "A body sentence" in sections[0]["content"]

    def test_plaintext_is_not_empty(self, parser):
        assert "A body sentence that is long enough." in parser.to_plaintext()


class TestPrefixedVocabulariesSurvive:
    """Only the root's own namespace is stripped, never prefixed ones."""

    def test_ali_license_ref_keeps_its_namespace(self):
        root = FullTextXMLParser(NAMESPACED).root
        assert root.find(f".//{{{ALI}}}license_ref") is not None

    def test_xlink_href_still_readable(self):
        root = FullTextXMLParser(NAMESPACED).root
        assert root.find(".//ext-link").get(f"{{{XLINK}}}href") == "https://e.example/1"

    def test_jats_tags_are_unprefixed(self):
        root = FullTextXMLParser(NAMESPACED).root
        assert root.tag == "article"
        assert all(
            not e.tag.startswith("{http://jats") for e in root.iter() if isinstance(e.tag, str)
        )


class TestUnnamespacedUnaffected:
    def test_tags_unchanged(self):
        root = FullTextXMLParser(PLAIN).root
        assert root.tag == "article"
        assert root.find(".//article-title") is not None
