"""The one way pyeuropepmc turns XML text into an element tree.

defusedxml refuses a document that declares entities: it raises
``DefusedXmlException``, a ``ValueError`` subclass that ``except ParseError``
does not catch. A refusal is not malformed XML either, so it has its own error
code. Every caller that reports failure by raising goes through
:func:`parse_xml`, which turns both outcomes into ``ParsingError``: ``PARSE005``
for a refused document, ``PARSE002`` for one that is not well formed.

Callers that report failure by returning nothing - the arXiv and PubMed
sources, figure extraction - catch that ``ParsingError``, log it and return
their documented empty value.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET  # nosec B405

from defusedxml import DefusedXmlException
import defusedxml.ElementTree as DefusedET

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError

__all__ = ["is_refused", "parse_xml"]


def parse_xml(xml_content: str | bytes, *, what: str = "The XML") -> ET.Element:
    """Parse ``xml_content`` with defusedxml.

    Parameters
    ----------
    xml_content : str or bytes
        The document to parse.
    what : str, optional
        What the document is, used to open the error message, for example
        ``"The EFetch response"``.

    Returns
    -------
    xml.etree.ElementTree.Element
        The root element.

    Raises
    ------
    ParsingError
        ``PARSE005`` when the document declares an XML entity, which defusedxml
        refuses; ``PARSE002`` when the document is not well-formed XML.
    """
    try:
        root: ET.Element = DefusedET.fromstring(xml_content)
    except DefusedXmlException as exc:
        raise ParsingError(
            ErrorCodes.PARSE005,
            message=(
                f"{what} declares an XML entity and was refused ({exc}). "
                "pyeuropepmc parses with defusedxml, which does not expand entity "
                "declarations; remove the <!ENTITY> declaration from the document."
            ),
            parser_type="defusedxml",
        ) from exc
    except ET.ParseError as exc:
        raise ParsingError(
            ErrorCodes.PARSE002,
            message=f"{what} is not well-formed XML: {exc}.",
            parser_type="defusedxml",
            line_number=getattr(exc, "position", (None, None))[0],
        ) from exc
    return root


def is_refused(error: ParsingError) -> bool:
    """Whether ``error`` reports a document defusedxml refused (``PARSE005``)."""
    return error.error_code is ErrorCodes.PARSE005
