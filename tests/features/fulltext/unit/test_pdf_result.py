"""Licence normalization and the provenance the PDF steps report (hermetic)."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch
import zipfile

import pytest

from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient
from pyeuropepmc.features.fulltext.pdf_result import PdfResult, normalize_license

PDF = b"%PDF-1.7\n" + b"x" * 5000


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("CC BY-NC-ND", "cc-by-nc-nd"),  # PMC
        ("cc by-nc-nd", "cc-by-nc-nd"),  # Europe PMC
        ("cc-by-nc-nd", "cc-by-nc-nd"),  # Unpaywall, OpenAlex
        ("CCBYNCND", "cc-by-nc-nd"),  # Semantic Scholar
        ("CCBY", "cc-by"),
        ("CC BY", "cc-by"),
        ("cc by 4.0", "cc-by-4.0"),
        ("cc-by-sa-3.0", "cc-by-sa-3.0"),
        ("CC0", "cc0"),
        ("cc0", "cc0"),
        ("other-oa", "other-oa"),
        ("Elsevier TDM", "elsevier-tdm"),
        ("  Publisher   Specific ", "publisher-specific"),
        ("", None),
        ("   ", None),
        (None, None),
        (5, None),
    ],
)
def test_normalize_license(given, expected):
    assert normalize_license(given) == expected


def test_pdf_result_defaults_say_nothing_and_are_immutable(tmp_path):
    result = PdfResult(tmp_path / "a.pdf", "cache")
    assert (result.url, result.license, result.md5_verified) == (None, None, False)
    with pytest.raises(AttributeError):
        result.source = "x"  # type: ignore[misc]


@pytest.fixture
def client():
    return FullTextClient(enable_cache=False, email="me@example.org")


def _reply(body=b"", status=200, headers=None):
    response = MagicMock()
    response.status_code = status
    response.headers = {"content-type": "application/pdf", **(headers or {})}
    response.iter_content.side_effect = lambda chunk_size=8192: iter([body])
    return response


class TestChainCarriesProvenance:
    @staticmethod
    def _spy_all(client, results):
        """Each step: fill its own provenance, then succeed or not as ``results`` says."""

        def make(name, where):
            def step(*args, **kwargs):
                provenance = kwargs.get("provenance")
                if provenance is None:
                    provenance = args[where]
                provenance.update(url=f"https://example.org/{name}", license="CC BY")
                return results[name]

            return step

        client._try_pdf_endpoint = make("endpoint", 4)
        client._try_pdf_from_pmc_cloud = make("cloud", 3)
        client._try_pdf_from_zip = make("zip", 3)
        client._try_unpaywall_pdf = make("unpaywall", 99)

    def test_the_winning_steps_url_and_licence_reach_the_result(self, client, tmp_path):
        self._spy_all(client, {"endpoint": False, "cloud": True, "zip": False, "unpaywall": False})
        result = client.download_pdf_with_provenance("PMC1", tmp_path / "a.pdf")
        assert result.source == "pmc_open_data"
        assert (result.url, result.license) == ("https://example.org/cloud", "cc-by")

    def test_a_failed_steps_leftovers_do_not_leak_into_the_next(self, client, tmp_path):
        def failing_endpoint(*args, **kwargs):
            args[4].update(url="https://example.org/failed", license="cc-by-nc", md5_verified=True)
            return False

        self._spy_all(client, {"endpoint": False, "cloud": False, "zip": True, "unpaywall": False})
        client._try_pdf_endpoint = failing_endpoint

        def zip_step(*args, **kwargs):
            args[3].update(url="https://example.org/zip")
            return True

        client._try_pdf_from_zip = zip_step
        result = client.download_pdf_with_provenance("PMC1", tmp_path / "a.pdf")
        assert result.source == "europepmc_ftp_zip"
        assert (result.url, result.license, result.md5_verified) == (
            "https://example.org/zip",
            None,
            False,
        )

    def test_a_cache_hit_has_no_url_and_no_licence(self, client, tmp_path):
        target = tmp_path / "a.pdf"
        target.write_bytes(PDF)
        with patch.object(client, "_check_cache_for_file", return_value=target):
            result = client.download_pdf_with_provenance("PMC1", target)
        assert result == PdfResult(target, "cache", from_cache=True)

    def test_by_pmcid_still_returns_just_the_path(self, client, tmp_path):
        self._spy_all(client, {"endpoint": True, "cloud": False, "zip": False, "unpaywall": False})
        assert client.download_pdf_by_pmcid("PMC1", tmp_path / "a.pdf") == tmp_path / "a.pdf"


class TestEachStepReportsItsUrl:
    def test_the_europe_pmc_endpoint(self, client, tmp_path):
        provenance: dict = {}
        with patch("requests.get", return_value=_reply(PDF)):
            assert client._try_pdf_endpoint(
                "https://europepmc.org/a", tmp_path / "a.pdf", "x", None, provenance
            )
        assert provenance == {"url": "https://europepmc.org/a"}

    def test_the_zip(self, client, tmp_path):
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("paper.pdf", PDF)
        provenance: dict = {}
        with patch("requests.get", return_value=_reply(archive.getvalue())):
            assert client._try_pdf_from_zip("3525259", tmp_path / "a.pdf", None, provenance)
        assert provenance == {
            "url": "https://ftp.ebi.ac.uk/pub/databases/pmc/pdf/OA/PMCxxxx353/PMC3525259.zip"
        }

    def test_unpaywall_with_the_locations_licence(self, client, tmp_path):
        unpaywall = MagicMock()
        unpaywall.get_best_oa_location.return_value = {
            "url_for_pdf": "https://example.org/paper.pdf",
            "license": "cc-by",
        }
        provenance: dict = {}
        with (
            patch(
                "pyeuropepmc.features.enrich.sources.unpaywall_client.UnpaywallClient",
                return_value=unpaywall,
            ),
            patch("requests.get", return_value=_reply(PDF)),
        ):
            assert client._try_unpaywall_pdf(
                "1", tmp_path / "a.pdf", doi="10.1/x", provenance=provenance
            )
        assert provenance == {"url": "https://example.org/paper.pdf", "license": "cc-by"}


class TestCachedFilesKeepTheirOrigin:
    @pytest.fixture
    def cached_client(self, tmp_path):
        return FullTextClient(enable_cache=True, cache_dir=tmp_path / "cache")

    @staticmethod
    def _download_once(client, target):
        def cloud(normalized_pmcid, output_path, max_bytes=None, provenance=None):
            output_path.write_bytes(PDF)
            provenance.update(
                url="https://example.org/PMC1.pdf", license="CC BY", md5_verified=True
            )
            return True

        client._try_pdf_endpoint = lambda *a, **k: False
        client._try_pdf_from_pmc_cloud = cloud
        return client.download_pdf_with_provenance("PMC1", target)

    def test_the_second_call_is_a_cache_hit_that_remembers_where_it_came_from(
        self, cached_client, tmp_path
    ):
        first = self._download_once(cached_client, tmp_path / "one" / "a.pdf")
        assert first.source == "pmc_open_data" and not first.from_cache

        second = cached_client.download_pdf_with_provenance("PMC1", tmp_path / "two" / "a.pdf")

        assert second.from_cache
        assert (second.source, second.url, second.license, second.md5_verified) == (
            "pmc_open_data",
            "https://example.org/PMC1.pdf",
            "cc-by",
            True,
        )

    def test_a_cache_file_that_is_not_the_one_recorded_is_just_cache(
        self, cached_client, tmp_path
    ):
        self._download_once(cached_client, tmp_path / "one" / "a.pdf")
        (cached_client.cache_dir / "pdf" / "PMC1.pdf").write_bytes(PDF + b"changed")

        second = cached_client.download_pdf_with_provenance("PMC1", tmp_path / "two" / "a.pdf")

        assert second == PdfResult(tmp_path / "two" / "a.pdf", "cache", from_cache=True)

    def test_a_cache_file_with_no_record_is_just_cache(self, cached_client, tmp_path):
        cache_file = cached_client.cache_dir / "pdf" / "PMC1.pdf"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(PDF)

        result = cached_client.download_pdf_with_provenance("PMC1", tmp_path / "a.pdf")

        assert (result.source, result.url, result.from_cache) == ("cache", None, True)

    def test_a_damaged_record_is_ignored(self, cached_client, tmp_path):
        self._download_once(cached_client, tmp_path / "one" / "a.pdf")
        record = cached_client.cache_dir / "pdf-provenance" / "PMC1.json"
        record.write_text("{not json")

        result = cached_client.download_pdf_with_provenance("PMC1", tmp_path / "two" / "a.pdf")

        assert (result.source, result.from_cache) == ("cache", True)

    def test_no_record_is_written_when_the_cache_is_off(self, tmp_path):
        client = FullTextClient(enable_cache=False)
        self._download_once(client, tmp_path / "a.pdf")
        assert not (tmp_path / "pdf-provenance").exists()
