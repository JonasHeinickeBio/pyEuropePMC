"""PDFs by DOI from third-party open copies (hermetic: DNS and ``requests.get`` are mocked)."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.fulltext import oa_pdf
from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient
from pyeuropepmc.features.fulltext.oa_pdf import Link

PDF = b"%PDF-1.7\n" + b"x" * 5000


def _reply(status=200, body=b"", headers=None):
    response = MagicMock()
    response.status_code = status
    response.headers = {"content-type": "application/pdf", **(headers or {})}
    response.iter_content.side_effect = lambda chunk_size=8192: iter(
        [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)]
    )
    response.json.return_value = {}
    return response


def _dns(mapping):
    """``getaddrinfo`` answering from ``mapping`` (host -> address), refusing unknown hosts."""

    def lookup(host, port, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (mapping[host], port))]

    return lookup


@pytest.fixture(autouse=True)
def public_dns():
    hosts = {
        "example.org": "93.184.216.34",
        "other.example.org": "93.184.216.35",
        "evil.example.org": "10.0.0.5",
        "meta.example.org": "169.254.169.254",
        "loop.example.org": "127.0.0.1",
        "arxiv.org": "151.101.0.1",
    }
    with patch("socket.getaddrinfo", _dns(hosts)):
        yield


class TestIsPublicUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://example.org/p.pdf",
            "http://example.org:8080/p.pdf",
            "https://other.example.org/a?b=c",
        ],
    )
    def test_public_hosts_pass(self, url):
        assert oa_pdf.is_public_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.example.org/p.pdf",  # resolves to a private range
            "http://meta.example.org/latest/meta-data/",  # link-local metadata address
            "http://loop.example.org/",
            "http://127.0.0.1/",
            "http://[::1]/",
            "http://[::ffff:127.0.0.1]/",
            "http://10.1.2.3/",
            "ftp://example.org/p.pdf",
            "file:///etc/passwd",
            "https://user:secret@example.org/p.pdf",
            "https://unknown.invalid/p.pdf",
            "not a url",
            "",
        ],
    )
    def test_everything_else_is_refused(self, url):
        assert not oa_pdf.is_public_url(url)


class TestFetchPdf:
    def test_a_pdf_is_saved(self, tmp_path):
        with patch("requests.get", return_value=_reply(body=PDF)):
            assert oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf")
        assert (tmp_path / "a.pdf").read_bytes() == PDF

    def test_a_private_link_is_never_requested(self, tmp_path):
        with patch("requests.get") as get:
            assert not oa_pdf.fetch_pdf("http://evil.example.org/p.pdf", tmp_path / "a.pdf")
        get.assert_not_called()

    def test_a_redirect_to_a_private_address_is_not_followed(self, tmp_path):
        hop = _reply(302, headers={"location": "http://meta.example.org/latest/meta-data/"})
        with patch("requests.get", return_value=hop) as get:
            assert not oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf")
        assert get.call_count == 1

    def test_a_redirect_to_a_public_host_is_followed_with_redirects_off(self, tmp_path):
        replies = [
            _reply(302, headers={"location": "https://other.example.org/real.pdf"}),
            _reply(body=PDF),
        ]
        with patch("requests.get", side_effect=replies) as get:
            assert oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf")
        assert get.call_args_list[1][0][0] == "https://other.example.org/real.pdf"
        assert all(c.kwargs["allow_redirects"] is False for c in get.call_args_list)

    def test_a_relative_redirect_stays_on_the_host(self, tmp_path):
        replies = [_reply(301, headers={"location": "/files/p.pdf"}), _reply(body=PDF)]
        with patch("requests.get", side_effect=replies) as get:
            assert oa_pdf.fetch_pdf("https://example.org/p", tmp_path / "a.pdf")
        assert get.call_args_list[1][0][0] == "https://example.org/files/p.pdf"

    def test_a_redirect_loop_gives_up(self, tmp_path):
        loop = _reply(302, headers={"location": "https://example.org/again"})
        with patch("requests.get", return_value=loop) as get:
            assert not oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf")
        assert get.call_count == oa_pdf.MAX_REDIRECTS + 1

    @pytest.mark.parametrize(
        "reply",
        [
            _reply(404),
            _reply(403, body=b"no"),
            _reply(body=b"<html>paywall</html>" * 100, headers={"content-type": "text/html"}),
            _reply(body=b"<html>" + b"x" * 5000),  # says PDF, is not
            _reply(body=b"%PDF-1.4 tiny"),  # too small to be a paper
        ],
    )
    def test_anything_that_is_not_a_real_pdf_leaves_no_file(self, tmp_path, reply):
        with patch("requests.get", return_value=reply):
            assert not oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf")
        assert list(tmp_path.iterdir()) == []

    def test_the_size_limit_holds_declared_and_counted(self, tmp_path):
        with patch(
            "requests.get", return_value=_reply(body=PDF, headers={"content-length": "9999"})
        ):
            assert not oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf", 100)
        with patch("requests.get", return_value=_reply(body=PDF)):
            assert not oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf", 100)
            assert oa_pdf.fetch_pdf("https://example.org/p.pdf", tmp_path / "a.pdf", 10_000)
        assert (tmp_path / "a.pdf").read_bytes() == PDF


class TestLinks:
    def test_arxiv_dois_map_to_the_arxiv_pdf(self):
        assert oa_pdf._arxiv_links("10.48550/arXiv.2401.00001", None) == [
            Link("https://arxiv.org/pdf/2401.00001")
        ]
        assert oa_pdf._arxiv_links("10.1038/nature14539", None) == []

    def test_unpaywall_is_skipped_without_an_email(self):
        assert oa_pdf._unpaywall_links("10.1/x", None) == []

    def test_unpaywall_links_are_best_first_and_only_those_with_a_pdf(self):
        record = {
            "best_oa_location": {
                "url_for_pdf": "https://example.org/best.pdf",
                "license": "cc-by",
            },
            "oa_locations": [
                {"url_for_pdf": "https://example.org/best.pdf", "license": "cc-by"},
                {"url_for_pdf": None, "url": "https://example.org/landing"},
                {"url_for_pdf": "https://other.example.org/b.pdf", "license": None},
            ],
        }
        client = MagicMock()
        client.return_value.lookup_by_doi.return_value = record
        with patch("pyeuropepmc.features.enrich.sources.unpaywall_client.UnpaywallClient", client):
            links = oa_pdf._unpaywall_links("10.1/x", "me@example.org")
        assert links == [
            Link("https://example.org/best.pdf", "cc-by"),
            Link("https://example.org/best.pdf", "cc-by"),
            Link("https://other.example.org/b.pdf", None),
        ]

    def test_openalex_links(self):
        data = {
            "best_oa_location": {"pdf_url": "https://example.org/a.pdf", "license": "cc-by-nc"},
            "locations": [{"pdf_url": None}, {"pdf_url": "https://other.example.org/b.pdf"}],
        }
        reply = _reply()
        reply.json.return_value = data
        with patch("requests.get", return_value=reply) as get:
            links = oa_pdf._openalex_links("10.1/x", "me@example.org")
        assert links == [
            Link("https://example.org/a.pdf", "cc-by-nc"),
            Link("https://other.example.org/b.pdf"),
        ]
        assert get.call_args.kwargs["params"]["mailto"] == "me@example.org"

    def test_semantic_scholar_link(self):
        reply = _reply()
        reply.json.return_value = {
            "openAccessPdf": {"url": "https://example.org/s.pdf", "license": "CCBY"}
        }
        with patch("requests.get", return_value=reply):
            assert oa_pdf._semantic_scholar_links("10.1/x", None) == [
                Link("https://example.org/s.pdf", "CCBY")
            ]

    def test_semantic_scholar_gets_the_api_key_when_one_is_set(self, monkeypatch):
        reply = _reply()
        reply.json.return_value = {}
        monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", " secret ")
        with patch("requests.get", return_value=reply) as get:
            oa_pdf._semantic_scholar_links("10.1/x", None)
        assert get.call_args.kwargs["headers"]["x-api-key"] == "secret"
        monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY")
        with patch("requests.get", return_value=reply) as get:
            oa_pdf._semantic_scholar_links("10.1/x", None)
        assert "x-api-key" not in get.call_args.kwargs["headers"]

    def test_a_failed_lookup_means_no_links(self):
        with patch("requests.get", return_value=_reply(429)):
            assert oa_pdf._openalex_links("10.1/x", None) == []
            assert oa_pdf._semantic_scholar_links("10.1/x", None) == []


class TestDownloadByDoi:
    @staticmethod
    def _links(**by_source):
        return patch.dict(
            oa_pdf._LINK_SOURCES,
            {
                name: (lambda doi, email, _v=v: [Link(u) if isinstance(u, str) else u for u in _v])
                for name, v in by_source.items()
            },
        )

    def test_the_first_source_with_a_pdf_wins_and_is_named(self, tmp_path):
        fetched = []

        def fetch(url, target, max_bytes):
            fetched.append(url)
            if "good" in url:
                target.write_bytes(PDF)
                return True
            return False

        links = self._links(
            arxiv=[],
            unpaywall=["https://example.org/bad"],
            openalex=["https://example.org/good"],
            semantic_scholar=["https://example.org/never"],
        )
        with links, patch.object(oa_pdf, "fetch_pdf", fetch):
            result = oa_pdf.download_pdf_by_doi("10.1/x", tmp_path / "a.pdf")
        assert (result.path, result.source) == (tmp_path / "a.pdf", "openalex")
        assert result.url == "https://example.org/good" and result.license is None
        assert fetched == ["https://example.org/bad", "https://example.org/good"]

    def test_a_source_that_raises_is_skipped(self, tmp_path):
        def boom(doi, email):
            raise RuntimeError("down")

        with (
            patch.dict(oa_pdf._LINK_SOURCES, {"unpaywall": boom}),
            self._links(arxiv=[], openalex=["https://example.org/p.pdf"], semantic_scholar=[]),
            patch.object(oa_pdf, "fetch_pdf", lambda u, t, m: t.write_bytes(PDF) and True),
        ):
            result = oa_pdf.download_pdf_by_doi("10.1/x", tmp_path / "a.pdf", email="a@b.c")
        assert result.source == "openalex"

    def test_named_sources_are_skipped(self, tmp_path):
        asked = []
        links = {
            name: (lambda doi, email, _n=name: asked.append(_n) or []) for name in oa_pdf.SOURCES
        }
        with patch.dict(oa_pdf._LINK_SOURCES, links):
            assert (
                oa_pdf.download_pdf_by_doi("10.1/x", tmp_path / "a.pdf", skip=("unpaywall",))
                is None
            )
        assert asked == ["arxiv", "openalex", "semantic_scholar"]

    def test_the_same_link_is_not_fetched_twice(self, tmp_path):
        fetched = []
        same = ["https://example.org/p.pdf"]
        with (
            self._links(arxiv=[], unpaywall=same, openalex=same, semantic_scholar=same),
            patch.object(oa_pdf, "fetch_pdf", lambda u, t, m: fetched.append(u) and False),
        ):
            assert oa_pdf.download_pdf_by_doi("10.1/x", tmp_path / "a.pdf") is None
        assert fetched == ["https://example.org/p.pdf"]

    def test_the_client_method_passes_its_email_and_limits(self, tmp_path):
        client = FullTextClient(enable_cache=False, email="me@example.org")
        with patch.object(oa_pdf, "download_pdf_by_doi", return_value=None) as run:
            client.download_pdf_by_doi("10.1/x", tmp_path / "a.pdf", max_bytes=7, skip=("arxiv",))
        run.assert_called_once_with(
            "10.1/x", tmp_path / "a.pdf", email="me@example.org", max_bytes=7, skip=("arxiv",)
        )

    def test_the_licence_the_source_reported_is_normalized_into_the_result(self, tmp_path):
        links = self._links(
            arxiv=[],
            unpaywall=[Link("https://example.org/p.pdf", "CC BY-NC-ND")],
            openalex=[],
            semantic_scholar=[],
        )
        with links, patch.object(oa_pdf, "fetch_pdf", lambda u, t, m: t.write_bytes(PDF) and True):
            result = oa_pdf.download_pdf_by_doi("10.1/x", tmp_path / "a.pdf", email="a@b.c")
        assert (result.source, result.license) == ("unpaywall", "cc-by-nc-nd")
        assert result.url == "https://example.org/p.pdf" and result.md5_verified is False
