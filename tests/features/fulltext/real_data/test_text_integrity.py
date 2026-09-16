"""Body text must survive every rendering exactly once.

These run against the real Europe PMC documents in tests/fixtures rather than
hand-written XML. Every defect fixed in #217-#229 was found by measuring
against real documents, and several were invisible to unit fixtures because
they only appear in markup nobody writes by hand: a <sub> mid-word, a table
nested inside a paragraph, a peer-review <sub-article> carrying its own
<body>.

The invariant is the same for each rendering. For a sentence of the article's
own <body>:

  it must appear at least once  - nothing is dropped
  and no more often than the source has it - nothing is repeated

`to_plaintext` also renders the abstract, and articles routinely repeat a
conclusion sentence verbatim there, so its allowance is body + abstract.
The structured blocks render the abstract too, so they take the same
allowance. `get_full_text_sections` does not, so its allowance is the body
alone - a difference in scope between the two APIs, verified against the
fixtures rather than assumed.
"""

from __future__ import annotations

import pytest

from .conftest import sentences, squash, unescape_markdown

pytestmark = [pytest.mark.unit]


@pytest.fixture(scope="module")
def body_sentences(document):
    assert document.body is not None, f"{document.pmcid} has no <body>"
    counts = sentences(document.body)
    assert counts, f"{document.pmcid}: no sentences over 60 characters to check"
    return counts


@pytest.fixture(scope="module")
def abstract_sentences(document):
    counts: dict[str, int] = {}
    for abstract in document.root.findall(".//abstract"):
        for key, n in sentences(abstract).items():
            counts[key] = counts.get(key, 0) + n
    return counts


def _missing(haystack: str, counts: dict[str, int]) -> list[str]:
    return [s for s in counts if haystack.count(s) == 0]


def _repeated(haystack: str, counts: dict[str, int], allowance: dict[str, int]) -> list[str]:
    out = []
    for sentence, n in counts.items():
        if haystack.count(sentence) > n + allowance.get(sentence, 0):
            out.append(sentence)
    return out


class TestNothingIsLost:
    def test_sections_keep_every_sentence(self, document, body_sentences):
        missing = _missing(document.section_text, body_sentences)
        assert not missing, (
            f"{document.pmcid}: {len(missing)} body sentences absent from "
            f"get_full_text_sections(), e.g. {missing[0][:90]!r}"
        )

    def test_plaintext_keeps_every_sentence(self, document, body_sentences):
        missing = _missing(squash(document.plaintext), body_sentences)
        assert not missing, (
            f"{document.pmcid}: {len(missing)} body sentences absent from "
            f"to_plaintext(), e.g. {missing[0][:90]!r}"
        )

    def test_structured_blocks_keep_every_sentence(self, document, body_sentences):
        """The RAG-facing API dropped figure and supplement text until #229."""
        missing = _missing(document.structured_text, body_sentences)
        assert not missing, (
            f"{document.pmcid}: {len(missing)} body sentences absent from "
            f"get_full_text_sections_structured(), e.g. {missing[0][:90]!r}"
        )


class TestNothingIsRepeated:
    def test_sections_do_not_duplicate(self, document, body_sentences):
        """Nested <sec> text was emitted by the parent and the child (#209)."""
        repeated = _repeated(document.section_text, body_sentences, {})
        assert not repeated, (
            f"{document.pmcid}: {len(repeated)} sentences emitted more often than the "
            f"source has them, e.g. {repeated[0][:90]!r}"
        )

    def test_plaintext_does_not_duplicate(self, document, body_sentences, abstract_sentences):
        repeated = _repeated(squash(document.plaintext), body_sentences, abstract_sentences)
        assert not repeated, (
            f"{document.pmcid}: {len(repeated)} sentences repeated in to_plaintext(), "
            f"e.g. {repeated[0][:90]!r}"
        )

    def test_structured_blocks_do_not_duplicate(
        self, document, body_sentences, abstract_sentences
    ):
        """Allowance includes the abstract: the structured blocks render it.

        `get_full_text_sections()` does not, which is why its allowance above
        is the body alone. Checked against all four fixtures rather than
        assumed - an article whose abstract repeats a methods sentence
        verbatim otherwise looks like the parser duplicating text.
        """
        repeated = _repeated(document.structured_text, body_sentences, abstract_sentences)
        assert not repeated, (
            f"{document.pmcid}: {len(repeated)} sentences repeated in the structured "
            f"blocks, e.g. {repeated[0][:90]!r}"
        )


class TestRenderingsAgree:
    def test_markdown_carries_the_body(self, document, body_sentences):
        """Compared against the text a Markdown reader sees, escapes resolved."""
        missing = _missing(squash(unescape_markdown(document.markdown)), body_sentences)
        assert not missing, (
            f"{document.pmcid}: {len(missing)} body sentences absent from to_markdown()"
        )

    def test_every_section_title_appears_in_markdown(self, document):
        markdown = squash(unescape_markdown(document.markdown))
        for section in document.sections:
            title = squash(section["title"])
            if title:
                assert title in markdown, (
                    f"{document.pmcid}: section {section['title']!r} missing from markdown"
                )
