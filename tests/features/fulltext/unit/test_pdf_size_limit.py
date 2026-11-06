"""The ``max_bytes`` limit of the PDF download steps (hermetic: ``requests.get`` is mocked)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
import zipfile

import pytest

from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient
from pyeuropepmc.utils.helpers import atomic_download

PDF = b"%PDF-1.7\n" + b"x" * 5000


def _response(body: bytes, *, declared: int | None = None, content_type="application/pdf"):
    response = MagicMock()
    response.status_code = 200
    headers = {"content-type": content_type}
    if declared is not None:
        headers["content-length"] = str(declared)
    response.headers = headers
    response.iter_content.side_effect = lambda chunk_size=8192: iter(
        [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)]
    )
    response.content = body
    return response


def _leftovers(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


class TestAtomicDownload:
    def test_a_file_within_the_limit_is_kept(self, tmp_path):
        target = tmp_path / "a.pdf"
        with patch("requests.get", return_value=_response(PDF)):
            assert atomic_download("http://x", target, lambda: None, max_bytes=len(PDF))
        assert target.read_bytes() == PDF

    def test_a_declared_size_over_the_limit_is_refused_unread(self, tmp_path):
        response = _response(PDF, declared=10_000)
        with patch("requests.get", return_value=response):
            assert not atomic_download("http://x", tmp_path / "a.pdf", lambda: None, max_bytes=100)
        response.iter_content.assert_not_called()
        assert _leftovers(tmp_path) == []

    def test_a_body_that_outgrows_the_limit_is_abandoned_and_removed(self, tmp_path):
        response = _response(PDF)  # no content-length: the size is only known by reading
        with patch("requests.get", return_value=response):
            assert not atomic_download("http://x", tmp_path / "a.pdf", lambda: None, max_bytes=100)
        assert _leftovers(tmp_path) == []

    def test_no_limit_means_no_check(self, tmp_path):
        with patch("requests.get", return_value=_response(PDF, declared=10**12)):
            assert atomic_download("http://x", tmp_path / "a.pdf", lambda: None)


@pytest.fixture
def client():
    return FullTextClient(enable_cache=False, email="me@example.org")


class TestPdfSteps:
    def test_the_limit_reaches_every_step(self, client, tmp_path):
        calls = {}
        for step in ("_try_pdf_endpoint", "_try_pdf_from_zip", "_try_unpaywall_pdf"):

            def spy(*args, _step=step, **kwargs):
                calls[_step] = (args, kwargs)
                return False

            setattr(client, step, spy)

        assert client.download_pdf_by_pmcid("PMC1", tmp_path / "a.pdf", max_bytes=123) is None

        assert calls["_try_pdf_endpoint"][0][3] == 123
        assert calls["_try_pdf_from_zip"][0][2] == 123
        assert calls["_try_unpaywall_pdf"][1]["max_bytes"] == 123

    def test_zip_member_over_the_limit_is_not_extracted(self, client, tmp_path):
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("paper.pdf", PDF)
        response = _response(archive.getvalue(), content_type="application/zip")
        with patch("requests.get", return_value=response):
            assert not client._try_pdf_from_zip("1", tmp_path / "a.pdf", max_bytes=100)
            assert client._try_pdf_from_zip("1", tmp_path / "a.pdf", max_bytes=100_000)
        assert (tmp_path / "a.pdf").read_bytes() == PDF

    def test_zip_declared_over_the_limit_is_not_read(self, client, tmp_path):
        response = _response(b"PK", declared=10**9, content_type="application/zip")
        with patch("requests.get", return_value=response):
            assert not client._try_pdf_from_zip("1", tmp_path / "a.pdf", max_bytes=100)

    def test_unpaywall_download_over_the_limit_is_abandoned(self, client, tmp_path):
        unpaywall = MagicMock()
        unpaywall.get_best_oa_location.return_value = {"url_for_pdf": "http://x/paper.pdf"}
        target = tmp_path / "a.pdf"
        with (
            patch(
                "pyeuropepmc.features.enrich.sources.unpaywall_client.UnpaywallClient",
                return_value=unpaywall,
            ),
            patch("requests.get", return_value=_response(PDF)),
        ):
            assert not client._try_unpaywall_pdf("1", target, doi="10.1/x", max_bytes=100)
            assert not target.exists()
            assert client._try_unpaywall_pdf("1", target, doi="10.1/x", max_bytes=100_000)
        assert target.read_bytes() == PDF
