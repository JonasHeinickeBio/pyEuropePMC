"""Error mapping, cache handling and parsing branches of SearchClient (hermetic)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import warnings

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError, SearchError
from pyeuropepmc.features.literature.search import SearchClient

pytestmark = pytest.mark.unit


@pytest.fixture
def client():
    c = SearchClient()
    yield c
    c.close()


def _http_error(status: int | None) -> requests.exceptions.HTTPError:
    response = None
    if status is not None:
        response = requests.Response()
        response.status_code = status
    return requests.exceptions.HTTPError("boom", response=response)


class TestMakeRequestMapping:
    def test_an_unparsable_json_body_is_a_search_error(self, client):
        response = MagicMock(status_code=200)
        response.json.side_effect = ValueError("no json")
        with (
            patch.object(client, "_make_http_request", return_value=response),
            pytest.raises(SearchError) as caught,
        ):
            client._make_request("search", {"format": "json"})
        assert caught.value.error_code == ErrorCodes.SEARCH003

    def test_a_non_response_object_is_a_timeout_style_error(self, client):
        with (
            patch.object(client, "_get", return_value="not a response"),
            pytest.raises(SearchError) as caught,
        ):
            client._make_request("search", {"format": "json"})
        assert caught.value.error_code == ErrorCodes.NET002

    def test_xml_is_returned_as_text(self, client):
        response = MagicMock(status_code=200, text="<a/>")
        with patch.object(client, "_make_http_request", return_value=response):
            assert client._make_request("search", {"format": "xml"}) == "<a/>"

    @pytest.mark.parametrize(
        ("status", "code"),
        [
            (404, ErrorCodes.HTTP404),
            (403, ErrorCodes.HTTP403),
            (500, ErrorCodes.HTTP500),
            (418, ErrorCodes.NET001),
            (None, ErrorCodes.NET001),
        ],
    )
    def test_http_errors_map_to_codes(self, client, status, code):
        with (
            patch.object(client, "_make_http_request", side_effect=_http_error(status)),
            pytest.raises(SearchError) as caught,
        ):
            client._make_request("search", {"format": "json"})
        assert caught.value.error_code == code

    @pytest.mark.parametrize(
        ("error", "code"),
        [
            (requests.exceptions.Timeout("slow"), ErrorCodes.NET002),
            (requests.exceptions.RequestException("read timeout"), ErrorCodes.NET002),
            (requests.exceptions.ConnectionError("connection reset"), ErrorCodes.NET001),
            (requests.exceptions.RequestException("odd"), ErrorCodes.NET001),
        ],
    )
    def test_request_exceptions_map_to_codes(self, client, error, code):
        with (
            patch.object(client, "_make_http_request", side_effect=error),
            pytest.raises(SearchError) as caught,
        ):
            client._make_request("search", {"format": "json"})
        assert caught.value.error_code == code

    def test_an_unexpected_exception_is_wrapped(self, client):
        with (
            patch.object(client, "_make_http_request", side_effect=RuntimeError("bug")),
            pytest.raises(SearchError) as caught,
        ):
            client._make_request("search", {"format": "json"})
        assert caught.value.error_code == ErrorCodes.NET001

    def test_post_sends_form_encoded_data(self, client):
        response = requests.Response()
        response.status_code = 200
        with patch.object(client, "_post", return_value=response) as post:
            assert client._make_http_request("searchPOST", {"query": "a"}, "POST") is response
        assert post.call_args.kwargs["headers"] == {
            "Content-Type": "application/x-www-form-urlencoded"
        }


@pytest.fixture(params=["search", "search_post"])
def entry(request, client):
    """Run each cache/error test through both GET and POST search."""
    return getattr(client, request.param)


class TestCacheHandling:
    def test_a_cached_dict_is_returned_without_a_request(self, client, entry):
        client._cache = MagicMock()
        client._cache.get.return_value = {"hitCount": 1}
        with patch.object(client, "_make_request") as request:
            assert entry("malaria") == {"hitCount": 1}
        request.assert_not_called()

    def test_a_cached_string_is_returned(self, client, entry):
        client._cache = MagicMock()
        client._cache.get.return_value = "<xml/>"
        assert entry("malaria", format="xml") == "<xml/>"

    def test_a_cached_value_of_another_type_is_refetched(self, client, entry):
        client._cache = MagicMock()
        client._cache.get.return_value = ["unexpected"]
        with patch.object(client, "_make_request", return_value={"hitCount": 2}) as request:
            assert entry("malaria") == {"hitCount": 2}
        request.assert_called_once()

    def test_a_broken_cache_read_does_not_fail_the_search(self, client, entry):
        client._cache = MagicMock()
        client._cache.get.side_effect = RuntimeError("disk gone")
        with patch.object(client, "_make_request", return_value={"hitCount": 3}):
            assert entry("malaria") == {"hitCount": 3}

    def test_a_broken_cache_write_does_not_fail_the_search(self, client, entry):
        client._cache = MagicMock()
        client._cache.get.return_value = None
        client._cache.set.side_effect = RuntimeError("disk full")
        with patch.object(client, "_make_request", return_value={"hitCount": 4}):
            assert entry("malaria") == {"hitCount": 4}

    def test_a_fresh_result_is_cached(self, client, entry):
        client._cache = MagicMock()
        client._cache.get.return_value = None
        with patch.object(client, "_make_request", return_value={"hitCount": 5}):
            entry("malaria")
        client._cache.set.assert_called_once()


class TestSearchErrorMapping:
    @pytest.mark.parametrize(
        ("error", "code"),
        [
            (requests.exceptions.Timeout("slow"), ErrorCodes.NET002),
            (requests.exceptions.RequestException("HTTP 404 not found"), ErrorCodes.SEARCH006),
            (requests.exceptions.RequestException("HTTP 429 slow down"), ErrorCodes.RATE429),
            (requests.exceptions.RequestException("odd"), ErrorCodes.NET001),
        ],
    )
    def test_request_exceptions_map_to_codes(self, client, error, code):
        with (
            patch.object(client, "_make_request", side_effect=error),
            pytest.raises(SearchError) as caught,
        ):
            client.search("malaria")
        assert caught.value.error_code == code

    def test_search_post_reports_a_request_exception_as_a_network_error(self, client):
        with (
            patch.object(client, "_make_request", side_effect=requests.exceptions.Timeout("x")),
            pytest.raises(SearchError) as caught,
        ):
            client.search_post("malaria")
        assert caught.value.error_code == ErrorCodes.NET001

    def test_a_search_error_passes_through(self, client, entry):
        original = SearchError(ErrorCodes.SEARCH004, {"format": "x", "valid_formats": []})
        with (
            patch.object(client, "_make_request", side_effect=original),
            pytest.raises(SearchError) as caught,
        ):
            entry("malaria")
        assert caught.value is original

    def test_an_unexpected_exception_is_wrapped(self, client, entry):
        with (
            patch.object(client, "_make_request", side_effect=RuntimeError("bug")),
            pytest.raises(SearchError) as caught,
        ):
            entry("malaria")
        assert caught.value.error_code == ErrorCodes.SEARCH003


class TestClientLifecycle:
    def test_close_closes_the_cache(self):
        c = SearchClient()
        c._cache = MagicMock()
        cache = c._cache
        c.close()
        cache.close.assert_called_once()


class TestFetchAllPages:
    def test_it_warns_and_delegates_to_search_all(self, client):
        with (
            patch.object(client, "search_all", return_value=[{"id": 1}]) as search_all,
            warnings.catch_warnings(record=True) as seen,
        ):
            warnings.simplefilter("always")
            assert client.fetch_all_pages("q", page_size=5, max_results=7, sort="x") == [{"id": 1}]
        assert any(issubclass(w.category, DeprecationWarning) for w in seen)
        search_all.assert_called_once_with("q", page_size=5, max_results=7, sort="x")


class TestExtractPageResults:
    @pytest.mark.parametrize(
        "data",
        [
            None,
            "text",
            {},
            {"resultList": "nope"},
            {"resultList": {}},
            {"resultList": {"result": "nope"}},
            {"resultList": {"result": []}},
        ],
    )
    def test_an_unusable_page_gives_nothing(self, client, data):
        assert client._extract_page_results(data) == ([], None)

    def test_a_non_string_cursor_is_dropped(self, client):
        data = {"resultList": {"result": [{"id": 1}]}, "nextCursorMark": 5}
        assert client._extract_page_results(data) == ([{"id": 1}], None)


class TestSearchAllPaging:
    def _pages(self, *page_ids):
        out = []
        for index, ids in enumerate(page_ids):
            body = {"hitCount": 99, "resultList": {"result": [{"id": i} for i in ids]}}
            if index < len(page_ids) - 1:
                body["nextCursorMark"] = f"c{index + 2}"
            out.append(body)
        return out

    def test_each_request_carries_the_cursor_of_the_page_before(self, client):
        with patch.object(client, "search", side_effect=self._pages([1], [2], [3])) as search:
            client.search_all("q", page_size=5)
        cursors = [call.kwargs["cursorMark"] for call in search.call_args_list]
        assert cursors == ["*", "c2", "c3"]

    def test_the_result_is_trimmed_to_max_results(self, client):
        with patch.object(client, "search", side_effect=self._pages([1, 2, 3, 4])):
            assert len(client.search_all("q", page_size=10, max_results=2)) == 2

    def test_no_request_is_made_for_a_non_positive_limit(self, client):
        with patch.object(client, "search") as search:
            assert client.search_all("q", max_results=0) == []
        search.assert_not_called()

    def test_the_page_size_is_clamped_to_the_api_range(self, client):
        with patch.object(client, "search", side_effect=self._pages([1])) as search:
            client.search_all("q", page_size=5000)
        assert search.call_args.kwargs["page_size"] == 1000

    def test_a_short_page_with_a_new_cursor_continues(self, client):
        with patch.object(client, "search", side_effect=self._pages([1], [2, 3])) as search:
            assert [r["id"] for r in client.search_all("q", page_size=5)] == [1, 2, 3]
        assert search.call_count == 2

    def test_a_failure_on_a_later_page_raises_instead_of_returning_a_part(self, client):
        pages = self._pages([1, 2])
        pages[0]["nextCursorMark"] = "c2"
        with (
            patch.object(
                client, "search", side_effect=[pages[0], SearchError(ErrorCodes.NET001, {})]
            ),
            pytest.raises(SearchError),
        ):
            client.search_all("q", page_size=2)


class TestInteractivePrompt:
    def test_ctrl_c_at_the_prompt_cancels(self, client):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            assert client._prompt_user_for_result_count(10, "q") == 0

    def test_an_out_of_range_number_asks_again(self, client):
        with patch("builtins.input", side_effect=["99", "3"]):
            assert client._prompt_user_for_result_count(10, "q") == 3

    def test_text_asks_again(self, client):
        with patch("builtins.input", side_effect=["many", "q"]):
            assert client._prompt_user_for_result_count(10, "q") == 0


class TestSearchAndParse:
    def test_an_unknown_format_is_rejected_before_any_request(self, client):
        with (
            patch.object(client, "search") as search,
            pytest.raises(SearchError) as caught,
        ):
            client.search_and_parse("q", format="csv")
        assert caught.value.error_code == ErrorCodes.SEARCH004
        search.assert_not_called()

    def test_json_must_arrive_as_a_dict(self, client):
        with (
            patch.object(client, "search", return_value="text"),
            pytest.raises(ParsingError) as caught,
        ):
            client.search_and_parse("q")
        assert caught.value.error_code == ErrorCodes.PARSE001

    @pytest.mark.parametrize("fmt", ["xml", "dc"])
    def test_xml_and_dc_must_arrive_as_text(self, client, fmt):
        with (
            patch.object(client, "search", return_value={"a": 1}),
            pytest.raises(ParsingError) as caught,
        ):
            client.search_and_parse("q", format=fmt)
        assert caught.value.error_code == ErrorCodes.PARSE004

    @pytest.mark.parametrize(
        ("fmt", "parser"), [("json", "parse_json"), ("xml", "parse_xml"), ("dc", "parse_dc")]
    )
    def test_each_format_goes_to_its_parser(self, client, fmt, parser):
        raw = {"resultList": {"result": []}} if fmt == "json" else "<x/>"
        with (
            patch.object(client, "search", return_value=raw),
            patch(
                f"pyeuropepmc.features.literature.search.EuropePMCParser.{parser}",
                return_value=[{"ok": 1}],
            ) as parse,
        ):
            assert client.search_and_parse("q", format=fmt.upper()) == [{"ok": 1}]
        parse.assert_called_once_with(raw)

    def test_a_parser_crash_is_a_search_error(self, client):
        with (
            patch.object(client, "search", return_value="<x/>"),
            patch(
                "pyeuropepmc.features.literature.search.EuropePMCParser.parse_xml",
                side_effect=RuntimeError("bad"),
            ),
            pytest.raises(SearchError) as caught,
        ):
            client.search_and_parse("q", format="xml")
        assert caught.value.error_code == ErrorCodes.SEARCH005
