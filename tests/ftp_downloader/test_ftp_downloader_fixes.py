"""FTPDownloader: rate limiting, concurrency, failed listings and reported paths.

HTTP is mocked at ``requests.Session.get`` with a small router that serves
directory listings and ZIP files; nothing reaches the network.
"""

from __future__ import annotations

from collections.abc import Callable
import io
from pathlib import Path
import threading
from unittest.mock import patch
import zipfile

import pytest
import requests

from pyeuropepmc.core.exceptions import FullTextError
from pyeuropepmc.features.literature.ftp_downloader import FTPDownloader

pytestmark = pytest.mark.unit


def _response(
    status_code: int = 200, *, text: str = "", content: bytes = b""
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "OK" if status_code < 400 else "Error"
    response.url = "https://europepmc.org/ftp/pdf/"
    response._content = content or text.encode("utf-8")
    response._content_consumed = True
    return response


def _listing(*pmcids: str) -> str:
    rows = "".join(
        f'<tr><td><a href="PMC{pmcid}.zip">PMC{pmcid}.zip</a></td>'
        "<td>2024-01-01 10:00</td><td>289K</td></tr>"
        for pmcid in pmcids
    )
    return f"<html><body><table>{rows}</table></body></html>"


def _zip_bytes(pmcid: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"PMC{pmcid}.pdf", b"%PDF-1.4 test")
    return buffer.getvalue()


def _router(
    listing: Callable[[str], requests.Response],
    zip_file: Callable[[str], requests.Response] | None = None,
) -> Callable[..., requests.Response]:
    def get(self, url, **kwargs):  # noqa: ARG001 - signature of Session.get
        if url.endswith(".zip"):
            pmcid = url.rsplit("PMC", 1)[-1].removesuffix(".zip")
            return zip_file(url) if zip_file else _response(content=_zip_bytes(pmcid))
        return listing(url)

    return get


@pytest.fixture
def sleeps():
    recorded: list[float] = []
    with patch("time.sleep", side_effect=recorded.append):
        yield recorded


class TestRateLimit:
    def test_requests_are_spaced_by_the_delay(self, sleeps):
        downloader = FTPDownloader(rate_limit_delay=0.7)
        with patch.object(requests.Session, "get", return_value=_response(text="<html/>")):
            downloader._get_ftp_url(downloader.BASE_FTP_URL)
            downloader._get_ftp_url(downloader.BASE_FTP_URL)
            downloader._get_ftp_url(downloader.BASE_FTP_URL)

        assert sleeps == [pytest.approx(0.7, abs=0.05)] * 2

    def test_only_the_remainder_is_waited(self, sleeps):
        downloader = FTPDownloader(rate_limit_delay=1.0)
        with (
            patch.object(requests.Session, "get", return_value=_response(text="<html/>")),
            patch("time.monotonic", side_effect=[50.0, 50.25, 51.0]),
        ):
            downloader._get_ftp_url(downloader.BASE_FTP_URL)
            downloader._get_ftp_url(downloader.BASE_FTP_URL)

        assert sleeps == [pytest.approx(0.75)]

    def test_zero_delay_never_waits(self, sleeps):
        downloader = FTPDownloader(rate_limit_delay=0)
        with patch.object(requests.Session, "get", return_value=_response(text="<html/>")):
            for _ in range(3):
                downloader._get_ftp_url(downloader.BASE_FTP_URL)

        assert sleeps == []


class TestConcurrency:
    PMCIDS = ["11691200", "11691201", "11691202"]

    def test_max_concurrent_downloads_overlap(self, sleeps, tmp_path):
        # Every ZIP request waits here until three are in flight at once; run one
        # after another, the first would time out and the article would fail.
        barrier = threading.Barrier(len(self.PMCIDS), timeout=5)

        def zip_file(url: str) -> requests.Response:
            barrier.wait()
            pmcid = url.rsplit("PMC", 1)[-1].removesuffix(".zip")
            return _response(content=_zip_bytes(pmcid))

        get = _router(lambda url: _response(text=_listing(*self.PMCIDS)), zip_file)
        downloader = FTPDownloader(rate_limit_delay=0)
        with patch.object(requests.Session, "get", get):
            results = downloader.bulk_download_and_extract(self.PMCIDS, tmp_path, max_concurrent=3)

        assert [result["status"] for result in results.values()] == ["success"] * 3

    def test_max_concurrent_one_is_sequential(self, sleeps, tmp_path):
        active = 0
        peak = 0
        lock = threading.Lock()

        def zip_file(url: str) -> requests.Response:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                pmcid = url.rsplit("PMC", 1)[-1].removesuffix(".zip")
                return _response(content=_zip_bytes(pmcid))
            finally:
                with lock:
                    active -= 1

        get = _router(lambda url: _response(text=_listing(*self.PMCIDS)), zip_file)
        downloader = FTPDownloader(rate_limit_delay=0)
        with patch.object(requests.Session, "get", get):
            results = downloader.bulk_download_and_extract(self.PMCIDS, tmp_path, max_concurrent=1)

        assert peak == 1
        assert all(result["status"] == "success" for result in results.values())

    def test_results_keep_the_requested_order_and_repeat_ids_once(self, sleeps, tmp_path):
        get = _router(lambda url: _response(text=_listing(*self.PMCIDS)))
        downloader = FTPDownloader(rate_limit_delay=0)
        requested = ["11691202", "11691200", "11691202", "11691201"]
        with patch.object(requests.Session, "get", get):
            results = downloader.bulk_download_and_extract(requested, tmp_path, max_concurrent=3)

        assert list(results) == ["11691202", "11691200", "11691201"]


class TestFailedListings:
    def test_unreachable_server_is_an_error_not_not_found(self, sleeps, tmp_path):
        def down(self, url, **kwargs):  # noqa: ARG001
            raise requests.ConnectionError("Connection refused")

        downloader = FTPDownloader(rate_limit_delay=0)
        with patch.object(requests.Session, "get", down):
            results = downloader.bulk_download_and_extract(["11691200"], tmp_path)

        result = results["11691200"]
        assert result["status"] == "error"
        assert "Connection refused" in result["error"]
        assert "PMC11691200" in result["error"]

    def test_missing_directories_still_mean_not_found(self, sleeps, tmp_path):
        """A candidate directory that does not exist (404) has been searched."""
        downloader = FTPDownloader(rate_limit_delay=0)
        with patch.object(requests.Session, "get", _router(lambda url: _response(404))):
            results = downloader.bulk_download_and_extract(["11691200"], tmp_path)

        assert results["11691200"] == {"status": "not_found", "error": "PMC ID not found in FTP"}
        assert downloader.last_query_failures == {}

    def test_only_articles_whose_directories_failed_are_errors(self, sleeps, tmp_path):
        def listing(url: str) -> requests.Response:
            # 11691200's directories answer; 5555's own directory is down.
            return _response(503) if url.endswith("PMCxxxx555/") else _response(text=_listing())

        downloader = FTPDownloader(rate_limit_delay=0)
        with patch.object(requests.Session, "get", _router(listing)):
            results = downloader.bulk_download_and_extract(["11691200", "5555"], tmp_path)

        assert results["11691200"]["status"] == "not_found"
        assert results["5555"]["status"] == "error"
        assert "PMCxxxx555" in results["5555"]["error"]

    def test_query_records_failed_and_unsearched_directories(self, sleeps):
        downloader = FTPDownloader(rate_limit_delay=0)
        with patch.object(requests.Session, "get", _router(lambda url: _response(503))):
            found = downloader.query_pmcids_in_ftp(["11691200"], max_directories=2)

        assert found == {"11691200": None}
        failures = downloader.last_query_failures
        assert len([reason for reason in failures.values() if "503" in reason]) == 2
        assert any(reason.startswith("not searched") for reason in failures.values())

    def test_a_404_carries_its_status_code(self, sleeps):
        downloader = FTPDownloader(rate_limit_delay=0)
        with (
            patch.object(requests.Session, "get", return_value=_response(404)),
            pytest.raises(FullTextError) as exc_info,
        ):
            downloader.get_zip_files_in_directory("PMCxxxx1200")

        assert exc_info.value.status_code == 404


class TestReportedZipPath:
    def _download(self, tmp_path: Path, **kwargs):
        downloader = FTPDownloader(rate_limit_delay=0)
        get = _router(lambda url: _response(text=_listing("11691200")))
        with patch("time.sleep"), patch.object(requests.Session, "get", get):
            return downloader.bulk_download_and_extract(["11691200"], tmp_path, **kwargs)[
                "11691200"
            ]

    def test_deleted_zip_is_not_reported(self, tmp_path):
        result = self._download(tmp_path, keep_zips=False)

        assert result["status"] == "success"
        assert result["zip_path"] is None
        assert not (tmp_path / "PMC11691200.zip").exists()
        assert [path.name for path in result["pdf_paths"]] == ["PMC11691200.pdf"]

    def test_kept_zip_is_reported(self, tmp_path):
        result = self._download(tmp_path, keep_zips=True)

        assert result["zip_path"] == tmp_path / "PMC11691200.zip"
        assert result["zip_path"].exists()

    def test_zip_without_extraction_is_reported(self, tmp_path):
        result = self._download(tmp_path, extract_pdfs=False)

        assert result["zip_path"].exists()
        assert "pdf_paths" not in result
