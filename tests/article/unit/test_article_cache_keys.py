"""ArticleClient cache keys cover every request parameter (hermetic).

HTTP is mocked at ``requests.Session.get``; each answer carries the parameters it was asked
with, so a response served from the wrong cache entry is visible. The cache is real, in a
temporary folder.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.features.literature.article import ArticleClient, _cache_key

pytestmark = pytest.mark.unit


def _answer(url, params=None, **kwargs):  # noqa: ARG001
    response = requests.Response()
    response.status_code = 200
    response.url = url
    response._content = json.dumps(
        {"hitCount": 1, "asked": params, "result": {"title": "t"}}
    ).encode("utf-8")
    response._content_consumed = True
    return response


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("time.sleep"):
        yield


@pytest.fixture
def client(tmp_path: Path):
    instance = ArticleClient(
        rate_limit_delay=0, cache_config=CacheConfig(enabled=True, cache_dir=tmp_path / "cache")
    )
    yield instance
    instance.close()


@pytest.fixture
def get():
    with patch.object(requests.Session, "get", side_effect=_answer) as mocked:
        yield mocked


class TestCacheKey:
    def test_the_same_parameters_in_any_order_give_one_key(self):
        a = _cache_key("citations", "MED", "1", {"page": 1, "sort": "x", "format": "json"})
        b = _cache_key("citations", "MED", "1", {"format": "json", "sort": "x", "page": 1})
        assert a == b

    @pytest.mark.parametrize(
        "other",
        [{"page": 2}, {"page": 1, "sort": "y"}, {"page": 1, "cursorMark": "*"}, {}],
    )
    def test_any_other_parameter_gives_another_key(self, other):
        assert _cache_key("citations", "MED", "1", {"page": 1}) != _cache_key(
            "citations", "MED", "1", other
        )

    def test_the_endpoint_and_article_are_part_of_the_key(self):
        base = _cache_key("citations", "MED", "1", {"page": 1})
        assert base != _cache_key("references", "MED", "1", {"page": 1})
        assert base != _cache_key("citations", "PMC", "1", {"page": 1})
        assert base != _cache_key("citations", "MED", "2", {"page": 1})

    def test_the_prefix_stays_readable_for_invalidation(self):
        assert _cache_key("citations", "MED", "123", {"page": 1}).startswith("citations:MED:123:")

    def test_values_that_are_not_json_still_make_a_key(self):
        assert _cache_key("citations", "MED", "1", {"when": Path("x")})

    def test_bytes_and_the_string_that_looks_like_them_are_different_requests(self):
        """``cursorMark=b"x"`` and ``cursorMark="b'x'"`` are sent as different query strings."""
        assert _cache_key("citations", "MED", "1", {"cursorMark": b"x"}) != _cache_key(
            "citations", "MED", "1", {"cursorMark": "b'x'"}
        )

    def test_a_parameter_set_to_none_is_not_part_of_the_request(self):
        """``requests`` does not send it, so it must not split the cache."""
        assert _cache_key("citations", "MED", "1", {"page": 1, "sort": None}) == _cache_key(
            "citations", "MED", "1", {"page": 1}
        )

    def test_parameters_that_cannot_be_serialized_give_no_key(self):
        mixed = {None: None, "P_PDATE_D desc": None}
        assert _cache_key("citations", "MED", "1", {"sort": mixed}) is None
        loop: list = []
        loop.append(loop)
        assert _cache_key("citations", "MED", "1", {"sort": loop}) is None


class TestDetails:
    def test_the_same_request_is_served_from_the_cache(self, client, get):
        client.get_article_details("MED", "1", resultType="core")
        client.get_article_details("MED", "1", resultType="core")
        assert get.call_count == 1

    def test_an_extra_parameter_is_a_different_request(self, client, get):
        first = client.get_article_details("MED", "1")
        second = client.get_article_details("MED", "1", synonym="true")
        assert get.call_count == 2
        assert "synonym" not in first["asked"] and second["asked"]["synonym"] == "true"

    def test_a_different_value_of_the_same_parameter_is_a_different_request(self, client, get):
        client.get_article_details("MED", "1", synonym="true")
        again = client.get_article_details("MED", "1", synonym="false")
        assert get.call_count == 2 and again["asked"]["synonym"] == "false"

    def test_a_jsonp_callback_is_never_cached(self, client, get):
        client.get_article_details("MED", "1", format="xml", callback="cb")
        client.get_article_details("MED", "1", format="xml", callback="cb")
        assert get.call_count == 2

    def test_a_callback_of_none_is_no_callback(self, client, get):
        client.get_article_details("MED", "1", callback=None)
        client.get_article_details("MED", "1", callback=None)
        client.get_article_details("MED", "1")
        assert get.call_count == 1

    def test_parameters_that_cannot_be_keyed_still_send_the_request(self, client, get):
        odd = {None: None, "x": None}
        first = client.get_article_details("MED", "1", extra=odd)
        client.get_article_details("MED", "1", extra=odd)
        assert first["hitCount"] == 1
        assert get.call_count == 2  # not cached, but not refused either


@pytest.mark.parametrize("method", ["get_citations", "get_references"])
class TestPagedLists:
    def test_the_same_request_is_served_from_the_cache(self, client, get, method):
        getattr(client, method)("MED", "1", page=2)
        getattr(client, method)("MED", "1", page=2)
        assert get.call_count == 1

    def test_sort_is_part_of_the_request(self, client, get, method):
        newest = getattr(client, method)("MED", "1", sort="P_PDATE_D desc")
        oldest = getattr(client, method)("MED", "1", sort="P_PDATE_D asc")
        assert get.call_count == 2
        assert newest["asked"]["sort"] != oldest["asked"]["sort"]

    def test_a_cursor_mark_is_part_of_the_request(self, client, get, method):
        getattr(client, method)("MED", "1", cursorMark="*")
        second = getattr(client, method)("MED", "1", cursorMark="AoE")
        assert get.call_count == 2 and second["asked"]["cursorMark"] == "AoE"

    def test_a_request_without_the_extra_parameter_is_not_answered_by_one_with_it(
        self, client, get, method
    ):
        getattr(client, method)("MED", "1", sort="x")
        plain = getattr(client, method)("MED", "1")
        assert get.call_count == 2 and "sort" not in plain["asked"]

    def test_a_jsonp_callback_is_never_cached(self, client, get, method):
        getattr(client, method)("MED", "1", callback="cb")
        getattr(client, method)("MED", "1", callback="cb")
        assert get.call_count == 2

    def test_parameters_that_cannot_be_keyed_still_send_the_request(self, client, get, method):
        odd = {None: None, "P_PDATE_D desc": None}
        getattr(client, method)("MED", "1", sort=odd)
        getattr(client, method)("MED", "1", sort=odd)
        assert get.call_count == 2  # not cached, but not refused either


def test_invalidating_one_article_still_finds_its_entries(client, get):
    client.get_article_details("MED", "1")
    client.get_citations("MED", "1", sort="x")
    client.get_references("MED", "1", cursorMark="*")
    client.get_citations("MED", "2")
    assert get.call_count == 4

    assert client.invalidate_article_cache(source="MED", article_id="1") == 3

    client.get_article_details("MED", "1")
    client.get_citations("MED", "2")
    assert get.call_count == 5  # article 1 was fetched again, article 2 was not


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("get_article_details", ("MED", "1")),
        ("get_citations", ("MED", "1")),
        ("get_references", ("MED", "1")),
    ],
)
def test_a_broken_cache_never_fails_the_request(client, get, method, args):
    """A cache that raises on read and on write only costs the saved request."""
    with (
        patch.object(client._cache, "get", side_effect=RuntimeError("cache down")),
        patch.object(client._cache, "set", side_effect=RuntimeError("cache full")),
    ):
        first = getattr(client, method)(*args)
        getattr(client, method)(*args)
    assert first["hitCount"] == 1
    assert get.call_count == 2
