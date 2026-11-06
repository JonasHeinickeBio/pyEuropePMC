"""Unit tests for the download_papers_pdf MCP tool and its path/validation helpers (hermetic).

No network: Europe PMC's lookup is a mock ``SearchClient`` and the download is a fake
``FullTextClient`` that writes bytes where the real one would save a PDF.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from unittest.mock import MagicMock

from mcp_wire import hint, schema_of
import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, FullTextError
from pyeuropepmc.mcp import _pdf as pdf, server as srv

PDF_BYTES = b"%PDF-1.7\n" + b"x" * 200
HTML_BYTES = b"<html>" + b"x" * 200


def _run(coro):
    return asyncio.run(coro)


def rec(pmid=None, pmcid=None, doi=None, *, source="MED", oa="Y"):
    out = {"id": pmid or pmcid or doi, "source": source, "isOpenAccess": oa}
    if pmid:
        out["pmid"] = pmid
    if pmcid:
        out["pmcid"] = pmcid
    if doi:
        out["doi"] = doi
    return out


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    monkeypatch.setenv(pdf.ENV_DIR, str(tmp_path / "pdfs"))
    for cache in (srv._client_cache, srv._fulltext_client_cache):
        cache.reset()
    yield
    for cache in (srv._client_cache, srv._fulltext_client_cache):
        cache.reset()


def _search(records):
    client = MagicMock()
    client.search_all.return_value = records
    srv._client_cache.set(client)
    return client


def _downloader(behaviour):
    """A FullTextClient whose ``download_pdf_by_pmcid`` follows ``behaviour[pmcid]``.

    A ``bytes`` value is written to the target path; ``None`` means "no PDF anywhere"
    (the real method returns ``None``); an exception is raised.
    """
    calls: list[str] = []
    dois: dict[str, str | None] = {}

    def download(pmcid, output_path=None, rate_limiter=None, doi=None):
        calls.append(pmcid)
        dois[pmcid] = doi
        outcome = behaviour[pmcid]
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            return None
        Path(output_path).write_bytes(outcome)
        return Path(output_path)

    client = MagicMock()
    client.download_pdf_by_pmcid.side_effect = download
    srv._fulltext_client_cache.set(client)
    client.calls = calls
    client.dois = dois
    return client


class TestHelpers:
    def test_download_dir_comes_from_the_environment(self, monkeypatch, tmp_path):
        monkeypatch.setenv(pdf.ENV_DIR, str(tmp_path / "mine"))
        assert pdf.download_dir() == tmp_path / "mine"

    def test_download_dir_default_is_under_the_home_folder(self, monkeypatch):
        monkeypatch.delenv(pdf.ENV_DIR, raising=False)
        assert pdf.download_dir() == Path.home() / "Downloads" / "pyeuropepmc"

    def test_blank_environment_value_means_the_default(self, monkeypatch):
        monkeypatch.setenv(pdf.ENV_DIR, "   ")
        assert pdf.download_dir() == Path.home() / "Downloads" / "pyeuropepmc"

    def test_pdf_path_is_the_pmcid_inside_the_directory(self, tmp_path):
        assert pdf.pdf_path(tmp_path, "PMC3525259") == tmp_path / "PMC3525259.pdf"

    @pytest.mark.parametrize(
        "bad", ["../PMC1", "PMC1/../x", "PMC", "3525259", "pmc1", "PMC1.pdf", "", "PMC12345678901"]
    )
    def test_pdf_path_refuses_anything_but_a_pmcid(self, tmp_path, bad):
        with pytest.raises(ValueError, match="not a PMCID"):
            pdf.pdf_path(tmp_path, bad)

    def test_check_pdf_accepts_a_pdf(self, tmp_path):
        path = tmp_path / "a.pdf"
        path.write_bytes(PDF_BYTES)
        assert pdf.check_pdf(path) is None

    def test_check_pdf_rejects_html(self, tmp_path):
        path = tmp_path / "a.pdf"
        path.write_bytes(HTML_BYTES)
        assert pdf.check_pdf(path) == "the file is not a PDF"

    def test_check_pdf_rejects_an_oversized_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf, "MAX_PDF_BYTES", 100)
        path = tmp_path / "a.pdf"
        path.write_bytes(PDF_BYTES)
        assert "over the 100 byte limit" in str(pdf.check_pdf(path))

    def test_check_pdf_reports_a_missing_file(self, tmp_path):
        assert "cannot read" in str(pdf.check_pdf(tmp_path / "missing.pdf"))

    def test_describe(self, tmp_path):
        path = tmp_path / "a.pdf"
        path.write_bytes(PDF_BYTES)
        assert pdf.describe(path) == {
            "path": str(path.resolve()),
            "size_bytes": len(PDF_BYTES),
            "sha256": hashlib.sha256(PDF_BYTES).hexdigest(),
        }


class TestRegistration:
    def test_the_tool_writes_but_destroys_nothing(self):
        tool = {t.name: t for t in _run(srv.mcp.list_tools())}["download_papers_pdf"]
        assert hint(tool.annotations, "readOnlyHint") is False
        assert hint(tool.annotations, "destructiveHint") is False
        assert hint(tool.annotations, "idempotentHint") is True

    def test_it_takes_identifiers_and_a_flag_but_no_path(self):
        tool = {t.name: t for t in _run(srv.mcp.list_tools())}["download_papers_pdf"]
        props = schema_of(tool)["properties"]
        assert set(props) == {"ids", "overwrite"}
        assert props["ids"]["maxItems"] == 20


class TestDownloadPapersPdf:
    def test_every_status(self, tmp_path):
        _search(
            [
                rec("1", "PMC1", "10.1234/one"),
                rec("2", "PMC2", oa="N"),  # closed article: still tried
                rec("3", None),
                rec("4", "PMC4"),
                rec("5", "PMC5"),
            ]
        )
        client = _downloader(
            {"PMC1": PDF_BYTES, "PMC2": PDF_BYTES, "PMC4": None, "PMC5": HTML_BYTES}
        )

        out = _run(
            srv.download_papers_pdf(ids=["PMC1", "2", "3", "99", "junk", "10.1234/one", "4", "5"])
        )

        statuses = {r["id"]: r["status"] for r in out["results"]}
        assert statuses == {
            "PMC1": "ok",
            "2": "ok",
            "3": "not_in_pmc",
            "99": "not_found",
            "junk": "invalid",
            "10.1234/one": "duplicate",
            "4": "no_pdf",
            "5": "error",
        }
        assert out["results"][5]["duplicate_of"] == 0
        assert sorted(client.calls) == ["PMC1", "PMC2", "PMC4", "PMC5"]  # the duplicate once
        assert out["directory"] == str(tmp_path / "pdfs")
        assert out["by_status"]["ok"] == 2
        first = out["results"][0]
        assert first["path"] == str((tmp_path / "pdfs" / "PMC1.pdf").resolve())
        assert first["size_bytes"] == len(PDF_BYTES)
        assert first["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()

    def test_a_download_that_is_not_a_pdf_is_removed(self, tmp_path):
        _search([rec("5", "PMC5")])
        _downloader({"PMC5": HTML_BYTES})

        out = _run(srv.download_papers_pdf(ids=["PMC5"]))

        assert "not a PDF" in out["results"][0]["error"]
        assert not (tmp_path / "pdfs" / "PMC5.pdf").exists()

    def test_an_existing_pdf_is_kept_unless_overwrite_is_set(self, tmp_path):
        _search([rec("1", "PMC1")])
        client = _downloader({"PMC1": PDF_BYTES + b"new"})
        target = tmp_path / "pdfs" / "PMC1.pdf"
        target.parent.mkdir()
        target.write_bytes(PDF_BYTES)

        kept = _run(srv.download_papers_pdf(ids=["PMC1"]))["results"][0]
        assert kept["status"] == "exists"
        assert kept["size_bytes"] == len(PDF_BYTES)
        assert client.calls == []

        fresh = _run(srv.download_papers_pdf(ids=["PMC1"], overwrite=True))["results"][0]
        assert fresh["status"] == "ok"
        assert fresh["size_bytes"] == len(PDF_BYTES) + 3
        assert client.calls == ["PMC1"]

    def test_a_foreign_file_under_the_name_is_fetched_again(self, tmp_path):
        _search([rec("1", "PMC1")])
        client = _downloader({"PMC1": PDF_BYTES})
        target = tmp_path / "pdfs" / "PMC1.pdf"
        target.parent.mkdir()
        target.write_bytes(HTML_BYTES)

        out = _run(srv.download_papers_pdf(ids=["PMC1"]))["results"][0]

        assert out["status"] == "ok"
        assert client.calls == ["PMC1"]
        assert target.read_bytes() == PDF_BYTES

    def test_one_failing_download_does_not_stop_the_others(self):
        _search([rec("1", "PMC1"), rec("2", "PMC2"), rec("3", "PMC3")])
        _downloader(
            {
                "PMC1": PDF_BYTES,
                "PMC2": FullTextError(ErrorCodes.FULL003, context={"pmcid": "PMC2"}),
                "PMC3": RuntimeError("boom"),
            }
        )

        out = _run(srv.download_papers_pdf(ids=["PMC1", "PMC2", "PMC3"]))

        assert [r["status"] for r in out["results"]] == ["ok", "error", "error"]
        assert "RuntimeError: boom" in out["results"][2]["error"]

    def test_a_directory_that_cannot_be_written_is_an_error_not_a_crash(
        self, tmp_path, monkeypatch
    ):
        blocker = tmp_path / "file"
        blocker.write_text("not a directory")
        monkeypatch.setenv(pdf.ENV_DIR, str(blocker / "inside"))
        _search([rec("1", "PMC1")])
        _downloader({"PMC1": PDF_BYTES})

        out = _run(srv.download_papers_pdf(ids=["PMC1"]))

        assert out["results"][0]["status"] == "error"

    def test_a_lookup_failure_is_reported_per_input(self):
        client = MagicMock()
        client.search_all.side_effect = APIClientError(
            ErrorCodes.NET001, {"error": "upstream down"}
        )
        srv._client_cache.set(client)
        _downloader({})

        out = _run(srv.download_papers_pdf(ids=["PMC1"]))

        assert out["results"][0]["status"] == "error"
        assert "NET001" in out["results"][0]["error"]

    def test_without_the_fulltext_client_the_tool_says_what_to_install(self, monkeypatch):
        monkeypatch.setattr(srv, "FULLTEXT_AVAILABLE", False)
        with pytest.raises(srv.ToolError):
            _run(srv.download_papers_pdf(ids=["PMC1"]))

    def test_the_doi_from_the_lookup_reaches_the_unpaywall_step(self):
        _search([rec("1", "PMC1", "https://doi.org/10.1234/One"), rec("2", "PMC2")])
        client = _downloader({"PMC1": PDF_BYTES, "PMC2": PDF_BYTES})

        out = _run(srv.download_papers_pdf(ids=["PMC1", "PMC2"]))

        assert client.dois == {"PMC1": "10.1234/One", "PMC2": None}
        assert out["results"][0]["doi"] == "10.1234/One"
        assert "doi" not in out["results"][1]
