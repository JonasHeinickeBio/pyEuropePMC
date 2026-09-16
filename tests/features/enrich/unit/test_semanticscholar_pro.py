"""Unit tests for pyeuropepmc.features.enrich.sources.semanticscholar_pro.

Mocks the underlying `semanticscholar.SemanticScholar` client so no real
network calls are made; drives retry/rate-limit/error-handling logic
directly via the mocked client's return values and side effects.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("semanticscholar")

from semanticscholar.Journal import Journal
from semanticscholar.SemanticScholarException import (
    GatewayTimeoutException,
    InternalServerErrorException,
    ObjectNotFoundException,
)

from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.enrich.sources.semanticscholar_pro import (
    ProfessionalSemanticScholarClient,
)


def _client(**kwargs) -> ProfessionalSemanticScholarClient:
    with patch("semanticscholar.SemanticScholar") as mock_cls:
        mock_cls.return_value = MagicMock()
        c = ProfessionalSemanticScholarClient(**kwargs)
    return c


class TestInit:
    def test_negative_rate_limit_clamped_to_zero(self):
        c = _client(rate_limit_delay=-5)
        assert c.rate_limit_delay == 0.0

    def test_positive_rate_limit_kept(self):
        c = _client(rate_limit_delay=2.0)
        assert c.rate_limit_delay == 2.0

    def test_exception_types_initialized(self):
        c = _client()
        assert c._object_not_found_exception is ObjectNotFoundException


class TestExecuteWithRetry:
    def test_success_first_try(self):
        c = _client()
        result = c._execute_with_retry(lambda: "ok", "op")
        assert result == "ok"

    def test_rate_limit_retries_then_succeeds(self):
        c = _client()
        calls = {"n": 0}

        def operation():
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("429 Too Many Requests")
            return "ok"

        with patch("time.sleep"):
            result = c._execute_with_retry(operation, "op", max_retries=3, initial_backoff=0.01)
        assert result == "ok"
        assert calls["n"] == 2

    def test_rate_limit_exhausts_retries_raises(self):
        c = _client()

        def operation():
            raise RuntimeError("rate limit exceeded")

        with patch("time.sleep"), pytest.raises(APIClientError):
            c._execute_with_retry(operation, "op", max_retries=1, initial_backoff=0.01)

    def test_server_error_retries_then_succeeds(self):
        c = _client()
        calls = {"n": 0}

        def operation():
            calls["n"] += 1
            if calls["n"] < 2:
                raise InternalServerErrorException()
            return "ok"

        with patch("time.sleep"):
            result = c._execute_with_retry(operation, "op", max_retries=3, initial_backoff=0.01)
        assert result == "ok"

    def test_server_error_exhausts_retries_raises_api_client_error(self):
        c = _client()

        def operation():
            raise GatewayTimeoutException()

        with patch("time.sleep"), pytest.raises(APIClientError):
            c._execute_with_retry(operation, "op", max_retries=1, initial_backoff=0.01)

    def test_non_retryable_error_raises_immediately(self):
        c = _client()
        calls = {"n": 0}

        def operation():
            calls["n"] += 1
            raise ValueError("bad request")

        with pytest.raises(APIClientError):
            c._execute_with_retry(operation, "op", max_retries=3)
        assert calls["n"] == 1


class TestEnforceRateLimit:
    def test_disabled_when_delay_zero(self):
        c = _client(rate_limit_delay=0)
        with patch("time.sleep") as mock_sleep:
            c._enforce_rate_limit()
        mock_sleep.assert_not_called()

    def test_sleeps_when_too_fast(self):
        c = _client(rate_limit_delay=5.0)
        c._last_request_time = 100.0
        with (
            patch("time.monotonic", side_effect=[100.5, 105.5]),
            patch("time.sleep") as mock_sleep,
        ):
            c._enforce_rate_limit()
        mock_sleep.assert_called_once()

    def test_no_sleep_when_enough_elapsed(self):
        c = _client(rate_limit_delay=1.0)
        c._last_request_time = 100.0
        with (
            patch("time.monotonic", side_effect=[105.0, 105.0]),
            patch("time.sleep") as mock_sleep,
        ):
            c._enforce_rate_limit()
        mock_sleep.assert_not_called()


class TestGetPaper:
    def test_found(self):
        c = _client()
        paper = SimpleNamespace(title="T", paperId="p1")
        c._client.get_paper.return_value = paper
        result = c.get_paper("p1")
        assert result["title"] == "T"

    def test_not_found_returns_none(self):
        c = _client()
        c._client.get_paper.return_value = None
        assert c.get_paper("missing") is None

    def test_uses_default_fields_when_none(self):
        c = _client()
        c._client.get_paper.return_value = SimpleNamespace(paperId="p1")
        c.get_paper("p1")
        _, kwargs = c._client.get_paper.call_args
        assert "title" in kwargs["fields"]


class TestGetPapers:
    def test_too_many_ids_raises(self):
        c = _client()
        with pytest.raises(ValueError):
            c.get_papers(["x"] * 501)

    def test_normal_batch(self):
        c = _client()
        c._client.get_papers.return_value = [SimpleNamespace(paperId="1")]
        result = c.get_papers(["1"])
        assert result[0]["s2_paper_id"] == "1"

    def test_return_not_found(self):
        c = _client()
        c._client.get_papers.return_value = ([SimpleNamespace(paperId="1")], ["2"])
        papers, not_found = c.get_papers(["1", "2"], return_not_found=True)
        assert papers[0]["s2_paper_id"] == "1"
        assert not_found == ["2"]

    def test_rate_limit_falls_back_to_single_retrieval(self):
        c = _client()
        with (
            patch.object(
                c,
                "_execute_with_retry",
                side_effect=APIClientError(message="429 rate limit hit"),
            ),
            patch.object(c, "_fallback_get_papers", return_value=["fallback"]) as mock_fb,
            patch("time.sleep"),
        ):
            result = c.get_papers(["1"])
        mock_fb.assert_called_once()
        assert result == ["fallback"]

    def test_non_rate_limit_api_error_reraised(self):
        c = _client()
        with (
            patch.object(
                c, "_execute_with_retry", side_effect=APIClientError(message="some other error")
            ),
            pytest.raises(APIClientError),
        ):
            c.get_papers(["1"])


class TestSearchPaper:
    def test_limit_too_low_raises(self):
        c = _client()
        with pytest.raises(ValueError):
            c.search_paper("q", limit=0)

    def test_limit_too_high_raises(self):
        c = _client()
        with pytest.raises(ValueError, match="between 1 and 1000"):
            c.search_paper("q", limit=1001)

    def test_limit_above_page_size_reads_further_pages(self):
        """The API serves 100 per page; iterating the results pages on, up to ``limit``."""
        c = _client()
        # PaginatedResults stands in as a plain iterable of 450 papers.
        c._client.search_paper.return_value = iter(
            [SimpleNamespace(paperId=str(i)) for i in range(450)]
        )
        result = c.search_paper("cancer", limit=300)

        assert len(result) == 300
        assert c._client.search_paper.call_args.kwargs["limit"] == 100  # page size

    def test_small_limit_is_the_page_size(self):
        c = _client()
        c._client.search_paper.return_value = [SimpleNamespace(paperId="1")]
        c.search_paper("cancer", limit=7)
        assert c._client.search_paper.call_args.kwargs["limit"] == 7

    def test_normal_search(self):
        c = _client()
        c._client.search_paper.return_value = [SimpleNamespace(paperId="1")]
        result = c.search_paper("cancer")
        assert result[0]["s2_paper_id"] == "1"

    def test_match_title(self):
        c = _client()
        c._client.search_paper.return_value = SimpleNamespace(paperId="1")
        result = c.search_paper("exact title", match_title=True)
        assert result == [{"s2_paper_id": "1", "authors": [], "external_ids": {}, "journal": {}}]


class TestGetPaperAuthors:
    def test_limit_out_of_range_raises(self):
        c = _client()
        with pytest.raises(ValueError):
            c.get_paper_authors("p1", limit=0)
        with pytest.raises(ValueError):
            c.get_paper_authors("p1", limit=1001)

    def test_normal(self):
        c = _client()
        c._client.get_paper_authors.return_value = [SimpleNamespace(authorId="a1", name="Jane")]
        result = c.get_paper_authors("p1")
        assert result[0]["author_id"] == "a1"


class TestGetAuthor:
    def test_found(self):
        c = _client()
        c._client.get_author.return_value = SimpleNamespace(authorId="a1", name="Jane")
        result = c.get_author("a1")
        assert result["name"] == "Jane"

    def test_falsy_result_returns_none(self):
        c = _client()
        c._client.get_author.return_value = None
        assert c.get_author("missing") is None

    def test_object_not_found_exception_returns_none(self):
        c = _client()
        c._client.get_author.side_effect = ObjectNotFoundException()
        assert c.get_author("missing") is None

    def test_other_api_error_reraised(self):
        c = _client()
        with (
            patch.object(c, "_execute_with_retry", side_effect=APIClientError(message="boom")),
            pytest.raises(APIClientError),
        ):
            c.get_author("a1")


class TestGetRecommendations:
    def test_limit_out_of_range_raises(self):
        c = _client()
        with pytest.raises(ValueError):
            c.get_recommendations("p1", limit=0)
        with pytest.raises(ValueError):
            c.get_recommendations("p1", limit=501)

    def test_invalid_pool_from_raises(self):
        c = _client()
        with pytest.raises(ValueError):
            c.get_recommendations("p1", pool_from="bogus")

    def test_normal(self):
        c = _client()
        c._client.get_recommended_papers.return_value = [SimpleNamespace(paperId="1")]
        result = c.get_recommendations("p1")
        assert result[0]["s2_paper_id"] == "1"


class TestGetRecommendationsFromLists:
    def test_limit_out_of_range_raises(self):
        c = _client()
        with pytest.raises(ValueError):
            c.get_recommendations_from_lists(["1"], limit=0)

    def test_normal(self):
        c = _client()
        c._client.get_recommended_papers_from_lists.return_value = [SimpleNamespace(paperId="1")]
        result = c.get_recommendations_from_lists(["1"], negative_paper_ids=["2"])
        assert result[0]["s2_paper_id"] == "1"


class TestSearchAuthor:
    def test_limit_out_of_range_raises(self):
        c = _client()
        with pytest.raises(ValueError):
            c.search_author("q", limit=0)
        with pytest.raises(ValueError):
            c.search_author("q", limit=1001)

    def test_normal(self):
        c = _client()
        c._client.search_author.return_value = [SimpleNamespace(authorId="a1", name="Jane")]
        result = c.search_author("Jane")
        assert result[0]["author_id"] == "a1"


class TestProcessSearchResults:
    def test_match_title_with_results(self):
        c = _client()
        paper = SimpleNamespace(paperId="1")
        result = c._process_search_results(paper, limit=10, match_title=True)
        assert result == [{"s2_paper_id": "1", "authors": [], "external_ids": {}, "journal": {}}]

    def test_match_title_no_results(self):
        c = _client()
        result = c._process_search_results(None, limit=10, match_title=True)
        assert result == []

    def test_iterable_results_respects_limit(self):
        c = _client()
        papers = [SimpleNamespace(paperId=str(i)) for i in range(5)]
        result = c._process_search_results(iter(papers), limit=2, match_title=False)
        assert len(result) == 2

    def test_non_iterable_falsy_returns_empty(self):
        c = _client()
        assert c._process_search_results(None, limit=10, match_title=False) == []

    def test_single_non_list_non_dict_truthy_result(self):
        c = _client()
        paper = SimpleNamespace(paperId="1")
        # A plain object is not iterable, so it falls into the "elif results"
        # branch and gets wrapped as a single-element list.
        result = c._process_search_results(paper, limit=10, match_title=False)
        assert result == [{"s2_paper_id": "1", "authors": [], "external_ids": {}, "journal": {}}]

    def test_iteration_exception_is_swallowed(self):
        c = _client()

        class BadIterable:
            def __iter__(self):
                raise RuntimeError("boom")

        result = c._process_search_results(BadIterable(), limit=10, match_title=False)
        assert result == []

    def test_filters_falsy_items(self):
        c = _client()
        result = c._process_search_results(
            [None, SimpleNamespace(paperId="1")], limit=10, match_title=False
        )
        assert result == [{"s2_paper_id": "1", "authors": [], "external_ids": {}, "journal": {}}]


class TestFallbackGetPapers:
    def test_partitions_found_and_not_found(self):
        c = _client()
        with patch.object(c, "get_paper", side_effect=[{"s2_paper_id": "1"}, None]):
            result = c._fallback_get_papers(["1", "2"], fields=[], return_not_found=False)
        assert result == [{"s2_paper_id": "1"}]

    def test_return_not_found_tuple(self):
        c = _client()
        with patch.object(c, "get_paper", side_effect=[{"s2_paper_id": "1"}, None]):
            results, not_found = c._fallback_get_papers(
                ["1", "2"], fields=[], return_not_found=True
            )
        assert results == [{"s2_paper_id": "1"}]
        assert not_found == ["2"]


class TestDefaultFields:
    def test_default_paper_fields_includes_title(self):
        c = _client()
        assert "title" in c._default_paper_fields()

    def test_default_author_fields_includes_name(self):
        c = _client()
        assert "name" in c._default_author_fields()


class TestPaperToDict:
    def test_falsy_paper_returns_empty_dict(self):
        c = _client()
        assert c._paper_to_dict(None) == {}

    def test_full_paper_mapping(self):
        c = _client()
        paper = SimpleNamespace(
            citationCount=5,
            influentialCitationCount=2,
            abstract="An abstract",
            authors=[SimpleNamespace(authorId="a1", name="Jane")],
            fieldsOfStudy=["Biology"],
            paperId="p1",
            externalIds={"DOI": "10.1/x"},
            openAccessPdf={"url": "http://pdf"},
            publicationTypes=["JournalArticle"],
            journal=Journal({"name": "Nature", "volume": "1", "pages": "1-2"}),
            tldr=SimpleNamespace(model="m1", text="summary"),
            year=2020,
            title="A Title",
            venue="Nature",
            url="http://x",
            publicationDate=datetime(2020, 1, 15),
            corpusId=123,
            referenceCount=10,
            isOpenAccess=True,
        )
        result = c._paper_to_dict(paper)
        assert result["citation_count"] == 5
        assert result["authors"][0]["name"] == "Jane"
        assert result["external_ids"] == {"DOI": "10.1/x"}
        assert result["open_access_pdf_url"] == "http://pdf"
        assert result["journal"]["name"] == "Nature"
        assert result["tldr"] == {"model": "m1", "text": "summary"}
        assert result["publication_date"] == "2020-01-15"
        assert result["corpus_id"] == 123
        assert result["is_open_access"] is True

    def test_minimal_paper_filters_none_values(self):
        c = _client()
        paper = SimpleNamespace(paperId="p1")
        result = c._paper_to_dict(paper)
        assert result == {"s2_paper_id": "p1", "authors": [], "external_ids": {}, "journal": {}}


class TestAuthorToDict:
    def test_falsy_author_returns_empty_dict(self):
        c = _client()
        assert c._author_to_dict(None) == {}

    def test_full_author_mapping(self):
        c = _client()
        author = SimpleNamespace(
            authorId="a1",
            name="Jane",
            affiliations=["MIT"],
            citationCount=100,
            hIndex=10,
            paperCount=20,
            homepage="http://jane.example",
            url="http://s2/a1",
        )
        result = c._author_to_dict(author)
        assert result["author_id"] == "a1"
        assert result["h_index"] == 10
        assert result["url"] == "http://s2/a1"

    def test_minimal_author_filters_none(self):
        c = _client()
        author = SimpleNamespace(authorId="a1", name=None)
        result = c._author_to_dict(author)
        assert result == {"author_id": "a1"}


class TestVenueToDict:
    def test_falsy_venue_returns_empty_dict(self):
        c = _client()
        assert c._venue_to_dict(None) == {}

    def test_journal_instance(self):
        c = _client()
        journal = Journal({"name": "Nature", "volume": "5", "pages": "10-20"})
        result = c._venue_to_dict(journal)
        assert result == {"name": "Nature", "volume": "5", "pages": "10-20"}

    def test_publication_venue_like_object(self):
        c = _client()
        venue = SimpleNamespace(
            name="ICML",
            venueType="conference",
            issn=None,
            isbn=None,
            url="http://icml.example",
            alternateVenues=None,
            citationCount=50,
            paperCount=None,
            paperTypes=None,
            references=None,
        )
        result = c._venue_to_dict(venue)
        assert result == {
            "name": "ICML",
            "type": "conference",
            "url": "http://icml.example",
            "citation_count": 50,
        }
