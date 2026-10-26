"""The Semantic Scholar search asks again when it is answered with HTTP 429 (hermetic)."""

from __future__ import annotations

import time
from typing import Any

import pytest
import requests

from pyeuropepmc.features.literature import adapters
from pyeuropepmc.features.literature.adapters import SemanticScholarLiteratureAdapter

PAGE = {"total": 1, "data": [{"paperId": "abc", "title": "A paper", "year": 2024}]}


def _response(status: int, retry_after: str | None = None, body: Any = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    if retry_after is not None:
        response.headers["Retry-After"] = retry_after
    response._content = b"{}" if body is None else __import__("json").dumps(body).encode()
    return response


class Session:
    """Answers with the given responses in order and counts the requests."""

    def __init__(self, *responses: requests.Response) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.headers: dict[str, str] = {}

    def get(self, url, params=None, timeout=None, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


@pytest.fixture
def pauses(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(adapters.time, "sleep", slept.append)
    return slept


def _adapter(session: Session) -> SemanticScholarLiteratureAdapter:
    adapter = SemanticScholarLiteratureAdapter()
    adapter._http.session = session  # type: ignore[assignment]
    return adapter


def test_a_429_is_asked_again_and_the_search_succeeds(pauses):
    session = Session(_response(429), _response(429), _response(200, body=PAGE))
    results = _adapter(session).search("long covid", limit=1)
    assert session.calls == 3 and len(results) == 1
    assert pauses == [1.5, 3.0]  # backs off when the server names no wait


def test_retry_after_is_honoured_up_to_a_ceiling(pauses):
    session = Session(_response(429, "4"), _response(429, "600"), _response(200, body=PAGE))
    _adapter(session).search("x", limit=1)
    assert pauses == [4.0, SemanticScholarLiteratureAdapter.RATE_LIMIT_MAX_WAIT]


def test_it_gives_up_after_a_few_attempts_and_the_error_reaches_the_caller(pauses):
    attempts = SemanticScholarLiteratureAdapter.RATE_LIMIT_ATTEMPTS
    session = Session(*[_response(429, "2") for _ in range(attempts)])
    adapter = _adapter(session)
    with pytest.raises(requests.HTTPError) as caught:
        adapter._search_http({"query": "x"})
    assert session.calls == attempts and len(pauses) == attempts - 1
    assert caught.value.response.status_code == 429  # lets UnifiedSearch call it rate_limited


def test_search_reports_the_failure_to_unified_search_instead_of_returning_nothing_silently(
    pauses,
):
    attempts = SemanticScholarLiteratureAdapter.RATE_LIMIT_ATTEMPTS
    adapter = _adapter(Session(*[_response(429) for _ in range(attempts)]))
    assert adapter.search("x", limit=1) == []
    assert isinstance(adapter.last_error, requests.HTTPError)


def test_other_errors_are_not_retried(pauses):
    session = Session(_response(403))
    with pytest.raises(requests.HTTPError):
        _adapter(session)._search_http({"query": "x"})
    assert session.calls == 1 and pauses == []


def test_a_successful_request_does_not_wait(pauses):
    session = Session(_response(200, body=PAGE))
    _adapter(session).search("x", limit=1)
    assert session.calls == 1 and pauses == []


def test_the_longest_total_pause_is_bounded():
    cls = SemanticScholarLiteratureAdapter
    assert (cls.RATE_LIMIT_ATTEMPTS - 1) * cls.RATE_LIMIT_MAX_WAIT <= 30
    assert time.sleep is not None
