"""Unit tests for pyeuropepmc.features.fulltext.extensions.image_fetcher."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.extensions.image_fetcher import (
    AssetFetchPolicy,
    AssetRef,
    AssetType,
    ImageFetcher,
)

XLINK = 'xmlns:xlink="http://www.w3.org/1999/xlink"'

XML_WITH_ASSETS = f"""<article {XLINK}>
  <body>
    <fig id="f1">
      <label>Fig. 1</label>
      <caption>
        <p>First figure, with
          <inline-formula><alternatives><graphic xlink:href="e001.jpg"/></alternatives></inline-formula>
          in the caption.</p>
      </caption>
      <alternatives>
        <graphic xlink:href="fig1.jpg" mimetype="image" mime-subtype="jpeg"/>
        <graphic xlink:href="fig1-hires.tif"/>
      </alternatives>
      <p><fig id="f1s1">
        <label>Fig. 1—figure supplement 1.</label>
        <caption><p>A supplement.</p></caption>
        <graphic xlink:href="fig1-figsupp1.jpg"/>
      </fig></p>
    </fig>
    <table-wrap id="t1">
      <label>Table 1</label>
      <caption><p>A table deposited as an image.</p></caption>
      <graphic xlink:href="table1.jpg"/>
    </table-wrap>
    <graphic xlink:href="standalone.png"/>
    <supplementary-material id="s1">
      <label>Supp 1</label>
      <caption><p>Extra data.</p></caption>
      <media xlink:href="supp1.zip"/>
    </supplementary-material>
    <media id="m1" xlink:href="video1.mp4" mimetype="video" mime-subtype="mp4">
      <label>Video 1</label>
    </media>
  </body>
</article>
"""


def _fetcher(xml: str = XML_WITH_ASSETS, **kwargs) -> ImageFetcher:
    root = DefusedET.fromstring(xml)
    return ImageFetcher(root=root, **kwargs)


def _by_file(assets: list[AssetRef]) -> dict[str, AssetRef]:
    """Assets keyed by the file they point at - one per file, by construction."""
    return {a.metadata["file_name"]: a for a in assets}


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


class TestAssetRef:
    def test_to_dict(self):
        ref = AssetRef(asset_type=AssetType.FIGURE, uri="http://x/fig.png", label="Fig 1")
        d = ref.to_dict()
        assert d["asset_type"] == "figure"
        assert d["uri"] == "http://x/fig.png"


class TestExtractAssetRefs:
    def test_no_root_raises(self):
        fetcher = ImageFetcher()
        with pytest.raises(Exception):  # noqa: B017
            fetcher.extract_asset_refs()

    def test_extracts_all_asset_kinds(self):
        fetcher = _fetcher()
        assets = fetcher.extract_asset_refs()
        types = {a.asset_type for a in assets}
        assert types == {
            AssetType.FIGURE,
            AssetType.TABLE,
            AssetType.SUPPLEMENTARY,
            AssetType.FORMULA,
            AssetType.VIDEO,
        }

    def test_figure_includes_alternatives(self):
        fetcher = _fetcher()
        assets = _by_file(fetcher.extract_asset_refs())
        assert assets["fig1.jpg"].asset_type == AssetType.FIGURE
        assert assets["fig1-hires.tif"].asset_type == AssetType.FIGURE
        # The first representation is the figure's; the rest are alternatives.
        assert assets["fig1.jpg"].metadata.get("alternative") is None
        assert assets["fig1-hires.tif"].metadata["alternative"] is True

    def test_standalone_graphic_included_once(self):
        fetcher = _fetcher()
        assets = fetcher.extract_asset_refs()
        standalone = [a for a in assets if a.metadata["file_name"] == "standalone.png"]
        assert len(standalone) == 1
        assert standalone[0].asset_type == AssetType.FIGURE
        assert standalone[0].label == ""

    def test_every_file_appears_once(self):
        """A figure's graphics were added again by the pass over graphics."""
        names = [a.metadata["file_name"] for a in _fetcher().extract_asset_refs()]
        assert sorted(names) == [
            "e001.jpg",
            "fig1-figsupp1.jpg",
            "fig1-hires.tif",
            "fig1.jpg",
            "standalone.png",
            "supp1.zip",
            "table1.jpg",
            "video1.mp4",
        ]

    def test_a_caption_formula_is_not_the_figure(self):
        assets = _by_file(_fetcher().extract_asset_refs())
        assert assets["e001.jpg"].asset_type == AssetType.FORMULA
        assert assets["e001.jpg"].label == ""

    def test_a_figure_supplement_keeps_its_own_label(self):
        assets = _by_file(_fetcher().extract_asset_refs())
        supplement = assets["fig1-figsupp1.jpg"]
        assert supplement.label == "Fig. 1—figure supplement 1."
        assert supplement.id == "f1s1"
        assert supplement.metadata["parent_id"] == "f1"
        assert supplement.metadata["parent_label"] == "Fig. 1"

    def test_a_parent_figures_caption_excludes_its_supplement(self):
        assets = _by_file(_fetcher().extract_asset_refs())
        assert "A supplement" not in assets["fig1.jpg"].caption

    def test_a_table_image_is_typed_as_a_table(self):
        table = _by_file(_fetcher().extract_asset_refs())["table1.jpg"]
        assert table.asset_type == AssetType.TABLE
        assert table.label == "Table 1"

    def test_supplementary_material_keeps_its_mime_type(self):
        supp = _by_file(_fetcher().extract_asset_refs())["supp1.zip"]
        assert supp.asset_type == AssetType.SUPPLEMENTARY
        assert supp.mime_type == "application/zip"
        assert supp.label == "Supp 1"
        assert "Extra data" in supp.caption

    def test_media_inside_supplementary_material_is_not_reported_twice(self):
        assets = [a for a in _fetcher().extract_asset_refs() if a.metadata["jats_tag"] == "media"]
        assert sorted(a.metadata["file_name"] for a in assets) == ["supp1.zip", "video1.mp4"]

    def test_a_standalone_media_is_typed_from_its_mime_type(self):
        video = _by_file(_fetcher().extract_asset_refs())["video1.mp4"]
        assert video.asset_type == AssetType.VIDEO
        assert video.mime_type == "video/mp4"
        assert video.label == ""

    def test_uris_resolved_when_article_id_set(self):
        fetcher = _fetcher(article_id="PMC1234567")
        fig = _by_file(fetcher.extract_asset_refs())["fig1.jpg"]
        assert fig.uri.startswith("https://europepmc.org/api/fulltextRepo?")
        assert _query(fig.uri) == {
            "pmcId": "PMC1234567",
            "type": "FILE",
            "fileName": "fig1.jpg",
            "mimeType": "image/jpeg",
            "version": "1",
        }

    def test_uris_stay_relative_without_a_pmcid(self):
        """A PMID cannot address a file in the PMC repository."""
        fetcher = _fetcher(article_id="28104805")
        assert _by_file(fetcher.extract_asset_refs())["fig1.jpg"].uri == "fig1.jpg"

    def test_no_assets_returns_empty(self):
        fetcher = _fetcher(f"<article {XLINK}><body/></article>")
        assert fetcher.extract_asset_refs() == []

    def test_an_element_with_no_href_is_skipped(self):
        fetcher = _fetcher(f"<article {XLINK}><body><graphic/></body></article>")
        assert fetcher.extract_asset_refs() == []


class TestSupplementaryShapes:
    def test_href_on_the_block_itself(self):
        xml = f"""<article {XLINK}><supplementary-material id="s2" xlink:href="supp2.pdf">
            <label>Supp 2</label>
        </supplementary-material></article>"""
        asset = _fetcher(xml).extract_asset_refs()[0]
        assert asset.asset_type == AssetType.SUPPLEMENTARY
        assert asset.metadata["file_name"] == "supp2.pdf"
        assert asset.label == "Supp 2"

    def test_falls_back_to_an_object_id_holding_a_file_name(self):
        xml = f"""<article {XLINK}><supplementary-material id="s2">
            <object-id> supp2.pdf </object-id>
        </supplementary-material></article>"""
        asset = _fetcher(xml).extract_asset_refs()[0]
        assert asset.metadata["file_name"] == "supp2.pdf"
        assert asset.asset_type == AssetType.SUPPLEMENTARY

    @pytest.mark.parametrize(
        "object_id",
        [
            '<object-id pub-id-type="doi">10.1371/journal.pcbi.1011761.s001.pdf</object-id>',
            "<object-id>10.1371/journal.pcbi.1011761.s001</object-id>",
        ],
    )
    def test_an_object_id_that_is_an_identifier_is_not_a_file(self, object_id):
        """A DOI names the object, not its file; a URL built from it cannot resolve."""
        xml = f"""<article {XLINK}><supplementary-material id="s2">
            {object_id}
        </supplementary-material></article>"""
        assert _fetcher(xml).extract_asset_refs() == []

    def test_a_media_child_wins_over_an_object_id(self):
        xml = f"""<article {XLINK}><supplementary-material id="s2">
            <object-id>other.pdf</object-id><media xlink:href="supp2.zip"/>
        </supplementary-material></article>"""
        assets = _fetcher(xml).extract_asset_refs()
        assert [a.metadata["file_name"] for a in assets] == ["supp2.zip"]

    def test_caption_falls_back_to_p_when_no_caption_element(self):
        xml = f"""<article {XLINK}><supplementary-material id="s3" xlink:href="supp3.pdf">
            <p>Just a paragraph.</p>
        </supplementary-material></article>"""
        asset = _fetcher(xml).extract_asset_refs()[0]
        assert "Just a paragraph" in asset.caption

    def test_caption_falls_back_to_the_media_element(self):
        """Nature describes the file on the <media>, not on the block."""
        xml = f"""<article {XLINK}><supplementary-material id="s4">
            <media xlink:href="supp4.pdf"><caption><p>Supplementary Information</p></caption></media>
        </supplementary-material></article>"""
        asset = _fetcher(xml).extract_asset_refs()[0]
        assert asset.caption == "Supplementary Information"

    def test_the_same_file_declared_twice_is_reported_once(self):
        xml = f"""<article {XLINK}><body>
            <supplementary-material id="a"><media xlink:href="supp.pdf"/></supplementary-material>
            <supplementary-material id="b">
                <label>Supp 1</label><media xlink:href="supp.pdf"/>
            </supplementary-material>
        </body></article>"""
        assets = _fetcher(xml).extract_asset_refs()
        assert len(assets) == 1
        # The second declaration fills in what the first left empty.
        assert assets[0].label == "Supp 1"


class TestMediaTypes:
    @pytest.mark.parametrize(
        ("attrs", "expected"),
        [
            ('mimetype="video" mime-subtype="mp4"', AssetType.VIDEO),
            ('mimetype="audio" mime-subtype="mpeg"', AssetType.AUDIO),
            ("", AssetType.UNKNOWN),
        ],
    )
    def test_type_comes_from_the_declared_mime_type(self, attrs, expected):
        xml = f'<article {XLINK}><media xlink:href="a.bin" {attrs}/></article>'
        assert _fetcher(xml).extract_asset_refs()[0].asset_type == expected


class TestHelpers:
    def test_get_xlink_href(self):
        fetcher = _fetcher()
        graphic = fetcher.root.find(".//table-wrap/graphic")
        assert fetcher._get_xlink_href(graphic) == "table1.jpg"

    def test_get_xlink_href_plain_href_fallback(self):
        fetcher = _fetcher()
        elem = DefusedET.fromstring('<graphic href="plain.png"/>')
        assert fetcher._get_xlink_href(elem) == "plain.png"

    def test_get_xlink_href_missing(self):
        fetcher = _fetcher()
        elem = DefusedET.fromstring("<graphic/>")
        assert fetcher._get_xlink_href(elem) == ""

    def test_resolve_uri_absolute_untouched(self):
        fetcher = _fetcher(article_id="PMC1")
        assert fetcher._resolve_uri("https://x/y.png") == "https://x/y.png"

    def test_resolve_uri_relative_with_article_id(self):
        fetcher = _fetcher(article_id="PMC1")
        assert _query(fetcher._resolve_uri("y.png")) == {
            "pmcId": "PMC1",
            "type": "FILE",
            "fileName": "y.png",
            "mimeType": "image/png",
            "version": "1",
        }

    def test_resolve_uri_relative_without_article_id(self):
        fetcher = _fetcher()
        assert fetcher._resolve_uri("y.png") == "y.png"

    def test_resolve_uri_leaves_a_non_pmcid_alone(self):
        fetcher = _fetcher(article_id="28104805")
        assert fetcher._resolve_uri("y.png") == "y.png"

    def test_resolve_uri_empty(self):
        fetcher = _fetcher()
        assert fetcher._resolve_uri("") == ""

    def test_get_local_tag_strips_namespace(self):
        assert ImageFetcher._get_local_tag("{http://ns}graphic") == "graphic"

    def test_get_local_tag_no_namespace(self):
        assert ImageFetcher._get_local_tag("graphic") == "graphic"


class TestDownloadAssets:
    def test_skip_policy_returns_unchanged(self):
        fetcher = _fetcher(policy=AssetFetchPolicy.SKIP, download_dir="/tmp/x")
        assets = [AssetRef(asset_type=AssetType.FIGURE, uri="http://x/y.png")]
        result = fetcher.download_assets(assets)
        assert result[0].local_path == ""

    def test_no_download_dir_returns_unchanged(self):
        fetcher = _fetcher(policy=AssetFetchPolicy.DOWNLOAD)
        assets = [AssetRef(asset_type=AssetType.FIGURE, uri="http://x/y.png")]
        result = fetcher.download_assets(assets)
        assert result[0].local_path == ""

    def test_downloads_and_sets_local_path(self, tmp_path):
        fetcher = _fetcher(policy=AssetFetchPolicy.DOWNLOAD, download_dir=str(tmp_path))
        assets = [AssetRef(asset_type=AssetType.FIGURE, uri="http://x/y.png")]
        with patch.object(fetcher, "_download_single_asset", return_value="/local/y.png"):
            result = fetcher.download_assets(assets)
        assert result[0].local_path == "/local/y.png"

    def test_skips_asset_with_no_uri(self, tmp_path):
        fetcher = _fetcher(policy=AssetFetchPolicy.DOWNLOAD, download_dir=str(tmp_path))
        assets = [AssetRef(asset_type=AssetType.FIGURE, uri="")]
        with patch.object(fetcher, "_download_single_asset") as mock_dl:
            fetcher.download_assets(assets)
        mock_dl.assert_not_called()

    def test_download_missing_skips_existing_local_file(self, tmp_path):
        existing = tmp_path / "already.png"
        existing.write_text("x")
        fetcher = _fetcher(policy=AssetFetchPolicy.DOWNLOAD_MISSING, download_dir=str(tmp_path))
        assets = [
            AssetRef(asset_type=AssetType.FIGURE, uri="http://x/y.png", local_path=str(existing))
        ]
        with patch.object(fetcher, "_download_single_asset") as mock_dl:
            fetcher.download_assets(assets)
        mock_dl.assert_not_called()

    def test_download_exception_is_caught(self, tmp_path):
        fetcher = _fetcher(policy=AssetFetchPolicy.DOWNLOAD, download_dir=str(tmp_path))
        assets = [AssetRef(asset_type=AssetType.FIGURE, uri="http://x/y.png")]
        with patch.object(fetcher, "_download_single_asset", side_effect=RuntimeError("boom")):
            result = fetcher.download_assets(assets)  # must not raise
        assert result[0].local_path == ""


class TestDownloadSingleAsset:
    def test_no_download_dir_returns_empty(self):
        fetcher = _fetcher()
        asset = AssetRef(asset_type=AssetType.FIGURE, uri="http://x/y.png")
        assert fetcher._download_single_asset(asset) == ""

    def test_rejects_non_http_scheme(self, tmp_path):
        fetcher = _fetcher(download_dir=str(tmp_path))
        asset = AssetRef(asset_type=AssetType.FIGURE, uri="file:///etc/passwd")
        assert fetcher._download_single_asset(asset) == ""

    def test_success(self, tmp_path):
        fetcher = _fetcher(download_dir=str(tmp_path))
        asset = AssetRef(asset_type=AssetType.FIGURE, uri="http://x/y.png", id="a1")
        with patch("urllib.request.urlretrieve") as mock_retrieve:
            path = fetcher._download_single_asset(asset)
        assert path.endswith("y.png")
        mock_retrieve.assert_called_once()

    def test_filename_falls_back_to_asset_id(self, tmp_path):
        fetcher = _fetcher(download_dir=str(tmp_path))
        asset = AssetRef(asset_type=AssetType.FIGURE, uri="http://x/?query=1", id="a1")
        with patch("urllib.request.urlretrieve"):
            path = fetcher._download_single_asset(asset)
        assert "a1" in path

    def test_urlretrieve_failure_returns_empty(self, tmp_path):
        fetcher = _fetcher(download_dir=str(tmp_path))
        asset = AssetRef(asset_type=AssetType.FIGURE, uri="http://x/y.png")
        with patch("urllib.request.urlretrieve", side_effect=OSError("network down")):
            assert fetcher._download_single_asset(asset) == ""


class TestResolveFigureUris:
    def test_resolves_relative_uris(self):
        figures = [{"graphic_uri": "fig1.jpg"}, {"graphic_uri": "https://x/fig2.jpg"}]
        result = ImageFetcher.resolve_figure_uris(figures, "PMC123")
        assert result[0]["graphic_uri"].startswith("http")
        assert result[1]["graphic_uri"] == "https://x/fig2.jpg"

    def test_missing_uri_key_untouched(self):
        figures = [{"label": "Fig 1"}]
        result = ImageFetcher.resolve_figure_uris(figures, "PMC123")
        assert "graphic_uri" not in result[0]
