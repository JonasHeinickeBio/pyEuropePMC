"""UnifiedSearch(diagnostics=True): per-source status and matched sources (hermetic).

The clients are fakes, so every status is produced on purpose: a source that answers, one that
finds nothing, one that fails, one that is rate limited and one that could not be created.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.search import UnifiedSearch
from pyeuropepmc.features.search.unified_search import _failure, _http_status, _retry_after
from pyeuropepmc.models.literature import LiteratureResult

SAME = ("10.1234/same", "Same paper about fatigue")


def _rec(source: str, ident: str, doi: str, title: str) -> LiteratureResult:
    return LiteratureResult(source=source, source_id=ident, doi=doi, title=title)


class Fake:
    """A source client: returns records, or raises, and remembers what it was asked."""

    def __init__(
        self, records: list[LiteratureResult] | None = None, error: Exception | None = None
    ):
        self.records = records or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def search(self, query: str, limit: int = 25, sort: str | None = None):
        self.calls.append({"query": query, "limit": limit, "sort": sort})
        if self.error:
            raise self.error
        return list(self.records)


def _http_error(status: int, retry_after: str | None = None) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    if retry_after:
        response.headers["Retry-After"] = retry_after
    return requests.HTTPError(f"{status} Client Error", response=response)


def _searcher(clients: dict[str, Any], **kwargs: Any) -> UnifiedSearch:
    searcher = UnifiedSearch(sources=list(clients), **kwargs)
    searcher._clients = clients
    return searcher


@pytest.fixture
def mixed() -> UnifiedSearch:
    clients = {
        "europepmc": Fake([_rec("europepmc", "1", *SAME)]),
        "pubmed": Fake([_rec("pubmed", "9", *SAME), _rec("pubmed", "10", "10.1/other", "Other")]),
        "arxiv": Fake([]),
        "openalex": Fake(error=_http_error(429, "7")),
        "core": Fake(error=ConnectionError("connection refused")),
        "doaj": None,
    }
    searcher = _searcher(clients)
    searcher._init_errors["doaj"] = "ImportError: DOAJ client needs a package"
    return searcher


class TestStatus:
    def test_every_queried_source_has_a_row_with_a_status(self, mixed):
        _, report = mixed.search("fatigue", diagnostics=True)
        status = report.metadata["source_status"]
        assert set(status) == {"europepmc", "pubmed", "arxiv", "openalex", "core", "doaj"}
        assert {n: row["status"] for n, row in status.items()} == {
            "europepmc": "ok",
            "pubmed": "ok",
            "arxiv": "empty",
            "openalex": "rate_limited",
            "core": "error",
            "doaj": "unavailable",
        }

    def test_zero_results_and_an_unavailable_source_are_different(self, mixed):
        status = mixed.search("fatigue", diagnostics=True)[1].metadata["source_status"]
        assert status["arxiv"]["records"] == 0 and status["arxiv"]["error"] is None
        assert status["doaj"]["records"] == 0 and status["doaj"]["error"] is not None
        assert status["arxiv"]["status"] != status["doaj"]["status"]

    def test_an_unavailable_source_says_why_it_could_not_be_created(self, mixed):
        row = mixed.search("fatigue", diagnostics=True)[1].metadata["source_status"]["doaj"]
        assert row["error"]["message"] == "ImportError: DOAJ client needs a package"
        assert row["query"] is None and row["seconds"] is None

    def test_a_failure_carries_the_error_type_message_and_http_status(self, mixed):
        status = mixed.search("fatigue", diagnostics=True)[1].metadata["source_status"]
        assert status["core"]["error"] == {
            "type": "ConnectionError",
            "message": "connection refused",
            "http_status": None,
        }
        assert status["openalex"]["error"]["http_status"] == 429
        assert status["openalex"]["retry_after"] == 7.0
        assert status["core"]["retry_after"] is None

    def test_a_row_records_what_was_sent(self, mixed):
        status = mixed.search("TITLE:fatigue", limit=10, sort="date", diagnostics=True)[
            1
        ].metadata["source_status"]
        assert status["europepmc"]["limit"] == 20  # the primary source asks for 2x
        assert status["pubmed"]["limit"] == 10
        assert status["europepmc"]["sort"] == "P_PDATE_D desc"
        assert status["pubmed"]["sort"] == "pub_date"
        assert status["pubmed"]["query"] == "TITLE:fatigue"
        assert status["arxiv"]["seconds"] >= 0

    def test_the_rows_are_plain_json(self, mixed):
        json.dumps(mixed.search("fatigue", diagnostics=True)[1].metadata["source_status"])

    def test_status_is_reported_when_every_source_fails(self):
        searcher = _searcher({"pubmed": Fake(error=ValueError("boom")), "arxiv": None})
        results, report = searcher.search("x", diagnostics=True)
        assert results == []
        assert {n: r["status"] for n, r in report.metadata["source_status"].items()} == {
            "pubmed": "error",
            "arxiv": "unavailable",
        }

    def test_the_old_error_map_is_unchanged(self, mixed):
        _, report = mixed.search("fatigue", diagnostics=True)
        assert report.metadata["source_errors"]["doaj"] == "client not initialised"
        assert report.metadata["source_errors"]["core"].startswith("ConnectionError")


class TestMatchedSources:
    def test_a_merged_record_lists_every_source_that_returned_it(self, mixed):
        results, _ = mixed.search("fatigue", diagnostics=True)
        by_doi = {r.doi: r for r in results}
        assert by_doi["10.1234/same"].matched_sources == ["europepmc", "pubmed"]
        assert by_doi["10.1/other"].matched_sources == ["pubmed"]

    def test_the_order_follows_the_order_the_sources_were_asked(self):
        clients = {
            "pubmed": Fake([_rec("pubmed", "9", *SAME)]),
            "arxiv": Fake([_rec("arxiv", "a", *SAME)]),
            "europepmc": Fake([_rec("europepmc", "1", *SAME)]),
        }
        results, _ = _searcher(clients, primary=None).search("x", diagnostics=True)
        assert results[0].matched_sources == ["pubmed", "arxiv", "europepmc"]

    def test_a_source_is_matched_by_pmid_too(self):
        a = LiteratureResult(source="europepmc", source_id="1", pmid="123", title="Alpha")
        b = LiteratureResult(source="pubmed", source_id="123", pmid="123", title="Different words")
        clients = {"europepmc": Fake([a]), "pubmed": Fake([b])}
        results, _ = _searcher(clients).search("x", diagnostics=True)
        assert results[0].matched_sources == ["europepmc", "pubmed"]

    def test_the_winning_source_is_always_in_the_list(self, mixed):
        for record in mixed.search("fatigue", diagnostics=True)[0]:
            assert record.source in record.matched_sources

    def test_matched_sources_survive_serialisation(self, mixed):
        record = mixed.search("fatigue", diagnostics=True)[0][0]
        assert record.model_dump()["matched_sources"] == record.matched_sources


class TestDefaultShapeIsUnchanged:
    def test_without_diagnostics_nothing_is_added(self, mixed):
        results, report = mixed.search("fatigue")
        assert "source_status" not in report.metadata
        assert all("matched_sources" not in (r.model_extra or {}) for r in results)
        assert all("matched_sources" not in r.model_dump() for r in results)

    def test_diagnostics_does_not_change_the_results_themselves(self, mixed):
        plain = [(r.source, r.source_id, r.doi) for r in mixed.search("fatigue")[0]]
        rich = [
            (r.source, r.source_id, r.doi) for r in mixed.search("fatigue", diagnostics=True)[0]
        ]
        assert plain == rich

    def test_diagnostics_is_not_forwarded_to_the_sources(self, mixed):
        mixed.search("fatigue", diagnostics=True)
        assert all(
            "diagnostics" not in call for c in mixed._clients.values() if c for call in c.calls
        )

    def test_search_all_is_unaffected(self, mixed):
        per_source, errors = mixed.search_all("fatigue")
        assert set(per_source) == {"europepmc", "pubmed", "arxiv"} and "openalex" in errors


class TestClassification:
    @pytest.mark.parametrize(
        ("error", "status"),
        [
            (_http_error(429), "rate_limited"),
            (_http_error(503), "error"),
            (RuntimeError("Rate limit exceeded, slow down"), "rate_limited"),
            (RuntimeError("HTTP 429 Too Many Requests"), "rate_limited"),
            (ValueError("bad payload"), "error"),
        ],
    )
    def test_failures(self, error, status):
        assert _failure(error)["status"] == status

    def test_the_http_status_is_found_on_the_library_error_and_on_its_cause(self):
        assert _http_status(APIClientError(ErrorCodes.NET001, {"status_code": 429})) == 429
        wrapped = RuntimeError("search failed")
        wrapped.__cause__ = _http_error(502)
        assert _http_status(wrapped) == 502
        assert _http_status(ValueError("no status")) is None

    def test_a_rate_limit_error_of_the_library_is_classified(self):
        error = APIClientError(ErrorCodes.NET001, {"status_code": 429})
        assert _failure(error)["status"] == "rate_limited"

    @pytest.mark.parametrize(
        ("value", "seconds"), [("7", 7.0), ("1.5", 1.5), ("Wed, 21 Oct", None)]
    )
    def test_retry_after_only_when_it_is_a_number_of_seconds(self, value, seconds):
        assert _retry_after(_http_error(429, value)) == seconds
        assert _retry_after(ValueError("x")) is None


class Swallowing(Fake):
    """A client that, like the Semantic Scholar, OpenAlex and DBLP clients, catches its own
    failure, records it in ``last_error`` and returns no records."""

    def __init__(self, error: Exception, records: list[LiteratureResult] | None = None):
        super().__init__(records)
        self.swallowed = error

    def search(self, query: str, limit: int = 25, sort: str | None = None):
        self.last_error = self.swallowed
        return list(self.records)


class TestSwallowedFailures:
    def test_a_failure_the_client_swallowed_is_an_error_not_an_empty_source(self):
        searcher = _searcher(
            {
                "pubmed": Fake([_rec("pubmed", "1", *SAME)]),
                "semantic_scholar": Swallowing(_http_error(403)),
            }
        )
        _, report = searcher.search("x", diagnostics=True)
        row = report.metadata["source_status"]["semantic_scholar"]
        assert row["status"] == "error" and row["error"]["http_status"] == 403
        assert "semantic_scholar" in report.metadata["source_errors"]

    def test_a_swallowed_rate_limit_is_reported_as_one(self):
        searcher = _searcher({"openalex": Swallowing(_http_error(429, "12"))})
        _, report = searcher.search("x", diagnostics=True)
        row = report.metadata["source_status"]["openalex"]
        assert (row["status"], row["retry_after"]) == ("rate_limited", 12.0)

    def test_a_decoding_failure_is_an_error(self):
        searcher = _searcher({"dblp": Swallowing(ValueError("Expecting value: line 1 column 1"))})
        _, report = searcher.search("x", diagnostics=True)
        assert report.metadata["source_status"]["dblp"]["error"]["type"] == "ValueError"

    def test_records_that_arrived_are_kept_even_if_the_client_noted_an_error(self):
        partial = Swallowing(RuntimeError("page 2 failed"), [_rec("pubmed", "1", *SAME)])
        results, report = _searcher({"pubmed": partial}).search("x", diagnostics=True)
        assert len(results) == 1 and report.metadata["source_status"]["pubmed"]["status"] == "ok"

    def test_a_source_that_really_found_nothing_stays_empty(self):
        _, report = _searcher({"arxiv": Fake([])}).search("x", diagnostics=True)
        assert report.metadata["source_status"]["arxiv"]["status"] == "empty"

    def test_the_error_of_an_earlier_call_does_not_leak_into_the_next(self):
        client = Fake([])
        client.last_error = RuntimeError("an old failure")
        _, report = _searcher({"arxiv": client}).search("x", diagnostics=True)
        assert report.metadata["source_status"]["arxiv"]["status"] == "empty"

    def test_the_http_clients_record_a_body_that_is_not_json(self):
        import requests as rq

        from pyeuropepmc.features.search.base import BaseLiteratureClient

        class Page(BaseLiteratureClient):
            def search(self, query, limit=25, **kwargs):  # pragma: no cover
                return []

            def get_paper(self, identifier):  # pragma: no cover
                return None

            def _normalize_result(self, raw):  # pragma: no cover
                raise NotImplementedError

        class Session:
            headers: dict[str, str] = {}

            def get(self, url, **kwargs):
                response = rq.Response()
                response.status_code = 200
                response._content = b"<html>Making sure you're not a bot</html>"
                return response

        client = Page(base_url="https://example.org", rate_limit_delay=0)
        client.session = Session()  # type: ignore[assignment]
        assert client._make_request("x", use_cache=False) is None
        assert isinstance(client.last_error, ValueError)
