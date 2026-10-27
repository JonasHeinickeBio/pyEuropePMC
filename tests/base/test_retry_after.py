"""BaseAPIClient waits as the server asks (``Retry-After``) and gives up when told to wait too long."""

from __future__ import annotations

import datetime
import email.utils
from unittest.mock import MagicMock

import pytest
import requests

from pyeuropepmc.core.base import RETRY_AFTER_MAX_WAIT, BaseAPIClient
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.core.retry_after import parse_retry_after, retry_after_of


def _response(status: int, retry_after: str | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.url = "https://example.test/x"
    if retry_after is not None:
        response.headers["Retry-After"] = retry_after
    return response


@pytest.fixture
def sleeps(monkeypatch):
    """Record every sleep instead of waiting; zero-length politeness sleeps are left out."""
    waited: list[float] = []
    monkeypatch.setattr("time.sleep", lambda seconds: waited.append(seconds) if seconds else None)
    return waited


def _client(*responses: requests.Response) -> BaseAPIClient:
    client = BaseAPIClient(rate_limit_delay=0)
    session = MagicMock()
    session.get.side_effect = list(responses)
    session.post.side_effect = list(responses)
    client.session = session
    return client


class TestParseRetryAfter:
    def test_seconds(self):
        assert parse_retry_after("7") == 7.0
        assert parse_retry_after(" 2.5 ") == 2.5

    def test_http_date(self):
        now = datetime.datetime(2026, 10, 27, 12, 0, 0, tzinfo=datetime.timezone.utc)
        due = email.utils.format_datetime(now + datetime.timedelta(seconds=45), usegmt=True)
        assert parse_retry_after(due, now=now) == 45.0

    @pytest.mark.parametrize("value", [None, "", "  ", "soon", "-3", "nan", "inf"])
    def test_unusable_values_count_as_absent(self, value):
        assert parse_retry_after(value) is None

    def test_more_digits_than_a_float_holds_is_a_very_long_wait_not_no_header(self):
        huge = "9" * 400
        assert parse_retry_after(huge) == 365 * 24 * 3600.0
        assert parse_retry_after("1" + "0" * 20) == 365 * 24 * 3600.0
        assert parse_retry_after("inf") is None  # not a delay-seconds

    def test_a_date_already_past_counts_as_absent(self):
        now = datetime.datetime(2026, 10, 27, 12, 0, 0, tzinfo=datetime.timezone.utc)
        past = email.utils.format_datetime(now - datetime.timedelta(minutes=5), usegmt=True)
        assert parse_retry_after(past, now=now) is None

    def test_read_from_an_error_response(self):
        error = requests.HTTPError(response=_response(429, "4"))
        assert retry_after_of(error) == 4.0
        assert retry_after_of(requests.HTTPError(response=_response(429))) is None
        assert retry_after_of(requests.ConnectionError("down")) is None


class TestGetHonoursRetryAfter:
    def test_waits_as_asked_then_succeeds(self, sleeps):
        client = _client(_response(429, "3"), _response(200))
        assert client._get("x").status_code == 200
        assert sleeps == [3.0]

    def test_without_the_header_it_backs_off_exponentially(self, sleeps):
        client = _client(_response(503), _response(503), _response(200))
        assert client._get("x").status_code == 200
        assert sleeps == [1.0, 2.0]

    def test_header_replaces_only_the_attempts_that_carry_it(self, sleeps):
        client = _client(_response(503), _response(429, "5"), _response(502), _response(200))
        client._get("x")
        assert sleeps == [1.0, 5.0, 4.0]

    def test_a_request_for_a_longer_wait_than_the_cap_is_not_retried(self, sleeps):
        asked = str(int(RETRY_AFTER_MAX_WAIT) + 90)
        client = _client(_response(429, asked), _response(200))
        with pytest.raises(APIClientError) as caught:
            client._get("x")
        assert caught.value.error_code == ErrorCodes.RATE429
        assert caught.value.context["retry_after"] == float(asked)
        assert sleeps == []
        assert client.session.get.call_count == 1

    def test_the_last_error_carries_the_advice(self, sleeps):
        client = _client(*[_response(429, "1")] * 5)
        with pytest.raises(APIClientError) as caught:
            client._get("x")
        assert caught.value.error_code == ErrorCodes.RATE429
        assert caught.value.context["retry_after"] == 1.0
        assert client.session.get.call_count == 5

    def test_a_status_a_retry_cannot_fix_is_still_not_retried(self, sleeps):
        client = _client(_response(404, "1"), _response(200))
        with pytest.raises(APIClientError) as caught:
            client._get("x")
        assert caught.value.error_code == ErrorCodes.HTTP404
        assert sleeps == []


class TestOversizedAdvice:
    def test_digits_beyond_float_range_stop_the_retries(self, sleeps):
        client = _client(_response(429, "9" * 400), _response(200))
        with pytest.raises(APIClientError) as caught:
            client._get("x")
        assert caught.value.context["retry_after"] == 365 * 24 * 3600.0
        assert sleeps == []
        assert client.session.get.call_count == 1


class TestPostHonoursRetryAfter:
    def test_waits_as_asked_then_succeeds(self, sleeps):
        client = _client(_response(503, "2"), _response(200))
        assert client._post("x", {"a": "b"}).status_code == 200
        assert sleeps == [2.0]

    def test_the_error_carries_the_advice(self, sleeps):
        client = _client(_response(429, "600"))
        with pytest.raises(APIClientError) as caught:
            client._post("x", {})
        assert caught.value.context["retry_after"] == 600.0
        assert caught.value.context["method"] == "POST"
        assert sleeps == []
