"""Coverage for fulltext_client.py's per-session download wrappers and
_handle_pdf_http_error (used by the batch download worker pool)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from pyeuropepmc.core.exceptions import FullTextError
from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient


@pytest.fixture
def client():
    c = FullTextClient(enable_cache=False)
    yield c
    c.close()


class TestDownloadWithSession:
    def test_pdf_swaps_session_and_restores_it(self, client, tmp_path):
        original = client.session
        fake_session = MagicMock()
        with patch.object(
            client, "download_pdf_by_pmcid", return_value=tmp_path / "a.pdf"
        ) as mock_dl:
            result = client._download_pdf_with_session("1", tmp_path / "a.pdf", fake_session)
        assert result == tmp_path / "a.pdf"
        mock_dl.assert_called_once()
        assert client.session is original  # restored

    def test_pdf_restores_session_even_on_exception(self, client):
        original = client.session
        fake_session = MagicMock()
        with patch.object(
            client, "download_pdf_by_pmcid", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError):
                client._download_pdf_with_session("1", MagicMock(), fake_session)
        assert client.session is original

    def test_xml_swaps_session(self, client, tmp_path):
        fake_session = MagicMock()
        with patch.object(
            client, "download_xml_by_pmcid", return_value=tmp_path / "a.xml"
        ) as mock_dl:
            result = client._download_xml_with_session("1", tmp_path / "a.xml", fake_session)
        assert result == tmp_path / "a.xml"
        mock_dl.assert_called_once()

    def test_html_swaps_session(self, client, tmp_path):
        fake_session = MagicMock()
        with patch.object(
            client, "download_html_by_pmcid", return_value=tmp_path / "a.html"
        ) as mock_dl:
            result = client._download_html_with_session("1", tmp_path / "a.html", fake_session)
        assert result == tmp_path / "a.html"
        mock_dl.assert_called_once()


def _http_error(status_code: int) -> requests.HTTPError:
    resp = MagicMock()
    resp.status_code = status_code
    return requests.HTTPError(response=resp)


class TestHandlePdfHttpError:
    def test_404_raises_full003(self, client):
        with pytest.raises(FullTextError) as exc:
            client._handle_pdf_http_error(_http_error(404), "123")
        assert "not found" in str(exc.value).lower()

    def test_403_raises_full008(self, client):
        with pytest.raises(FullTextError) as exc:
            client._handle_pdf_http_error(_http_error(403), "123")
        assert "access denied" in str(exc.value).lower()

    def test_other_status_raises_full005(self, client):
        with pytest.raises(FullTextError) as exc:
            client._handle_pdf_http_error(_http_error(500), "123")
        assert "500" in str(exc.value)
