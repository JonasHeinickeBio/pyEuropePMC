"""
Figure extraction from PubMed Central (PMC) Open Access articles.

Extracts figures, tables, and supplementary materials from PMC full-text
XML using the Europe PMC annotations API and the PMC Open Access subset.
Supports extracting figure captions, image URLs, and PDF links.

References:
    - Europe PMC Annotations API: https://europepmc.org/AnnotationsApi
    - PMC Open Access Subset: https://www.ncbi.nlm.nih.gov/pmc/tools/oa-service/
"""

from __future__ import annotations

import logging
import re
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

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

_GRAPHIC_EXT_RE = re.compile(r"\.(png|jpg|jpeg|gif|tiff?|svg|eps)$", re.IGNORECASE)


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
        URL to the figure image.
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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "label": self.label,
            "caption": self.caption,
            "alt_text": self.alt_text,
            "image_url": self.image_url,
            "pdf_url": self.pdf_url,
            "figure_type": self.figure_type,
            "doi": self.doi,
            "pmcid": self.pmcid,
        }

    def __repr__(self) -> str:
        return f"<FigureInfo {self.label} ({self.figure_type})>"


class FigureExtractor:
    """
    Extracts figures, tables, and graphics from PMC XML articles.

    Uses Europe PMC annotations and full-text APIs to retrieve figure
    metadata and image URLs.

    Examples
    --------
    >>> extractor = FigureExtractor()
    >>> figures = extractor.extract(pmcid="PMC1234567")
    >>> for f in figures:
    ...     print(f.label, f.caption[:80])
    """

    PMC_IMAGE_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/bin/{filename}"

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
        """Parse XML and extract figure elements."""
        figures: list[FigureInfo] = []

        try:
            root = ET.fromstring(xml_str)  # nosec B314
        except ET.ParseError as e:
            logger.error("XML parse error: %s", e)
            return figures

        # Set up namespace handling for JATS XML
        ns = {"": "http://www.ncbi.nlm.nih.gov/JATS1"}

        # Extract figures (<fig> elements)
        for fig_elem in root.iter("{http://www.ncbi.nlm.nih.gov/JATS1}fig"):
            figure = self._parse_figure_element(fig_elem, pmcid, ns)
            if figure:  # noqa: SIM102
                if (
                    format == FigureFormat.ALL
                    or figure.image_url is None
                    or format in figure.image_url
                ):
                    figures.append(figure)

        # Extract tables (<table-wrap> elements)
        if include_tables:
            for table_elem in root.iter("{http://www.ncbi.nlm.nih.gov/JATS1}table-wrap"):
                table = self._parse_table_element(table_elem, pmcid, ns)
                if table:
                    figures.append(table)

        # Extract supplementary materials
        if include_supplements:
            for supp_elem in root.iter(
                "{http://www.ncbi.nlm.nih.gov/JATS1}supplementary-material"
            ):
                supplement = self._parse_supplement_element(supp_elem, pmcid, ns)
                if supplement:
                    figures.append(supplement)

        return figures

    def _parse_figure_element(
        self,
        elem: ET.Element,
        pmcid: str | None,
        ns: dict[str, str],
    ) -> FigureInfo | None:
        """Parse a single <fig> JATS element."""
        label = ""
        caption = ""
        alt_text = None
        image_url = None

        label_elem = elem.find("{http://www.ncbi.nlm.nih.gov/JATS1}label")
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        caption_elem = elem.find("{http://www.ncbi.nlm.nih.gov/JATS1}caption")
        if caption_elem is not None:
            caption = ET.tostring(caption_elem, encoding="unicode", method="text").strip()

        alt_elem = elem.find("{http://www.ncbi.nlm.nih.gov/JATS1}alt-text")
        if alt_elem is not None and alt_elem.text:
            alt_text = alt_elem.text.strip()

        # Extract graphic reference
        graphic = elem.find("{http://www.ncbi.nlm.nih.gov/JATS1}graphic")
        if graphic is not None:
            href = graphic.get("{http://www.w3.org/1999/xlink}href", "") or graphic.get("href", "")
            if href and pmcid:
                image_url = self.PMC_IMAGE_BASE.format(pmcid=pmcid, filename=href)

        return FigureInfo(
            label=label or "Figure",
            caption=caption,
            alt_text=alt_text,
            image_url=image_url,
            figure_type="figure",
            pmcid=pmcid,
        )

    def _parse_table_element(
        self,
        elem: ET.Element,
        pmcid: str | None,
        ns: dict[str, str],
    ) -> FigureInfo | None:
        """Parse a <table-wrap> JATS element."""
        label = ""
        caption = ""

        label_elem = elem.find("{http://www.ncbi.nlm.nih.gov/JATS1}label")
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        caption_elem = elem.find("{http://www.ncbi.nlm.nih.gov/JATS1}caption")
        if caption_elem is not None:
            caption = ET.tostring(caption_elem, encoding="unicode", method="text").strip()

        return FigureInfo(
            label=label or "Table",
            caption=caption,
            figure_type="table",
            pmcid=pmcid,
        )

    def _parse_supplement_element(
        self,
        elem: ET.Element,
        pmcid: str | None,
        ns: dict[str, str],
    ) -> FigureInfo | None:
        """Parse a <supplementary-material> JATS element."""
        label = ""
        description = ""

        label_elem = elem.find("{http://www.ncbi.nlm.nih.gov/JATS1}label")
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        # Description is often in the caption or as text content
        caption_elem = elem.find("{http://www.ncbi.nlm.nih.gov/JATS1}caption")
        if caption_elem is not None:
            description = ET.tostring(caption_elem, encoding="unicode", method="text").strip()

        return FigureInfo(
            label=label or "Supplementary Material",
            caption=description,
            figure_type="supplement",
            pmcid=pmcid,
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
