"""JATSNormalizer on the real Europe PMC documents.

Measured on these files, the normalizer

* raised ParseError on PMC3258128 and PMC12311175, which escape "<" and "&"
  as numeric character references that were decoded before parsing;
* took the DOI from whichever <article-id> came last - in PMC13567752 the
  ninth peer-review <sub-article>'s;
* listed every <sub-article> contributor as an author, and none at all for
  documents that declare authorship on the <contrib-group>;
* returned the sections in neither document order nor its reverse.

Expectations are read from the article's own front matter and body.
"""

from __future__ import annotations

import unicodedata

import pytest

from pyeuropepmc.features.fulltext.jats_normalizer import JATSNormalizer

from .conftest import fixture_paths, normalise

pytestmark = [pytest.mark.unit]

PATHS = fixture_paths()


@pytest.fixture(params=PATHS, ids=[p.stem for p in PATHS], scope="module")
def normalized(request):
    """(raw root, normalizer result) for one committed document."""
    import defusedxml.ElementTree as DefusedET

    data = request.param.read_bytes()
    return DefusedET.fromstring(data), JATSNormalizer().normalize_xml(data)


def _front(root):
    front = root.find("./front")
    return front if front is not None else root


def test_every_document_normalizes(normalized):
    """PMC3258128 and PMC12311175 raised ParseError before producing anything."""
    _, result = normalized
    assert result["body_text"]


class TestMetadata:
    def test_doi_is_the_articles_own(self, normalized):
        root, result = normalized
        own = next(
            (
                a.text.strip()
                for a in _front(root).iter("article-id")
                if a.get("pub-id-type") == "doi" and a.text
            ),
            None,
        )
        if own is None:
            pytest.skip("no DOI")
        assert result["metadata"]["doi"] == own.lower()

    def test_authors_are_the_articles_own(self, normalized):
        """Surnames in order; the normalizer writes "Given Surname"."""
        root, result = normalized
        front = _front(root)
        grouped = {
            id(c)
            for g in front.iter("contrib-group")
            if g.get("content-type") == "author"
            for c in g.findall("contrib")
            if not c.get("contrib-type")
        }
        expected = [
            normalise(c.findtext("name/surname"))
            for c in front.iter("contrib")
            if (c.get("contrib-type") == "author" or id(c) in grouped)
            and c.findtext("name/surname")
        ]
        if not expected:
            pytest.skip("no tagged authors")
        got = [normalise(a["name"]) for a in result["metadata"].get("authors", [])]
        assert len(got) == len(expected)
        assert all(name.endswith(surname) for name, surname in zip(got, expected, strict=True))


class TestSections:
    def test_sections_are_in_document_order(self, normalized):
        root, result = normalized
        body = root.find("./body")
        if body is None or body.find("sec") is None:
            pytest.skip("no <sec> in the body")

        expected: list[str] = []

        def walk(parent):
            for sec in parent.findall("sec"):
                title = sec.find("title")
                expected.append("".join(title.itertext()) if title is not None else "")
                walk(sec)

        walk(body)

        def key(text):
            return normalise(unicodedata.normalize("NFC", text))

        assert [key(s["title"]) for s in result["sections"]] == [key(t) for t in expected]
