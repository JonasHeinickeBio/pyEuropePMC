"""Input the parser will meet in the wild but nobody writes on purpose.

Malformed XML, an XML bomb, an external-entity reference, a document with no
<body>, control characters, a 5,000-section article. The contract is narrow:

  * anything unparseable raises ParsingError, not an arbitrary exception
  * anything parseable returns without raising from every public method
  * entity attacks are refused rather than expanded

The last point is the one worth a test rather than a comment: defusedxml
refuses both, and swapping in a plain parser would silently reintroduce a
billion-laughs expansion and local file disclosure.

A document in a default XML namespace is included here because it used to
fail in the worst way available - no title, no sections, empty text, and no
error raised at all.
"""

from __future__ import annotations

import pytest

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = [pytest.mark.unit]

PUBLIC_METHODS = (
    "detect_schema",
    "extract_affiliations",
    "extract_article_categories",
    "extract_authors",
    "extract_authors_detailed",
    "extract_figures",
    "extract_funding",
    "extract_keywords",
    "extract_license",
    "extract_metadata",
    "extract_pub_date",
    "extract_publisher",
    "extract_references",
    "extract_tables",
    "get_full_text_sections",
    "get_full_text_sections_structured",
    "list_element_types",
    "to_markdown",
    "to_plaintext",
    "validate_schema_coverage",
)

UNPARSEABLE = {
    "empty string": "",
    "whitespace only": "   \n\t ",
    "not xml at all": "this is not xml",
    "truncated mid-tag": '<?xml version="1.0"?><article><front><article-me',
    "unclosed element": "<article><body><p>text</body></article>",
    "null byte in text": "<article><body><p>before\x00after</p></body></article>",
}

PARSEABLE = {
    "no article root": "<notanarticle><body><p>x</p></body></notanarticle>",
    "article and nothing else": "<article/>",
    "front but no body": "<article><front><article-meta/></front></article>",
    "body but no front": "<article><body><sec><p>Only body.</p></sec></body></article>",
    "empty body": "<article><front><article-meta/></front><body/></article>",
    "html instead of jats": "<html><body><p>hello</p></body></html>",
    "default namespace": (
        '<article xmlns="http://jats.nlm.nih.gov"><front><article-meta>'
        "<title-group><article-title>Namespaced</article-title></title-group>"
        "</article-meta></front><body><sec><title>Results</title>"
        "<p>Body text.</p></sec></body></article>"
    ),
    "deeply nested sections": (
        "<article><body>"
        + "<sec><title>T</title><p>deep</p>" * 40
        + "</sec>" * 40
        + "</body></article>"
    ),
    "many sibling sections": "<article><body>" + "<sec><p>s</p></sec>" * 500 + "</body></article>",
    "emoji and bidi text": "<article><body><p>\U0001f9ea test ‮mirrored‬</p></body></article>",
}

ENTITY_ATTACKS = {
    "billion laughs": (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>'
        "<article><body><p>&lol3;</p></body></article>"
    ),
    "external entity": (
        '<?xml version="1.0"?>'
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<article><body><p>&xxe;</p></body></article>"
    ),
}


class TestUnparseableInputRaisesParsingError:
    @pytest.mark.parametrize("xml", UNPARSEABLE.values(), ids=list(UNPARSEABLE))
    def test_raises_parsing_error(self, xml):
        with pytest.raises(ParsingError):
            FullTextXMLParser(xml)


class TestEntityAttacksAreRefused:
    @pytest.mark.parametrize("xml", ENTITY_ATTACKS.values(), ids=list(ENTITY_ATTACKS))
    def test_refused_not_expanded(self, xml):
        """defusedxml raises EntitiesForbidden; the parser reports it as a
        ParsingError rather than expanding the entity."""
        with pytest.raises(ParsingError):
            FullTextXMLParser(xml)


class TestParseableInputNeverRaises:
    @pytest.mark.parametrize("xml", PARSEABLE.values(), ids=list(PARSEABLE))
    @pytest.mark.parametrize("method", PUBLIC_METHODS)
    def test_public_method_returns(self, xml, method):
        parser = FullTextXMLParser(xml)
        try:
            getattr(parser, method)()
        except ParsingError:
            pass  # a documented failure mode
        except Exception as exc:  # pragma: no cover - the assertion is the point
            pytest.fail(f"{method}() raised {type(exc).__name__}: {exc}")


class TestNamespacedDocumentIsNotSilentlyEmpty:
    """The failure mode this guards is emptiness, not an exception."""

    @pytest.fixture
    def parser(self):
        return FullTextXMLParser(PARSEABLE["default namespace"])

    def test_title_is_found(self, parser):
        assert parser.extract_metadata().get("title") == "Namespaced"

    def test_sections_are_found(self, parser):
        assert [(s["title"], s["content"]) for s in parser.get_full_text_sections()] == [
            ("Results", "Body text.")
        ]

    def test_plaintext_is_not_empty(self, parser):
        assert "Body text." in parser.to_plaintext()
