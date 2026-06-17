"""
Image and Asset Fetching for Full-Text Articles.

Fetches figures and supplementary assets referenced in JATS XML.
Supports downloading from PMC OA tar.gz packages or per-file URLs.

Based on patterns from pmcgrab's AssetFetchPolicy.

Reference
---------
- PMC OA service: https://www.ncbi.nlm.nih.gov/pmc/tools/oa-service/
- pmcgrab asset fetching: https://github.com/rajdeepmondaldotcom/pmcgrab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
import os
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# Base URL for PMC article binaries
PMC_BINARY_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles/"


class AssetType(str, Enum):
    """Types of assets that can be fetched."""

    FIGURE = "figure"
    TABLE = "table"
    SUPPLEMENTARY = "supplementary"
    VIDEO = "video"
    AUDIO = "audio"
    UNKNOWN = "unknown"


class AssetFetchPolicy(str, Enum):
    """Policy for fetching assets."""

    SKIP = "skip"  # Don't fetch any assets
    METADATA_ONLY = "metadata_only"  # Only extract metadata/URLs
    DOWNLOAD = "download"  # Download all referenced assets
    DOWNLOAD_MISSING = "download_missing"  # Download only if not already present


@dataclass
class AssetRef:
    """
    Reference to an external asset in the XML.

    Parameters
    ----------
    asset_type : AssetType
        Type of the asset.
    uri : str
        URI or URL of the asset.
    local_path : str, optional
        Local file path after download.
    label : str, optional
        Display label (e.g. ``"Fig. 1"``).
    caption : str, optional
        Caption text.
    id : str, optional
        Element ID from the XML.
    mime_type : str, optional
        MIME type of the asset.
    metadata : dict
        Additional metadata.
    """

    asset_type: AssetType
    uri: str = ""
    local_path: str = ""
    label: str = ""
    caption: str = ""
    id: str = ""
    mime_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "asset_type": self.asset_type.value,
            "uri": self.uri,
            "local_path": self.local_path,
            "label": self.label,
            "caption": self.caption,
            "id": self.id,
            "mime_type": self.mime_type,
            "metadata": self.metadata,
        }


class ImageFetcher(BaseParser):
    """
    Identifies and optionally downloads images/assets referenced in JATS XML.

    Works with the existing ``FigureParser`` results but adds the ability to
    resolve actual file URLs and download them.

    Parameters
    ----------
    root : ET.Element, optional
        Root element of the parsed XML.
    article_id : str, optional
        PMCID or PMID of the article (for URL resolution).
    download_dir : str, optional
        Directory to download assets into.
    policy : AssetFetchPolicy, optional
        Fetch policy (default: METADATA_ONLY).

    Examples
    --------
    >>> fetcher = ImageFetcher(root, article_id="PMC1234567")
    >>> assets = fetcher.extract_asset_refs()
    >>> for asset in assets:
    ...     print(f"{asset.label}: {asset.uri}")
    """

    NS_XLINK = "http://www.w3.org/1999/xlink"

    def __init__(
        self,
        root: ET.Element | None = None,
        article_id: str = "",
        download_dir: str = "",
        policy: AssetFetchPolicy = AssetFetchPolicy.METADATA_ONLY,
    ):
        super().__init__(root)
        self.article_id = article_id
        self.download_dir = download_dir
        self.policy = policy

    def extract_asset_refs(self) -> list[AssetRef]:
        """
        Extract all asset references from the XML.

        Scans for:
        - ``<graphic>`` elements (figures, inline graphics)
        - ``<media>`` elements (video, audio, supplementary)
        - ``<supplementary-material>`` elements

        Returns
        -------
        list[AssetRef]
            List of asset references found in the document.
        """
        self._require_root()

        assets: list[AssetRef] = []

        if self.root is None:
            return assets

        # Extract from <fig> elements
        for fig in self.root.findall(".//fig"):
            assets.extend(self._extract_figure_assets(fig))

        # Extract from standalone <graphic> elements (not inside fig)
        for graphic in self.root.findall(".//graphic"):
            if self._is_inside_fig(graphic):
                continue
            uri = self._get_xlink_href(graphic)
            if uri:
                assets.append(
                    AssetRef(
                        asset_type=AssetType.FIGURE,
                        uri=uri,
                        label="",
                        caption="",
                        id=graphic.get("id", ""),
                    )
                )

        # Extract supplementary materials
        for supp in self.root.findall(".//supplementary-material"):
            assets.append(self._extract_supplementary_asset(supp))

        # Extract media elements (video, audio)
        for media in self.root.findall(".//media"):
            assets.append(self._extract_media_asset(media))

        # Resolve relative URIs if we have an article ID
        if self.article_id:
            for asset in assets:
                asset.uri = self._resolve_uri(asset.uri)

        logger.info(f"Extracted {len(assets)} asset references from XML")
        return assets

    def _extract_figure_assets(self, fig_elem: ET.Element) -> list[AssetRef]:
        """Extract asset references from a <fig> element."""
        assets: list[AssetRef] = []

        fig_id = fig_elem.get("id", "")

        # Label
        label = ""
        label_elem = fig_elem.find("label")
        if label_elem is not None:
            label = self._get_text_content(label_elem)

        # Caption
        caption = ""
        caption_elem = fig_elem.find("caption")
        if caption_elem is not None:
            caption = self._get_text_content(caption_elem)

        # Graphics
        for graphic in fig_elem.findall(".//graphic"):
            uri = self._get_xlink_href(graphic)
            mime = graphic.get("mimetype", "")
            if uri:
                assets.append(
                    AssetRef(
                        asset_type=AssetType.FIGURE,
                        uri=uri,
                        label=label,
                        caption=caption,
                        id=fig_id,
                        mime_type=mime,
                    )
                )

        # Alternative representations
        for alt in fig_elem.findall(".//alternatives"):
            for graphic in alt.findall(".//graphic"):
                uri = self._get_xlink_href(graphic)
                if uri:
                    mime = graphic.get("mimetype", "")
                    assets.append(
                        AssetRef(
                            asset_type=AssetType.FIGURE,
                            uri=uri,
                            label=label,
                            caption=caption,
                            id=fig_id,
                            mime_type=mime,
                        )
                    )

        return assets

    def _extract_supplementary_asset(self, supp_elem: ET.Element) -> AssetRef:
        """Extract asset reference from a <supplementary-material> element."""
        supp_id = supp_elem.get("id", "")

        # Label
        label = ""
        label_elem = supp_elem.find("label")
        if label_elem is not None:
            label = self._get_text_content(label_elem)

        # Caption / description
        caption = ""
        caption_elem = supp_elem.find("caption") or supp_elem.find("p")
        if caption_elem is not None:
            caption = self._get_text_content(caption_elem)

        # Get the actual file reference
        uri = ""
        for child in supp_elem:
            tag = self._get_local_tag(child.tag)
            if tag in ("graphic", "media", "inline-graphic"):
                uri = self._get_xlink_href(child)
                if uri:
                    break

        # Try object-id for the filename
        if not uri:
            obj_id = supp_elem.find("object-id")
            if obj_id is not None and obj_id.text:
                uri = obj_id.text.strip()

        return AssetRef(
            asset_type=AssetType.SUPPLEMENTARY,
            uri=uri,
            label=label,
            caption=caption,
            id=supp_id,
        )

    def _extract_media_asset(self, media_elem: ET.Element) -> AssetRef:
        """Extract asset reference from a <media> element."""
        media_id = media_elem.get("id", "")
        uri = self._get_xlink_href(media_elem)
        mime = media_elem.get("mimetype", "")
        mime_subtype = media_elem.get("mime-subtype", "")
        full_mime = f"{mime}/{mime_subtype}" if mime else ""

        # Determine asset type from MIME
        asset_type = AssetType.UNKNOWN
        if "video" in full_mime:
            asset_type = AssetType.VIDEO
        elif "audio" in full_mime:
            asset_type = AssetType.AUDIO

        # Label
        label = ""
        label_elem = media_elem.find("label")
        if label_elem is not None:
            label = self._get_text_content(label_elem)

        return AssetRef(
            asset_type=asset_type,
            uri=uri,
            label=label,
            id=media_id,
            mime_type=full_mime,
        )

    def download_assets(self, asset_refs: list[AssetRef]) -> list[AssetRef]:
        """
        Download assets to the local download directory.

        Requires ``download_dir`` to be set and policy to allow downloads.

        Parameters
        ----------
        asset_refs : list[AssetRef]
            Asset references to download.

        Returns
        -------
        list[AssetRef]
            Updated asset references with local paths filled in.
        """
        if self.policy not in (
            AssetFetchPolicy.DOWNLOAD,
            AssetFetchPolicy.DOWNLOAD_MISSING,
        ):
            logger.info("Policy does not allow downloads, skipping")
            return asset_refs

        if not self.download_dir:
            logger.warning("No download directory set, cannot download assets")
            return asset_refs

        os.makedirs(self.download_dir, exist_ok=True)

        for asset in asset_refs:
            if not asset.uri:
                continue

            # Check if already downloaded
            if (
                self.policy == AssetFetchPolicy.DOWNLOAD_MISSING
                and asset.local_path
                and os.path.exists(asset.local_path)
            ):
                continue

            try:
                local_path = self._download_single_asset(asset)
                if local_path:
                    asset.local_path = local_path
            except Exception as e:
                logger.warning(f"Failed to download {asset.uri}: {e}")

        return asset_refs

    def _download_single_asset(self, asset: AssetRef) -> str:
        """Download a single asset and return the local path."""
        import urllib.request

        if not self.download_dir:
            return ""

        # Determine filename from URI
        filename = os.path.basename(asset.uri.split("?")[0])
        if not filename:
            filename = f"{asset.id or 'asset'}.bin"

        local_path = os.path.join(self.download_dir, filename)

        try:
            urllib.request.urlretrieve(asset.uri, local_path)  # nosec
            logger.info(f"Downloaded {asset.uri} -> {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Download failed for {asset.uri}: {e}")
            return ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_xlink_href(self, elem: ET.Element) -> str:
        """Get the xlink:href attribute from an element."""
        return elem.get(f"{{{self.NS_XLINK}}}href") or elem.get("href") or ""

    def _resolve_uri(self, uri: str) -> str:
        """Resolve a possibly-relative URI to an absolute URL."""
        if not uri:
            return ""

        if uri.startswith(("http://", "https://", "ftp://")):
            return uri  # Already absolute

        # Resolve relative to the PMC article page
        if self.article_id:
            base = f"{PMC_BINARY_BASE}{self.article_id}/"
            return urljoin(base, uri)

        return uri

    @staticmethod
    def _is_inside_fig(elem: ET.Element) -> bool:
        """Check if an element is inside a <fig> element."""
        parent: ET.Element | None = elem
        while parent is not None:
            if parent.tag == "fig" or parent.tag.endswith("}fig"):
                return True
            parent = parent.find("..")
        return False

    @staticmethod
    def _get_local_tag(tag: str) -> str:
        """Strip namespace from a tag name."""
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def resolve_figure_uris(
        cls,
        figures: list[dict[str, Any]],
        article_id: str,
    ) -> list[dict[str, Any]]:
        """
        Resolve figure graphic URIs to absolute URLs using article ID.

        Useful when you already have figure data from ``FigureParser``
        and just need to resolve the URIs.

        Parameters
        ----------
        figures : list[dict]
            Figure dicts from ``FigureParser.extract_figures()``.
        article_id : str
            PMCID or PMID for URL resolution.

        Returns
        -------
        list[dict]
            Updated figure dicts with resolved URIs.
        """
        for fig in figures:
            uri = fig.get("graphic_uri", "")
            if uri and not uri.startswith(("http://", "https://")):
                base = f"{PMC_BINARY_BASE}{article_id}/"
                fig["graphic_uri"] = urljoin(base, uri)
        return figures
