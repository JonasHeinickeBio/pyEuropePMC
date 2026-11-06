"""The ``max_bytes`` limit of the PDF download steps (hermetic: ``requests.get`` is mocked)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
import zipfile

import pytest
import requests

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

    @pytest.mark.skipif(not Path("/proc/self/fd").exists(), reason="needs /proc/self/fd")
    @pytest.mark.parametrize(
        "failure", ["status", "content_type", "declared", "raises", "invalid"]
    )
    def test_no_descriptor_is_left_open_on_a_failed_download(self, tmp_path, failure):
        def open_fds():
            return len(list(Path("/proc/self/fd").iterdir()))

        response = _response(PDF, declared=10_000 if failure == "declared" else None)
        if failure == "status":
            response.status_code = 403
        kwargs = {"content_type_check": "text/html"} if failure == "content_type" else {}
        kwargs["max_bytes"] = 100 if failure == "declared" else None
        patch_args = (
            {"side_effect": OSError("down")} if failure == "raises" else {"return_value": response}
        )
        validator = (lambda _p: False) if failure == "invalid" else None
        before = open_fds()
        for _ in range(5):
            with patch("requests.get", **patch_args):
                assert not atomic_download(
                    "http://x", tmp_path / "a.pdf", lambda: None, validator=validator, **kwargs
                )
        assert open_fds() == before
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
        for step in (
            "_try_pdf_endpoint",
            "_try_pdf_from_pmc_cloud",
            "_try_pdf_from_zip",
            "_try_unpaywall_pdf",
        ):

            def spy(*args, _step=step, **kwargs):
                calls[_step] = (args, kwargs)
                return False

            setattr(client, step, spy)

        assert client.download_pdf_by_pmcid("PMC1", tmp_path / "a.pdf", max_bytes=123) is None

        assert calls["_try_pdf_endpoint"][0][3] == 123
        assert calls["_try_pdf_from_pmc_cloud"][0][2] == 123
        assert calls["_try_pdf_from_zip"][0][2] == 123
        assert calls["_try_unpaywall_pdf"][1]["max_bytes"] == 123

    def test_zip_member_over_the_limit_is_not_extracted(self, client, tmp_path):
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("paper.pdf", PDF)
        response = _response(archive.getvalue(), content_type="application/zip")
        with patch("requests.get", return_value=response):
            assert not client._try_pdf_from_zip("1", tmp_path / "a.pdf", max_bytes=100)
            assert _leftovers(tmp_path) == []
        with patch("requests.get", return_value=_response(archive.getvalue())):
            assert client._try_pdf_from_zip("1", tmp_path / "a.pdf", max_bytes=100_000)
        assert (tmp_path / "a.pdf").read_bytes() == PDF

    def test_zip_declared_over_the_limit_is_not_read(self, client, tmp_path):
        response = _response(b"PK", declared=10**9, content_type="application/zip")
        with patch("requests.get", return_value=response):
            assert not client._try_pdf_from_zip("1", tmp_path / "a.pdf", max_bytes=100)
        response.iter_content.assert_not_called()

    def test_zip_that_outgrows_the_limit_while_streaming_is_abandoned(self, client, tmp_path):
        response = _response(b"PK" + b"0" * 10_000)  # no content-length
        with patch("requests.get", return_value=response):
            assert not client._try_pdf_from_zip("1", tmp_path / "a.pdf", max_bytes=1000)
        assert _leftovers(tmp_path) == []

    def test_zip_member_larger_than_its_header_says_is_cut_off(self, client, tmp_path):
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("paper.pdf", PDF)
        # lie about the uncompressed size so only counting the bytes read can catch it
        real_getinfo = zipfile.ZipFile.getinfo

        def getinfo(self, name):
            member = real_getinfo(self, name)
            member.file_size = 10
            return member

        with (
            patch("requests.get", return_value=_response(archive.getvalue())),
            patch.object(zipfile.ZipFile, "getinfo", getinfo),
        ):
            assert not client._try_pdf_from_zip("1", tmp_path / "a.pdf", max_bytes=1000)
        assert _leftovers(tmp_path) == []

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


class TestPdfZipUrl:
    @pytest.mark.parametrize(
        ("pmcid", "folder"),
        [
            ("3525259", "PMCxxxx353"),
            ("7029158", "PMCxxxx703"),
            ("25774", "PMCxxxx003"),
            ("10000", "PMCxxxx001"),
            ("10001", "PMCxxxx002"),
            ("13710763", "PMCxxxx1372"),
        ],
    )
    def test_folder_is_the_id_in_blocks_of_10000(self, client, tmp_path, pmcid, folder):
        response = MagicMock()
        response.status_code = 404
        with patch("requests.get", return_value=response) as get:
            assert not client._try_pdf_from_zip(pmcid, tmp_path / "a.pdf")
        assert get.call_args[0][0] == (
            f"https://ftp.ebi.ac.uk/pub/databases/pmc/pdf/OA/{folder}/PMC{pmcid}.zip"
        )
        response.close.assert_called()

    def test_a_dropped_connection_is_retried_once(self, client, tmp_path):
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("paper.pdf", PDF)
        with patch(
            "requests.get",
            side_effect=[requests.ConnectionError("reset"), _response(archive.getvalue())],
        ) as get:
            assert client._try_pdf_from_zip("1", tmp_path / "a.pdf")
        assert get.call_count == 2

    def test_a_second_failure_gives_up(self, client, tmp_path):
        with patch("requests.get", side_effect=requests.Timeout("slow")) as get:
            assert not client._try_pdf_from_zip("1", tmp_path / "a.pdf")
        assert get.call_count == 2


class TestChainBookkeeping:
    """Which step supplied the file, which steps an open_access=False paper skips, and the
    cooldown after a browser check."""

    @staticmethod
    def _steps(client, *, succeed=None):
        """Replace every step by a spy that answers True only for ``succeed``."""
        asked = []
        for name in (
            "_try_pdf_endpoint",
            "_try_pdf_from_pmc_cloud",
            "_try_pdf_from_zip",
            "_try_unpaywall_pdf",
        ):

            def spy(*args, _name=name, **kwargs):
                asked.append(_name)
                return _name == succeed

            setattr(client, name, spy)
        return asked

    @pytest.mark.parametrize(
        ("winner", "source"),
        [
            ("_try_pdf_from_pmc_cloud", "pmc_open_data"),
            ("_try_pdf_from_zip", "europepmc_ftp_zip"),
            ("_try_unpaywall_pdf", "unpaywall"),
        ],
    )
    def test_the_winning_step_is_named(self, client, tmp_path, winner, source):
        self._steps(client, succeed=winner)
        result = client.download_pdf_with_provenance("PMC1", tmp_path / "a.pdf")
        assert (result.path, result.source) == (tmp_path / "a.pdf", source)

    def test_every_step_failing_gives_nothing(self, client, tmp_path):
        self._steps(client)
        assert client.download_pdf_with_provenance("PMC1", tmp_path / "a.pdf") is None

    def test_download_pdf_by_pmcid_still_returns_just_the_path(self, client, tmp_path):
        self._steps(client, succeed="_try_unpaywall_pdf")
        assert client.download_pdf_by_pmcid("PMC1", tmp_path / "a.pdf") == tmp_path / "a.pdf"

    def test_a_closed_article_skips_the_two_open_access_only_steps(self, client, tmp_path):
        asked = self._steps(client, succeed="_try_unpaywall_pdf")
        client.download_pdf_with_provenance("PMC1", tmp_path / "a.pdf", open_access=False)
        assert "_try_pdf_from_pmc_cloud" not in asked
        assert "_try_pdf_from_zip" not in asked
        assert asked[-1] == "_try_unpaywall_pdf"

    @pytest.mark.parametrize("flag", [None, True])
    def test_otherwise_every_step_runs(self, client, tmp_path, flag):
        asked = self._steps(client)
        client.download_pdf_with_provenance("PMC1", tmp_path / "a.pdf", open_access=flag)
        assert "_try_pdf_from_pmc_cloud" in asked and "_try_pdf_from_zip" in asked


class TestChallengeCooldown:
    @pytest.fixture(autouse=True)
    def _clean(self):
        FullTextClient._challenged_hosts.clear()
        yield
        FullTextClient._challenged_hosts.clear()

    @staticmethod
    def _challenge():
        response = _response(b"<html>Just a moment</html>", content_type="text/html")
        response.status_code = 403
        response.headers["cf-mitigated"] = "challenge"
        return response

    def test_a_browser_check_silences_the_host_for_the_cooldown(self, client, tmp_path):
        with patch("requests.get", return_value=self._challenge()) as get:
            assert not client._try_pdf_endpoint("https://europepmc.org/a", tmp_path / "a.pdf", "x")
            assert not client._try_pdf_endpoint("https://europepmc.org/b", tmp_path / "b.pdf", "x")
            assert not client._try_pdf_endpoint("https://europepmc.org/c", tmp_path / "c.pdf", "x")
        assert get.call_count == 1  # the later papers do not knock again

    def test_other_hosts_are_not_affected(self, client, tmp_path):
        with patch("requests.get", return_value=self._challenge()):
            client._try_pdf_endpoint("https://europepmc.org/a", tmp_path / "a.pdf", "x")
        with patch("requests.get", return_value=_response(PDF)) as get:
            assert client._try_pdf_endpoint("https://example.org/p.pdf", tmp_path / "b.pdf", "x")
        assert get.call_count == 1

    def test_a_plain_403_is_not_a_browser_check(self, client, tmp_path):
        refused = _response(b"no", content_type="text/html")
        refused.status_code = 403
        with patch("requests.get", return_value=refused) as get:
            client._try_pdf_endpoint("https://europepmc.org/a", tmp_path / "a.pdf", "x")
            client._try_pdf_endpoint("https://europepmc.org/b", tmp_path / "b.pdf", "x")
        assert get.call_count == 2

    def test_the_cooldown_ends(self, client, tmp_path, monkeypatch):
        with patch("requests.get", return_value=self._challenge()):
            client._try_pdf_endpoint("https://europepmc.org/a", tmp_path / "a.pdf", "x")
        FullTextClient._challenged_hosts["europepmc.org"] = 0.0
        with patch("requests.get", return_value=_response(PDF)) as get:
            assert client._try_pdf_endpoint("https://europepmc.org/b", tmp_path / "b.pdf", "x")
        assert get.call_count == 1
