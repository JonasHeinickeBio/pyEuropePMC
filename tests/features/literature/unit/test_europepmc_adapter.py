"""Unit tests for EuropePMCLiteratureAdapter (hermetic — search_client mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.literature.adapters import EuropePMCLiteratureAdapter

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter():
    return EuropePMCLiteratureAdapter(search_client=MagicMock())


class TestInit:
    def test_uses_provided_search_client(self):
        client = MagicMock()
        adapter = EuropePMCLiteratureAdapter(search_client=client)
        assert adapter.search_client is client

    def test_creates_default_search_client(self):
        with patch("pyeuropepmc.features.literature.search.SearchClient") as MockSC:
            adapter = EuropePMCLiteratureAdapter(rate_limit_delay=2.0)
        MockSC.assert_called_once_with(rate_limit_delay=2.0)
        assert adapter.search_client is MockSC.return_value

    def test_ignores_unknown_kwargs(self):
        client = MagicMock()
        EuropePMCLiteratureAdapter(search_client=client, unexpected_kwarg="ignored")


class TestSearch:
    def test_basic_search(self, adapter):
        adapter.search_client.search_and_parse.return_value = [
            {"title": "T1", "source": "MED", "id": "1"},
            {"title": "T2", "source": "MED", "id": "2"},
        ]
        results = adapter.search("cancer", limit=10)
        assert len(results) == 2
        assert results[0].title == "T1"
        args, kwargs = adapter.search_client.search_and_parse.call_args
        assert args[0] == "cancer"
        assert kwargs["pageSize"] == 10

    def test_sort_passed_through(self, adapter):
        adapter.search_client.search_and_parse.return_value = []
        adapter.search("cancer", sort="date")
        _, kwargs = adapter.search_client.search_and_parse.call_args
        assert kwargs["sort"] == "date"

    def test_page_size_capped_at_1000(self, adapter):
        adapter.search_client.search_and_parse.return_value = []
        adapter.search("cancer", limit=5000)
        _, kwargs = adapter.search_client.search_and_parse.call_args
        assert kwargs["pageSize"] == 1000

    def test_extra_kwargs_forwarded(self, adapter):
        adapter.search_client.search_and_parse.return_value = []
        adapter.search("cancer", resultType="core")
        _, kwargs = adapter.search_client.search_and_parse.call_args
        assert kwargs["resultType"] == "core"

    def test_search_exception_returns_empty_list(self, adapter):
        adapter.search_client.search_and_parse.side_effect = RuntimeError("down")
        assert adapter.search("cancer") == []

    def test_unparseable_record_is_skipped(self, adapter):
        adapter.search_client.search_and_parse.return_value = [
            {"title": "Good", "source": "MED", "id": "1"},
            {"source": "MED", "id": "2", "pubYear": object()},  # triggers unexpected error path
        ]
        with patch.object(
            adapter,
            "_normalize_to_literature_format",
            side_effect=[MagicMock(title="Good"), RuntimeError("bad record")],
        ):
            results = adapter.search("cancer")
        assert len(results) == 1

    def test_results_respect_limit(self, adapter):
        adapter.search_client.search_and_parse.return_value = [
            {"title": f"T{i}", "source": "MED", "id": str(i)} for i in range(5)
        ]
        results = adapter.search("cancer", limit=2)
        assert len(results) == 2


class TestGetPaper:
    def test_by_doi(self, adapter):
        with patch.object(adapter, "search", return_value=[MagicMock()]) as mock_search:
            adapter.get_paper("10.1234/x")
        assert 'DOI:"10.1234/x"' in mock_search.call_args[0][0]

    def test_by_pmcid(self, adapter):
        with patch.object(adapter, "search", return_value=[MagicMock()]) as mock_search:
            adapter.get_paper("PMC12345")
        assert "PMCID:PMC12345" in mock_search.call_args[0][0]

    def test_by_pmid(self, adapter):
        with patch.object(adapter, "search", return_value=[MagicMock()]) as mock_search:
            adapter.get_paper("12345678")
        assert "EXT_ID:12345678 AND SRC:MED" in mock_search.call_args[0][0]

    def test_fallback_uses_raw_identifier(self, adapter):
        with patch.object(adapter, "search", return_value=[MagicMock()]) as mock_search:
            adapter.get_paper("some free text query")
        assert mock_search.call_args[0][0] == "some free text query"

    def test_no_hits_returns_none(self, adapter):
        with patch.object(adapter, "search", return_value=[]):
            assert adapter.get_paper("10.1234/x") is None


class TestClose:
    def test_closes_search_client(self, adapter):
        adapter.close()
        adapter.search_client.close.assert_called_once()

    def test_close_swallows_exception(self, adapter):
        adapter.search_client.close.side_effect = RuntimeError("boom")
        adapter.close()  # must not raise


class TestNormalizeToLiteratureFormat:
    def test_full_record(self, adapter):
        data = {
            "title": "A Great Paper",
            "doi": "https://doi.org/10.1234/X",
            "pmid": "111",
            "pmcid": "PMC111",
            "authorString": "Smith J., Doe A.",
            "pubYear": "2021",
            "journalTitle": "Nature",
            "citedByCount": "42",
            "abstractText": "  An abstract.  ",
            "source": "MED",
            "id": "111",
            "isOpenAccess": "Y",
        }
        result = adapter._normalize_to_literature_format(data)
        assert result.title == "A Great Paper"
        assert result.doi == "10.1234/x"
        assert result.pmid == "111"
        assert result.pmcid == "PMC111"
        assert len(result.authors) == 2
        assert result.publication_year == 2021
        assert result.journal == "Nature"
        assert result.citation_count == 42
        assert result.abstract == "An abstract."
        assert result.source == "europepmc"
        assert result.extra_metadata["is_open_access"] == "Y"

    def test_pmid_falls_back_to_id_when_source_is_med(self, adapter):
        data = {"title": "T", "source": "MED", "id": "999"}
        result = adapter._normalize_to_literature_format(data)
        assert result.pmid == "999"

    def test_pmid_not_inferred_for_non_med_source(self, adapter):
        data = {"title": "T", "source": "PPR", "id": "999"}
        result = adapter._normalize_to_literature_format(data)
        assert result.pmid is None

    def test_journal_from_nested_journal_info(self, adapter):
        data = {
            "title": "T",
            "source": "MED",
            "id": "1",
            "journalInfo": {"journal": {"title": "Nested Journal"}},
        }
        result = adapter._normalize_to_literature_format(data)
        assert result.journal == "Nested Journal"

    def test_invalid_pub_year_ignored(self, adapter):
        data = {"title": "T", "source": "MED", "id": "1", "pubYear": "not-a-year"}
        result = adapter._normalize_to_literature_format(data)
        assert result.publication_year is None

    def test_invalid_citation_count_ignored(self, adapter):
        data = {"title": "T", "source": "MED", "id": "1", "citedByCount": "not-a-number"}
        result = adapter._normalize_to_literature_format(data)
        assert result.citation_count is None

    def test_no_authors(self, adapter):
        data = {"title": "T", "source": "MED", "id": "1", "authorString": ""}
        result = adapter._normalize_to_literature_format(data)
        assert result.authors is None

    def test_source_id_falls_back_through_pmid_doi(self, adapter):
        data = {"title": "T", "doi": "10.1234/x", "source": "PPR"}
        result = adapter._normalize_to_literature_format(data)
        assert result.source_id == "10.1234/x"
