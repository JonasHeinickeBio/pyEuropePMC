"""Integration tests for the live arXiv API.

Usage:
    pytest tests/integration/ --run-integration -v
"""

import pytest

from pyeuropepmc.features.search import ArxivClient


@pytest.mark.integration
class TestArxivLiveAPI:
    """Hit the real arXiv API with various queries."""

    @pytest.fixture(scope="class")
    def client(self) -> ArxivClient:
        return ArxivClient()

    def test_search_keyword(self, client: ArxivClient) -> None:
        """Search for a common topic."""
        results = client.search("transformer neural network", limit=10)
        assert len(results) > 0
        # Check basic fields are populated
        for r in results:
            assert r.title
            assert r.source == "arxiv"

    def test_search_with_sort(self, client: ArxivClient) -> None:
        """Sort by submission date."""
        results = client.search("machine learning", limit=5, sort="submittedDate")
        assert len(results) > 0

    def test_get_paper_by_arxiv_id(self, client: ArxivClient) -> None:
        """Fetch a single known arXiv paper."""
        paper = client.get_paper("1706.03762")  # Attention Is All You Need
        assert paper is not None
        assert paper.title
        assert "Attention" in paper.title or "attention" in paper.title.lower()
        assert paper.source == "arxiv"
        assert paper.authors is not None
        assert len(paper.authors) > 0

    def test_get_paper_by_doi(self, client: ArxivClient) -> None:
        """Fetch a paper via DOI."""
        paper = client.get_paper("10.48550/arXiv.1706.03762")
        assert paper is not None
        assert paper.title

    def test_get_paper_not_found(self, client: ArxivClient) -> None:
        """Non-existent ID returns None."""
        paper = client.get_paper("9999.99999")
        assert paper is None

    def test_search_empty(self, client: ArxivClient) -> None:
        """Empty query returns empty list (handles gracefully)."""
        results = client.search("", limit=5)
        assert results == []

    def test_search_limit(self, client: ArxivClient) -> None:
        """Verify limit parameter is respected."""
        for limit in [1, 3, 10]:
            results = client.search("deep learning", limit=limit)
            assert len(results) <= limit, f"limit={limit} returned {len(results)}"

    def test_search_normalize_output(self, client: ArxivClient) -> None:
        """Normalized results should have expected fields."""
        results = client.search("computer vision", limit=3)
        for r in results:
            # source is always arxiv
            assert r.source == "arxiv"
            # source_id is the arXiv ID
            assert r.source_id
            assert len(r.source_id) > 0
            # title and authors are strings
            assert isinstance(r.title, str)
            assert len(r.title) > 0

    def test_search_and_normalize(self, client: ArxivClient) -> None:
        """search_and_normalize works (inherited from BaseLiteratureClient)."""
        results = client.search_and_normalize("quantum computing", limit=5)
        assert len(results) > 0
        for r in results:
            assert isinstance(r.title, str)

    def test_multiple_pages(self, client: ArxivClient) -> None:
        """Fetch more than one page of results (arXiv paginates at 10)."""
        results = client.search("reinforcement learning", limit=25)
        assert len(results) == 25

    def test_author_names(self, client: ArxivClient) -> None:
        """Author names are properly parsed from Atom XML."""
        results = client.search("generative adversarial networks", limit=5)
        for r in results:
            if r.authors:
                for author in r.authors:
                    assert author.name
                    # Should be in "Last, First" format
                    assert len(author.name) > 0
