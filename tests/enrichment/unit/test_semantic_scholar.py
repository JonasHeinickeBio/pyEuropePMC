"""Unit tests for Semantic Scholar enrichment client."""

import pytest

from pyeuropepmc.enrichment.semantic_scholar import SemanticScholarClient


class TestSemanticScholarRecommendations:
    """Tests for Semantic Scholar recommendations endpoints."""

    def test_get_recommendations_for_paper_success(self) -> None:
        """GET endpoint returns parsed recommendation papers."""
        client = SemanticScholarClient(rate_limit_delay=0)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                client,
                "_make_get_request",
                lambda **_: {
                    "recommendedPapers": [
                        {"paperId": "p1", "title": "Paper 1"},
                        {"paperId": "p2", "title": "Paper 2"},
                    ]
                },
            )
            recommendations = client.get_recommendations_for_paper(
                "649def34f8be52c8b66281af98ae884c09aef38b"
            )

        assert len(recommendations) == 2
        assert recommendations[0]["paperId"] == "p1"

    def test_get_recommendations_for_papers_with_negative_ids_success(self) -> None:
        """POST endpoint sends positive and negative IDs and parses recommendations."""
        client = SemanticScholarClient(rate_limit_delay=0)
        captured: dict[str, object] = {}

        def mock_post_request(**kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"recommendedPapers": [{"paperId": "p3"}]}

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(client, "_make_post_request", mock_post_request)
            recommendations = client.get_recommendations_for_papers(
                positive_paper_ids=["649def34f8be52c8b66281af98ae884c09aef38b"],
                negative_paper_ids=["ArXiv:1805.02262"],
                limit=1000,
            )

        assert recommendations == [{"paperId": "p3"}]
        assert captured["json_data"] == {
            "positivePaperIds": ["649def34f8be52c8b66281af98ae884c09aef38b"],
            "negativePaperIds": ["ArXiv:1805.02262"],
        }
        assert captured["params"] == {"limit": 500}
        assert captured["params"]["limit"] == client.MAX_RECOMMENDATIONS

    def test_get_recommendations_for_paper_invalid_id_raises(self) -> None:
        """Invalid paper IDs are rejected."""
        client = SemanticScholarClient(rate_limit_delay=0)
        with pytest.raises(ValueError, match="invalid characters"):
            client.get_recommendations_for_paper("bad id with spaces")

    def test_get_recommendations_for_papers_requires_positive_ids(self) -> None:
        """POST endpoint requires at least one positive paper ID."""
        client = SemanticScholarClient(rate_limit_delay=0)
        with pytest.raises(ValueError, match="positive_paper_ids"):
            client.get_recommendations_for_papers(positive_paper_ids=[])

    def test_get_recommendations_for_papers_disallows_id_overlap(self) -> None:
        """Positive and negative IDs must not overlap."""
        client = SemanticScholarClient(rate_limit_delay=0)
        paper_id = "649def34f8be52c8b66281af98ae884c09aef38b"
        with pytest.raises(ValueError, match="must not contain the same"):
            client.get_recommendations_for_papers(
                positive_paper_ids=[paper_id],
                negative_paper_ids=[paper_id],
            )

    def test_get_recommendations_for_paper_invalid_limit_raises(self) -> None:
        """Limit must be positive."""
        client = SemanticScholarClient(rate_limit_delay=0)
        with pytest.raises(ValueError, match="positive integer"):
            client.get_recommendations_for_paper(
                "649def34f8be52c8b66281af98ae884c09aef38b", limit=0
            )
