"""
Image and Asset Fetching for Full-Text Articles.

Fetches figures and supplementary assets referenced in JATS XML.
Each file-bearing element is reported once, labelled by the block that owns
it, with the Europe PMC URL the file can be downloaded from.

Based on patterns from pmcgrab's AssetFetchPolicy.

Reference
---------
- PMC OA service: https://www.ncbi.nlm.nih.gov/pmc/tools/oa-service/
- pmcgrab asset fetching: https://github.com/rajdeepmondaldotcom/pmcgrab
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import logging
import os
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser
from pyeuropepmc.features.fulltext.utils.asset_urls import (
    DEFAULT_IMAGE_EXTENSION,
    asset_file_name,
    build_asset_url,
    guess_mime_type,
)
from pyeuropepmc.features.fulltext.utils.figure_assets import (
    FILE_TAGS,
    local_tag,
    own_graphics,
    parent_figure_map,
    supplementary_href,
)
from pyeuropepmc.features.fulltext.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)

#: Elements that name a file. ``<supplementary-material>`` usually delegates to
#: a ``<media>`` child, but can name the file itself (see ``supplementary_href``).
_ASSET_TAGS = FILE_TAGS | {"supplementary-material"}

#: Tags whose file name may be written without an extension.
_EXTENSIONLESS_TAGS = frozenset({"graphic", "inline-graphic"})


class AssetType(str, Enum):
    """Types of assets that can be fetched."""

    FIGURE = "figure"
    TABLE = "table"
    SUPPLEMENTARY = "supplementary"
    FORMULA = "formula"
    VIDEO = "video"
    AUDIO = "audio"
    UNKNOWN = "unknown"


#: What such an element is when no block claims it. A <media> is absent: its
#: type comes from its own MIME type.
_UNCLAIMED_TYPES = {"graphic": AssetType.FIGURE, "inline-graphic": AssetType.UNKNOWN}


@dataclass(frozen=True)
class _Owner:
    """What a file-bearing element inherits from the block that contains it."""

    asset_type: AssetType
    label: str = ""
    caption: str = ""
    id: str = ""
    parent_id: str = ""
    parent_label: str = ""
    alternative: bool = False


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
        PMCID of the article, used to build Europe PMC download URLs. Without
        one - or with an identifier that is not a PMCID - each ``uri`` stays
        the file name written in the XML.
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

        One reference per file-bearing element - ``<graphic>``, ``<inline-graphic>``
        and ``<media>`` - in document order, labelled by whatever contains it:
        a figure, a table, a supplementary-material block or a formula.

        This used to search for each kind separately, so most files were
        reported several times: every graphic inside a figure was added again by
        the pass over "standalone" graphics (``_is_inside_fig`` could never say
        otherwise, since ElementTree has no parent axis), and every ``<media>``
        inside supplementary material was added again by the pass over media.

        Returns
        -------
        list[AssetRef]
            List of asset references found in the document.
        """
        self._require_root()

        if self.root is None:
            return []

        owners = self._asset_owners(self.root)

        assets: list[AssetRef] = []
        seen: dict[tuple[str, str], AssetRef] = {}
        for elem in self.root.iter():
            tag = local_tag(elem.tag)
            if tag not in _ASSET_TAGS:
                continue
            asset = self._build_asset(elem, tag, owners.get(elem))
            if asset is None:
                continue
            # Publishers do repeat a declaration: Nature articles list each
            # supplementary file twice, once in the body and once in the back
            # matter, with identical <media>. One file, one reference.
            key = (asset.asset_type.value, asset.metadata["file_name"])
            kept = seen.get(key)
            if kept is None:
                seen[key] = asset
                assets.append(asset)
            else:
                self._merge_duplicate(kept, asset)

        logger.info(f"Extracted {len(assets)} asset references from XML")
        return assets

    @staticmethod
    def _merge_duplicate(kept: AssetRef, other: AssetRef) -> None:
        """Fill in what the first declaration of a file left empty."""
        kept.label = kept.label or other.label
        kept.caption = kept.caption or other.caption
        kept.id = kept.id or other.id

    def _asset_owners(self, root: ET.Element) -> dict[ET.Element, _Owner]:
        """Maps each file-bearing element to the block that describes it.

        Only the elements a block owns directly are claimed, so a caption's
        formula images stay with the formula and a nested figure supplement's
        image stays with the supplement rather than being labelled as its
        parent figure.
        """
        owners: dict[ET.Element, _Owner] = {}
        parents = parent_figure_map(root)

        for elem in root.iter():
            tag = local_tag(elem.tag)
            if tag == "fig":
                parent = parents.get(elem)
                owner = _Owner(
                    asset_type=AssetType.FIGURE,
                    label=self._label_of(elem),
                    caption=self._caption_of(elem),
                    id=elem.get("id", ""),
                    parent_id=parent.get("id", "") if parent is not None else "",
                    parent_label=self._label_of(parent) if parent is not None else "",
                )
                self._claim_graphics(owners, elem, owner)
            elif tag == "table-wrap":
                owner = _Owner(
                    asset_type=AssetType.TABLE,
                    label=self._label_of(elem),
                    caption=self._caption_of(elem),
                    id=elem.get("id", ""),
                )
                self._claim_graphics(owners, elem, owner)
            elif tag == "supplementary-material":
                self._claim_supplementary(owners, elem)
            elif tag in ("inline-formula", "disp-formula"):
                owner = _Owner(
                    asset_type=AssetType.FORMULA,
                    label=self._label_of(elem),
                    id=elem.get("id", ""),
                )
                for descendant in elem.iter():
                    if local_tag(descendant.tag) in ("graphic", "inline-graphic"):
                        owners.setdefault(descendant, owner)

        return owners

    @staticmethod
    def _claim_graphics(owners: dict[ET.Element, _Owner], elem: ET.Element, owner: _Owner) -> None:
        """Claim the graphics ``elem`` carries itself, first one primary."""
        for position, graphic in enumerate(own_graphics(elem)):
            owners.setdefault(
                graphic, owner if position == 0 else replace(owner, alternative=True)
            )

    def _claim_supplementary(self, owners: dict[ET.Element, _Owner], elem: ET.Element) -> None:
        """Claim the file a ``<supplementary-material>`` block points at."""
        owner = _Owner(
            asset_type=AssetType.SUPPLEMENTARY,
            label=self._label_of(elem),
            caption=self._supplementary_caption(elem),
            id=elem.get("id", ""),
        )
        # The block itself, for when it names the file without a file child;
        # it yields no asset otherwise.
        owners.setdefault(elem, owner)
        for child in elem:
            if local_tag(child.tag) in FILE_TAGS:
                owners.setdefault(child, owner)

    def _build_asset(self, elem: ET.Element, tag: str, owner: _Owner | None) -> AssetRef | None:
        """Turn one file-bearing element into an :class:`AssetRef`."""
        if tag == "supplementary-material":
            href = supplementary_href(elem)
        else:
            href = self._get_xlink_href(elem)
        if not href:
            return None

        if owner is None:
            # Nothing claims this file. A <graphic> standing on its own is still
            # a figure - a graphical abstract, an image dropped into a section.
            # An <inline-graphic> is not: it is an image inside a line of text,
            # such as the ORCID icon beside an author's name. A <media> is typed
            # from its own MIME type.
            owner = _Owner(
                asset_type=_UNCLAIMED_TYPES.get(tag) or self._media_asset_type(elem),
                id=elem.get("id", ""),
            )

        # A graphic's file name may be written without an extension; a media
        # file's may not (see asset_urls).
        default_extension = DEFAULT_IMAGE_EXTENSION if tag in _EXTENSIONLESS_TAGS else None
        file_name = asset_file_name(href, default_extension)
        mime_type = self._declared_mime(elem) or guess_mime_type(file_name)

        # Nature puts the description on the <media> rather than on the
        # <supplementary-material> around it, so the block's caption is empty
        # while "Supplementary Information" sits one level down.
        caption = owner.caption or self._caption_of(elem)

        metadata: dict[str, Any] = {"file_name": file_name, "jats_tag": tag}
        if owner.alternative:
            metadata["alternative"] = True
        if owner.parent_id or owner.parent_label:
            metadata["parent_id"] = owner.parent_id
            metadata["parent_label"] = owner.parent_label

        url = build_asset_url(self.article_id, href, self._declared_mime(elem), default_extension)

        return AssetRef(
            asset_type=owner.asset_type,
            uri=url or href,
            label=owner.label,
            caption=caption,
            id=owner.id or elem.get("id", ""),
            mime_type=mime_type,
            metadata=metadata,
        )

    @staticmethod
    def _media_asset_type(elem: ET.Element) -> AssetType:
        """VIDEO, AUDIO or UNKNOWN, from a ``<media>`` element's MIME type."""
        mime = ImageFetcher._declared_mime(elem)
        if "video" in mime:
            return AssetType.VIDEO
        if "audio" in mime:
            return AssetType.AUDIO
        return AssetType.UNKNOWN

    @staticmethod
    def _declared_mime(elem: ET.Element) -> str:
        """The MIME type the element states, as ``type/subtype``."""
        mimetype = elem.get("mimetype", "")
        subtype = elem.get("mime-subtype", "")
        if mimetype and subtype:
            return f"{mimetype}/{subtype}"
        return mimetype or ""

    def _label_of(self, elem: ET.Element | None) -> str:
        if elem is None:
            return ""
        label = elem.find("label")
        return self._get_text_content(label) if label is not None else ""

    def _caption_of(self, elem: ET.Element) -> str:
        """The block's caption, without the text of any figure nested in it."""
        caption = elem.find("caption")
        if caption is None:
            return ""
        return XMLHelper.get_text_content(caption, exclude_tags=frozenset({"fig"}))

    def _supplementary_caption(self, elem: ET.Element) -> str:
        # `or`-chaining Element.find() is unsafe: a childless <caption>text</caption>
        # is falsy, so `or` would skip a real match and fall through to <p>.
        caption = self._caption_of(elem)
        if caption:
            return caption
        paragraph = elem.find("p")
        return self._get_text_content(paragraph) if paragraph is not None else ""

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
        import urllib.parse
        import urllib.request

        if not self.download_dir:
            return ""

        # Validate URI scheme to prevent SSRF / file:// attacks
        parsed = urllib.parse.urlparse(asset.uri)
        if parsed.scheme not in ("http", "https"):
            logger.warning(
                f"Skipping asset with unsupported scheme '{parsed.scheme}': {asset.uri}"
            )
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

    def _resolve_uri(self, uri: str, default_extension: str | None = None) -> str:
        """Resolve a JATS file reference to a Europe PMC download URL.

        Returns ``uri`` unchanged when it is already absolute, and when
        ``article_id`` is not a PMC ID: the download endpoint is addressed by
        PMCID, so a PMID or a DOI cannot name a file there, and the URL the
        previous implementation built from one - the article page address with
        the file name appended - answered 404.
        """
        if not uri:
            return ""

        if uri.startswith(("http://", "https://", "ftp://")):
            return uri  # Already absolute

        return build_asset_url(self.article_id, uri, default_extension=default_extension) or uri

    @staticmethod
    def _get_local_tag(tag: str) -> str:
        """Strip namespace from a tag name."""
        return local_tag(tag)

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
            PMCID for URL resolution. A value that is not a PMC ID leaves the
            file names as they are, rather than building a URL that cannot
            resolve.

        Returns
        -------
        list[dict]
            Updated figure dicts with resolved URIs.
        """
        for fig in figures:
            uri = fig.get("graphic_uri", "")
            if uri and not uri.startswith(("http://", "https://")):
                resolved = build_asset_url(
                    article_id, uri, default_extension=DEFAULT_IMAGE_EXTENSION
                )
                if resolved:
                    fig["graphic_uri"] = resolved
        return figures
