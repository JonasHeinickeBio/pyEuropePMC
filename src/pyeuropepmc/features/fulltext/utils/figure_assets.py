"""Which file belongs to which figure.

Two JATS shapes break a ``.//graphic`` search inside a ``<fig>``:

* A caption can contain images of its own. PLOS renders inline mathematics as
  ``<inline-formula><alternatives><graphic/></alternatives></inline-formula>``,
  so the first descendant graphic of PMC10775981's Fig 3 is ``pcbi.1011761.e012.jpg``,
  a fragment of an equation, and not the figure at all.
* eLife nests each figure supplement as a ``<fig>`` inside its parent figure's
  ``<p>``. Its graphic is a descendant of the parent too, and it is a different
  figure, with its own label ("Figure 1-figure supplement 1.").

A figure's own graphic is therefore the one it carries directly, or inside an
``<alternatives>`` it carries directly - never one reached by descending into a
caption, a formula or another figure.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.utils.asset_urls import has_known_extension

__all__ = [
    "FILE_TAGS",
    "child_figures",
    "href_of",
    "local_tag",
    "own_graphic",
    "own_graphics",
    "parent_figure_map",
    "supplementary_href",
]

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"

#: Elements that reference a file through their own ``xlink:href``.
FILE_TAGS = frozenset({"graphic", "inline-graphic", "media"})


def local_tag(tag: object) -> str:
    """An element's tag without its namespace."""
    if not isinstance(tag, str):
        return ""
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def own_graphics(elem: ET.Element) -> list[ET.Element]:
    """The ``<graphic>`` elements ``elem`` itself carries, in document order.

    Direct children, plus the children of a direct ``<alternatives>`` - where
    publishers put the same image in several formats (Springer Nature ships a
    full-size JPEG and a GIF thumbnail). Nothing else is reached, which is what
    keeps caption formulas and nested figures out.
    """
    graphics: list[ET.Element] = []
    for child in elem:
        tag = local_tag(child.tag)
        if tag == "graphic":
            graphics.append(child)
        elif tag == "alternatives":
            graphics.extend(sub for sub in child if local_tag(sub.tag) == "graphic")
    return graphics


def own_graphic(elem: ET.Element) -> ET.Element | None:
    """The first graphic ``elem`` itself carries, or ``None``."""
    graphics = own_graphics(elem)
    return graphics[0] if graphics else None


def child_figures(fig: ET.Element) -> list[ET.Element]:
    """The ``<fig>`` elements nested inside ``fig`` - its figure supplements."""
    return [elem for elem in fig.iter() if elem is not fig and local_tag(elem.tag) == "fig"]


def parent_figure_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    """Maps each nested ``<fig>`` to the figure that contains it.

    Figures that stand on their own are absent from the mapping, so
    ``mapping.get(fig)`` is ``None`` exactly for a figure with no parent.
    """
    parents: dict[ET.Element, ET.Element] = {}
    for elem in root.iter():
        if local_tag(elem.tag) != "fig":
            continue
        for nested in child_figures(elem):
            # The innermost enclosing figure wins: iter() reaches an outer
            # figure first, so only overwrite while descending.
            parents[nested] = elem
    return parents


def href_of(elem: ET.Element) -> str:
    """An element's ``xlink:href``, or a bare ``href``, or ``""``."""
    return elem.get(XLINK_HREF) or elem.get("href") or ""


def supplementary_href(elem: ET.Element) -> str:
    """The file a ``<supplementary-material>`` names without a file child.

    Usually the block wraps a ``<media>`` that names the file, and then this
    returns ``""`` - the child is the file's reference, not the block. JATS
    also allows the ``xlink:href`` on the block itself. Failing both, an
    ``<object-id>`` holding a file name is accepted, as it always was here; one
    typed as a DOI, or one that does not end in a file type, is an identifier
    for the object rather than its file, and is not.
    """
    own = href_of(elem)
    if own:
        return own
    if any(local_tag(child.tag) in FILE_TAGS for child in elem):
        return ""
    for child in elem:
        if local_tag(child.tag) != "object-id":
            continue
        if child.get("pub-id-type", "").lower() == "doi":
            continue
        text = (child.text or "").strip()
        if has_known_extension(text):
            return text
    return ""
