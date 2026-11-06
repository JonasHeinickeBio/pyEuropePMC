"""Unit tests for the download_papers_pdf MCP tool and its path/validation helpers (hermetic).

No network: Europe PMC's lookup is a mock ``SearchClient`` and the download is a fake
``FullTextClient`` that writes bytes where the real one would save a PDF.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

from mcp_wire import hint, schema_of
import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, FullTextError
from pyeuropepmc.features.fulltext.pdf_result import PdfResult
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


def _downloader(behaviour, by_doi=None, licenses=None):
    """A FullTextClient whose ``download_pdf_by_pmcid`` follows ``behaviour[pmcid]``.

    A ``bytes`` value is written to the target path; ``None`` means "no PDF anywhere"
    (the real method returns ``None``); an exception is raised.
    """
    calls: list[str] = []
    limits: list[int | None] = []
    dois: dict[str, str | None] = {}
    access: dict[str, bool | None] = {}

    def download(
        pmcid, output_path=None, rate_limiter=None, doi=None, max_bytes=None, open_access=None
    ):
        calls.append(pmcid)
        limits.append(max_bytes)
        dois[pmcid] = doi
        access[pmcid] = open_access
        outcome = behaviour[pmcid]
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            return None
        Path(output_path).write_bytes(outcome)
        return PdfResult(
            Path(output_path),
            "unpaywall",
            url=f"https://example.org/{pmcid}.pdf",
            license=(licenses or {}).get(pmcid),
        )

    doi_calls: list[tuple[str, tuple[str, ...]]] = []

    def download_by_doi(doi, output_path, max_bytes=None, skip=()):
        doi_calls.append((doi, tuple(skip)))
        outcome = (by_doi or {}).get(doi.lower())
        if outcome is None:
            return None
        Path(output_path).write_bytes(outcome)
        return PdfResult(
            Path(output_path),
            "openalex",
            url="https://example.org/doi.pdf",
            license=(licenses or {}).get(doi.lower()),
        )

    client = MagicMock()
    client.download_pdf_with_provenance.side_effect = download
    client.download_pdf_by_doi.side_effect = download_by_doi
    srv._fulltext_client_cache.set(client)
    client.doi_calls = doi_calls
    client.calls = calls
    client.limits = limits
    client.dois = dois
    client.access = access
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
        "bad",
        [
            "../PMC1",
            "PMC1/../x",
            "PMC",
            "3525259",
            "pmc1",
            "PMC1.pdf",
            "",
            "PMC12345678901",
            "PMC1\n",
        ],
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

    def test_a_write_that_fails_midway_names_the_file(self):
        _search([rec("1", "PMC1")])
        _downloader({"PMC1": OSError("disk full")})

        item = _run(srv.download_papers_pdf(ids=["PMC1"]))["results"][0]

        assert item["status"] == "error"
        assert "cannot write" in item["error"] and "disk full" in item["error"]

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

    def test_the_size_limit_is_handed_to_the_downloader(self):
        _search([rec("1", "PMC1")])
        client = _downloader({"PMC1": PDF_BYTES})

        _run(srv.download_papers_pdf(ids=["PMC1"]))

        assert client.limits == [pdf.MAX_PDF_BYTES]

    def test_the_open_access_flag_reaches_the_downloader_and_the_source_the_result(self):
        _search([rec("1", "PMC1", oa="Y"), rec("2", "PMC2", oa="N"), rec("3", "PMC3", oa="")])
        client = _downloader({"PMC1": PDF_BYTES, "PMC2": PDF_BYTES, "PMC3": PDF_BYTES})

        out = _run(srv.download_papers_pdf(ids=["PMC1", "PMC2", "PMC3"]))

        assert client.access == {"PMC1": True, "PMC2": False, "PMC3": None}
        assert [r.get("open_access") for r in out["results"]] == [True, False, None]
        assert [r["source"] for r in out["results"]] == ["unpaywall"] * 3

    def test_calls_for_the_same_file_wait_for_each_other(self, tmp_path):
        """Two overlapping downloads of one PMCID must never run the downloader at once."""
        import threading
        import time

        active = 0
        peak = 0
        guard = threading.Lock()

        def slow(
            pmcid, output_path=None, rate_limiter=None, doi=None, max_bytes=None, open_access=None
        ):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            Path(output_path).write_bytes(PDF_BYTES)
            with guard:
                active -= 1
            return PdfResult(Path(output_path), "pmc_open_data")

        client = MagicMock()
        client.download_pdf_with_provenance.side_effect = slow
        srv._fulltext_client_cache.set(client)
        directory = tmp_path / "pdfs"

        async def both():
            return await asyncio.gather(
                *(srv._pdf_or_error("PMC1", directory, True, None) for _ in range(4))
            )

        outcomes = _run(both())

        assert peak == 1
        assert all(o["status"] == "ok" for o in outcomes)

    def test_different_files_download_in_parallel(self, tmp_path):
        import threading

        both_inside = threading.Barrier(2, timeout=5)

        def rendezvous(
            pmcid, output_path=None, rate_limiter=None, doi=None, max_bytes=None, open_access=None
        ):
            both_inside.wait()  # only passes if the two downloads overlap
            Path(output_path).write_bytes(PDF_BYTES)
            return PdfResult(Path(output_path), "pmc_open_data")

        client = MagicMock()
        client.download_pdf_with_provenance.side_effect = rendezvous
        srv._fulltext_client_cache.set(client)
        directory = tmp_path / "pdfs"

        async def two():
            return await asyncio.gather(
                srv._pdf_or_error("PMC1", directory, True, None),
                srv._pdf_or_error("PMC2", directory, True, None),
            )

        assert [o["status"] for o in _run(two())] == ["ok", "ok"]


class TestPapersOutsidePmc:
    def test_a_doi_without_pmcid_is_fetched_by_doi_into_a_hashed_name(self, tmp_path):
        _search([rec("5", None, "10.1234/Abc.1")])
        client = _downloader({}, {"10.1234/abc.1": PDF_BYTES})

        out = _run(srv.download_papers_pdf(ids=["10.1234/Abc.1"]))

        item = out["results"][0]
        assert item["status"] == "ok" and item["source"] == "openalex"
        assert "pmcid" not in item
        assert Path(item["path"]).name == pdf.doi_path(Path("."), "10.1234/Abc.1").name
        assert Path(item["path"]).parent == (tmp_path / "pdfs").resolve()
        assert client.calls == []
        assert client.doi_calls == [("10.1234/Abc.1", ())]

    def test_a_doi_europe_pmc_has_never_heard_of_is_still_tried(self):
        _search([])
        client = _downloader({}, {"10.1234/x": PDF_BYTES})

        out = _run(srv.download_papers_pdf(ids=["10.1234/x"]))

        assert out["results"][0]["status"] == "ok"
        assert client.doi_calls == [("10.1234/x", ())]

    def test_a_pmid_with_neither_pmcid_nor_doi_has_nothing_to_ask_for(self):
        _search([rec("5", None, None)])
        client = _downloader({})

        out = _run(srv.download_papers_pdf(ids=["5"]))

        assert out["results"][0]["status"] == "not_in_pmc"
        assert client.doi_calls == [] and client.calls == []

    def test_an_unknown_pmid_is_still_not_found(self):
        _search([])
        _downloader({})
        assert _run(srv.download_papers_pdf(ids=["5"]))["results"][0]["status"] == "not_found"

    def test_a_pmc_paper_with_no_pdf_falls_back_to_the_doi_sources_without_unpaywall(self):
        _search([rec("1", "PMC1", "10.1234/one")])
        client = _downloader({"PMC1": None}, {"10.1234/one": PDF_BYTES})

        out = _run(srv.download_papers_pdf(ids=["PMC1"]))

        assert out["results"][0]["status"] == "ok"
        assert out["results"][0]["source"] == "openalex"
        assert client.doi_calls == [("10.1234/one", ("unpaywall",))]
        assert Path(out["results"][0]["path"]).name == "PMC1.pdf"

    def test_nothing_anywhere_is_no_pdf_and_names_the_input(self):
        _search([rec("5", None, "10.1234/none")])
        _downloader({})
        item = _run(srv.download_papers_pdf(ids=["10.1234/none"]))["results"][0]
        assert item["status"] == "no_pdf" and "10.1234/none" in item["error"]

    def test_the_same_doi_twice_is_one_download(self):
        _search([rec("5", None, "10.1234/Same")])
        client = _downloader({}, {"10.1234/same": PDF_BYTES})

        out = _run(srv.download_papers_pdf(ids=["10.1234/Same", "doi:10.1234/same"]))

        assert [r["status"] for r in out["results"]] == ["ok", "duplicate"]
        assert len(client.doi_calls) == 1

    def test_a_doi_and_its_pmcid_are_one_paper(self):
        _search([rec("1", "PMC1", "10.1234/one")])
        client = _downloader({"PMC1": PDF_BYTES})

        out = _run(srv.download_papers_pdf(ids=["PMC1", "10.1234/one"]))

        assert [r["status"] for r in out["results"]] == ["ok", "duplicate"]
        assert client.calls == ["PMC1"]


class TestDoiPath:
    def test_the_name_is_readable_safe_and_stable(self, tmp_path):
        path = pdf.doi_path(tmp_path, "10.1038/nature14539")
        assert path.parent == tmp_path
        assert path.name.startswith("10.1038_nature14539-") and path.suffix == ".pdf"
        assert path == pdf.doi_path(tmp_path, "10.1038/NATURE14539")

    def test_dois_differing_only_in_replaced_characters_stay_apart(self, tmp_path):
        assert pdf.doi_path(tmp_path, "10.1234/a(b)") != pdf.doi_path(tmp_path, "10.1234/a[b]")

    def test_nothing_in_a_doi_can_leave_the_directory(self, tmp_path):
        path = pdf.doi_path(tmp_path, "10.1234/../../etc/passwd")
        assert path.parent == tmp_path and "/" not in path.name and not path.name.startswith(".")

    def test_a_very_long_doi_gives_a_short_name(self, tmp_path):
        assert len(pdf.doi_path(tmp_path, "10.1234/" + "a" * 500).name) < 100

    @pytest.mark.parametrize(
        "bad", ["", "nature14539", "10.1/", "10.12/ab", "../10.1234/x", "10.1234/x\n"]
    )
    def test_anything_but_a_doi_is_refused(self, tmp_path, bad):
        with pytest.raises(ValueError, match="not a DOI"):
            pdf.doi_path(tmp_path, bad)


def _manifest(tmp_path):
    path = tmp_path / "pdfs" / pdf.MANIFEST_NAME
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class TestManifestAndLicence:
    def test_a_saved_pdf_gets_a_manifest_line_with_source_url_and_licence(self, tmp_path):
        _search([rec("1", "PMC1", "10.1234/one")])
        _downloader({"PMC1": PDF_BYTES}, licenses={"PMC1": "cc-by"})

        out = _run(srv.download_papers_pdf(ids=["PMC1"]))

        item = out["results"][0]
        assert (item["license"], item["license_source"]) == ("cc-by", "unpaywall")
        assert item["source_url"] == "https://example.org/PMC1.pdf"
        assert out["manifest"] == str(tmp_path / "pdfs" / pdf.MANIFEST_NAME)
        [line] = _manifest(tmp_path)
        assert line["file"] == "PMC1.pdf" and line["pmcid"] == "PMC1"
        assert line["doi"] == "10.1234/one" and line["source"] == "unpaywall"
        assert line["url"] == "https://example.org/PMC1.pdf"
        assert (line["license"], line["license_source"]) == ("cc-by", "unpaywall")
        assert line["sha256"] == item["sha256"] and line["size_bytes"] == item["size_bytes"]
        assert line["md5_verified"] is False and line["pyeuropepmc"]
        assert line["saved_at"].endswith("+00:00")

    def test_europe_pmc_licence_fills_in_when_the_source_says_nothing(self, tmp_path):
        record = rec("1", "PMC1")
        record["license"] = "cc by-nc-nd"
        _search([record])
        _downloader({"PMC1": PDF_BYTES})

        item = _run(srv.download_papers_pdf(ids=["PMC1"]))["results"][0]

        assert (item["license"], item["license_source"]) == ("cc-by-nc-nd", "europepmc")
        assert _manifest(tmp_path)[0]["license_source"] == "europepmc"

    def test_the_sources_own_licence_wins_over_europe_pmcs(self):
        record = rec("1", "PMC1")
        record["license"] = "cc by"
        _search([record])
        _downloader({"PMC1": PDF_BYTES}, licenses={"PMC1": "cc-by-nc"})

        item = _run(srv.download_papers_pdf(ids=["PMC1"]))["results"][0]

        assert (item["license"], item["license_source"]) == ("cc-by-nc", "unpaywall")

    def test_nobody_saying_anything_is_null_not_a_guess(self, tmp_path):
        _search([rec("1", "PMC1")])
        _downloader({"PMC1": PDF_BYTES})

        item = _run(srv.download_papers_pdf(ids=["PMC1"]))["results"][0]

        assert item["license"] is None and item["license_source"] is None
        assert _manifest(tmp_path)[0]["license"] is None

    def test_a_doi_download_is_recorded_with_its_doi_and_no_pmcid(self, tmp_path):
        _search([rec("5", None, "10.1234/x")])
        _downloader({}, {"10.1234/x": PDF_BYTES}, licenses={"10.1234/x": "cc0"})

        _run(srv.download_papers_pdf(ids=["10.1234/x"]))

        [line] = _manifest(tmp_path)
        assert (line["pmcid"], line["doi"], line["license"]) == (None, "10.1234/x", "cc0")
        assert line["file"].startswith("10.1234_x-")

    def test_a_file_that_already_exists_is_not_written_to_the_manifest_again(self, tmp_path):
        _search([rec("1", "PMC1")])
        _downloader({"PMC1": PDF_BYTES})
        _run(srv.download_papers_pdf(ids=["PMC1"]))
        again = _run(srv.download_papers_pdf(ids=["PMC1"]))

        assert again["results"][0]["status"] == "exists"
        assert len(_manifest(tmp_path)) == 1

    def test_downloading_again_adds_a_line_and_the_last_one_is_current(self, tmp_path):
        _search([rec("1", "PMC1")])
        _downloader({"PMC1": PDF_BYTES})
        _run(srv.download_papers_pdf(ids=["PMC1"]))
        _run(srv.download_papers_pdf(ids=["PMC1"], overwrite=True))

        assert [line["file"] for line in _manifest(tmp_path)] == ["PMC1.pdf", "PMC1.pdf"]

    def test_failures_leave_no_manifest_line(self, tmp_path):
        _search([rec("1", "PMC1"), rec("2", "PMC2")])
        _downloader({"PMC1": None, "PMC2": HTML_BYTES})

        _run(srv.download_papers_pdf(ids=["PMC1", "PMC2"]))

        assert _manifest(tmp_path) == []

    def test_an_unwritable_manifest_is_reported_but_the_pdf_stays(self, tmp_path, monkeypatch):
        _search([rec("1", "PMC1")])
        _downloader({"PMC1": PDF_BYTES})
        monkeypatch.setattr(pdf, "MANIFEST_NAME", "no/such/dir/manifest.jsonl")

        item = _run(srv.download_papers_pdf(ids=["PMC1"]))["results"][0]

        assert item["status"] == "ok" and "manifest" in item["manifest_error"]
        assert (tmp_path / "pdfs" / "PMC1.pdf").exists()

    def test_parallel_writers_never_interleave_lines(self, tmp_path):
        import threading

        directory = tmp_path / "pdfs"
        directory.mkdir()
        record = {"file": "x" * 3000, "n": 0}

        def write(n):
            for i in range(20):
                assert pdf.append_manifest(directory, {**record, "n": n * 100 + i}) is None

        threads = [threading.Thread(target=write, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        lines = (directory / pdf.MANIFEST_NAME).read_text().splitlines()
        assert len(lines) == 160 and all(json.loads(line)["file"] == "x" * 3000 for line in lines)

    def test_the_tool_asks_europe_pmc_for_core_records_to_get_the_licence(self):
        client = _search([rec("1", "PMC1")])
        _downloader({"PMC1": PDF_BYTES})
        _run(srv.download_papers_pdf(ids=["PMC1"]))
        assert client.search_all.call_args.kwargs["resultType"] == "core"

    def test_a_file_from_the_cache_says_so_in_the_result_and_the_manifest(self, tmp_path):
        _search([rec("1", "PMC1")])
        client = _downloader({"PMC1": PDF_BYTES})
        original = client.download_pdf_with_provenance.side_effect

        def from_cache(*args, **kwargs):
            result = original(*args, **kwargs)
            return PdfResult(
                result.path,
                "pmc_open_data",
                url="https://example.org/original.pdf",
                license="cc-by",
                from_cache=True,
            )

        client.download_pdf_with_provenance.side_effect = from_cache

        item = _run(srv.download_papers_pdf(ids=["PMC1"]))["results"][0]

        assert (item["source"], item["from_cache"]) == ("pmc_open_data", True)
        assert item["source_url"] == "https://example.org/original.pdf"
        assert _manifest(tmp_path)[0]["from_cache"] is True
