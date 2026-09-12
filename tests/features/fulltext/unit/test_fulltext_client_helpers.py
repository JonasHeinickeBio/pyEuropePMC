"""Coverage for more fulltext_client.py helpers: PDF content validation,
HTML article URL construction, search-and-download's building blocks
(param validation, output dir prep, search-result -> PMCID extraction,
availability filtering), and the API-cache passthrough methods.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.core.exceptions import FullTextError
from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient


@pytest.fixture
def client():
    c = FullTextClient(enable_cache=False)
    yield c
    c.close()


class TestValidatePdfContent:
    def test_valid_pdf(self, client, tmp_path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF-1.4" + b"x" * 2000)
        assert client._validate_pdf_content(f) is True

    def test_missing_file(self, client, tmp_path):
        assert client._validate_pdf_content(tmp_path / "missing.pdf") is False

    def test_too_small(self, client, tmp_path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF")
        assert client._validate_pdf_content(f) is False

    def test_invalid_header(self, client, tmp_path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"NOTAPDF" + b"x" * 2000)
        assert client._validate_pdf_content(f) is False

    def test_suspiciously_small_valid_header(self, client, tmp_path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF" + b"x" * 200)  # >100 bytes but <1024
        assert client._validate_pdf_content(f) is False

    def test_exception_returns_false(self, client, tmp_path):
        f = tmp_path / "dir_not_file"
        f.mkdir()
        assert client._validate_pdf_content(f) is False


class TestGetHtmlArticleUrl:
    def test_by_pmcid(self, client):
        url = client.get_html_article_url("PMC123456")
        assert "123456" in url
        assert "PMC" in url

    def test_by_medid_takes_precedence(self, client):
        url = client.get_html_article_url("PMC123456", medid="999")
        assert "999" in url
        assert "MED" in url


class TestValidateSearchDownloadParams:
    def test_valid_formats_do_not_raise(self, client):
        for fmt in ["pdf", "xml", "html"]:
            client._validate_search_download_params(fmt, None)

    def test_invalid_format_raises(self, client):
        with pytest.raises(FullTextError):
            client._validate_search_download_params("docx", None)


class TestPrepareOutputDirectory:
    def test_none_uses_cwd(self, client):
        result = client._prepare_output_directory(None)
        assert result.exists()

    def test_creates_nested_directory(self, client, tmp_path):
        target = tmp_path / "a" / "b" / "c"
        result = client._prepare_output_directory(target)
        assert result == target
        assert target.exists()


class TestExtractPapersFromResults:
    def test_dict_with_result_list(self, client):
        results = {"resultList": {"result": [{"pmcid": "PMC1"}]}}
        papers = client._extract_papers_from_results(results)
        assert papers == [{"pmcid": "PMC1"}]

    def test_dict_missing_result_key(self, client):
        results = {"resultList": {}}
        assert client._extract_papers_from_results(results) == []

    def test_list_passthrough(self, client):
        results = [{"pmcid": "PMC1"}]
        assert client._extract_papers_from_results(results) == results

    def test_unexpected_format_returns_empty(self, client):
        assert client._extract_papers_from_results("not a dict or list") == []


class TestExtractPmcidsFromPapers:
    def test_extracts_and_strips_prefix(self, client):
        papers = [{"pmcid": "PMC123"}, {"pmcid": "PMC456"}]
        assert client._extract_pmcids_from_papers(papers) == ["123", "456"]

    def test_skips_papers_without_pmcid(self, client):
        papers = [{"title": "no pmcid"}, {"pmcid": "PMC1"}]
        assert client._extract_pmcids_from_papers(papers) == ["1"]

    def test_skips_non_dict_entries(self, client):
        papers = ["not a dict", {"pmcid": "PMC1"}]
        assert client._extract_pmcids_from_papers(papers) == ["1"]

    def test_empty_list(self, client):
        assert client._extract_pmcids_from_papers([]) == []


class TestFilterAvailablePmcids:
    def test_keeps_only_available(self, client):
        with patch.object(
            client,
            "check_fulltext_availability",
            side_effect=[{"xml": True}, {"xml": False}],
        ):
            result = client._filter_available_pmcids(["1", "2"], "xml")
        assert result == ["1"]

    def test_exception_is_skipped(self, client):
        with patch.object(
            client,
            "check_fulltext_availability",
            side_effect=[RuntimeError("boom"), {"xml": True}],
        ):
            result = client._filter_available_pmcids(["1", "2"], "xml")
        assert result == ["2"]

    def test_empty_input(self, client):
        assert client._filter_available_pmcids([], "xml") == []


class TestSearchForPmcids:
    def test_delegates_to_search_client(self, client):
        fake_search_client = MagicMock()
        fake_search_client.search.return_value = {
            "resultList": {"result": [{"pmcid": "PMC1"}]}
        }
        with patch(
            "pyeuropepmc.features.literature.search.SearchClient",
            return_value=fake_search_client,
        ):
            result = client._search_for_pmcids("cancer", 10)
        assert result == ["1"]
        fake_search_client.close.assert_called_once()

    def test_closes_search_client_on_exception(self, client):
        fake_search_client = MagicMock()
        fake_search_client.search.side_effect = RuntimeError("boom")
        with patch(
            "pyeuropepmc.features.literature.search.SearchClient",
            return_value=fake_search_client,
        ):
            with pytest.raises(RuntimeError):
                client._search_for_pmcids("cancer", 10)
        fake_search_client.close.assert_called_once()


class TestApiCachePassthroughs:
    def test_get_api_cache_stats(self, client):
        with patch.object(client._cache, "get_stats", return_value={"hits": 1}):
            assert client.get_api_cache_stats() == {"hits": 1}

    def test_get_api_cache_stats_exception_returns_empty(self, client):
        with patch.object(client._cache, "get_stats", side_effect=RuntimeError("boom")):
            assert client.get_api_cache_stats() == {}

    def test_get_api_cache_health(self, client):
        with patch.object(client._cache, "get_health", return_value={"status": "ok"}):
            assert client.get_api_cache_health() == {"status": "ok"}

    def test_get_api_cache_health_exception_returns_empty(self, client):
        with patch.object(client._cache, "get_health", side_effect=RuntimeError("boom")):
            assert client.get_api_cache_health() == {}

    def test_clear_api_cache(self, client):
        with patch.object(client._cache, "clear", return_value=True):
            assert client.clear_api_cache() is True

    def test_clear_api_cache_exception_returns_false(self, client):
        with patch.object(client._cache, "clear", side_effect=RuntimeError("boom")):
            assert client.clear_api_cache() is False

    def test_invalidate_fulltext_cache_with_pmcid(self, client):
        with patch.object(
            client._cache, "invalidate_pattern", return_value=3
        ) as mock_invalidate:
            count = client.invalidate_fulltext_cache("PMC123")
        assert count == 3
        mock_invalidate.assert_called_once_with("*:123*")

    def test_invalidate_fulltext_cache_without_pmcid(self, client):
        with patch.object(
            client._cache, "invalidate_pattern", return_value=5
        ) as mock_invalidate:
            client.invalidate_fulltext_cache()
        mock_invalidate.assert_called_once_with("*")

    def test_invalidate_fulltext_cache_exception_returns_zero(self, client):
        with patch.object(
            client._cache, "invalidate_pattern", side_effect=RuntimeError("boom")
        ):
            assert client.invalidate_fulltext_cache() == 0

    def test_close_calls_cache_close(self, client):
        with patch.object(client._cache, "close") as mock_close:
            client.close()
        mock_close.assert_called_once()
