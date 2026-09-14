"""Nested <sec> content must be emitted exactly once (#209).

JATS sections nest. Every flat extractor here selected descendant content with
``.//``, so a parent section carried its subsections' paragraphs as well as its
own and each subsection then emitted them again. Measured on Europe PMC
samples that duplicated 43.0% of ``get_full_text_sections()`` output, 40.5% of
``to_plaintext()`` and 59.6% of ``to_markdown()``; on PMC8097965 the Results
section and its Participants subsection came back byte-identical.

The tokens below are deliberately non-overlapping: an earlier version of this
check used PARENT/CHILD/GRANDCHILD and reported a false duplicate, because
"GRANDCHILD." contains "CHILD.".
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit

NESTED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>T</article-title>
</title-group></article-meta></front><body>
<sec><title>Results</title><p>ALPHA.</p>
  <sec><title>Participants</title><p>BETA.</p>
    <sec><title>Deep</title><p>GAMMA.</p></sec>
  </sec>
</sec>
<sec><title>Boxed</title><boxed-text><p>DELTA.</p></boxed-text></sec>
</body></article>"""

TOKENS = ("ALPHA.", "BETA.", "GAMMA.", "DELTA.")


@pytest.fixture
def parser():
    return FullTextXMLParser(NESTED_XML)


def _counts(text):
    return {token: text.count(token) for token in TOKENS}


class TestNestedSectionsEmittedOnce:
    def test_sections_assign_each_paragraph_to_one_section(self, parser):
        """Each section carries its own text and nothing from its children."""
        got = {s["title"]: s["content"] for s in parser.get_full_text_sections()}
        assert got["Results"] == "ALPHA."
        assert got["Participants"] == "BETA."
        assert got["Deep"] == "GAMMA."

    def test_sections_emit_every_token_once(self, parser):
        joined = "\n".join(s["content"] for s in parser.get_full_text_sections())
        assert _counts(joined) == dict.fromkeys(TOKENS, 1)

    def test_plaintext_emits_every_token_once(self, parser):
        assert _counts(parser.to_plaintext()) == dict.fromkeys(TOKENS, 1)

    def test_markdown_emits_every_token_once(self, parser):
        assert _counts(parser.to_markdown()) == dict.fromkeys(TOKENS, 1)

    def test_structured_output_unchanged(self, parser):
        """The structured traversal was already correct; it stays correct."""
        joined = "\n".join(
            block.get("text", "")
            for section in parser.get_full_text_sections_structured()
            for block in section["content"]
        )
        assert _counts(joined) == dict.fromkeys(TOKENS, 1)


class TestSectionContentNotLost:
    def test_boxed_text_paragraph_survives(self, parser):
        """A <p> wrapped in <boxed-text> still belongs to its section.

        A direct-children-only rule would drop it; the fix stops at nested
        <sec> instead, so non-section wrappers are traversed.
        """
        got = {s["title"]: s["content"] for s in parser.get_full_text_sections()}
        assert got["Boxed"] == "DELTA."

    def test_every_section_still_listed(self, parser):
        titles = [s["title"] for s in parser.get_full_text_sections()]
        for expected in ("Results", "Participants", "Deep", "Boxed"):
            assert expected in titles


class TestMarkdownHeadingDepth:
    def test_subsections_nest_once_at_one_level_each(self, parser):
        """Subsections were rendered under their parent *and* again flat.

        The body loop walked every descendant <sec> while the section renderer
        already recursed, so a grandchild appeared at two different depths.
        """
        headings = [line for line in parser.to_markdown().splitlines() if line.startswith("#")]
        assert headings.count("## Results") == 1
        assert headings.count("### Participants") == 1
        assert headings.count("#### Deep") == 1
        assert headings.count("## Boxed") == 1


class TestFlatSectionsWithoutNesting:
    def test_sibling_sections_are_unaffected(self):
        """The common non-nested case behaves exactly as before."""
        xml = """<?xml version="1.0"?><article><body>
        <sec><title>Introduction</title><p>Intro text.</p></sec>
        <sec><title>Methods</title><p>Methods text.</p></sec>
        </body></article>"""
        sections = FullTextXMLParser(xml).get_full_text_sections()
        assert [(s["title"], s["content"]) for s in sections] == [
            ("Introduction", "Intro text."),
            ("Methods", "Methods text."),
        ]


BARE_AND_LIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><title-group><article-title>T</article-title>
</title-group></article-meta></front><body>
<p>OPENING paragraph that sits outside any section.</p>
<sec><title>Methods</title><p>EPSILON.</p>
  <list list-type="bullet"><list-item><p>ZETA item text.</p></list-item></list>
</sec>
</body></article>"""


class TestBareBodyParagraphs:
    """<p> directly under <body>, in a document that also has sections."""

    @pytest.fixture
    def parser(self):
        return FullTextXMLParser(BARE_AND_LIST_XML)

    def test_plaintext_keeps_bare_paragraph(self, parser):
        """to_plaintext() ran this branch only when the document had no <sec>.

        That guard dodged the duplication fixed in #209, but it silently
        dropped the opening paragraphs of any article that had both - four in
        PMC12018715, three in PMC12126031, found by validating against real
        Europe PMC documents.
        """
        assert parser.to_plaintext().count("OPENING") == 1

    def test_markdown_keeps_bare_paragraph(self, parser):
        """to_markdown() only ever walked sections, so it never emitted these."""
        assert parser.to_markdown().count("OPENING") == 1

    def test_sections_keep_bare_paragraph(self, parser):
        """get_full_text_sections() already handled this; it still does."""
        joined = "\n".join(s["content"] for s in parser.get_full_text_sections())
        assert joined.count("OPENING") == 1


class TestListParagraphsEmittedOnce:
    """A <p> inside a <list-item> must not be emitted as a paragraph too."""

    @pytest.fixture
    def parser(self):
        return FullTextXMLParser(BARE_AND_LIST_XML)

    def test_plaintext_does_not_double_emit_list_text(self, parser):
        """Plaintext renders lists separately, so paragraphs stop at <list>.

        Eight paragraphs in PMC11699693 were emitted twice this way.
        """
        assert parser.to_plaintext().count("ZETA item text.") == 1

    def test_plaintext_still_emits_ordinary_paragraphs(self, parser):
        assert parser.to_plaintext().count("EPSILON.") == 1

    def test_markdown_keeps_list_text(self, parser):
        """Markdown has no list rendering, so it must NOT stop at <list>.

        Excluding list paragraphs there would drop the text entirely - the
        opposite bug, which this guards against.
        """
        assert parser.to_markdown().count("ZETA item text.") == 1
