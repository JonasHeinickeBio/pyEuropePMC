"""
Optional lxml parser backend for high-performance XML parsing.

Provides a secure ``lxml``-based parser that can be used as a drop-in replacement
for the default ``defusedxml.ElementTree`` backend. ``lxml`` is significantly faster
for large XML documents and provides better XPath support.

Usage::

    from pyeuropepmc.processing.extensions.lxml_backend import LXMLParser

    # Fast parsing with security hardening
    root = LXMLParser.fromstring(xml_content)

    # Or use as a context manager with FullTextXMLParser
    parser = FullTextXMLParser()
    LXMLParser.enable_for(parser)  # swap backend

Security
--------
The parser disables entity resolution, DTD loading, and network access,
matching the security guarantees of ``defusedxml``.

References
----------
- lxml security: https://lxml.de/parsing.html
- defusedxml: https://pypi.org/project/defusedxml/
- docling JATS backend (reference implementation): https://github.com/DS4SD/docling
"""

from __future__ import annotations

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.core.exceptions import ParsingError

logger = logging.getLogger(__name__)

# Try to import lxml; fail gracefully if not installed
_HAS_LXML = False
try:
    from lxml import etree as lxml_etree

    _HAS_LXML = True
except ImportError:  # pragma: no cover
    lxml_etree = None

__all__ = ["LXMLParser", "is_lxml_available"]


def is_lxml_available() -> bool:
    """Check whether lxml is installed and usable."""
    return _HAS_LXML


# Secure parser configuration (matching docling's approach)
SECURE_PARSER_KWARGS: dict[str, Any] = {
    "resolve_entities": False,
    "load_dtd": False,
    "no_network": True,
    "huge_tree": True,  # Allow large documents
}


class LXMLParser:
    """
    lxml-based XML parser with security hardening.

    Can be used as a drop-in replacement for ``defusedxml.ElementTree``.
    Provides significantly faster parsing for large XML documents and
    better XPath support.

    Parameters
    ----------
    recover : bool, optional
        If True, try to recover from malformed XML (default: False).
    remove_blank_text : bool, optional
        If True, remove blank text nodes (default: True).

    Examples
    --------
    >>> # Direct usage
    >>> root = LXMLParser.fromstring(xml_string)
    >>> root.findall(".//sec")  # Same API as ElementTree

    >>> # Enable for a FullTextXMLParser instance
    >>> parser = FullTextXMLParser()
    >>> LXMLParser.enable_for(parser, xml_content)
    >>> parser.extract_metadata()
    """

    def __init__(
        self,
        recover: bool = False,
        remove_blank_text: bool = True,
    ):
        if not _HAS_LXML:
            raise ImportError(
                "lxml is not installed. Install it with: pip install pyeuropepmc[xml]"
            ) from None

        self._parser = lxml_etree.XMLParser(
            **SECURE_PARSER_KWARGS,
            recover=recover,
            remove_blank_text=remove_blank_text,
        )

    @property
    def parser(self) -> Any:
        """The underlying lxml parser instance."""
        return self._parser

    @classmethod
    def fromstring(cls, xml_content: str, **kwargs: Any) -> ET.Element:
        """
        Parse XML string using the secure lxml backend.

        Parameters
        ----------
        xml_content : str
            XML content to parse.
        **kwargs
            Additional keyword arguments forwarded to ``LXMLParser.__init__``.

        Returns
        -------
        ET.Element
            Root element (compatible with ``xml.etree.ElementTree`` API).

        Raises
        ------
        ImportError
            If lxml is not installed.
        lxml.etree.XMLSyntaxError
            If the XML is malformed.
        """
        parser = cls(**kwargs)
        try:
            return lxml_etree.fromstring(xml_content, parser=parser._parser)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"lxml parsing error: {e}")
            raise ParsingError(
                message=f"lxml XML parsing failed: {e}",
                parser_type="lxml",
            ) from e

    @classmethod
    def fromfile(cls, filepath: str, **kwargs: Any) -> ET.Element:
        """
        Parse XML file using the secure lxml backend.

        Parameters
        ----------
        filepath : str
            Path to the XML file.
        **kwargs
            Additional keyword arguments forwarded to ``LXMLParser.__init__``.

        Returns
        -------
        ET.Element
            Root element.

        Raises
        ------
        ImportError
            If lxml is not installed.
        FileNotFoundError
            If the file does not exist.
        """
        parser = cls(**kwargs)
        try:
            return lxml_etree.parse(filepath, parser._parser).getroot()  # type: ignore[no-any-return]  # noqa: SLF001
        except Exception as e:
            logger.error(f"lxml file parsing error for {filepath}: {e}")
            raise ParsingError(
                message=f"lxml file parsing failed for {filepath}: {e}",
                parser_type="lxml",
            ) from e

    @staticmethod
    def enable_for(
        parser_instance: Any,
        xml_content: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Swap the XML backend of a ``FullTextXMLParser`` instance to lxml.

        Modifies the ``parse()`` method of the given parser instance to use
        lxml instead of defusedxml.

        Parameters
        ----------
        parser_instance : FullTextXMLParser
            The parser instance to modify.
        xml_content : str, optional
            If provided, immediately parse this content with lxml.
        **kwargs
            Additional keyword arguments for ``LXMLParser.__init__``.

        Examples
        --------
        >>> parser = FullTextXMLParser()
        >>> LXMLParser.enable_for(parser, xml_string)
        >>> parser.extract_metadata()  # Uses lxml under the hood
        """
        original_parse = parser_instance.parse

        def lxml_parse(
            content: str | ET.Element,
        ) -> ET.Element:
            if isinstance(content, str):
                root = LXMLParser.fromstring(content, **kwargs)
                parser_instance.xml_content = content
                parser_instance.root = root
                parser_instance._reset_parsers()  # noqa: SLF001
                return root
            return original_parse(content)  # type: ignore[no-any-return]

        parser_instance.parse = lxml_parse

        if xml_content is not None:
            lxml_parse(xml_content)
