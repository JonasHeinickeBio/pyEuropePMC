"""Tests for pyeuropepmc.processing.extensions.reference_resolver."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.processing.extensions.reference_resolver import (
    EUROPE_PMC_API,
    ReferenceResolver,
    ResolvedReference,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# ResolvedReference.to_dict()
# ---------------------------------------------------------------------------

class TestResolvedReferenceToDict:
    def test_to_dict_all_fields(self):
        ref = ResolvedReference(
            source_ref={"id": "src1", "title": "Orig"},
            resolved_pmid="12345",
            resolved_doi="10.1234/test",
            title="A Test Article",
            authors="Doe J",
            year="2023",
            journal="Test Journal",
            citations=42,
            is_open_access=True,
        )
        d = ref.to_dict()
        assert d == {
            "source_ref": {"id": "src1", "title": "Orig"},
            "resolved_pmid": "12345",
            "resolved_doi": "10.1234/test",
            "title": "A Test Article",
            "authors": "Doe J",
            "year": "2023",
            "journal": "Test Journal",
            "citations": 42,
            "is_open_access": True,
        }

    def test_to_dict_returns_new_dict(self):
        ref = ResolvedReference(resolved_pmid="1")
        d1 = ref.to_dict()
        d1["resolved_pmid"] = "mutated"
        d2 = ref.to_dict()
        assert d2["resolved_pmid"] == "1"

    def test_to_dict_defaults(self):
        ref = ResolvedReference()
        d = ref.to_dict()
        assert d["source_ref"] == {}
        assert d["resolved_pmid"] == ""
        assert d["resolved_doi"] == ""
        assert d["title"] == ""
        assert d["authors"] == ""
        assert d["year"] == ""
        assert d["journal"] == ""
        assert d["citations"] == 0
        assert d["is_open_access"] is False


# ---------------------------------------------------------------------------
# ReferenceResolver.__init__()
# ---------------------------------------------------------------------------

class TestReferenceResolverInit:
    def test_default_params(self):
        r = ReferenceResolver()
        assert r.rate_limit == 3.0
        assert r.api_key is None
        assert r._cache == {}
        assert r._last_request_time == 0.0
        assert r._stats == {"lookups": 0, "cache_hits": 0, "cache_size": 0}

    def test_rate_limit_minimum_positive(self):
        r = ReferenceResolver(rate_limit=5.0)
        assert r.rate_limit == 5.0

    def test_rate_limit_negative_clamped_to_0_1(self):
        r = ReferenceResolver(rate_limit=-10.0)
        assert r.rate_limit == 0.1

    def test_rate_limit_zero_clamped_to_0_1(self):
        r = ReferenceResolver(rate_limit=0.0)
        assert r.rate_limit == 0.1

    def test_rate_limit_small_positive_kept(self):
        r = ReferenceResolver(rate_limit=0.1)
        assert r.rate_limit == 0.1

    def test_rate_limit_between_zero_and_min_kept(self):
        r = ReferenceResolver(rate_limit=0.05)
        assert r.rate_limit == 0.1

    def test_api_key_stored(self):
        r = ReferenceResolver(api_key="mykey123")
        assert r.api_key == "mykey123"


# ---------------------------------------------------------------------------
# ReferenceResolver.resolve_reference()
# ---------------------------------------------------------------------------

class TestResolveReference:
    def test_cache_hit(self):
        r = ReferenceResolver()
        cached = ResolvedReference(
            resolved_pmid="99999",
            title="Cached Article",
        )
        r._cache["10.1234/cached"] = cached

        ref = {"doi": "10.1234/cached", "pmid": "11111", "title": "Some title"}
        result = r.resolve_reference(ref)

        assert result is not None
        assert result.resolved_pmid == "99999"
        assert result.title == "Cached Article"
        assert r._stats["cache_hits"] == 1
        assert r._stats["lookups"] == 0

    def test_cache_hit_returns_deepcopy(self):
        r = ReferenceResolver()
        cached = ResolvedReference(resolved_pmid="p1", title="T")
        r._cache["key1"] = cached

        ref = {"pmid": "key1"}
        result = r.resolve_reference(ref)
        result.title = "mutated"
        assert r._cache["key1"].title == "T"

    @patch.object(ReferenceResolver, "_lookup_by_doi")
    @patch.object(ReferenceResolver, "_throttle")
    def test_cache_miss_doi_lookup(self, mock_throttle, mock_doi):
        r = ReferenceResolver()
        mock_doi.return_value = ResolvedReference(
            resolved_doi="10.1234/x", resolved_pmid="22222"
        )

        ref = {"doi": "10.1234/x", "title": "Title here"}
        result = r.resolve_reference(ref)

        mock_doi.assert_called_once_with("10.1234/x")
        assert result is not None
        assert result.source_ref == ref
        assert r._stats["lookups"] == 1

    @patch.object(ReferenceResolver, "_lookup_by_doi", return_value=None)
    @patch.object(ReferenceResolver, "_lookup_by_pmid")
    @patch.object(ReferenceResolver, "_throttle")
    def test_cache_miss_pmid_fallback(self, mock_throttle, mock_pmid, mock_doi):
        r = ReferenceResolver()
        mock_pmid.return_value = ResolvedReference(resolved_pmid="33333")

        ref = {"doi": "bad", "pmid": "44444", "title": "T"}
        result = r.resolve_reference(ref)

        mock_doi.assert_called_once_with("bad")
        mock_pmid.assert_called_once_with("44444")
        assert result is not None

    @patch.object(ReferenceResolver, "_lookup_by_doi", return_value=None)
    @patch.object(ReferenceResolver, "_lookup_by_pmid", return_value=None)
    @patch.object(ReferenceResolver, "_lookup_by_title")
    @patch.object(ReferenceResolver, "_throttle")
    def test_cache_miss_title_fallback(
        self, mock_throttle, mock_title, mock_pmid, mock_doi
    ):
        r = ReferenceResolver()
        mock_title.return_value = ResolvedReference(title="A Long Title Here")

        ref = {"doi": "", "pmid": "", "title": "A Long Title Here"}
        result = r.resolve_reference(ref)

        mock_title.assert_called_once_with("A Long Title Here")
        assert result is not None

    @patch.object(ReferenceResolver, "_lookup_by_doi", return_value=None)
    @patch.object(ReferenceResolver, "_lookup_by_pmid", return_value=None)
    @patch.object(ReferenceResolver, "_lookup_by_title", return_value=None)
    @patch.object(ReferenceResolver, "_throttle")
    def test_cache_miss_all_return_none(
        self, mock_throttle, mock_title, mock_pmid, mock_doi
    ):
        r = ReferenceResolver()
        ref = {"doi": "x", "pmid": "y", "title": "z"}
        result = r.resolve_reference(ref)

        assert result is None
        assert r._stats["lookups"] == 1

    @patch.object(ReferenceResolver, "_lookup_by_doi", return_value=None)
    @patch.object(ReferenceResolver, "_lookup_by_pmid", return_value=None)
    @patch.object(ReferenceResolver, "_lookup_by_title", return_value=None)
    @patch.object(ReferenceResolver, "_throttle")
    def test_failed_lookup_not_cached(
        self, mock_throttle, mock_title, mock_pmid, mock_doi
    ):
        r = ReferenceResolver()
        ref = {"doi": "10.fail/x"}
        r.resolve_reference(ref)

        assert "10.fail/x" not in r._cache
        assert r._stats["cache_size"] == 0


# ---------------------------------------------------------------------------
# ReferenceResolver.resolve_batch()
# ---------------------------------------------------------------------------

class TestResolveBatch:
    @patch.object(ReferenceResolver, "resolve_reference")
    def test_resolve_batch_mixed(self, mock_resolve):
        refs = [
            {"doi": "d1", "title": "t1"},
            {"doi": "d2", "title": "t2"},
            {"doi": "d3", "title": "t3"},
        ]

        def side_effect(ref):
            if ref["doi"] == "d2":
                return None
            return ResolvedReference(resolved_doi=ref["doi"], title=ref["title"])

        mock_resolve.side_effect = side_effect

        r = ReferenceResolver()
        results = r.resolve_batch(refs)

        assert len(results) == 3
        assert results[0].resolved_doi == "d1"
        assert results[1].resolved_doi == "d2"
        assert results[1].resolved_pmid == ""
        assert results[2].resolved_doi == "d3"

    @patch.object(ReferenceResolver, "resolve_reference")
    def test_resolve_batch_progress_callback(self, mock_resolve):
        mock_resolve.return_value = ResolvedReference()
        refs = [{"doi": "a"}, {"doi": "b"}]
        callback = MagicMock()

        r = ReferenceResolver()
        r.resolve_batch(refs, progress_callback=callback)

        assert callback.call_count == 2
        callback.assert_any_call(1, 2)
        callback.assert_any_call(2, 2)

    @patch.object(ReferenceResolver, "resolve_reference", return_value=None)
    def test_resolve_batch_all_unresolved(self, mock_resolve):
        refs = [{"doi": "x"}, {"doi": "y"}]
        r = ReferenceResolver()
        results = r.resolve_batch(refs)

        assert len(results) == 2
        for res in results:
            assert isinstance(res, ResolvedReference)
            assert res.resolved_pmid == ""

    @patch.object(ReferenceResolver, "resolve_reference", return_value=None)
    def test_resolve_batch_empty(self, mock_resolve):
        r = ReferenceResolver()
        results = r.resolve_batch([])
        assert results == []


# ---------------------------------------------------------------------------
# ReferenceResolver._lookup_by_doi()
# ---------------------------------------------------------------------------

class TestLookupByDoi:
    @patch("urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        response_data = {
            "resultList": {
                "result": [
                    {
                        "pmid": "12345",
                        "doi": "10.1234/test",
                        "title": "Test Title",
                        "authorString": "Smith A",
                        "firstPublicationDate": "2023-01-15",
                        "journalTitle": "J Test",
                        "citedByCount": 10,
                        "isOpenAccess": True,
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_urlopen.return_value = mock_resp

        r = ReferenceResolver()
        result = r._lookup_by_doi("10.1234/test")

        assert result is not None
        assert result.resolved_pmid == "12345"
        assert result.resolved_doi == "10.1234/test"
        assert result.citations == 10
        assert result.is_open_access is True

    @patch("urllib.request.urlopen")
    def test_failure_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("network error")

        r = ReferenceResolver()
        result = r._lookup_by_doi("10.1234/fail")

        assert result is None


# ---------------------------------------------------------------------------
# ReferenceResolver._lookup_by_pmid()
# ---------------------------------------------------------------------------

class TestLookupByPmid:
    @patch("urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        response_data = {
            "resultList": {
                "result": [
                    {
                        "pmid": "99999",
                        "doi": "10.9999/pmid",
                        "title": "PMID Article",
                        "authorString": "Jones B",
                        "firstPublicationDate": "2022-06-01",
                        "journalTitle": "PMID J",
                        "citedByCount": 5,
                        "isOpenAccess": False,
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_urlopen.return_value = mock_resp

        r = ReferenceResolver()
        result = r._lookup_by_pmid("99999")

        assert result is not None
        assert result.resolved_pmid == "99999"
        assert result.citations == 5
        assert result.is_open_access is False

    @patch("urllib.request.urlopen")
    def test_failure_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("timeout")

        r = ReferenceResolver()
        result = r._lookup_by_pmid("00000")

        assert result is None


# ---------------------------------------------------------------------------
# ReferenceResolver._lookup_by_title()
# ---------------------------------------------------------------------------

class TestLookupByTitle:
    def test_title_too_short_returns_none(self):
        r = ReferenceResolver()
        result = r._lookup_by_title("Short")
        assert result is None

    def test_title_exactly_19_chars_returns_none(self):
        r = ReferenceResolver()
        result = r._lookup_by_title("A" * 19)
        assert result is None

    @patch("urllib.request.urlopen")
    def test_title_exactly_20_chars_proceeds(self, mock_urlopen):
        r = ReferenceResolver()
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"resultList": {"result": []}}
        ).encode()
        mock_urlopen.return_value = mock_resp

        result = r._lookup_by_title("A" * 20)
        assert result is None
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        response_data = {
            "resultList": {
                "result": [
                    {
                        "pmid": "55555",
                        "doi": "10.5555/title",
                        "title": "Long Enough Title For Lookup",
                        "authorString": "Lee C",
                        "firstPublicationDate": "2021-03-20",
                        "journalTitle": "Title J",
                        "citedByCount": 7,
                        "isOpenAccess": True,
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_urlopen.return_value = mock_resp

        r = ReferenceResolver()
        result = r._lookup_by_title("Long Enough Title For Lookup")

        assert result is not None
        assert result.resolved_pmid == "55555"
        assert result.title == "Long Enough Title For Lookup"

    @patch("urllib.request.urlopen")
    def test_failure_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("dns error")

        r = ReferenceResolver()
        result = r._lookup_by_title("A" * 20)
        assert result is None


# ---------------------------------------------------------------------------
# ReferenceResolver._parse_api_response()
# ---------------------------------------------------------------------------

class TestParseApiResponse:
    def test_with_results(self):
        data = {
            "resultList": {
                "result": [
                    {
                        "pmid": "111",
                        "doi": "10.1/a",
                        "title": "A Title",
                        "authorString": "X",
                        "firstPublicationDate": "2020-01-01",
                        "journalTitle": "J",
                        "citedByCount": 3,
                        "isOpenAccess": False,
                    }
                ]
            }
        }
        r = ReferenceResolver()
        result = r._parse_api_response(data)

        assert result is not None
        assert result.resolved_pmid == "111"
        assert result.resolved_doi == "10.1/a"

    def test_empty_results(self):
        r = ReferenceResolver()
        assert r._parse_api_response({"resultList": {"result": []}}) is None
        assert r._parse_api_response({}) is None
        assert r._parse_api_response({"resultList": {}}) is None


# ---------------------------------------------------------------------------
# ReferenceResolver._parse_entry()
# ---------------------------------------------------------------------------

class TestParseEntry:
    def test_all_fields(self):
        entry = {
            "pmid": "P1",
            "doi": "D1",
            "title": "Full Title",
            "authorString": "Author A",
            "firstPublicationDate": "2022-12-31",
            "journalTitle": "Journal",
            "citedByCount": 25,
            "isOpenAccess": True,
        }
        ref = ReferenceResolver._parse_entry(entry)

        assert ref.resolved_pmid == "P1"
        assert ref.resolved_doi == "D1"
        assert ref.title == "Full Title"
        assert ref.authors == "Author A"
        assert ref.year == "2022"
        assert ref.journal == "Journal"
        assert ref.citations == 25
        assert ref.is_open_access is True

    def test_missing_fields(self):
        ref = ReferenceResolver._parse_entry({})
        assert ref.resolved_pmid == ""
        assert ref.resolved_doi == ""
        assert ref.title == ""
        assert ref.authors == ""
        assert ref.year == ""
        assert ref.journal == ""
        assert ref.citations == 0
        assert ref.is_open_access is False

    def test_cited_by_count_as_string(self):
        entry = {"citedByCount": "42"}
        ref = ReferenceResolver._parse_entry(entry)
        assert ref.citations == 42

    def test_cited_by_count_none(self):
        entry = {"citedByCount": None}
        ref = ReferenceResolver._parse_entry(entry)
        assert ref.citations == 0

    def test_first_publication_date_slicing(self):
        entry = {"firstPublicationDate": "2023-07-10"}
        ref = ReferenceResolver._parse_entry(entry)
        assert ref.year == "2023"

    def test_first_publication_date_empty(self):
        entry = {"firstPublicationDate": ""}
        ref = ReferenceResolver._parse_entry(entry)
        assert ref.year == ""


# ---------------------------------------------------------------------------
# ReferenceResolver._throttle()
# ---------------------------------------------------------------------------

class TestThrottle:
    @patch("pyeuropepmc.processing.extensions.reference_resolver.time.time")
    @patch("pyeuropepmc.processing.extensions.reference_resolver.time.sleep")
    def test_sleep_called_when_too_fast(self, mock_sleep, mock_time):
        mock_time.side_effect = [0.0, 0.0]
        r = ReferenceResolver(rate_limit=3.0)
        r._last_request_time = 0.0

        r._throttle()

        min_interval = 1.0 / 3.0
        mock_sleep.assert_called_once()
        slept = mock_sleep.call_args[0][0]
        assert slept == pytest.approx(min_interval, abs=1e-6)

    @patch("pyeuropepmc.processing.extensions.reference_resolver.time.time")
    @patch("pyeuropepmc.processing.extensions.reference_resolver.time.sleep")
    def test_sleep_not_called_when_enough_time(self, mock_sleep, mock_time):
        mock_time.side_effect = [1.0, 1.0]
        r = ReferenceResolver(rate_limit=3.0)
        r._last_request_time = 0.0

        r._throttle()

        mock_sleep.assert_not_called()

    @patch("pyeuropepmc.processing.extensions.reference_resolver.time.time")
    @patch("pyeuropepmc.processing.extensions.reference_resolver.time.sleep")
    def test_throttle_updates_last_request_time(self, mock_sleep, mock_time):
        mock_time.side_effect = [5.0, 5.0]
        r = ReferenceResolver(rate_limit=3.0)
        r._last_request_time = 0.0

        r._throttle()

        assert r._last_request_time == 5.0


# ---------------------------------------------------------------------------
# ReferenceResolver.stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_returns_copy(self):
        r = ReferenceResolver()
        s1 = r.stats
        s1["lookups"] = 999
        s2 = r.stats
        assert s2["lookups"] == 0

    def test_stats_reflects_actual_state(self):
        r = ReferenceResolver()
        r._stats["lookups"] = 5
        r._stats["cache_hits"] = 2
        r._stats["cache_size"] = 3
        s = r.stats
        assert s == {"lookups": 5, "cache_hits": 2, "cache_size": 3}


# ---------------------------------------------------------------------------
# API key appended to URL in lookup methods
# ---------------------------------------------------------------------------

class TestApiKeyInLookup:
    @patch("urllib.request.urlopen")
    def test_api_key_in_doi_url(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"resultList": {"result": []}}
        ).encode()
        mock_urlopen.return_value = mock_resp

        r = ReferenceResolver(api_key="MYKEY")
        r._lookup_by_doi("10.1234/x")

        called_url = mock_urlopen.call_args[0][0]
        assert "apiKey=MYKEY" in called_url

    @patch("urllib.request.urlopen")
    def test_api_key_in_pmid_url(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"resultList": {"result": []}}
        ).encode()
        mock_urlopen.return_value = mock_resp

        r = ReferenceResolver(api_key="MYKEY")
        r._lookup_by_pmid("12345")

        called_url = mock_urlopen.call_args[0][0]
        assert "apiKey=MYKEY" in called_url

    @patch("urllib.request.urlopen")
    def test_api_key_in_title_url(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"resultList": {"result": []}}
        ).encode()
        mock_urlopen.return_value = mock_resp

        r = ReferenceResolver(api_key="MYKEY")
        r._lookup_by_title("A" * 20)

        called_url = mock_urlopen.call_args[0][0]
        assert "apiKey=MYKEY" in called_url

    @patch("urllib.request.urlopen")
    def test_no_api_key_no_key_param(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"resultList": {"result": []}}
        ).encode()
        mock_urlopen.return_value = mock_resp

        r = ReferenceResolver()
        r._lookup_by_doi("10.1234/x")

        called_url = mock_urlopen.call_args[0][0]
        assert "apiKey" not in called_url


# ---------------------------------------------------------------------------
# Cache key priority: doi > pmid > title[:50]
# ---------------------------------------------------------------------------

class TestCacheKeyPriority:
    def test_cache_key_uses_doi_when_present(self):
        r = ReferenceResolver()
        cached = ResolvedReference(resolved_pmid="cached")
        r._cache["10.1234/doi"] = cached

        ref = {"doi": "10.1234/doi", "pmid": "other_pmid", "title": "other title"}
        result = r.resolve_reference(ref)
        assert result is not None
        assert r._stats["cache_hits"] == 1

    def test_cache_key_uses_pmid_when_no_doi(self):
        r = ReferenceResolver()
        cached = ResolvedReference(resolved_pmid="cached")
        r._cache["PMID_ONLY"] = cached

        ref = {"doi": "", "pmid": "PMID_ONLY", "title": "other title"}
        result = r.resolve_reference(ref)
        assert result is not None
        assert r._stats["cache_hits"] == 1

    def test_cache_key_uses_title_when_no_doi_no_pmid(self):
        r = ReferenceResolver()
        long_title = "A" * 50
        cached = ResolvedReference(title="cached")
        r._cache[long_title] = cached

        ref = {"doi": "", "pmid": "", "title": long_title + "B" * 100}
        result = r.resolve_reference(ref)
        assert result is not None
        assert r._stats["cache_hits"] == 1

    def test_cache_key_title_truncated_to_50(self):
        r = ReferenceResolver()
        title_50 = "X" * 50
        r._cache[title_50] = ResolvedReference(title="hit")

        ref = {"doi": "", "pmid": "", "title": "X" * 100}
        result = r.resolve_reference(ref)
        assert result is not None
        assert result.title == "hit"
