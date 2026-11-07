"""ArticleClient.get_related_articles (hermetic).

HTTP is mocked at ``requests.Session.get``; the real ``BaseAPIClient._get`` runs.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, ValidationError
from pyeuropepmc.features.literature.article import ArticleClient

pytestmark = pytest.mark.unit


def _json_response(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response.reason = "OK" if status < 400 else "Error"
    response.url = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
    response._content = json.dumps(payload).encode("utf-8")
    response._content_consumed = True
    return response


def _mesh(*headings):
    return {
        "meshHeadingList": {
            "meshHeading": [{"descriptorName": n, "majorTopic_YN": y} for n, y in headings]
        }
    }


RECORD = {
    "result": {
        "id": "1",
        **_mesh(
            ("Humans", "N"),
            ("Mitochondria", "N"),
            ("Mutation", "Y"),
            ("Animals", "N"),
            ("DNA, Mitochondrial", "N"),
            ("Transfection", "N"),
        ),
        "keywordList": {"keyword": ["heteroplasmy", "RNA import"]},
    }
}
HITS = {
    "version": "6.9",
    "hitCount": 2,
    "nextCursorMark": "AoE=",
    "resultList": {
        "result": [
            {"id": "10", "source": "MED", "title": "A"},
            {"id": "11", "source": "MED", "title": "B"},
        ]
    },
}


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("time.sleep"):
        yield


@pytest.fixture
def client():
    instance = ArticleClient(rate_limit_delay=0)
    yield instance
    instance.close()


def _route(record=RECORD, hits=HITS):
    def get(url, params=None, **kwargs):  # noqa: ARG001
        return _json_response(hits if url.endswith("/search") else record)

    return patch.object(requests.Session, "get", side_effect=get)


def _search_params(mocked):
    calls = [c for c in mocked.call_args_list if c[0][0].endswith("/search")]
    assert len(calls) == 1
    return calls[0].kwargs["params"]


class TestQuery:
    def test_major_topics_come_first_and_generic_headings_are_left_out(self, client):
        with _route() as get:
            page = client.get_related_articles("MED", "1")
        assert page["terms"] == ["Mutation", "Mitochondria", "DNA, Mitochondrial"]
        assert _search_params(get)["query"] == (
            'MESH:("Mutation" OR "Mitochondria" OR "DNA, Mitochondrial") '
            "AND NOT (EXT_ID:1 AND SRC:MED)"
        )

    def test_the_field_is_named_once_not_per_term(self, client):
        """Europe PMC evaluates ``MESH:"a" OR MESH:"b"`` as ``MESH:"b"`` alone."""
        with _route() as get:
            client.get_related_articles("MED", "1")
        assert _search_params(get)["query"].count("MESH:") == 1

    def test_match_all_joins_the_terms_with_and(self, client):
        with _route() as get:
            client.get_related_articles("MED", "1", match="all", max_terms=2)
        assert _search_params(get)["query"].startswith(
            'MESH:("Mutation" AND "Mitochondria") AND NOT'
        )

    def test_the_article_is_left_out_by_source_and_id(self, client):
        with _route() as get:
            client.get_related_articles("PMC", "PMC123")
        assert "AND NOT (EXT_ID:PMC123 AND SRC:PMC)" in _search_params(get)["query"]

    def test_keywords_when_asked_for(self, client):
        with _route() as get:
            page = client.get_related_articles("MED", "1", basis="keywords")
        assert page["terms"] == ["heteroplasmy", "RNA import"]
        assert _search_params(get)["query"].startswith('KW:("heteroplasmy" OR "RNA import")')

    def test_auto_falls_back_to_keywords_without_mesh(self, client):
        record = {"result": {"keywordList": {"keyword": ["heteroplasmy"]}}}
        with _route(record=record) as get:
            page = client.get_related_articles("MED", "1")
        assert page["terms"] == ["heteroplasmy"]
        assert _search_params(get)["query"].startswith("KW:(")

    def test_quotes_in_a_term_cannot_break_out_of_the_phrase(self, client):
        with _route() as get:
            client.get_related_articles("MED", "1", terms=['a" OR "b'])
        assert _search_params(get)["query"].startswith('MESH:("a  OR  b")')


class TestPaging:
    def test_page_arguments_reach_the_search(self, client):
        with _route() as get:
            client.get_related_articles(
                "MED", "1", page_size=5, cursor_mark="AoX=", result_type="core", sort="CITED desc"
            )
        params = _search_params(get)
        assert (
            params["pageSize"],
            params["cursorMark"],
            params["resultType"],
            params["sort"],
        ) == (
            5,
            "AoX=",
            "core",
            "CITED desc",
        )
        assert params["format"] == "json"

    def test_given_terms_save_the_request_for_the_article(self, client):
        with _route() as get:
            page = client.get_related_articles("MED", "1", terms=["Mutation", "Mutation", " "])
        assert [c[0][0] for c in get.call_args_list] == [
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        ]
        assert page["terms"] == ["Mutation"]

    def test_the_response_has_the_query_the_cursor_and_parsed_records(self, client):
        with _route():
            page = client.get_related_articles("MED", "1")
        assert page["hitCount"] == 2 and page["nextCursorMark"] == "AoE="
        assert [r["id"] for r in page["results"]] == ["10", "11"]
        assert page["query"].startswith("MESH:(")

    def test_extra_parameters_are_sent(self, client):
        with _route() as get:
            client.get_related_articles("MED", "1", synonym="true")
        assert _search_params(get)["synonym"] == "true"


class TestNothingToSearch:
    @pytest.mark.parametrize("record", [{"result": {}}, {"result": None}, {}])
    def test_an_article_without_terms_is_an_empty_page_and_no_search(self, client, record):
        with _route(record=record) as get:
            page = client.get_related_articles("MED", "1")
        assert page == {
            "query": None,
            "terms": [],
            "hitCount": 0,
            "nextCursorMark": None,
            "results": [],
        }
        assert all(not c[0][0].endswith("/search") for c in get.call_args_list)

    def test_no_matches_is_an_empty_list_with_a_zero_count(self, client):
        empty = {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}
        with _route(hits=empty), pytest.warns(UserWarning):
            page = client.get_related_articles("MED", "1")
        assert page["hitCount"] == 0 and page["results"] == []


class TestErrors:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"basis": "title"},
            {"match": "some"},
            {"max_terms": 0},
            {"max_terms": 11},
            {"page_size": 0},
            {"page_size": 1001},
            {"result_type": "full"},
        ],
    )
    def test_invalid_arguments_are_refused_before_any_request(self, client, kwargs):
        with patch.object(requests.Session, "get") as get, pytest.raises(ValidationError):
            client.get_related_articles("MED", "1", **kwargs)
        get.assert_not_called()

    def test_a_bad_source_is_refused(self, client):
        with pytest.raises(ValidationError):
            client.get_related_articles("MEDLINE", "1")

    def test_a_failed_search_is_raised(self, client):
        def get(url, params=None, **kwargs):  # noqa: ARG001
            if url.endswith("/search"):
                return _json_response({"error": "x"}, status=500)
            return _json_response(RECORD)

        with (
            patch.object(requests.Session, "get", side_effect=get),
            pytest.raises(APIClientError) as caught,
        ):
            client.get_related_articles("MED", "1")
        assert caught.value.error_code in {ErrorCodes.HTTP500, ErrorCodes.NET001}

    def test_a_failed_article_lookup_is_raised(self, client):
        with (
            patch.object(requests.Session, "get", return_value=_json_response({}, status=404)),
            pytest.raises(APIClientError),
        ):
            client.get_related_articles("MED", "1")
