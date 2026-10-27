"""Authors of a mixed-citation that names no <person-group>: the whole list, particles included.

The text pass cut the list at the first capitalised word after the first author, so
"Mayoral del Moral O., Salvat Salvat I." became the author "Mayoral del" with a title that began
"Moral O., Salvat Salvat I." (PMC8658482), and "Zhang J., Wang L." kept only "Zhang J".
"""

from __future__ import annotations

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.features.fulltext.parsers.reference_parser import ReferenceParser


@pytest.fixture(scope="module")
def parser():
    return ReferenceParser.__new__(ReferenceParser)


@pytest.mark.parametrize(
    ("text", "authors", "rest"),
    [
        (
            "Mayoral del Moral O., Salvat Salvat I., Miota Ibarra J., Martinez Cuenca J.M. "
            "El síndrome de dolor miofascial. In: Mayoral del Moral O., editors. Fisio",
            "Mayoral del Moral O., Salvat Salvat I., Miota Ibarra J., Martinez Cuenca J.M",
            "El síndrome de dolor miofascial. In: Mayoral del Moral O., editors. Fisio",
        ),
        (
            "Zhang J., Wang L. Deep learning for X. Nature. 2020;5:1-2",
            "Zhang J., Wang L",
            "Deep learning for X. Nature. 2020;5:1-2",
        ),
        (
            "van der Berg A., de la Cruz M.-J. Study of things. Lancet 2018",
            "van der Berg A., de la Cruz M.-J",
            "Study of things. Lancet 2018",
        ),
        (
            "O'Brien P., Garcia-Lopez M. A thing. BMJ 2001",
            "O'Brien P., Garcia-Lopez M",
            "A thing. BMJ 2001",
        ),
        ("Smith J. A study of X. Nature 2001", "Smith J", "A study of X. Nature 2001"),
    ],
)
def test_the_whole_list_is_the_authors(parser, text, authors, rest):
    assert parser._extract_authors_from_text(text) == (authors, rest)


@pytest.mark.parametrize(
    ("text", "authors"),
    [
        ("Smith JM, Jones K. Title of paper. J Med. 2019", "Smith JM, Jones K"),
        ("Smith J., Jones K., et al. A title. Nature 2020", "Smith J., Jones K"),
    ],
)
def test_other_styles_are_unchanged(parser, text, authors):
    assert parser._extract_authors_from_text(text)[0] == authors


MDPI_REFERENCE = """<article><back><ref-list><ref id="B1"><label>1.</label><mixed-citation>
<named-content content-type="citation-string">Mayoral del Moral O., Salvat Salvat I.  El síndrome
de dolor miofascial. In: Mayoral del Moral O., Salvat Salvat I., editors. Fisioterapia Invasiva.
1st ed. Editorial Médica Panamericana; Madrid, Spain: 2017. pp. 3–25.</named-content>
</mixed-citation></ref></ref-list></back></article>"""


def test_through_the_full_parser():
    (reference,) = FullTextXMLParser(MDPI_REFERENCE).extract_references()
    assert reference["authors"].startswith("Mayoral del Moral O., Salvat Salvat I")
    assert not str(reference.get("title") or "").startswith("Moral")
