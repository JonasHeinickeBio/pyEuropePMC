"""
Figure extraction from PubMed Central (PMC) Open Access articles.

Extracts figures, tables, and supplementary materials from the full-text XML
Europe PMC serves, with the Europe PMC download URL of each file.

References:
    - Europe PMC REST API: https://europepmc.org/RestfulWebService
    - PMC Open Access Subset: https://www.ncbi.nlm.nih.gov/pmc/tools/oa-service/
"""

from __future__ import annotations

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.features.fulltext.utils.asset_urls import (
    DEFAULT_IMAGE_EXTENSION,
    asset_file_name,
    build_asset_url,
    guess_mime_type,
    normalise_pmcid,
)
from pyeuropepmc.features.fulltext.utils.figure_assets import (
    local_tag,
    own_graphic,
    parent_figure_map,
)
from pyeuropepmc.features.fulltext.utils.xml_helpers import XMLHelper

# Lazy imports to avoid circular dependency with clients → processing → clients
# FullTextClient and AnnotationsClient imported only when needed

logger = logging.getLogger(__name__)

__all__ = [
    "FigureExtractor",
    "FigureInfo",
    "extract_figures_from_pmc",
    "extract_tables_from_pmc",
    "FigureFormat",
]


class FigureFormat:
    """Constants for figure output formats."""

    PNG = "png"
    JPEG = "jpg"
    SVG = "svg"
    TIFF = "tiff"
    ALL = "all"


class FigureInfo:
    """
    Metadata for a single figure extracted from a PMC article.

    Attributes
    ----------
    label : str
        Figure label (e.g., "Fig. 1", "Figure 2").
    caption : str
        Figure caption text.
    alt_text : str, optional
        Alternative text description.
    image_url : str, optional
        Europe PMC download URL for the file, or ``None`` when the element
        references no file or the PMCID is unknown.
    pdf_url : str, optional
        URL to the PDF version containing the figure.
    figure_type : str
        Type: "figure", "table", "supplement", "graphic".
    doi : str, optional
        DOI of the article.
    pmcid : str, optional
        PMCID of the article.
    width : int, optional
        Image width in pixels.
    height : int, optional
        Image height in pixels.
    id : str, optional
        The element's ``id`` attribute, as referenced by ``<xref>``.
    file_name : str, optional
        The file the element references, as Europe PMC stores it.
    mime_type : str, optional
        MIME type of that file.
    parent_id : str, optional
        For a figure supplement, the ``id`` of the figure it belongs to;
        ``None`` for a figure that stands on its own.
    parent_label : str, optional
        That figure's label.
    """

    def __init__(
        self,
        label: str,
        caption: str,
        alt_text: str | None = None,
        image_url: str | None = None,
        pdf_url: str | None = None,
        figure_type: str = "figure",
        doi: str | None = None,
        pmcid: str | None = None,
        width: int | None = None,
        height: int | None = None,
        id: str | None = None,  # noqa: A002 - matches the JATS attribute name
        file_name: str | None = None,
        mime_type: str | None = None,
        parent_id: str | None = None,
        parent_label: str | None = None,
    ) -> None:
        self.label = label
        self.caption = caption
        self.alt_text = alt_text
        self.image_url = image_url
        self.pdf_url = pdf_url
        self.figure_type = figure_type
        self.doi = doi
        self.pmcid = pmcid
        self.width = width
        self.height = height
        self.id = id
        self.file_name = file_name
        self.mime_type = mime_type
        self.parent_id = parent_id
        self.parent_label = parent_label

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "label": self.label,
            "caption": self.caption,
            "alt_text": self.alt_text,
            "image_url": self.image_url,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
            "pdf_url": self.pdf_url,
            "figure_type": self.figure_type,
            "parent_id": self.parent_id,
            "parent_label": self.parent_label,
            "doi": self.doi,
            "pmcid": self.pmcid,
        }

    def __repr__(self) -> str:
        return f"<FigureInfo {self.label} ({self.figure_type})>"


class FigureExtractor:
    """
    Extracts figures, tables, and graphics from PMC XML articles.

    Reads the full-text XML from Europe PMC and reports every ``<fig>``,
    ``<table-wrap>`` and ``<supplementary-material>`` in it, each with the
    Europe PMC download URL of the file it references.

    Examples
    --------
    >>> extractor = FigureExtractor()
    >>> figures = extractor.extract(pmcid="PMC1234567")
    >>> for f in figures:
    ...     print(f.label, f.image_url, f.caption[:80])
    """

    def __init__(
        self,
        timeout: int = 30,
    ) -> None:
        # Lazy imports to avoid circular dependency
        from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient
        from pyeuropepmc.features.literature.search import SearchClient

        self.fulltext_client = FullTextClient(rate_limit_delay=1.0, enable_cache=True)
        self.search_client = SearchClient(rate_limit_delay=1.0)

    # ------------------------------------------------------------------
    # Main extraction
    # ------------------------------------------------------------------

    def extract(
        self,
        pmcid: str | None = None,
        pmid: str | None = None,
        doi: str | None = None,
        include_tables: bool = True,
        include_supplements: bool = True,
        format: str = FigureFormat.ALL,
    ) -> list[FigureInfo]:
        """
        Extract figures from a PMC article.

        Parameters
        ----------
        pmcid : str, optional
            PMCID of the article.
        pmid : str, optional
            PubMed ID (alternative to PMCID).
        doi : str, optional
            DOI (alternative to PMCID).
        include_tables : bool, optional
            Whether to include tables as extractable items.
        include_supplements : bool, optional
            Whether to include supplementary materials.
        format : str, optional
            Image format filter.

        Returns
        -------
        list[FigureInfo]
            Extracted figures and their metadata.
        """
        # Resolve identifier to PMCID if needed
        resolved_pmcid = pmcid or self._resolve_pmcid(pmid=pmid, doi=doi)
        if not resolved_pmcid:
            logger.warning("Could not resolve PMCID for pmid=%s doi=%s", pmid, doi)
            return []

        # Fetch the full-text XML
        try:
            xml_str = self.fulltext_client.get_fulltext_content(resolved_pmcid, format_type="xml")
        except Exception as exc:  # noqa: BLE001 - any retrieval failure -> no figures
            logger.warning("No full-text XML available for %s: %s", resolved_pmcid, exc)
            return []
        if not xml_str:
            logger.warning("No full-text XML available for %s", resolved_pmcid)
            return []

        return self._extract_from_xml(
            xml_str,
            pmcid=resolved_pmcid,
            include_tables=include_tables,
            include_supplements=include_supplements,
            format=format,
        )

    def extract_from_xml(
        self,
        xml_str: str,
        pmcid: str | None = None,
        include_tables: bool = True,
        include_supplements: bool = True,
        format: str = FigureFormat.ALL,
    ) -> list[FigureInfo]:
        """
        Extract figures from raw PMC XML string.

        Parameters
        ----------
        xml_str : str
            PMC full-text XML as string.
        pmcid : str, optional
            PMCID (for constructing image URLs).
        include_tables, include_supplements, format
            Same as extract().

        Returns
        -------
        list[FigureInfo]
        """
        return self._extract_from_xml(
            xml_str,
            pmcid=pmcid,
            include_tables=include_tables,
            include_supplements=include_supplements,
            format=format,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_pmcid(
        self,
        pmid: str | None = None,
        doi: str | None = None,
    ) -> str | None:
        """Resolve a PMID or DOI to a PMCID via a Europe PMC lookup."""
        if pmid:
            query = f"EXT_ID:{pmid} AND SRC:MED"
        elif doi:
            query = f'DOI:"{doi}"'
        else:
            return None
        try:
            records = self.search_client.search_and_parse(query, format="json", pageSize=1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PMCID lookup failed for pmid=%s doi=%s: %s", pmid, doi, exc)
            return None
        if records:
            pmcid = records[0].get("pmcid")
            if pmcid:
                return str(pmcid)
        return None

    def _extract_from_xml(
        self,
        xml_str: str,
        pmcid: str | None = None,
        include_tables: bool = True,
        include_supplements: bool = True,
        format: str = FigureFormat.ALL,
    ) -> list[FigureInfo]:
        """Parse XML and extract figure elements.

        Parsing goes through ``FullTextXMLParser`` so that a schema-based JATS
        document, whose tags carry a default namespace, is matched by the same
        unprefixed searches as the DTD-based JATS Europe PMC serves. Searching
        for namespaced tags directly - as this did for the JATS1 namespace, which
        Europe PMC documents do not use - found nothing in either form.
        """
        figures: list[FigureInfo] = []

        try:
            root: ET.Element | None = FullTextXMLParser(xml_str).root
        except ParsingError as e:
            logger.error("XML parse error: %s", e)
            return figures
        if root is None:
            return figures

        parents = parent_figure_map(root)

        for elem in root.iter():
            tag = local_tag(elem.tag)
            if tag == "fig":
                item = self._parse_figure_element(elem, pmcid, parents.get(elem))
            elif tag == "table-wrap" and include_tables:
                item = self._parse_table_element(elem, pmcid)
            elif tag == "supplementary-material" and include_supplements:
                item = self._parse_supplement_element(elem, pmcid)
            else:
                continue
            if item is not None and self._matches_format(item, format):
                figures.append(item)

        return figures

    @staticmethod
    def _matches_format(figure: FigureInfo, format: str) -> bool:
        """Whether ``figure`` passes the ``format`` filter.

        Items with no file pass any filter: a table rendered as markup, or a
        figure whose graphic the publisher did not deposit, is not the wrong
        image format - it has no image to judge. Formats are compared by MIME
        type, so ``FigureFormat.TIFF`` matches a ``.tif`` file and ``jpg`` a
        ``.jpeg`` one.
        """
        if format == FigureFormat.ALL or not figure.file_name:
            return True
        wanted = format.lower().lstrip(".")
        if figure.file_name.lower().endswith(f".{wanted}"):
            return True
        wanted_mime = guess_mime_type(f"x.{wanted}")
        # An unrecognised format guesses the same fallback type as any
        # unrecognised file, which would match everything.
        if wanted_mime == guess_mime_type("x.unknown"):
            return False
        return guess_mime_type(figure.file_name) == wanted_mime

    @staticmethod
    def _label_of(elem: ET.Element) -> str:
        label = elem.find("label")
        return XMLHelper.get_text_content(label).strip() if label is not None else ""

    @staticmethod
    def _caption_of(elem: ET.Element) -> str:
        """The element's caption, with any nested figure's text left out.

        An eLife figure carries its supplements inside its own ``<p>``; those
        sit outside ``<caption>``, but a publisher that puts one inside would
        otherwise have the supplement's caption appended to its parent's.
        """
        caption = elem.find("caption")
        if caption is None:
            return ""
        return XMLHelper.get_text_content(caption, exclude_tags=frozenset({"fig"})).strip()

    def _file_fields(
        self,
        source: ET.Element | None,
        pmcid: str | None,
        default_extension: str | None = None,
    ) -> tuple[str | None, str | None, str | None]:
        """``(file_name, mime_type, image_url)`` for a ``<graphic>`` or ``<media>``."""
        if source is None:
            return None, None, None
        href = source.get("{http://www.w3.org/1999/xlink}href") or source.get("href") or ""
        if not href:
            return None, None, None

        mimetype = source.get("mimetype", "")
        subtype = source.get("mime-subtype", "")
        declared = f"{mimetype}/{subtype}" if mimetype and subtype else ""

        file_name = asset_file_name(href, default_extension)
        mime_type = declared or guess_mime_type(file_name)
        url = build_asset_url(pmcid, href, declared, default_extension)
        return file_name, mime_type, url

    def _parse_figure_element(
        self,
        elem: ET.Element,
        pmcid: str | None,
        parent: ET.Element | None = None,
    ) -> FigureInfo | None:
        """Parse a single ``<fig>`` JATS element."""
        alt_elem = elem.find("alt-text")
        alt_text = XMLHelper.get_text_content(alt_elem).strip() if alt_elem is not None else None

        file_name, mime_type, image_url = self._file_fields(
            own_graphic(elem), pmcid, DEFAULT_IMAGE_EXTENSION
        )

        return FigureInfo(
            label=self._label_of(elem) or "Figure",
            caption=self._caption_of(elem),
            alt_text=alt_text or None,
            image_url=image_url,
            figure_type="figure",
            pmcid=normalise_pmcid(pmcid) or pmcid,
            id=elem.get("id") or None,
            file_name=file_name,
            mime_type=mime_type,
            parent_id=(parent.get("id") or None) if parent is not None else None,
            parent_label=self._label_of(parent) or None if parent is not None else None,
        )

    def _parse_table_element(
        self,
        elem: ET.Element,
        pmcid: str | None,
    ) -> FigureInfo | None:
        """Parse a ``<table-wrap>`` JATS element.

        A table can also be deposited as an image, in an ``<alternatives>``
        beside the markup; that image is the table's file.
        """
        file_name, mime_type, image_url = self._file_fields(
            own_graphic(elem), pmcid, DEFAULT_IMAGE_EXTENSION
        )

        return FigureInfo(
            label=self._label_of(elem) or "Table",
            caption=self._caption_of(elem),
            image_url=image_url,
            figure_type="table",
            pmcid=normalise_pmcid(pmcid) or pmcid,
            id=elem.get("id") or None,
            file_name=file_name,
            mime_type=mime_type,
        )

    def _parse_supplement_element(
        self,
        elem: ET.Element,
        pmcid: str | None,
    ) -> FigureInfo | None:
        """Parse a ``<supplementary-material>`` JATS element."""
        source = None
        for child in elem:
            if local_tag(child.tag) in ("media", "graphic", "inline-graphic"):
                source = child
                break

        file_name, mime_type, image_url = self._file_fields(source, pmcid)

        description = self._caption_of(elem)
        if not description:
            paragraph = elem.find("p")
            if paragraph is not None:
                description = XMLHelper.get_text_content(paragraph).strip()

        return FigureInfo(
            label=self._label_of(elem) or "Supplementary Material",
            caption=description,
            image_url=image_url,
            figure_type="supplement",
            pmcid=normalise_pmcid(pmcid) or pmcid,
            id=elem.get("id") or None,
            file_name=file_name,
            mime_type=mime_type,
        )


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------


def extract_figures_from_pmc(
    pmcid: str | None = None,
    pmid: str | None = None,
    doi: str | None = None,
    include_tables: bool = True,
    include_supplements: bool = True,
) -> list[FigureInfo]:
    """
    Convenience function to extract figures from a PMC article.

    Parameters
    ----------
    pmcid, pmid, doi : str, optional
        Identifier for the article.
    include_tables, include_supplements : bool
        What to include.

    Returns
    -------
    list[FigureInfo]
    """
    extractor = FigureExtractor()
    return extractor.extract(
        pmcid=pmcid,
        pmid=pmid,
        doi=doi,
        include_tables=include_tables,
        include_supplements=include_supplements,
    )


def extract_tables_from_pmc(
    pmcid: str | None = None,
    pmid: str | None = None,
    doi: str | None = None,
) -> list[FigureInfo]:
    """
    Convenience function to extract only tables from a PMC article.

    Parameters
    ----------
    pmcid, pmid, doi : str, optional
        Identifier for the article.

    Returns
    -------
    list[FigureInfo]
    """
    extractor = FigureExtractor()
    return extractor.extract(
        pmcid=pmcid,
        pmid=pmid,
        doi=doi,
        include_tables=True,
        include_supplements=False,
    )
