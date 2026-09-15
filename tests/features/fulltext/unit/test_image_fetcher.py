"""Unit tests for pyeuropepmc.features.fulltext.extensions.image_fetcher."""

from __future__ import annotations

from unittest.mock import patch

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
      <caption><p>First figure.</p></caption>
      <graphic xlink:href="fig1.jpg" mimetype="image"/>
      <alternatives>
        <graphic xlink:href="fig1-hires.tif"/>
      </alternatives>
    </fig>
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
        assert AssetType.FIGURE in types
        assert AssetType.SUPPLEMENTARY in types
        assert AssetType.VIDEO in types

    def test_figure_includes_alternatives(self):
        fetcher = _fetcher()
        assets = fetcher.extract_asset_refs()
        uris = {a.uri for a in assets if a.asset_type == AssetType.FIGURE}
        assert "fig1.jpg" in uris
        assert "fig1-hires.tif" in uris

    def test_standalone_graphic_included_once(self):
        fetcher = _fetcher()
        assets = fetcher.extract_asset_refs()
        standalone = [a for a in assets if a.uri == "standalone.png"]
        assert len(standalone) == 1

    def test_uris_resolved_when_article_id_set(self):
        fetcher = _fetcher(article_id="PMC1234567")
        assets = fetcher.extract_asset_refs()
        fig = next(a for a in assets if a.uri.endswith("fig1.jpg"))
        assert fig.uri.startswith("http")

    def test_no_assets_returns_empty(self):
        fetcher = _fetcher(f"<article {XLINK}><body/></article>")
        assert fetcher.extract_asset_refs() == []


class TestExtractSupplementaryAsset:
    def test_uses_media_child_uri(self):
        fetcher = _fetcher()
        root = fetcher.root
        supp = root.find(".//supplementary-material")
        asset = fetcher._extract_supplementary_asset(supp)
        assert asset.uri == "supp1.zip"
        assert asset.label == "Supp 1"
        assert "Extra data" in asset.caption

    def test_falls_back_to_object_id(self):
        xml = f"""<article {XLINK}><supplementary-material id="s2">
            <object-id> supp2.pdf </object-id>
        </supplementary-material></article>"""
        fetcher = _fetcher(xml)
        supp = fetcher.root.find(".//supplementary-material")
        asset = fetcher._extract_supplementary_asset(supp)
        assert asset.uri == "supp2.pdf"

    def test_caption_falls_back_to_p_when_no_caption_element(self):
        xml = f"""<article {XLINK}><supplementary-material id="s3">
            <p>Just a paragraph.</p>
        </supplementary-material></article>"""
        fetcher = _fetcher(xml)
        supp = fetcher.root.find(".//supplementary-material")
        asset = fetcher._extract_supplementary_asset(supp)
        assert "Just a paragraph" in asset.caption


class TestExtractMediaAsset:
    def test_video_type_detected(self):
        xml = f'<article {XLINK}><media xlink:href="v.mp4" mimetype="video" mime-subtype="mp4"/></article>'
        fetcher = _fetcher(xml)
        media = fetcher.root.find(".//media")
        asset = fetcher._extract_media_asset(media)
        assert asset.asset_type == AssetType.VIDEO
        assert asset.mime_type == "video/mp4"

    def test_audio_type_detected(self):
        xml = f'<article {XLINK}><media xlink:href="a.mp3" mimetype="audio" mime-subtype="mpeg"/></article>'
        fetcher = _fetcher(xml)
        media = fetcher.root.find(".//media")
        asset = fetcher._extract_media_asset(media)
        assert asset.asset_type == AssetType.AUDIO

    def test_unknown_type_when_no_mime(self):
        xml = f'<article {XLINK}><media xlink:href="a.bin"/></article>'
        fetcher = _fetcher(xml)
        media = fetcher.root.find(".//media")
        asset = fetcher._extract_media_asset(media)
        assert asset.asset_type == AssetType.UNKNOWN


class TestHelpers:
    def test_get_xlink_href(self):
        fetcher = _fetcher()
        graphic = fetcher.root.find(".//graphic")
        assert fetcher._get_xlink_href(graphic) == "fig1.jpg"

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
        result = fetcher._resolve_uri("y.png")
        assert "PMC1" in result

    def test_resolve_uri_relative_without_article_id(self):
        fetcher = _fetcher()
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
