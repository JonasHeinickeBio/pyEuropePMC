"""Coverage for the parts of fulltext_client.py that need no network:
ProgressInfo, DownloadReport, RateLimiter, and FullTextClient's file-cache
management (_get_cache_path, _is_cached_file_valid, _verify_file_format,
_check_cache_for_file, _save_to_cache, clear_cache, get_cache_stats,
get_file_cache_health and its sub-checks).
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from pyeuropepmc.features.fulltext.fulltext_client import (
    DownloadReport,
    FullTextClient,
    ProgressInfo,
    RateLimiter,
)


class TestProgressInfo:
    def test_progress_percent(self):
        p = ProgressInfo(total_items=10, current_item=5)
        assert p.progress_percent == 50.0

    def test_progress_percent_zero_total(self):
        p = ProgressInfo(total_items=0, current_item=0)
        assert p.progress_percent == 0.0

    def test_elapsed_time_positive(self):
        p = ProgressInfo(total_items=10, start_time=time.time() - 5)
        assert p.elapsed_time >= 5

    def test_estimated_total_time_none_at_start(self):
        p = ProgressInfo(total_items=10, current_item=0)
        assert p.estimated_total_time is None

    def test_estimated_total_time_computed(self):
        p = ProgressInfo(total_items=10, current_item=5, start_time=time.time() - 5)
        assert p.estimated_total_time is not None
        assert p.estimated_total_time > 0

    def test_estimated_remaining_time_none_at_start(self):
        p = ProgressInfo(total_items=10, current_item=0)
        assert p.estimated_remaining_time is None

    def test_estimated_remaining_time_non_negative(self):
        p = ProgressInfo(total_items=10, current_item=9, start_time=time.time() - 9)
        assert p.estimated_remaining_time >= 0

    def test_completion_rate_zero_elapsed(self):
        now = time.time()
        p = ProgressInfo(total_items=10, current_item=5, start_time=now)
        with patch("time.time", return_value=now):
            assert p.completion_rate == 0.0

    def test_completion_rate_positive(self):
        p = ProgressInfo(total_items=10, current_item=5, start_time=time.time() - 5)
        assert p.completion_rate > 0

    def test_to_dict_has_expected_keys(self):
        p = ProgressInfo(total_items=10, current_item=5, current_pmcid="123")
        d = p.to_dict()
        assert d["total_items"] == 10
        assert d["current_pmcid"] == "123"
        assert "progress_percent" in d

    def test_str_representation(self):
        p = ProgressInfo(total_items=10, current_item=5, current_pmcid="123", status="running")
        text = str(p)
        assert "5/10" in text
        assert "PMC123" in text
        assert "running" in text


class TestDownloadReport:
    def test_initial_state(self):
        report = DownloadReport("123")
        assert report.pmcid == "123"
        assert report.overall_status == "pending"

    def test_add_successful_attempt(self):
        report = DownloadReport("123")
        report.add_attempt("rest_api", success=True, path="/tmp/PMC123.xml")
        assert report.overall_status == "success"
        assert report.successful_method == "rest_api"
        assert report.successful_path == "/tmp/PMC123.xml"

    def test_add_failed_attempt_does_not_change_status(self):
        report = DownloadReport("123")
        report.add_attempt("rest_api", success=False, error="404")
        assert report.overall_status == "pending"
        assert len(report.download_attempts) == 1

    def test_add_fallback(self):
        report = DownloadReport("123")
        report.add_fallback(1, "rest_api", tried=True, success=False)
        assert report.fallback_chain[0]["method"] == "rest_api"

    def test_set_detailed_analysis(self):
        report = DownloadReport("123")
        report.set_detailed_analysis({"key": "value"})
        assert report.detailed_analysis == {"key": "value"}

    def test_to_dict(self):
        report = DownloadReport("123")
        report.add_attempt("rest_api", success=True, path="/tmp/x.xml")
        d = report.to_dict()
        assert d["pmcid"] == "123"
        assert d["overall_status"] == "success"

    def test_to_json(self):
        report = DownloadReport("123")
        text = report.to_json()
        parsed = json.loads(text)
        assert parsed["pmcid"] == "123"

    def test_save(self, tmp_path):
        report = DownloadReport("123")
        report.add_attempt("rest_api", success=True)
        out = report.save(tmp_path / "sub" / "report.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["pmcid"] == "123"

    def test_str_includes_attempts_and_errors(self):
        report = DownloadReport("123")
        report.add_attempt("rest_api", success=False, error="Something went wrong" * 10)
        text = str(report)
        assert "123" in text
        assert "rest_api" in text
        assert "Error:" in text


class TestRateLimiter:
    def test_check_and_record_allows_under_threshold(self):
        rl = RateLimiter(worker_id=1, max_requests_per_second=10.0)
        assert rl.check_and_record() is True

    def test_check_and_record_blocks_over_threshold(self):
        rl = RateLimiter(worker_id=1, max_requests_per_second=2.0)
        rl.check_and_record()
        rl.check_and_record()
        # third call within the same window should exceed 80% threshold (1.6 -> 1)
        result = rl.check_and_record()
        assert result is False

    def test_threshold_minimum_is_one(self):
        rl = RateLimiter(worker_id=1, max_requests_per_second=0.5)
        assert rl.request_threshold == 1

    def test_window_resets_after_one_second(self):
        # Use a high enough rate that the reset request doesn't itself trip
        # the 80% threshold (max_requests_per_second=2.0 -> threshold=1,
        # which *would* immediately re-trip on the very first post-reset call).
        rl = RateLimiter(worker_id=1, max_requests_per_second=10.0)
        rl.check_and_record()
        rl.window_start = time.time() - 2  # simulate window elapsed
        assert rl.check_and_record() is True
        assert rl.requests_made == 1

    def test_wait_if_needed_does_not_block_under_limit(self):
        rl = RateLimiter(worker_id=1, max_requests_per_second=100.0)
        start = time.time()
        rl.wait_if_needed()
        assert time.time() - start < 1.0

    def test_wait_if_needed_resets_window_when_elapsed(self):
        rl = RateLimiter(worker_id=1, max_requests_per_second=1.0)
        rl.requests_made = 1
        rl.window_start = time.time() - 2
        rl.wait_if_needed()
        assert rl.requests_made == 1

    def test_get_stats(self):
        rl = RateLimiter(worker_id=5, max_requests_per_second=1.0)
        rl.check_and_record()
        stats = rl.get_stats()
        assert stats["worker_id"] == 5
        assert stats["requests_made"] == 1


@pytest.fixture
def client(tmp_path):
    c = FullTextClient(enable_cache=True, cache_dir=str(tmp_path), cache_max_age_days=30)
    yield c


class TestCachePath:
    def test_disabled_cache_returns_none(self, tmp_path):
        c = FullTextClient(enable_cache=False)
        assert c._get_cache_path("1", "xml") is None

    def test_returns_path_and_creates_dir(self, client, tmp_path):
        path = client._get_cache_path("1", "xml")
        assert path == tmp_path / "xml" / "PMC1.xml"
        assert (tmp_path / "xml").exists()


class TestIsCachedFileValid:
    def test_missing_file_invalid(self, client, tmp_path):
        assert client._is_cached_file_valid(tmp_path / "nope.xml") is False

    def test_empty_file_invalid(self, client, tmp_path):
        f = tmp_path / "empty.xml"
        f.write_text("")
        assert client._is_cached_file_valid(f) is False

    def test_stale_file_invalid(self, client, tmp_path):
        f = tmp_path / "stale.xml"
        f.write_text("<article/>")
        old_time = time.time() - (client.cache_max_age_days + 1) * 24 * 3600
        import os

        os.utime(f, (old_time, old_time))
        assert client._is_cached_file_valid(f) is False

    def test_fresh_valid_file(self, client, tmp_path):
        f = tmp_path / "good.xml"
        f.write_text("<article/>")
        assert client._is_cached_file_valid(f) is True

    def test_verification_disabled_skips_format_check(self, tmp_path):
        c = FullTextClient(
            enable_cache=True,
            cache_dir=str(tmp_path),
            verify_cached_files=False,
        )
        f = tmp_path / "bad.xml"
        f.write_text("not xml at all")
        assert c._is_cached_file_valid(f) is True


class TestVerifyFileFormat:
    def test_valid_pdf(self, client, tmp_path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF-1.4\n...")
        assert client._verify_file_format(f) is True

    def test_invalid_pdf(self, client, tmp_path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"not a pdf")
        assert client._verify_file_format(f) is False

    def test_valid_xml(self, client, tmp_path):
        f = tmp_path / "a.xml"
        f.write_text("<article/>")
        assert client._verify_file_format(f) is True

    def test_invalid_xml(self, client, tmp_path):
        f = tmp_path / "a.xml"
        f.write_text("not xml")
        assert client._verify_file_format(f) is False

    def test_valid_html(self, client, tmp_path):
        f = tmp_path / "a.html"
        f.write_text("<html><body>hi</body></html>")
        assert client._verify_file_format(f) is True

    def test_invalid_html(self, client, tmp_path):
        f = tmp_path / "a.html"
        f.write_text("just plain text")
        assert client._verify_file_format(f) is False

    def test_unknown_extension_assumed_valid(self, client, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"\x00\x01")
        assert client._verify_file_format(f) is True

    def test_nonexistent_file_returns_false(self, client, tmp_path):
        assert client._verify_file_format(tmp_path / "missing.pdf") is False


class TestCheckCacheForFile:
    def test_disabled_returns_none(self, tmp_path):
        c = FullTextClient(enable_cache=False)
        assert c._check_cache_for_file("1", "xml") is None

    def test_no_cached_file_returns_none(self, client):
        assert client._check_cache_for_file("1", "xml") is None

    def test_returns_cache_path_when_valid(self, client, tmp_path):
        cache_path = client._get_cache_path("1", "xml")
        cache_path.write_text("<article/>")
        result = client._check_cache_for_file("1", "xml")
        assert result == cache_path

    def test_copies_to_output_path_when_given(self, client, tmp_path):
        cache_path = client._get_cache_path("1", "xml")
        cache_path.write_text("<article/>")
        output = tmp_path / "out" / "result.xml"
        result = client._check_cache_for_file("1", "xml", output_path=output)
        assert result == output
        assert output.exists()


class TestSaveToCache:
    def test_disabled_returns_false(self, tmp_path):
        c = FullTextClient(enable_cache=False)
        f = tmp_path / "x.xml"
        f.write_text("<a/>")
        assert c._save_to_cache(f, "1", "xml") is False

    def test_missing_file_returns_false(self, client, tmp_path):
        assert client._save_to_cache(tmp_path / "missing.xml", "1", "xml") is False

    def test_saves_successfully(self, client, tmp_path):
        src = tmp_path / "downloaded.xml"
        src.write_text("<article/>")
        assert client._save_to_cache(src, "1", "xml") is True
        assert client._get_cache_path("1", "xml").exists()

    def test_already_in_cache_location_returns_true(self, client):
        cache_path = client._get_cache_path("1", "xml")
        cache_path.write_text("<article/>")
        assert client._save_to_cache(cache_path, "1", "xml") is True


class TestClearCache:
    def test_disabled_returns_zero(self, tmp_path):
        c = FullTextClient(enable_cache=False)
        assert c.clear_cache() == 0

    def test_removes_stale_files_only(self, client, tmp_path):
        fresh = client._get_cache_path("1", "xml")
        fresh.write_text("<a/>")
        stale = client._get_cache_path("2", "xml")
        stale.write_text("<a/>")
        import os

        old_time = time.time() - 100 * 24 * 3600
        os.utime(stale, (old_time, old_time))

        removed = client.clear_cache(max_age_days=30)
        assert removed == 1
        assert fresh.exists()
        assert not stale.exists()

    def test_specific_format_only(self, client):
        xml_path = client._get_cache_path("1", "xml")
        xml_path.write_text("<a/>")
        import os

        old_time = time.time() - 100 * 24 * 3600
        os.utime(xml_path, (old_time, old_time))
        removed = client.clear_cache(format_type="pdf", max_age_days=1)
        assert removed == 0
        assert xml_path.exists()


class TestGetCacheStats:
    def test_disabled(self, tmp_path):
        c = FullTextClient(enable_cache=False)
        assert c.get_cache_stats() == {"enabled": False}

    def test_counts_files_and_size(self, client):
        xml_path = client._get_cache_path("1", "xml")
        xml_path.write_text("<article/>")
        stats = client.get_cache_stats()
        assert stats["enabled"] is True
        assert stats["total_files"] == 1
        assert stats["formats"]["xml"]["count"] == 1
        assert stats["total_size_bytes"] > 0


class TestFileCacheHealth:
    def test_disabled(self, tmp_path):
        c = FullTextClient(enable_cache=False)
        health = c.get_file_cache_health()
        assert health["status"] == "disabled"

    def test_healthy_when_writable_and_fresh(self, client):
        health = client.get_file_cache_health()
        assert health["status"] == "healthy"
        assert health["directory_writable"] is True

    def test_warns_on_stale_files(self, client):
        xml_path = client._get_cache_path("1", "xml")
        xml_path.write_text("<article/>")
        import os

        old_time = time.time() - 100 * 24 * 3600
        os.utime(xml_path, (old_time, old_time))
        health = client.get_file_cache_health()
        assert health["files_within_age_limit"] is False
        assert health["status"] == "warning"

    def test_missing_directory_errors(self, tmp_path):
        missing_dir = tmp_path / "does_not_exist"
        c = FullTextClient(enable_cache=True, cache_dir=str(missing_dir))
        import shutil

        shutil.rmtree(missing_dir, ignore_errors=True)
        health = c.get_file_cache_health()
        assert health["status"] == "error"

    def test_determine_health_status_exception_handled(self, client):
        # A non-string warning entry makes `"not writable" in w` raise
        # TypeError inside _determine_health_status's try/except.
        health = {"warnings": [123], "disk_space_available": True}
        client._determine_health_status(health)
        assert health["status"] == "error"
