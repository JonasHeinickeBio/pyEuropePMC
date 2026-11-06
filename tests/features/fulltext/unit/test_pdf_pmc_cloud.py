"""The PMC open-data step of the PDF chain (hermetic: ``requests.get`` is mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient

PDF = b"%PDF-1.7\n" + b"x" * 5000
NS = "http://s3.amazonaws.com/doc/2006-03-01/"


def _listing(*versions: int, pmcid="7029158") -> bytes:
    prefixes = "".join(
        f"<CommonPrefixes><Prefix>PMC{pmcid}.{v}/</Prefix></CommonPrefixes>" for v in versions
    )
    return (
        f'<?xml version="1.0"?><ListBucketResult xmlns="{NS}"><Name>b</Name>'
        f"<Prefix>PMC{pmcid}.</Prefix>{prefixes}</ListBucketResult>"
    ).encode()


def _reply(status=200, body=b"", headers=None):
    response = MagicMock()
    response.status_code = status
    response.content = body
    response.headers = headers or {}
    response.iter_content.side_effect = lambda chunk_size=8192: iter(
        [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)]
    )
    return response


@pytest.fixture
def client():
    return FullTextClient(enable_cache=False)


def _bucket(objects: dict[str, bytes], listing: bytes):
    """A fake ``requests.get``: the listing for the bucket root, objects by key, else 404."""
    asked: list[str] = []

    def get(url, **kwargs):
        asked.append(url)
        if url == FullTextClient.PMC_CLOUD_URL:
            return _reply(200, listing)
        key = url.removeprefix(FullTextClient.PMC_CLOUD_URL + "/")
        return _reply(200, objects[key]) if key in objects else _reply(404)

    get.asked = asked  # type: ignore[attr-defined]
    return get


class TestVersions:
    def test_newest_first_and_only_version_folders(self, client):
        with patch("requests.get", _bucket({}, _listing(1, 2, 10))):
            assert client._pmc_cloud_versions("7029158") == [10, 2, 1]

    def test_another_article_with_the_same_digits_prefix_is_not_taken(self, client):
        # PMC70291580.1/ starts with PMC7029158 but is another article
        listing = _listing(1, pmcid="70291580")
        with patch("requests.get", _bucket({}, listing)):
            assert client._pmc_cloud_versions("7029158") == []

    def test_an_error_status_means_no_versions(self, client):
        with patch("requests.get", return_value=_reply(503)):
            assert client._pmc_cloud_versions("7029158") == []


class TestStep:
    def test_the_newest_version_with_a_pdf_is_saved(self, client, tmp_path):
        objects = {"PMC7029158.1/PMC7029158.1.pdf": PDF + b"old"}
        get = _bucket(objects, _listing(1, 2))  # version 2 has no PDF in this fake
        target = tmp_path / "a.pdf"
        with patch("requests.get", get):
            assert client._try_pdf_from_pmc_cloud("7029158", target)
        assert target.read_bytes() == PDF + b"old"
        assert get.asked[-2:] == [
            f"{FullTextClient.PMC_CLOUD_URL}/PMC7029158.2/PMC7029158.2.pdf",
            f"{FullTextClient.PMC_CLOUD_URL}/PMC7029158.1/PMC7029158.1.pdf",
        ]

    def test_a_file_that_is_not_a_pdf_is_refused(self, client, tmp_path):
        objects = {"PMC7029158.1/PMC7029158.1.pdf": b"<html>" + b"x" * 5000}
        with patch("requests.get", _bucket(objects, _listing(1))):
            assert not client._try_pdf_from_pmc_cloud("7029158", tmp_path / "a.pdf")
        assert list(tmp_path.iterdir()) == []

    def test_the_size_limit_applies(self, client, tmp_path):
        objects = {"PMC7029158.1/PMC7029158.1.pdf": PDF}
        with patch("requests.get", _bucket(objects, _listing(1))):
            assert not client._try_pdf_from_pmc_cloud("7029158", tmp_path / "a.pdf", 100)
            assert client._try_pdf_from_pmc_cloud("7029158", tmp_path / "a.pdf", 100_000)

    def test_a_closed_article_is_simply_not_there(self, client, tmp_path):
        with patch("requests.get", _bucket({}, _listing())):
            assert not client._try_pdf_from_pmc_cloud("7029158", tmp_path / "a.pdf")

    def test_a_network_error_is_not_an_exception(self, client, tmp_path):
        with patch("requests.get", side_effect=OSError("down")):
            assert not client._try_pdf_from_pmc_cloud("7029158", tmp_path / "a.pdf")


class TestChain:
    def test_it_runs_after_the_europe_pmc_endpoints_and_before_the_rest(self, client, tmp_path):
        order = []
        for name in (
            "_try_pdf_endpoint",
            "_try_pdf_from_pmc_cloud",
            "_try_pdf_from_zip",
            "_try_unpaywall_pdf",
        ):

            def step(*args, _n=name, **kwargs):
                order.append(_n)
                return _n == "_try_pdf_from_pmc_cloud" and (Path(args[1]).write_bytes(PDF) or True)

            setattr(client, name, step)

        assert client.download_pdf_by_pmcid("PMC7029158", tmp_path / "a.pdf") == tmp_path / "a.pdf"
        assert order == ["_try_pdf_endpoint", "_try_pdf_endpoint", "_try_pdf_from_pmc_cloud"]
