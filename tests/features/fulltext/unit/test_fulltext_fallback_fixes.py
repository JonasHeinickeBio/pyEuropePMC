"""Unit tests for the full-text download chain's fallback and error handling.

Every HTTP request is mocked at the requests layer (``requests.Session.get``
and the module-level ``requests.get``), so the tests exercise the real
``BaseAPIClient._get`` error translation rather than a stubbed ``_get``.
"""

from __future__ import annotations

import gzip
from io import BytesIO
from pathlib import Path
import typing
from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, FullTextError
from pyeuropepmc.features.fulltext.fulltext_client import (
    FullTextClient,
    ProgressInfo,
    _extract_article_xml,
)
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit

MODULE = "pyeuropepmc.features.fulltext.fulltext_client"


def _response(status_code: int = 200, text: str = "", content: bytes = b"") -> requests.Response:
    """A real ``requests.Response`` with the body already loaded."""
    response = requests.Response()
    response.status_code = status_code
    response.reason = "OK" if status_code < 400 else "Error"
    response.url = "https://example.org/"
    response._content = content or text.encode("utf-8")
    response._content_consumed = True
    return response


def _not_found(*_args, **_kwargs) -> requests.Response:
    return _response(404)


def _article(pmcid: str, title: str, *, id_type: str = "pmcid", extra: str = "") -> str:
    return (
        '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
        f'<article-id pub-id-type="{id_type}">{pmcid}</article-id>'
        f"<title-group><article-title>{title}</article-title></title-group>"
        f"</article-meta></front><body><p>{title} body</p>{extra}</body></article>"
    )


def _article_set(*articles: str) -> bytes:
    xml = '<?xml version="1.0" encoding="UTF-8"?><pmc-articleset>' + "".join(articles)
    return (xml + "</pmc-articleset>").encode("utf-8")


@pytest.fixture(autouse=True)
def no_sleep():
    """Keep the rate-limit delay and any retry backoff out of the clock."""
    with patch("time.sleep"):
        yield


@pytest.fixture
def client(monkeypatch):
    # email=None falls back to these variables, which a .env file loaded by
    # another test (pyeuropepmc.cli calls load_env() on import) may have set.
    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
    monkeypatch.delenv("CROSSREF_EMAIL", raising=False)
    instance = FullTextClient(rate_limit_delay=0, enable_cache=False, email=None)
    assert instance.email is None
    yield instance
    instance.close()


@pytest.fixture
def client_with_email():
    instance = FullTextClient(rate_limit_delay=0, enable_cache=False, email="me@example.org")
    yield instance
    instance.close()


# ---------------------------------------------------------------------------
# fulltextRepo
# ---------------------------------------------------------------------------


class TestFulltextRepoUrl:
    def test_requests_the_endpoint_under_the_api_base_url_once(self, client, tmp_path):
        with patch.object(client.session, "get", side_effect=_not_found) as mock_get:
            assert client._try_fulltext_repo("3257301", tmp_path / "out.xml") is False

        url = mock_get.call_args.args[0]
        assert url == f"{client.BASE_URL}PMC3257301/fulltextRepo"
        assert url.count("https://") == 1

    def test_saves_a_jats_body(self, client, tmp_path):
        body = _article("PMC3257301", "From the repo")
        output = tmp_path / "out.xml"
        with patch.object(client.session, "get", return_value=_response(200, body)):
            assert client._try_fulltext_repo("3257301", output) is True

        assert "From the repo" in output.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Unpaywall steps
# ---------------------------------------------------------------------------


class TestUnpaywallStepsWithoutEmail:
    @pytest.mark.parametrize("step", ["_try_unpaywall_xml", "_try_unpaywall_pdf"])
    def test_no_doi_lookup_without_an_email(self, client, tmp_path, step):
        with (
            patch.object(requests.Session, "get", side_effect=_not_found) as session_get,
            patch.object(client, "_lookup_doi_for_pmcid") as lookup,
        ):
            assert getattr(client, step)("3257301", tmp_path / "out") is False

        lookup.assert_not_called()
        session_get.assert_not_called()


class TestUnpaywallStepsWithEmail:
    @pytest.mark.parametrize("step", ["_try_unpaywall_xml", "_try_unpaywall_pdf"])
    def test_failed_doi_lookup_is_not_found_not_an_error(self, client_with_email, tmp_path, step):
        """The Europe PMC lookup answering 404 must not escape as APIClientError."""
        with patch.object(requests.Session, "get", side_effect=_not_found):
            assert getattr(client_with_email, step)("3257301", tmp_path / "out") is False

    @pytest.mark.parametrize("step", ["_try_unpaywall_xml", "_try_unpaywall_pdf"])
    def test_api_client_error_from_unpaywall_is_not_found(self, client_with_email, tmp_path, step):
        error = APIClientError(ErrorCodes.HTTP404, {"url": "u", "status_code": 404})
        with patch(
            "pyeuropepmc.features.enrich.sources.unpaywall_client.UnpaywallClient"
            ".get_best_oa_location",
            side_effect=error,
        ):
            assert (
                getattr(client_with_email, step)("3257301", tmp_path / "out", doi="10.1/x")
                is False
            )

    def test_given_doi_is_used_without_a_lookup(self, client_with_email, tmp_path):
        with (
            patch.object(client_with_email, "_lookup_doi_for_pmcid") as lookup,
            patch(
                "pyeuropepmc.features.enrich.sources.unpaywall_client.UnpaywallClient"
                ".get_best_oa_location",
                return_value=None,
            ) as best_location,
        ):
            assert (
                client_with_email._try_unpaywall_xml("1", tmp_path / "o.xml", doi="10.1/x")
                is False
            )

        lookup.assert_not_called()
        best_location.assert_called_once_with("10.1/x")


class TestDownloadChainWhenEverythingIsMissing:
    """Every source answers 404: the documented outcome, not APIClientError."""

    @pytest.fixture(autouse=True)
    def all_requests_404(self):
        with (
            patch.object(requests.Session, "get", side_effect=_not_found),
            patch(f"{MODULE}.requests.get", side_effect=_not_found),
        ):
            yield

    @pytest.mark.parametrize("fixture_name", ["client", "client_with_email"])
    def test_xml_raises_full_text_error(self, request, tmp_path, fixture_name):
        client = request.getfixturevalue(fixture_name)
        with pytest.raises(FullTextError) as exc_info:
            client.download_xml_by_pmcid("PMC3257301", tmp_path / "a.xml", extra_strategies=False)

        assert exc_info.value.error_code == ErrorCodes.FULL003

    @pytest.mark.parametrize("fixture_name", ["client", "client_with_email"])
    def test_pdf_returns_none(self, request, tmp_path, fixture_name):
        client = request.getfixturevalue(fixture_name)
        assert client.download_pdf_by_pmcid("PMC3257301", tmp_path / "a.pdf") is None

    def test_xml_passes_the_given_doi_to_unpaywall(self, client_with_email, tmp_path):
        with (
            patch.object(client_with_email, "_lookup_doi_for_pmcid") as lookup,
            patch.object(client_with_email, "_try_unpaywall_xml", return_value=False) as step,
            pytest.raises(FullTextError),
        ):
            client_with_email.download_xml_by_pmcid(
                "3257301", tmp_path / "a.xml", doi="10.1/x", extra_strategies=False
            )

        lookup.assert_not_called()
        assert step.call_args.kwargs["doi"] == "10.1/x"


def test_download_xml_methods_are_annotated_to_return_a_path():
    """Both raise FullTextError when nothing is found; neither returns None."""
    for method in (
        FullTextClient.download_xml_by_pmcid,
        FullTextClient.download_xml_by_pmcid_bulk,
    ):
        assert typing.get_type_hints(method)["return"] is Path


# ---------------------------------------------------------------------------
# get_fulltext_content
# ---------------------------------------------------------------------------


class TestGetFulltextContentErrors:
    @pytest.mark.parametrize(
        ("status_code", "error_code"),
        [
            (404, ErrorCodes.FULL003),
            (403, ErrorCodes.FULL008),
            (500, ErrorCodes.FULL005),
            (503, ErrorCodes.FULL005),
        ],
    )
    def test_http_error_becomes_full_text_error(self, client, status_code, error_code):
        with (
            patch.object(client.session, "get", return_value=_response(status_code)),
            pytest.raises(FullTextError) as exc_info,
        ):
            client.get_fulltext_content("PMC3257301")

        assert exc_info.value.error_code == error_code
        assert isinstance(exc_info.value.__cause__, APIClientError)

    def test_network_failure_becomes_full_text_error(self, client):
        with (
            patch.object(client.session, "get", side_effect=requests.ConnectionError("down")),
            pytest.raises(FullTextError) as exc_info,
        ):
            client.get_fulltext_content("PMC3257301", format_type="html")

        assert exc_info.value.error_code == ErrorCodes.FULL005

    def test_closed_client_error_is_not_disguised(self, client):
        client.close()
        with pytest.raises(APIClientError) as exc_info:
            client.get_fulltext_content("PMC3257301")

        assert exc_info.value.error_code == ErrorCodes.FULL007

    def test_success_returns_the_body(self, client):
        with patch.object(client.session, "get", return_value=_response(200, "<article/>")):
            assert client.get_fulltext_content("3257301") == "<article/>"


# ---------------------------------------------------------------------------
# Bulk archives
# ---------------------------------------------------------------------------


class TestBulkArchiveExtraction:
    def _download(self, client, tmp_path, archive: bytes, pmcid: str = "3257301"):
        output = tmp_path / f"PMC{pmcid}.xml"
        with patch(
            f"{MODULE}.requests.get", return_value=_response(200, content=gzip.compress(archive))
        ):
            ok = client._try_bulk_xml_download(pmcid, output)
        return ok, output

    def test_saves_only_the_requested_article(self, client, tmp_path):
        archive = _article_set(
            _article("PMC3257300", "Before"),
            _article("PMC3257301", "Wanted"),
            _article("PMC3257302", "After"),
        )
        ok, output = self._download(client, tmp_path, archive)

        assert ok is True
        text = output.read_text(encoding="utf-8")
        assert "Wanted" in text
        assert "Before" not in text
        assert "After" not in text
        assert "pmc-articleset" not in text

    @pytest.mark.parametrize(
        ("id_type", "value"),
        [
            ("pmcid", "3257301"),
            ("pmc", "3257301"),
            ("pmc", "PMC3257301"),
            ("pmcid-ver", "PMC3257301.2"),
        ],
    )
    def test_matches_every_form_of_the_pmc_id(self, client, tmp_path, id_type, value):
        archive = _article_set(_article(value, "Wanted", id_type=id_type))
        ok, _ = self._download(client, tmp_path, archive)
        assert ok is True

    @pytest.mark.parametrize("id_type", ["pmcaid", "pmcaiid", "publisher-id"])
    def test_ignores_ids_that_are_not_the_pmc_id(self, client, tmp_path, id_type):
        archive = _article_set(_article("3257301", "Other", id_type=id_type))
        ok, output = self._download(client, tmp_path, archive)
        assert ok is False
        assert not output.exists()

    def test_the_id_must_be_the_whole_number(self, client, tmp_path):
        archive = _article_set(_article("PMC32573010", "Longer id"))
        ok, _ = self._download(client, tmp_path, archive)
        assert ok is False

    def test_a_sub_article_id_does_not_select_its_parent(self, client, tmp_path):
        sub_article = (
            "<sub-article><front-stub>"
            '<article-id pub-id-type="pmcid">PMC3257301</article-id>'
            "</front-stub></sub-article>"
        )
        archive = _article_set(_article("PMC1111111", "Parent", extra=sub_article))
        ok, _ = self._download(client, tmp_path, archive)
        assert ok is False

    def test_a_mention_in_the_text_does_not_match(self, client, tmp_path):
        """The old check only looked for the string 'PMC3257301' anywhere."""
        archive = _article_set(_article("PMC1111111", "Cites PMC3257301 in passing"))
        ok, _ = self._download(client, tmp_path, archive)
        assert ok is False

    def test_malformed_archive_is_not_found(self, client, tmp_path):
        ok, output = self._download(client, tmp_path, b"<pmc-articleset><article>")
        assert ok is False
        assert not output.exists()

    def test_entity_declarations_are_refused(self, client, tmp_path):
        archive = (
            b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY boom "x">]>'
            b"<pmc-articleset>&boom;</pmc-articleset>"
        )
        ok, _ = self._download(client, tmp_path, archive)
        assert ok is False

    def test_extracted_article_parses_with_namespaces_intact(self, client, tmp_path):
        figure = (
            '<fig id="f1"><label>Figure 1</label><caption><p>A figure</p></caption>'
            '<graphic xlink:href="fig1.jpg"/></fig>'
        )
        archive = _article_set(_article("PMC3257301", "Namespaced", extra=figure))
        ok, output = self._download(client, tmp_path, archive)
        assert ok is True

        parser = FullTextXMLParser(output.read_text(encoding="utf-8"))
        assert parser.extract_metadata()["title"] == "Namespaced"
        graphics = parser.root.findall(".//graphic")
        assert graphics[0].get("{http://www.w3.org/1999/xlink}href") == "fig1.jpg"

    def test_single_article_document(self):
        stream = BytesIO(_article("PMC3257301", "Alone").encode("utf-8"))
        xml = _extract_article_xml(stream, "3257301")
        assert xml is not None
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')


# ---------------------------------------------------------------------------
# Progress reporting
# ---------------------------------------------------------------------------


class TestProgressText:
    @pytest.mark.parametrize("pmcid", ["PMC3257301", "3257301", "pmc3257301"])
    def test_batch_status_has_one_pmc_prefix(self, client, tmp_path, pmcid):
        statuses = []
        with patch.object(client, "_process_batch_download_item", return_value=None):
            client.download_fulltext_batch(
                [pmcid],
                format_type="xml",
                output_dir=tmp_path,
                progress_callback=lambda progress: statuses.append(progress.status),
                progress_update_interval=0,
            )

        downloading = [status for status in statuses if status.startswith("downloading")]
        assert downloading
        assert "PMCPMC" not in downloading[0].upper()
        assert downloading[0].upper() == "DOWNLOADING PMC3257301"

    def test_error_status_has_one_pmc_prefix(self, client, tmp_path):
        progress = ProgressInfo(total_items=1)
        error = FullTextError(ErrorCodes.FULL003, pmcid="3257301")

        client._handle_batch_download_error(error, "PMC3257301", "xml", progress, skip_errors=True)

        assert progress.status.startswith("error PMC3257301: ")

    def test_str_without_a_current_item(self):
        text = str(ProgressInfo(total_items=3))
        assert "None" not in text
        assert text == "Progress: 0/3 (0.0%) - Status: starting"

    def test_str_with_a_prefixed_current_item(self):
        text = str(ProgressInfo(total_items=3, current_item=1, current_pmcid="PMC5"))
        assert "Current: PMC5 -" in text
