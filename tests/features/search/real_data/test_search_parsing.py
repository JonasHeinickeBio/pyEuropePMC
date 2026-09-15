"""Search responses must parse into the records they actually contain.

The existing tests for `EuropePMCParser` are mock-based: they assert that the
right parse function was called and that a list came back. That checks the
wiring, not the values — the same gap that let `extract_references()` return
the second and third authors as a citation's title and journal for as long as
it did (#226), on a code path whose coverage tests all passed.

These read the captured Europe PMC responses in tests/fixtures and compare
what the parser produces against the raw payload.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from pyeuropepmc.features.literature.search_parser import EuropePMCParser

pytestmark = [pytest.mark.unit]

FIXTURES = pathlib.Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture(scope="module")
def raw_json() -> dict:
    return json.loads((FIXTURES / "search_cancer.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw_records(raw_json) -> list[dict]:
    records = raw_json["resultList"]["result"]
    assert records, "fixture carries no results"
    return records


class TestJsonParsing:
    def test_every_record_is_returned(self, raw_json, raw_records):
        assert len(EuropePMCParser.parse_json(raw_json)) == len(raw_records)

    def test_ids_match_in_order(self, raw_json, raw_records):
        """Order matters: results are ranked, and callers page through them."""
        assert [r.get("id") for r in EuropePMCParser.parse_json(raw_json)] == [
            r.get("id") for r in raw_records
        ]

    def test_no_field_is_altered(self, raw_json, raw_records):
        """Every field of every record, not a sampled few."""
        parsed = EuropePMCParser.parse_json(raw_json)
        for index, (source, got) in enumerate(zip(raw_records, parsed, strict=True)):
            differing = {k: (source[k], got.get(k)) for k in source if source[k] != got.get(k)}
            assert not differing, f"record {index} ({source.get('id')}): {differing}"

    def test_missing_result_list_is_not_an_error(self):
        assert EuropePMCParser.parse_json({"hitCount": 0}) == []


@pytest.fixture(scope="module")
def parsed_xml() -> list[dict]:
    return EuropePMCParser.parse_xml((FIXTURES / "search_cancer.xml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parsed_dc() -> list[dict]:
    return EuropePMCParser.parse_dc(
        (FIXTURES / "search_cancer_dc.xml").read_text(encoding="utf-8")
    )


class TestXmlParsing:
    def test_every_record_is_returned(self, parsed_xml, raw_records):
        assert len(parsed_xml) == len(raw_records)

    def test_ids_agree_with_the_json_response(self, parsed_xml, raw_records):
        """The same search in two formats must name the same articles."""
        assert [str(r.get("id")) for r in parsed_xml] == [str(r.get("id")) for r in raw_records]

    def test_titles_are_populated(self, parsed_xml):
        assert all(r.get("title") for r in parsed_xml)


class TestDublinCoreParsing:
    def test_every_record_is_returned(self, parsed_dc, raw_records):
        assert len(parsed_dc) == len(raw_records)

    def test_records_carry_dublin_core_fields(self, parsed_dc):
        """DC uses its own vocabulary rather than the Europe PMC field names."""
        assert parsed_dc
        first = parsed_dc[0]
        assert first.get("title")
        assert any(first.get(k) for k in ("identifier", "creator", "date"))
