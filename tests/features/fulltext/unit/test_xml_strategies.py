"""Unit tests for pyeuropepmc.features.fulltext.xml_strategies (hermetic)."""

from __future__ import annotations

import io
import tarfile
from unittest.mock import MagicMock

import pytest

from pyeuropepmc.features.fulltext.xml_strategies import (
    FetchContext,
    default_strategies,
    fetch_bioc_pmc,
    fetch_biorxiv,
    fetch_doi_negotiation,
    fetch_ncbi_efetch,
    fetch_pmc_oa_service,
    register_strategy,
    run_strategies,
)

JATS = '<?xml version="1.0"?><article><body>content</body></article>'


def _resp(text="", status=200, json_data=None, content_type="application/xml"):
    r = MagicMock()
    r.text = text
    r.status_code = status
    r.headers = {"content-type": content_type}
    r.content = text.encode() if isinstance(text, str) else text
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status}")
    if json_data is not None:
        r.json.return_value = json_data
    return r


class TestFetchContext:
    def test_pmcid_full_none(self):
        ctx = FetchContext()
        assert ctx.pmcid_full is None

    def test_pmcid_full_formats(self):
        ctx = FetchContext(pmcid="12345")
        assert ctx.pmcid_full == "PMC12345"

    def test_get_uses_session_when_present(self):
        session = MagicMock()
        session.get.return_value = _resp("ok")
        ctx = FetchContext(session=session, timeout=10)
        resp = ctx._get("https://example.org")
        session.get.assert_called_once()
        assert resp.text == "ok"

    def test_get_falls_back_to_requests_module(self, monkeypatch):
        ctx = FetchContext(session=None, timeout=5)
        fake_requests = MagicMock()
        fake_requests.get.return_value = _resp("ok")
        monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)
        resp = ctx._get("https://example.org")
        assert resp.text == "ok"


class TestFetchPmcOaService:
    def test_no_pmcid_returns_none(self):
        assert fetch_pmc_oa_service(FetchContext()) is None

    def test_no_package_link_returns_none(self):
        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(return_value=_resp("<records></records>"))
        assert fetch_pmc_oa_service(ctx) is None

    def test_success_extracts_nxml(self):
        # Build an in-memory tar.gz containing one .nxml file
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            data = JATS.encode()
            info = tarfile.TarInfo(name="PMC123/PMC123.nxml")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        buf.seek(0)

        meta_resp = _resp('<link format="tgz" href="ftp://ftp.ncbi.nlm.nih.gov/pkg.tar.gz"/>')
        pkg_resp = MagicMock()
        pkg_resp.content = buf.getvalue()
        pkg_resp.raise_for_status = MagicMock()

        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(side_effect=[meta_resp, pkg_resp])
        text = fetch_pmc_oa_service(ctx)
        assert text is not None
        assert "article" in text

    def test_package_without_nxml_returns_none(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            data = b"not xml"
            info = tarfile.TarInfo(name="readme.txt")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        buf.seek(0)
        meta_resp = _resp('<link format="tgz" href="https://example.org/pkg.tar.gz"/>')
        pkg_resp = MagicMock()
        pkg_resp.content = buf.getvalue()
        pkg_resp.raise_for_status = MagicMock()

        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(side_effect=[meta_resp, pkg_resp])
        assert fetch_pmc_oa_service(ctx) is None

    def test_exception_returns_none(self):
        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(side_effect=RuntimeError("network down"))
        assert fetch_pmc_oa_service(ctx) is None


class TestFetchNcbiEfetch:
    def test_no_pmcid_returns_none(self):
        assert fetch_ncbi_efetch(FetchContext()) is None

    def test_success_with_body(self):
        ctx = FetchContext(pmcid="123", email="a@b.com")
        ctx._get = MagicMock(return_value=_resp(JATS))
        assert fetch_ncbi_efetch(ctx) == JATS

    def test_no_body_returns_none(self):
        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(return_value=_resp("<?xml version='1.0'?><front-only/>"))
        assert fetch_ncbi_efetch(ctx) is None

    def test_exception_returns_none(self):
        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(side_effect=RuntimeError("boom"))
        assert fetch_ncbi_efetch(ctx) is None


class TestFetchBiocPmc:
    def test_no_pmcid_returns_none(self):
        assert fetch_bioc_pmc(FetchContext()) is None

    def test_success(self):
        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(
            return_value=_resp('<?xml version="1.0"?><collection><passage>x</passage></collection>')
        )
        assert fetch_bioc_pmc(ctx) is not None

    def test_no_passage_returns_none(self):
        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(return_value=_resp('<?xml version="1.0"?><collection></collection>'))
        assert fetch_bioc_pmc(ctx) is None

    def test_exception_returns_none(self):
        ctx = FetchContext(pmcid="123")
        ctx._get = MagicMock(side_effect=RuntimeError("boom"))
        assert fetch_bioc_pmc(ctx) is None


class TestFetchDoiNegotiation:
    def test_no_doi_returns_none(self):
        assert fetch_doi_negotiation(FetchContext()) is None

    def test_success(self):
        ctx = FetchContext(doi="10.1234/x")
        ctx._get = MagicMock(return_value=_resp(JATS, content_type="application/xml"))
        assert fetch_doi_negotiation(ctx) == JATS

    def test_non_xml_content_type_returns_none(self):
        ctx = FetchContext(doi="10.1234/x")
        ctx._get = MagicMock(return_value=_resp("<html></html>", content_type="text/html"))
        assert fetch_doi_negotiation(ctx) is None

    def test_crossref_unixsd_body_rejected(self):
        ctx = FetchContext(doi="10.1234/x")
        text = "crossref" + JATS
        ctx._get = MagicMock(return_value=_resp(text, content_type="application/xml"))
        assert fetch_doi_negotiation(ctx) is None

    def test_exception_returns_none(self):
        ctx = FetchContext(doi="10.1234/x")
        ctx._get = MagicMock(side_effect=RuntimeError("boom"))
        assert fetch_doi_negotiation(ctx) is None


class TestFetchBiorxiv:
    def test_no_doi_returns_none(self):
        assert fetch_biorxiv(FetchContext()) is None

    def test_non_biorxiv_doi_returns_none(self):
        assert fetch_biorxiv(FetchContext(doi="10.1234/x")) is None

    def test_success(self):
        ctx = FetchContext(doi="10.1101/2020.01.01.123456")
        meta_resp = _resp(json_data={"collection": [{"jatsxml": "https://x/y.xml"}]})
        xml_resp = _resp(JATS)
        ctx._get = MagicMock(side_effect=[meta_resp, xml_resp])
        assert fetch_biorxiv(ctx) == JATS

    def test_empty_collection_tries_medrxiv_then_gives_up(self):
        ctx = FetchContext(doi="10.1101/2020.01.01.123456")
        empty_resp = _resp(json_data={"collection": []})
        ctx._get = MagicMock(return_value=empty_resp)
        assert fetch_biorxiv(ctx) is None

    def test_missing_jatsxml_key(self):
        ctx = FetchContext(doi="10.1101/2020.01.01.123456")
        resp = _resp(json_data={"collection": [{}]})
        ctx._get = MagicMock(return_value=resp)
        assert fetch_biorxiv(ctx) is None

    def test_exception_is_swallowed(self):
        ctx = FetchContext(doi="10.1101/2020.01.01.123456")
        ctx._get = MagicMock(side_effect=RuntimeError("boom"))
        assert fetch_biorxiv(ctx) is None


class TestRegistry:
    def test_default_strategies_order(self):
        strategies = default_strategies()
        names = [n for n, _ in strategies]
        assert names == [
            "pmc_oa_service",
            "ncbi_efetch",
            "bioc_pmc",
            "doi_negotiation",
            "biorxiv",
        ]

    def test_default_strategies_custom_subset(self):
        strategies = default_strategies(["bioc_pmc"])
        assert [n for n, _ in strategies] == ["bioc_pmc"]

    def test_register_strategy_duplicate_raises(self):
        with pytest.raises(ValueError):
            register_strategy("bioc_pmc", fetch_bioc_pmc)

    def test_register_strategy_replace(self):
        called = {}

        def custom(ctx):
            called["yes"] = True
            return "custom-xml"

        register_strategy("bioc_pmc", custom, replace=True)
        try:
            text, winner = run_strategies(FetchContext(pmcid="1"), names=["bioc_pmc"])
            assert text == "custom-xml"
            assert winner == "bioc_pmc"
            assert called["yes"]
        finally:
            register_strategy("bioc_pmc", fetch_bioc_pmc, replace=True)

    def test_register_strategy_new_name(self):
        def custom(ctx):
            return None

        register_strategy("my_custom_strategy", custom)
        assert any(n == "my_custom_strategy" for n, _ in default_strategies(["my_custom_strategy"]))


class TestRunStrategies:
    def test_run_strategies_returns_first_success(self):
        ctx = FetchContext(pmcid="123", doi="10.1234/x")

        def fails(_ctx):
            return None

        def succeeds(_ctx):
            return "found-it"

        register_strategy("t_fail", fails, replace=True)
        register_strategy("t_ok", succeeds, replace=True)
        text, winner = run_strategies(ctx, names=["t_fail", "t_ok"])
        assert text == "found-it"
        assert winner == "t_ok"

    def test_run_strategies_all_fail(self):
        ctx = FetchContext()
        text, winner = run_strategies(ctx, names=[])
        assert text is None
        assert winner is None
