"""extract_peer_reviews() on the shapes PLOS and eLife actually publish.

It kept a small part of the review text: it skipped PLOS's
``aggregated-review-documents``, read a review's title only from an
``<article-meta>`` that ``<front-stub>`` does not have, took top-level sections
without their subsections, and - with no sections at all, which is how every
review of these publishers is written - kept the bare ``<p>`` and nothing else.
An eLife author response quotes each reviewer comment in a ``<disp-quote>``
before replying to it; the quotes were lost.
"""

from __future__ import annotations

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.extensions.peer_review import (
    PeerReviewExtractor,
    PeerReviewType,
)

pytestmark = [pytest.mark.unit]


def _reviews(sub_articles: str):
    xml = (
        "<article><front><article-meta><article-id pub-id-type='doi'>10.1/x</article-id>"
        "</article-meta></front><body><p>Main.</p></body>"
        f"{sub_articles}</article>"
    )
    return PeerReviewExtractor(DefusedET.fromstring(xml)).extract_peer_reviews()


def _texts(review) -> list[str]:
    return [block.text for section in review.sections for block in section.content]


class TestPlos:
    SUB = (
        '<sub-article article-type="aggregated-review-documents" id="r1">'
        "<front-stub><title-group><article-title>Decision Letter 0</article-title></title-group>"
        "</front-stub><body><p>Dear Dr. Gast,</p><p>Reviewer #1: The model is sound.</p></body>"
        "</sub-article>"
        '<sub-article article-type="author-comment" id="r2">'
        "<front-stub><title-group><article-title>Author response</article-title></title-group>"
        "</front-stub><body><p>We thank the reviewers.</p><supplementary-material>"
        "<label>Attachment</label><caption><title>Response to reviewers.</title></caption>"
        "</supplementary-material></body></sub-article>"
    )

    def test_aggregated_review_documents_are_extracted(self):
        result = _reviews(self.SUB)
        assert [r.review_type for r in result.reviews] == [
            PeerReviewType.AGGREGATED_REVIEW_DOCUMENTS,
            PeerReviewType.AUTHOR_COMMENT,
        ]
        assert _texts(result.reviews[0]) == ["Dear Dr. Gast,", "Reviewer #1: The model is sound."]

    def test_title_from_front_stub(self):
        assert [r.title for r in _reviews(self.SUB).reviews] == [
            "Decision Letter 0",
            "Author response",
        ]

    def test_supplementary_material_in_a_review_is_kept(self):
        texts = _texts(_reviews(self.SUB).reviews[1])
        assert "Response to reviewers." in " ".join(texts)


class TestElifeAuthorResponse:
    def test_quoted_comments_stay_between_the_replies(self):
        result = _reviews(
            '<sub-article article-type="author-comment" id="sa4"><front-stub><title-group>'
            "<article-title>Author response</article-title></title-group></front-stub><body>"
            "<p>We thank the reviewers.</p>"
            "<disp-quote><p>The sample is small.</p></disp-quote>"
            "<p>We added 20 patients.</p>"
            "<disp-quote><p>Figure 2 is unclear.</p></disp-quote>"
            "<p>We redrew it.</p></body></sub-article>"
        )
        assert _texts(result.reviews[0]) == [
            "We thank the reviewers.",
            "The sample is small.",
            "We added 20 patients.",
            "Figure 2 is unclear.",
            "We redrew it.",
        ]


class TestSections:
    def test_subsections_are_kept_with_their_path(self):
        result = _reviews(
            '<sub-article article-type="referee-report"><front-stub><title-group>'
            "<article-title>Reviewer #1</article-title></title-group></front-stub><body>"
            "<sec><title>Major</title><p>Top.</p><sec><title>Statistics</title><p>Nested.</p></sec>"
            "</sec></body></sub-article>"
        )
        sections = result.reviews[0].sections
        assert [(s.section_path, [b.text for b in s.content]) for s in sections] == [
            ("Major", ["Top."]),
            ("Major/Statistics", ["Nested."]),
        ]
        assert {s.section_type for s in sections} == {"peer_review"}

    def test_content_outside_a_section_beside_sections_is_kept(self):
        result = _reviews(
            '<sub-article article-type="editor-report"><body><p>Summary.</p>'
            "<sec><title>Details</title><p>More.</p></sec></body></sub-article>"
        )
        assert sorted(_texts(result.reviews[0])) == ["More.", "Summary."]
