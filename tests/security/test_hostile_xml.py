"""Hostile XML through every entry point that parses it.

defusedxml refuses a document that declares entities, and a refusal is not the
same thing as malformed XML. Each entry point either raises ``ParsingError`` or
returns its documented empty value; nothing checked that before, and eight of
them let a raw ``EntitiesForbidden`` escape, which ``except ParseError`` does
not catch.

The payloads stay small and local. The external-entity cases point at a file
this test writes and at a closed port, so nothing is fetched even if a parser
tried; the expansion cases stay far below the size at which expat gives up, so
they test the refusal rather than expat's limit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from pyeuropepmc.benchmark.metrics import compute_all_metrics, compute_element_coverage
from pyeuropepmc.benchmark.profiler import time_et_parse
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.features.fulltext.extensions.local_processing import (
    _safe_parse,
    extract_article_id_from_xml,
    process_biorxiv_manifest,
)
from pyeuropepmc.features.fulltext.figures import FigureExtractor
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.features.fulltext.jats_normalizer import JATSNormalizer, normalize_jats_xml
from pyeuropepmc.features.literature.search_parser import EuropePMCParser
from pyeuropepmc.features.search.sources.arxiv import ArxivClient
from pyeuropepmc.features.search.sources.pubmed import PubMedClient

pytestmark = [pytest.mark.unit]

SECRET = "PYEUROPEPMC-SECRET-MARKER"

ARTICLE = (
    "<article><front><article-meta><title-group>"
    "<article-title>A study</article-title></title-group></article-meta></front>"
    "<body><sec><title>Results</title><p>Body text.</p></sec></body></article>"
)


@pytest.fixture
def payloads(tmp_path: Path) -> dict[str, str]:
    """One document per attack, plus the two documents that must still parse."""
    target = tmp_path / "secret.txt"
    target.write_text(SECRET, encoding="utf-8")
    return {
        "entity declaration": (
            '<?xml version="1.0"?><!DOCTYPE article [<!ENTITY nbsp "&#160;">]>' + ARTICLE
        ),
        "billion laughs": (
            '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
            '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">'
            '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;">]>'
            "<article><body><p>&lol3;</p></body></article>"
        ),
        "external file entity": (
            '<?xml version="1.0"?>'
            f'<!DOCTYPE article [<!ENTITY xxe SYSTEM "file://{target}">]>'
            "<article><body><p>&xxe;</p></body></article>"
        ),
        "external http entity": (
            '<?xml version="1.0"?>'
            '<!DOCTYPE article [<!ENTITY xxe SYSTEM "http://127.0.0.1:9/never">]>'
            "<article><body><p>&xxe;</p></body></article>"
        ),
        "parameter entity": (
            '<?xml version="1.0"?>'
            '<!DOCTYPE article [<!ENTITY % pe SYSTEM "http://127.0.0.1:9/never"> %pe;]>' + ARTICLE
        ),
        "malformed": "<article><body><p>unclosed",
        "doctype without entities": (
            '<?xml version="1.0"?>'
            '<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and '
            'Interchange DTD v1.0 20120330//EN" "JATS-archivearticle1.dtd">' + ARTICLE
        ),
    }


REFUSED = [
    "entity declaration",
    "billion laughs",
    "external file entity",
    "external http entity",
    "parameter entity",
]


@dataclass(frozen=True)
class Caller:
    """An entry point that parses XML, and what it does when parsing fails."""

    name: str
    run: Callable[[str, Path], Any]
    empty: Any = None
    raises: bool = True


def _benign_parser() -> FullTextXMLParser:
    return FullTextXMLParser(ARTICLE)


def _manifest(xml: str, tmp_path: Path) -> Any:
    path = tmp_path / "manifest.xml"
    path.write_text(xml, encoding="utf-8")
    return process_biorxiv_manifest(str(path))


RAISING = [
    Caller("FullTextXMLParser", lambda xml, _: FullTextXMLParser(xml)),
    Caller("EuropePMCParser.parse_xml", lambda xml, _: EuropePMCParser.parse_xml(xml)),
    Caller("JATSNormalizer.normalize_xml", lambda xml, _: JATSNormalizer().normalize_xml(xml)),
    Caller("normalize_jats_xml", lambda xml, _: normalize_jats_xml(xml)),
    Caller("process_biorxiv_manifest", _manifest),
    Caller(
        "metrics.compute_element_coverage",
        lambda xml, _: compute_element_coverage(_benign_parser(), xml),
    ),
    Caller(
        "metrics.compute_all_metrics", lambda xml, _: compute_all_metrics(_benign_parser(), xml)
    ),
    Caller("profiler.time_et_parse", lambda xml, _: time_et_parse(xml)),
]

RETURNING = [
    Caller(
        "ArxivClient._parse_feed",
        lambda xml, _: ArxivClient()._parse_feed(xml),
        empty=[],
        raises=False,
    ),
    Caller(
        "PubMedClient._parse_efetch_xml",
        lambda xml, _: PubMedClient()._parse_efetch_xml(xml, "1"),
        empty=None,
        raises=False,
    ),
    Caller(
        "local_processing._safe_parse", lambda xml, _: _safe_parse(xml), empty=None, raises=False
    ),
    Caller(
        "extract_article_id_from_xml",
        lambda xml, _: extract_article_id_from_xml(xml),
        empty=None,
        raises=False,
    ),
]

FIGURES = Caller(
    "FigureExtractor._extract_from_xml",
    lambda xml, _: FigureExtractor()._extract_from_xml(xml),
    empty=[],
)


def _ids(callers: list[Caller]) -> list[str]:
    return [c.name for c in callers]


class TestRefusedDocument:
    """A document that declares entities is refused, never expanded."""

    @pytest.mark.parametrize("caller", [*RAISING, FIGURES], ids=_ids([*RAISING, FIGURES]))
    @pytest.mark.parametrize("attack", REFUSED)
    def test_raises_parsing_error(
        self, caller: Caller, attack: str, payloads: dict[str, str], tmp_path: Path
    ) -> None:
        with pytest.raises(ParsingError) as excinfo:
            caller.run(payloads[attack], tmp_path)
        assert excinfo.value.error_code is ErrorCodes.PARSE005

    @pytest.mark.parametrize("caller", RETURNING, ids=_ids(RETURNING))
    @pytest.mark.parametrize("attack", REFUSED)
    def test_returns_its_empty_value(
        self, caller: Caller, attack: str, payloads: dict[str, str], tmp_path: Path
    ) -> None:
        assert caller.run(payloads[attack], tmp_path) == caller.empty

    def test_the_external_file_is_never_read(
        self, payloads: dict[str, str], tmp_path: Path
    ) -> None:
        with pytest.raises(ParsingError) as excinfo:
            FullTextXMLParser(payloads["external file entity"])
        assert SECRET not in str(excinfo.value)
        assert SECRET not in repr(excinfo.value.__cause__)


class TestMalformedDocument:
    """Malformed XML keeps its own error code, and is not confused with a refusal."""

    @pytest.mark.parametrize("caller", RAISING, ids=_ids(RAISING))
    def test_raises_parse002(
        self, caller: Caller, payloads: dict[str, str], tmp_path: Path
    ) -> None:
        with pytest.raises(ParsingError) as excinfo:
            caller.run(payloads["malformed"], tmp_path)
        assert excinfo.value.error_code is ErrorCodes.PARSE002

    @pytest.mark.parametrize("caller", [*RETURNING, FIGURES], ids=_ids([*RETURNING, FIGURES]))
    def test_returns_its_empty_value(
        self, caller: Caller, payloads: dict[str, str], tmp_path: Path
    ) -> None:
        assert caller.run(payloads["malformed"], tmp_path) == caller.empty


class TestDocumentThatMustStillParse:
    """Europe PMC ships a DOCTYPE; only entity declarations are refused."""

    @pytest.mark.parametrize(
        "caller", [*RAISING, *RETURNING, FIGURES], ids=_ids([*RAISING, *RETURNING, FIGURES])
    )
    def test_doctype_without_entities_is_not_a_parse_failure(
        self, caller: Caller, payloads: dict[str, str], tmp_path: Path
    ) -> None:
        try:
            caller.run(payloads["doctype without entities"], tmp_path)
        except ParsingError as error:
            # PARSE004 is fine: a search parser may find no results in an article.
            assert error.error_code not in {ErrorCodes.PARSE002, ErrorCodes.PARSE005}
