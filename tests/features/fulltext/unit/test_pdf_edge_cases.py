"""Corners of the PDF chain that the main tests walk past (hermetic)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch
import zipfile

import pytest
import requests

from pyeuropepmc.features.fulltext import oa_pdf
from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient
from pyeuropepmc.features.fulltext.oa_pdf import Link
from pyeuropepmc.features.fulltext.pdf_result import PdfResult
from pyeuropepmc.utils.helpers import DownloadTooLarge, copy_capped

PDF = b"%PDF-1.7\n" + b"x" * 5000


def _reply(status=200, headers=None):
    response = MagicMock()
    response.status_code = status
    response.headers = headers or {}
    return response


class TestIsPublicUrlCorners:
    def test_a_host_that_resolves_to_nothing_is_refused(self):
        with patch("socket.getaddrinfo", return_value=[]):
            assert not oa_pdf.is_public_url("https://example.org/p.pdf")

    @pytest.mark.parametrize(
        ("address", "public"),
        [("::ffff:93.184.216.34", True), ("::ffff:10.0.0.5", False), ("::ffff:127.0.0.1", False)],
    )
    def test_an_ipv4_address_inside_ipv6_is_judged_as_ipv4(self, address, public):
        answer = [(10, 1, 6, "", (address, 443, 0, 0))]
        with patch("socket.getaddrinfo", return_value=answer):
            assert oa_pdf.is_public_url("https://example.org/p.pdf") is public


class TestFetchPdfCorners:
    def test_a_redirect_without_a_location_gives_up(self, tmp_path):
        with (
            patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]),
            patch("requests.get", return_value=_reply(302)) as get,
        ):
            assert not oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf")
        assert get.call_count == 1

    def test_a_file_that_vanished_is_not_a_pdf(self, tmp_path):
        assert oa_pdf._is_pdf_file(tmp_path / "missing.pdf") is False

    def test_a_network_error_on_one_link_moves_on_to_the_next(self, tmp_path):
        def fetch(url, target, max_bytes):
            if "down" in url:
                raise requests.ConnectionError("reset")
            target.write_bytes(PDF)
            return True

        links = {"unpaywall": lambda doi, email: [Link("https://example.org/down")]}
        links["openalex"] = lambda doi, email: [Link("https://example.org/up")]
        with (
            patch.dict(oa_pdf._LINK_SOURCES, links, clear=True),
            patch.object(oa_pdf, "fetch_pdf", fetch),
        ):
            result = oa_pdf.download_pdf_by_doi("10.1/x", tmp_path / "a.pdf")
        assert isinstance(result, PdfResult) and result.source == "openalex"

    def test_a_network_error_on_every_link_means_no_pdf(self, tmp_path):
        def fetch(url, target, max_bytes):
            raise requests.Timeout("slow")

        links = {"unpaywall": lambda doi, email: [Link("https://example.org/a")]}
        with (
            patch.dict(oa_pdf._LINK_SOURCES, links, clear=True),
            patch.object(oa_pdf, "fetch_pdf", fetch),
        ):
            assert oa_pdf.download_pdf_by_doi("10.1/x", tmp_path / "a.pdf") is None


@pytest.fixture
def client():
    return FullTextClient(enable_cache=False)


class TestClientCorners:
    def test_an_unreachable_bucket_means_no_metadata(self, client):
        with patch("requests.get", side_effect=requests.ConnectionError("down")):
            assert client._pmc_cloud_metadata("1", 1) == {}

    def test_metadata_that_is_not_json_is_ignored(self, client):
        response = MagicMock(status_code=200)
        response.json.side_effect = ValueError("no json")
        with patch("requests.get", return_value=response):
            assert client._pmc_cloud_metadata("1", 1) == {}

    def test_a_pdf_declared_over_the_limit_is_refused_before_reading_it(self, client, tmp_path):
        response = MagicMock()
        response.headers = {"content-length": "999999"}
        assert client._save_pdf_stream(response, tmp_path / "a.pdf", 1000) is False
        response.close.assert_called_once()
        response.iter_content.assert_not_called()

    def test_a_zip_member_over_the_limit_is_refused(self, client, tmp_path):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("PMC1.pdf", PDF)
        buffer.seek(0)
        with pytest.raises(DownloadTooLarge):
            client._extract_pdf_from_zip(buffer, "1", tmp_path / "a.pdf", 100)
        assert not (tmp_path / "a.pdf").exists()


class TestProvenanceRecordCorners:
    def test_without_a_cache_nothing_is_recorded(self, client, tmp_path):
        (tmp_path / "a.pdf").write_bytes(PDF)
        client._write_pdf_provenance("1", PdfResult(tmp_path / "a.pdf", "unpaywall"))
        assert client._pdf_provenance_path("1") is None

    def test_a_record_that_cannot_be_written_does_not_fail_the_download(self, tmp_path):
        cached = FullTextClient(enable_cache=True, cache_dir=tmp_path / "cache")
        (tmp_path / "a.pdf").write_bytes(PDF)
        with patch.object(FullTextClient, "_sha256_of", side_effect=OSError("gone")):
            cached._write_pdf_provenance("1", PdfResult(tmp_path / "a.pdf", "unpaywall"))
        assert not (tmp_path / "cache" / "pdf-provenance" / "PMC1.json").exists()


class TestKeepAliveAndRepeatChallenge:
    def test_empty_chunks_are_skipped_when_copying(self):
        sink = io.BytesIO()
        copy_capped([b"ab", b"", b"cd"], sink, 10)
        assert sink.getvalue() == b"abcd"

    def test_a_second_challenge_extends_the_cooldown_quietly(self, caplog):
        challenge = MagicMock(status_code=403, headers={"cf-mitigated": "challenge"})
        FullTextClient._note_challenge("europepmc.org", challenge)
        with caplog.at_level("WARNING"):
            caplog.clear()
            FullTextClient._note_challenge("europepmc.org", challenge)
        assert "browser check" not in caplog.text
        assert FullTextClient._in_challenge_cooldown("europepmc.org")
