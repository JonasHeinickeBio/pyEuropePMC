"""The lxml backend must return what the default backend returns.

`LXMLParser.enable_for()` swaps the XML engine underneath a parser for speed.
Nothing checked that the two engines then agree, and they did not: lxml keeps
XML comments in the tree as children, stdlib ElementTree discards them at
parse time, so an editorial marker ended up inside extracted text on one
backend only. PMC3258128 carries `<!--CREATIVE COMMONS-->` at the head of its
licence, and the licence text differed between the two.

Structured values must match exactly. Rendered text is compared with
whitespace collapsed: the engines disagree about whitespace-only nodes
between inline elements, which changes spacing but no words.
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("lxml")

from pyeuropepmc.features.fulltext.extensions.lxml_backend import (  # noqa: E402
    LXMLParser,
)
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser  # noqa: E402

pytestmark = [pytest.mark.unit]


@pytest.fixture(scope="module")
def both_backends(document):
    """The same document parsed by each backend."""
    text = document.path.read_text(encoding="utf-8", errors="replace")
    default = FullTextXMLParser(text)
    lxml_backed = FullTextXMLParser()
    LXMLParser.enable_for(lxml_backed, text)
    return default, lxml_backed


def _squash(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


class TestStructuredValuesMatchExactly:
    def test_metadata(self, both_backends, document):
        default, lxml_backed = both_backends
        assert default.extract_metadata() == lxml_backed.extract_metadata(), document.pmcid

    def test_authors(self, both_backends, document):
        default, lxml_backed = both_backends
        assert (
            default.extract_authors_detailed() == lxml_backed.extract_authors_detailed()
        ), document.pmcid

    def test_references(self, both_backends, document):
        default, lxml_backed = both_backends
        assert default.extract_references() == lxml_backed.extract_references(), document.pmcid

    def test_section_titles(self, both_backends, document):
        default, lxml_backed = both_backends
        assert [s["title"] for s in default.get_full_text_sections()] == [
            s["title"] for s in lxml_backed.get_full_text_sections()
        ], document.pmcid


class TestRenderedTextMatchesIgnoringWhitespace:
    def test_plaintext(self, both_backends, document):
        default, lxml_backed = both_backends
        assert _squash(default.to_plaintext()) == _squash(
            lxml_backed.to_plaintext()
        ), document.pmcid

    def test_markdown(self, both_backends, document):
        default, lxml_backed = both_backends
        assert _squash(default.to_markdown()) == _squash(
            lxml_backed.to_markdown()
        ), document.pmcid

    def test_sections(self, both_backends, document):
        default, lxml_backed = both_backends
        assert _squash(
            "\n".join(s["content"] for s in default.get_full_text_sections())
        ) == _squash(
            "\n".join(s["content"] for s in lxml_backed.get_full_text_sections())
        ), document.pmcid


class TestCommentsAreNotContent:
    def test_a_real_document_with_a_comment_agrees(self, both_backends, document):
        """PMC3258128 opens its <license-p> with <!--CREATIVE COMMONS-->."""
        raw = document.path.read_text(encoding="utf-8", errors="replace")
        comments = [" ".join(c.split()) for c in re.findall(r"<!--(.*?)-->", raw, re.S)]
        comments = [c for c in comments if len(c) > 3]
        if not comments:
            pytest.skip(f"{document.pmcid} contains no XML comments")

        default, lxml_backed = both_backends
        for backend, name in ((default, "default"), (lxml_backed, "lxml")):
            # Every place extracted text surfaces, not just the body. The leak
            # showed up in the licence: PMC3258128's <license-p> opens with the
            # comment, so to_plaintext() never carried it but extract_license()
            # did, on the lxml backend only.
            surfaces = {
                "to_plaintext": backend.to_plaintext(),
                "licence text": (backend.extract_license() or {}).get("text") or "",
                "sections": "\n".join(
                    s["content"] for s in backend.get_full_text_sections()
                ),
                "abstract": str(backend.extract_metadata().get("abstract") or ""),
            }
            for where, rendered in surfaces.items():
                for comment in comments:
                    assert _squash(comment) not in _squash(rendered), (
                        f"{document.pmcid}: {name} backend leaked comment "
                        f"{comment[:60]!r} into {where}"
                    )
