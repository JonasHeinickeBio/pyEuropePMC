"""Structured output on real documents: references, inline offsets, spacing, reviews.

Measured on the previous release of this code:

- PMC1764484 and PMC12738713 keep their reference list inside a ``<sec>`` of
  the body and got it twice: flattened into one unknown block there, and again
  as References.
- Every labelled reference repeated its label ("1. 1.Rowlett"), ran the fields
  of an element citation together, and gave a ``<citation-alternatives>`` twice;
  its inline positions were not moved past the label, so all 1,278 reference
  inlines of PMC12311175 pointed at the wrong characters.
- An inline element whose text ends in a space lost it: PMC1764484's
  ``R<sup>2 </sup>= 0.90`` read "R2= 0.90", and 51 words ran together that way.
- ``extract_peer_reviews()`` skipped PLOS's ``aggregated-review-documents`` and
  left every review untitled: 312 of PMC13567752's 368 review sentences were
  kept.
"""

from __future__ import annotations

import pathlib
import re
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.extensions.peer_review import PeerReviewExtractor
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

from .conftest import SENTENCE, normalise, squash

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "fulltext_downloads"
DOCUMENTS = sorted(FIXTURE_DIR.glob("PMC*.xml"))

pytestmark = [pytest.mark.unit]

INLINE_TAGS = frozenset(
    {
        "xref",
        "bold",
        "italic",
        "sup",
        "sub",
        "inline-formula",
        "chem-struct",
        "named-content",
        "strike",
        "underline",
        "monospace",
        "sc",
        "roman",
        "sans-serif",
        "styled-content",
    }
)


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _own(root: ET.Element, tag: str) -> list[ET.Element]:
    """``tag`` elements of the article itself, not of its sub-articles."""
    found: list[ET.Element] = []

    def walk(node: ET.Element) -> None:
        for child in node:
            if _local(child.tag) in ("sub-article", "response"):
                continue
            if _local(child.tag) == tag:
                found.append(child)
            walk(child)

    walk(root)
    return found


class _Parsed:
    def __init__(self, path: pathlib.Path) -> None:
        raw = path.read_text(encoding="utf-8")
        self.pmcid = path.stem
        self.root = DefusedET.fromstring(raw.encode("utf-8"))
        parser = FullTextXMLParser(raw)
        self.parser = parser
        self.sections = parser.get_full_text_sections_structured()
        self.blocks = [(s, b) for s in self.sections for b in s["content"]]


@pytest.fixture(scope="module", params=DOCUMENTS, ids=lambda p: p.stem)
def doc(request: pytest.FixtureRequest) -> _Parsed:
    return _Parsed(request.param)


class TestReferences:
    def test_each_reference_is_one_block(self, doc: _Parsed) -> None:
        refs = [
            ref
            for ref_list in _own(doc.root, "ref-list")
            for ref in ref_list
            if _local(ref.tag) == "ref"
        ]
        if not refs:
            pytest.skip(f"{doc.pmcid} has no references")
        targets = [b.get("target_id") for _, b in doc.blocks if b["type"] == "paragraph"]
        for ref in refs:
            if ref.get("id"):
                assert targets.count(ref.get("id")) == 1, f"{doc.pmcid}: reference {ref.get('id')}"

    def test_no_reference_list_is_flattened_into_the_body(self, doc: _Parsed) -> None:
        assert not [b for _, b in doc.blocks if b.get("jats_tag") == "ref-list"]

    def test_the_label_is_given_once(self, doc: _Parsed) -> None:
        for _, block in doc.blocks:
            text = block.get("text") or ""
            label, _, rest = text.partition(" ")
            if block.get("target_id") and re.fullmatch(r"\[?\d+[.\]]?", label):
                assert not rest.startswith(label), f"{doc.pmcid}: {text[:40]!r}"

    def test_a_citation_is_not_given_twice(self, doc: _Parsed) -> None:
        """A <citation-alternatives> gave its element and mixed citation one after the other."""
        for ref in (r for rl in _own(doc.root, "ref-list") for r in rl if _local(r.tag) == "ref"):
            block = next((b for _, b in doc.blocks if b.get("target_id") == ref.get("id")), None)
            if block is None:
                continue
            label = (
                normalise(
                    "".join(next((c for c in ref if _local(c.tag) == "label"), ref).itertext())
                )
                if any(_local(c.tag) == "label" for c in ref)
                else ""
            )
            body = squash(block["text"])[len(squash(label)) :]
            opening = body[:40]
            if len(opening) == 40:
                assert body.count(opening) == 1, f"{doc.pmcid}: {block['text'][:60]!r} repeats"


class TestInlineOffsets:
    def test_every_inline_indexes_the_text_it_names(self, doc: _Parsed) -> None:
        """Positions index ``text``; a figure's its caption; a list's the item it names."""
        checked = 0
        for section, block in doc.blocks:
            for inline in block.get("inlines") or []:
                meta = inline.get("metadata") or {}
                if "item" in meta:
                    target = block["items"][meta["item"]]
                elif "term" in meta:
                    target = block["definition_terms"][meta["term"]]["term"]
                elif "definition" in meta:
                    target = block["definition_terms"][meta["definition"]]["def"]
                elif not block.get("text"):
                    target = block.get("caption") or ""
                else:
                    target = block["text"]
                start, length = inline["position"], inline["length"]
                assert target[start : start + length] == inline["text"], (
                    f"{doc.pmcid} [{section['title'][:30]}] {block['type']}: "
                    f"{inline['text']!r} at {start} reads {target[start : start + length]!r}"
                )
                checked += 1
        assert checked, f"{doc.pmcid}: no inline element to check"


class TestSpacing:
    def test_an_inline_element_ending_in_a_space_keeps_it(self, doc: _Parsed) -> None:
        text = " ".join(b.get("text") or "" for _, b in doc.blocks)
        glued = []
        for para in doc.root.iter():
            if _local(para.tag) != "p":
                continue
            for child in para:
                if _local(child.tag) not in INLINE_TAGS:
                    continue
                inner, tail = "".join(child.itertext()), child.tail or ""
                if inner.strip() and inner[-1].isspace() and tail and not tail[0].isspace():
                    joined = inner.strip()[-10:] + tail.strip()[:10]
                    if joined in text:
                        glued.append(joined)
        assert not glued, f"{doc.pmcid}: {len(glued)} words run together, e.g. {glued[0]!r}"


@pytest.fixture(scope="module")
def reviews(doc: _Parsed):
    subs = [e for e in doc.root.iter() if _local(e.tag) == "sub-article"]
    if not subs:
        pytest.skip(f"{doc.pmcid} has no sub-article")
    return subs, PeerReviewExtractor(doc.parser.root).extract_peer_reviews()


class TestPeerReviews:
    def test_every_review_sentence_is_kept(self, doc: _Parsed, reviews) -> None:
        subs, review_set = reviews
        parts: list[str] = []
        for review in review_set.reviews:
            for section in review.sections:
                for block in section.content:
                    parts.extend([block.text, block.caption, *block.items])
                    parts.extend(t for d in block.definition_terms for t in d.values())
                    parts.extend(c for row in block.rows for c in row)
        got = squash(" ".join(p for p in parts if p))
        missing = []
        for sub in subs:
            for para in (e for e in sub.iter() if _local(e.tag) == "p"):
                for sentence in SENTENCE.split(normalise("".join(para.itertext()))):
                    key = squash(sentence)
                    if len(key) > 60 and key not in got:
                        missing.append(key)
        assert not missing, (
            f"{doc.pmcid}: {len(missing)} review sentences lost, e.g. {missing[0][:70]!r}"
        )

    def test_every_review_type_is_extracted_and_titled(self, doc: _Parsed, reviews) -> None:
        subs, review_set = reviews
        assert len(review_set.reviews) == len(subs)
        assert all(review.title for review in review_set.reviews)

    def test_review_sections_are_typed_peer_review(self, doc: _Parsed, reviews) -> None:
        _, review_set = reviews
        types = {s.section_type for r in review_set.reviews for s in r.sections}
        assert types == {"peer_review"}
