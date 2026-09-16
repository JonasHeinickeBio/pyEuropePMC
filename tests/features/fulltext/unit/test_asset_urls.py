"""Unit tests for pyeuropepmc.features.fulltext.utils.asset_urls.

The URL shape and the two rules the endpoint enforces - a ``mimeType`` must be
present, and a graphic's file name must carry an extension - were checked
against the live service; see the module docstring.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from pyeuropepmc.features.fulltext.utils.asset_urls import (
    EUROPE_PMC_FILE_ENDPOINT,
    asset_file_name,
    build_asset_url,
    guess_mime_type,
    has_known_extension,
    normalise_pmcid,
)

pytestmark = pytest.mark.unit


def query_of(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


class TestNormalisePmcid:
    @pytest.mark.parametrize("value", ["PMC3258128", "pmc3258128", "  PMC3258128 "])
    def test_accepts_pmc_ids(self, value):
        assert normalise_pmcid(value) == "PMC3258128"

    @pytest.mark.parametrize("value", ["", None, "28104805", "10.1371/journal.pone.1", "PMC"])
    def test_rejects_everything_else(self, value):
        """A PMID or a DOI cannot address a file in the PMC repository."""
        assert normalise_pmcid(value) is None


class TestAssetFileName:
    def test_keeps_a_name_that_has_an_extension(self):
        assert asset_file_name("elife-99323-fig1.jpg", "jpg") == "elife-99323-fig1.jpg"

    def test_appends_the_default_extension(self):
        """Oxford University Press and Springer Nature write graphics bare."""
        assert asset_file_name("gkr715f1", "jpg") == "gkr715f1.jpg"
        assert (
            asset_file_name("41392_2025_2280_Fig1_HTML", "jpg") == "41392_2025_2280_Fig1_HTML.jpg"
        )

    def test_a_dotted_id_is_not_an_extension(self):
        """``.g001`` is part of PLOS's file naming, not a file type."""
        assert asset_file_name("pone.0357759.g001", "jpg") == "pone.0357759.g001.jpg"

    def test_without_a_default_the_name_is_left_alone(self):
        """Media file types (.yaml, .m, .fasta) are too varied to complete."""
        assert asset_file_name("pcbi.1011761.s002.m") == "pcbi.1011761.s002.m"
        assert asset_file_name("pone.0357759.g001") == "pone.0357759.g001"

    def test_drops_a_directory_part(self):
        assert asset_file_name("./figures/fig1.jpg", "jpg") == "fig1.jpg"

    @pytest.mark.parametrize("value", ["", "   "])
    def test_empty_stays_empty(self, value):
        assert asset_file_name(value, "jpg") == ""


class TestHasKnownExtension:
    @pytest.mark.parametrize("name", ["fig1.jpg", "supp1.XLSX", "model.yaml"])
    def test_file_types(self, name):
        assert has_known_extension(name)

    @pytest.mark.parametrize(
        "name", ["pone.0357759.g001", "10.1371/journal.pone.0357759.s001", "gkr715f1", ""]
    )
    def test_dotted_identifiers_are_not_file_types(self, name):
        assert not has_known_extension(name)


class TestGuessMimeType:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("fig1.jpg", "image/jpeg"),
            ("fig1.WEBP", "image/webp"),
            ("supp1.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("model.yaml", "text/yaml"),
            ("report.pdf", "application/pdf"),
        ],
    )
    def test_known_extensions(self, name, expected):
        assert guess_mime_type(name) == expected

    @pytest.mark.parametrize("name", ["data.fasta", "noextension", ""])
    def test_unknown_falls_back_to_octet_stream(self, name):
        assert guess_mime_type(name) == "application/octet-stream"


class TestBuildAssetUrl:
    def test_full_url(self):
        url = build_asset_url("PMC3258128", "gkr715f1", default_extension="jpg")
        assert url.startswith(f"{EUROPE_PMC_FILE_ENDPOINT}?")
        assert query_of(url) == {
            "pmcId": "PMC3258128",
            "type": "FILE",
            "fileName": "gkr715f1.jpg",
            "mimeType": "image/jpeg",
            "version": "1",
        }

    def test_a_mime_type_is_always_sent(self):
        """The endpoint answers 500 without one, whatever the file."""
        url = build_asset_url("PMC1", "data.fasta")
        assert query_of(url)["mimeType"] == "application/octet-stream"

    def test_declared_mime_type_wins(self):
        url = build_asset_url("PMC1", "video1.mp4", "video/mp4")
        assert query_of(url)["mimeType"] == "video/mp4"

    def test_pmcid_is_not_doubled(self):
        """``PMC{pmcid}`` over a PMCID gave PMCPMC11687933."""
        assert "PMCPMC" not in build_asset_url("PMC11687933", "fig1.jpg")

    @pytest.mark.parametrize(
        ("pmcid", "href"),
        [("28104805", "fig1.jpg"), ("", "fig1.jpg"), (None, "fig1.jpg"), ("PMC1", "")],
    )
    def test_returns_none_when_no_url_can_resolve(self, pmcid, href):
        assert build_asset_url(pmcid, href) is None
