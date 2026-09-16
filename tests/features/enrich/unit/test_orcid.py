"""Unit tests for OrcidClient parsing of ORCID public API v3.0 records.

The fixture mirrors the JSON returned by ``GET https://pub.orcid.org/v3.0/{orcid}``
with ``Accept: application/json``: absent values are ``null``, affiliations are
grouped under ``affiliation-group`` and value objects wrap strings.
"""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import patch

import pytest

from pyeuropepmc.features.enrich.sources.orcid import OrcidClient

ORCID = "0000-0002-1825-0097"


def _date(year: str | None) -> dict[str, Any] | None:
    return {"year": {"value": year}, "month": None, "day": None} if year else None


def _affiliation(kind: str, org: str, dept: str | None, role: str | None, start, end) -> dict:
    return {
        "last-modified-date": {"value": 1},
        "external-ids": {"external-id": []},
        "summaries": [
            {
                f"{kind}-summary": {
                    "department-name": dept,
                    "role-title": role,
                    "start-date": _date(start),
                    "end-date": _date(end),
                    "organization": {"name": org, "address": {"city": "Braunschweig"}},
                    "visibility": "public",
                }
            }
        ],
    }


RECORD: dict[str, Any] = {
    "orcid-identifier": {"path": ORCID},
    "person": {
        "name": {
            "given-names": {"value": "Josiah"},
            "family-name": {"value": "Carberry"},
            "credit-name": None,
        },
        "other-names": {"other-name": [{"content": "J. S. Carberry"}]},
        "biography": None,
        "researcher-urls": {
            "researcher-url": [
                {"url-name": "Homepage", "url": {"value": "https://example.org/carberry"}}
            ]
        },
        "keywords": {"keyword": [{"content": "psychoceramics"}]},
    },
    "activities-summary": {
        "employments": {
            "affiliation-group": [
                # current position: "end-date": null
                _affiliation(
                    "employment", "Brown University", "Psychoceramics", "Professor", "2011", None
                ),
                _affiliation(
                    "employment", "Wesleyan University", None, "Lecturer", "2005", "2010"
                ),
            ]
        },
        "educations": {
            "affiliation-group": [
                _affiliation(
                    "education", "Wesleyan University", "Ceramics", "PhD", "2000", "2005"
                ),
            ]
        },
        "works": {
            "group": [
                {
                    "work-summary": [
                        {
                            "title": {"title": {"value": "Cracked pots"}, "subtitle": None},
                            "external-ids": {
                                "external-id": [
                                    {
                                        "external-id-type": "doi",
                                        "external-id-value": "10.5555/12345678",
                                    }
                                ]
                            },
                            "type": "journal-article",
                            "publication-date": {"year": {"value": "2012"}, "month": None},
                            "journal-title": {"value": "Journal of Psychoceramics"},
                            "visibility": "public",
                            "path": "/0000-0002-1825-0097/work/1",
                        }
                    ]
                },
                {
                    "work-summary": [
                        {
                            "title": {"title": {"value": "Undated note"}},
                            "external-ids": None,
                            "type": "other",
                            "publication-date": None,
                            "journal-title": None,
                            "visibility": "public",
                            "path": "/0000-0002-1825-0097/work/2",
                        }
                    ]
                },
            ]
        },
    },
}


@pytest.fixture
def client() -> OrcidClient:
    return OrcidClient(rate_limit_delay=0)


class TestParseProfile:
    def test_null_biography_does_not_raise(self, client):
        with patch.object(client, "_make_request", return_value=copy.deepcopy(RECORD)):
            profile = client.get_profile(ORCID)

        assert profile is not None
        assert profile["biography"] is None
        assert profile["credit_name"] is None
        assert profile["name"] == "Josiah Carberry"

    def test_biography_content_is_read(self, client):
        record = copy.deepcopy(RECORD)
        record["person"]["biography"] = {
            "content": "Studies cracked pottery.",
            "visibility": "public",
        }
        profile = OrcidClient._parse_profile(record)
        assert profile["biography"] == "Studies cracked pottery."

    def test_employments_are_read_from_affiliation_groups(self, client):
        profile = OrcidClient._parse_profile(copy.deepcopy(RECORD))

        assert profile["employments"] == [
            {
                "organization": "Brown University",
                "department": "Psychoceramics",
                "role": "Professor",
                "start": "2011",
                "end": "",
            },
            {
                "organization": "Wesleyan University",
                "department": None,
                "role": "Lecturer",
                "start": "2005",
                "end": "2010",
            },
        ]

    def test_educations_are_read_from_affiliation_groups(self):
        profile = OrcidClient._parse_profile(copy.deepcopy(RECORD))
        assert profile["educations"] == [
            {
                "organization": "Wesleyan University",
                "department": "Ceramics",
                "role": "PhD",
                "start": "2000",
                "end": "2005",
            }
        ]

    def test_other_person_fields(self):
        profile = OrcidClient._parse_profile(copy.deepcopy(RECORD))
        assert profile["other_names"] == ["J. S. Carberry"]
        assert profile["keywords"] == ["psychoceramics"]
        assert profile["urls"] == {"Homepage": "https://example.org/carberry"}

    def test_works_with_null_parts(self):
        profile = OrcidClient._parse_profile(copy.deepcopy(RECORD))
        assert profile["works"] == [
            {
                "title": "Cracked pots",
                "doi": "10.5555/12345678",
                "year": 2012,
                "type": "journal-article",
                "journal_title": "Journal of Psychoceramics",
                "visibility": "public",
                "path": "/0000-0002-1825-0097/work/1",
            },
            {
                "title": "Undated note",
                "doi": None,
                "year": None,
                "type": "other",
                "journal_title": None,
                "visibility": "public",
                "path": "/0000-0002-1825-0097/work/2",
            },
        ]

    @pytest.mark.parametrize(
        "section", ["person", "activities-summary", "employments", "educations", "works"]
    )
    def test_null_sections_give_empty_values(self, section):
        record = copy.deepcopy(RECORD)
        if section in ("person", "activities-summary"):
            record[section] = None
        else:
            record["activities-summary"][section] = None
        profile = OrcidClient._parse_profile(record)  # must not raise
        assert isinstance(profile["employments"], list)
        assert isinstance(profile["works"], list)

    def test_enrich_uses_the_same_parser(self, client):
        with patch.object(client, "_make_request", return_value=copy.deepcopy(RECORD)) as req:
            profile = client.enrich(f"https://orcid.org/{ORCID}")
        req.assert_called_once_with(ORCID)
        assert profile["employments"][0]["organization"] == "Brown University"


class TestGetWorks:
    def test_works_endpoint(self, client):
        works_response = {"group": RECORD["activities-summary"]["works"]["group"]}
        with patch.object(
            client, "_make_request", return_value=copy.deepcopy(works_response)
        ) as req:
            works = client.get_works(ORCID)
        req.assert_called_once_with(f"{ORCID}/works")
        assert [w["title"] for w in works] == ["Cracked pots", "Undated note"]
        assert works[0]["journal_title"] == "Journal of Psychoceramics"

    def test_invalid_orcid(self, client):
        assert client.get_works("not an orcid") == []
        assert client.get_profile("not an orcid") is None
