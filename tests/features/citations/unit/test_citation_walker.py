"""Unit tests for CitationWalker against the Semantic Scholar Graph API shapes.

HTTP is mocked at ``requests.get``; the seed lookup goes through
``SemanticScholarClient.enrich``, which is replaced with a stub returning the
dict that client really produces (``s2_paper_id``, not ``paperId``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("semanticscholar")

from pyeuropepmc.features.citations.walker import CitationWalker, SnowballingStrategy

SEED_ID = "649def34f8be52c8b66281af98ae884c09aef38b"


def _paper(paper_id: str | None, title: str, citations: int = 5, doi: str | None = None) -> dict:
    return {
        "paperId": paper_id,
        "externalIds": {"DOI": doi} if doi else {},
        "title": title,
        "authors": [{"authorId": "1", "name": "Jane Doe"}],
        "year": 2021,
        "citationCount": citations,
    }


def _response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


# What GET /graph/v1/paper/{id}/citations and /references really return.
CITATIONS_PAGE = {
    "offset": 0,
    "data": [
        {"citingPaper": _paper("c1", "Citing paper one", doi="10.1000/c1")},
        {"citingPaper": _paper("c2", "Citing paper two", doi="10.1000/c2")},
    ],
}
REFERENCES_PAGE = {
    "offset": 0,
    "data": [
        {"citedPaper": _paper("r1", "Referenced paper", doi="10.1000/r1")},
        # A reference Semantic Scholar has no record for.
        {"citedPaper": {"paperId": None, "title": "Unindexed reference"}},
    ],
}


def _fake_get(url: str, **_: Any) -> MagicMock:
    if url.endswith("/citations"):
        return _response(CITATIONS_PAGE if f"/paper/{SEED_ID}/" in url else {"data": []})
    if url.endswith("/references"):
        return _response(REFERENCES_PAGE if f"/paper/{SEED_ID}/" in url else {"data": []})
    raise AssertionError(f"unexpected request {url}")


@pytest.fixture
def walker() -> CitationWalker:
    w = CitationWalker(rate_limit_delay=0, skip_dedup=True)
    # SemanticScholarClient.enrich() output: the ID is "s2_paper_id".
    w._s2_client = MagicMock()
    w._s2_client.enrich.return_value = {"s2_paper_id": SEED_ID, "title": "Seed paper"}
    return w


class TestSnowball:
    def test_forward_returns_citing_papers(self, walker):
        with patch("requests.get", side_effect=_fake_get) as get:
            papers, _ = walker.snowball(
                "DOI:10.1000/seed", strategy=SnowballingStrategy.FORWARD, max_depth=0
            )

        assert [p.title for p in papers] == ["Citing paper one", "Citing paper two"]
        assert {p.source_id for p in papers} == {"c1", "c2"}
        assert get.call_args_list[0].args[0].endswith(f"/paper/{SEED_ID}/citations")

    def test_backward_returns_referenced_papers_and_skips_unindexed(self, walker):
        with patch("requests.get", side_effect=_fake_get) as get:
            papers, _ = walker.snowball(
                "DOI:10.1000/seed", strategy=SnowballingStrategy.BACKWARD, max_depth=1
            )

        assert [p.title for p in papers] == ["Referenced paper"]
        requested = [c.args[0] for c in get.call_args_list]
        assert not any("/paper/None/" in url for url in requested), requested

    def test_both_directions(self, walker):
        with patch("requests.get", side_effect=_fake_get):
            papers, _ = walker.snowball(
                "DOI:10.1000/seed", strategy=SnowballingStrategy.BOTH, max_depth=0
            )

        assert {p.source_id for p in papers} == {"c1", "c2", "r1"}

    def test_get_citations_and_references_wrappers(self, walker):
        with patch("requests.get", side_effect=_fake_get):
            assert len(walker.get_citations("DOI:10.1000/seed")) == 2
            assert len(walker.get_references("DOI:10.1000/seed")) == 1

    def test_seed_from_raw_search_fallback_uses_paper_id(self, walker):
        """The fallback search returns the API's own "paperId" key."""
        walker._s2_client.enrich.return_value = None

        def fake_get(url: str, **kwargs: Any) -> MagicMock:
            if url.endswith("/paper/search"):
                return _response({"total": 1, "data": [{"paperId": SEED_ID, "title": "Seed"}]})
            return _fake_get(url, **kwargs)

        with patch("requests.get", side_effect=fake_get):
            papers, _ = walker.snowball("some title", max_depth=0)

        assert len(papers) == 2

    def test_seed_without_any_id_returns_nothing(self, walker):
        walker._s2_client.enrich.return_value = {"title": "no id"}
        with patch("requests.get") as get:
            papers, report = walker.snowball("DOI:10.1000/seed")
        assert papers == []
        assert report.total_input == 0
        get.assert_not_called()

    def test_min_citations_filters(self, walker):
        page = {
            "data": [
                {"citingPaper": _paper("c1", "Well cited", citations=50)},
                {"citingPaper": _paper("c2", "Barely cited", citations=1)},
            ]
        }
        with patch("requests.get", return_value=_response(page)):
            papers, _ = walker.snowball("DOI:10.1000/seed", max_depth=0, min_citations=10)
        assert [p.title for p in papers] == ["Well cited"]

    def test_malformed_page_yields_nothing(self, walker):
        with patch("requests.get", return_value=_response({"data": "not a list"})):
            papers, _ = walker.snowball("DOI:10.1000/seed", max_depth=0)
        assert papers == []

    def test_deduplicates_by_default(self):
        w = CitationWalker(rate_limit_delay=0)
        w._s2_client = MagicMock()
        w._s2_client.enrich.return_value = {"s2_paper_id": SEED_ID}
        page = {
            "data": [
                {"citingPaper": _paper("c1", "Same paper", doi="10.1000/same")},
                {"citingPaper": _paper("c2", "Same paper", doi="10.1000/same")},
            ]
        }
        with patch("requests.get", return_value=_response(page)):
            papers, report = w.snowball("DOI:10.1000/seed", max_depth=0)
        assert len(papers) == 1
        assert report.duplicates_removed == 1
