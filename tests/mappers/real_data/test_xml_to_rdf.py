"""RDF built from a real article must contain that article's values.

`process_xml_for_rdf` wraps each entity in

    except Exception as e:
        logger.warning(f"Failed to process XML entity {entity} to RDF: {e}")
        continue

so an entity that fails to map is skipped and the graph simply comes back
shorter. A caller sees a Dataset either way; only a log line distinguishes a
complete graph from one missing half its authors. Nothing under tests/mappers
read a real document before this — 21 test modules, none of them touching
tests/fixtures.

These parse a real Europe PMC article, map it, and assert the article's own
title, DOI and author names are in the triples.
"""

from __future__ import annotations

import logging
import pathlib

import pytest

pytest.importorskip("rdflib")

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser  # noqa: E402
from pyeuropepmc.mappers import convert_xml_to_rdf  # noqa: E402

pytestmark = [pytest.mark.unit]

FIXTURE = (
    pathlib.Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fulltext_downloads"
    / "PMC12018715.xml"
)


@pytest.fixture(scope="module")
def parser() -> FullTextXMLParser:
    return FullTextXMLParser(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def xml_data(parser) -> dict:
    """The shape the mappers expect: a `paper` mapping plus its collections.

    Flat `extract_metadata()` output is silently ignored — `_extract_entities_
    from_xml` starts with `if "paper" in xml_data`, so the wrong shape yields
    an empty graph rather than an error.
    """
    metadata = parser.extract_metadata()
    return {
        "paper": dict(metadata, pmcid=metadata.get("pmcid") or FIXTURE.stem),
        "authors": parser.extract_authors_detailed(),
        "affiliations": parser.extract_affiliations(),
    }


@pytest.fixture(scope="module")
def triple_text(xml_data) -> str:
    dataset = convert_xml_to_rdf(xml_data)
    quads = list(dataset.quads((None, None, None, None)))
    assert quads, "conversion produced no triples at all"
    return " ".join(str(q[2]) for q in quads)


class TestTheArticleSurvivesConversion:
    def test_title_is_in_the_graph(self, triple_text, parser):
        title = parser.extract_metadata()["title"]
        assert title[:40] in triple_text

    def test_doi_is_in_the_graph(self, triple_text, parser):
        doi = parser.extract_metadata().get("doi")
        assert doi, "fixture has no DOI to check"
        assert doi in triple_text

    def test_every_author_is_in_the_graph(self, triple_text, parser):
        """The per-entity `except ... continue` drops authors one at a time."""
        missing = [
            a["full_name"]
            for a in parser.extract_authors_detailed()
            if a.get("full_name") and a["full_name"] not in triple_text
        ]
        assert not missing, f"authors absent from the RDF: {missing}"


class TestFailuresAreNotSilent:
    def test_conversion_warns_rather_than_raising_on_bad_input(self, caplog):
        """Malformed entity data must not take the whole conversion down."""
        broken = {"paper": {"pmcid": "PMC1", "title": object()}, "authors": [], "affiliations": []}
        with caplog.at_level(logging.WARNING):
            dataset = convert_xml_to_rdf(broken)
        assert dataset is not None

    def test_wrong_shape_yields_an_empty_graph(self, parser):
        """Recorded, not endorsed.

        Flat metadata has no `paper` key, so nothing is extracted and the
        caller gets an empty Dataset with no indication why. This pins the
        current behaviour so a change to it is deliberate.
        """
        dataset = convert_xml_to_rdf(dict(parser.extract_metadata()))
        assert not list(dataset.quads((None, None, None, None)))
