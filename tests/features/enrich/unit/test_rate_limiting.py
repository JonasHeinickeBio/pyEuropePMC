"""Rate limiting and error behaviour shared by the BaseEnrichmentClient clients.

Requests are mocked at ``requests.Session.get``; ``time.sleep`` is patched so
the waits are recorded instead of slept.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.enrich.base import BaseEnrichmentClient
from pyeuropepmc.features.enrich.sources.crossref import CrossRefClient
from pyeuropepmc.features.enrich.sources.datacite import DataCiteClient
from pyeuropepmc.features.enrich.sources.icite import ICiteClient
from pyeuropepmc.features.enrich.sources.openalex import OpenAlexClient
from pyeuropepmc.features.enrich.sources.orcid import OrcidClient
from pyeuropepmc.features.enrich.sources.ror import RorClient
from pyeuropepmc.features.enrich.sources.unpaywall import UnpaywallClient
from pyeuropepmc.utils.dependencies import is_dependency_available

pytestmark = pytest.mark.skipif(
    not is_dependency_available("cryptography"),
    reason="skipped due to missing cryptography (enrichment dependency)",
)

DELAY = 0.5


def _json_response(status_code: int = 200, body: bytes = b"{}") -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "OK" if status_code < 400 else "Error"
    response.url = "https://api.example.org/"
    response._content = body
    response._content_consumed = True
    return response


@pytest.fixture
def sleeps():
    """Record the waits instead of sleeping them."""
    recorded: list[float] = []
    with patch("time.sleep", side_effect=recorded.append):
        yield recorded


class TestThrottle:
    def test_no_wait_before_the_first_request(self, sleeps):
        client = BaseEnrichmentClient(base_url="https://api.example.org", rate_limit_delay=DELAY)
        with patch.object(requests.Session, "get", return_value=_json_response()):
            client._make_request("first")

        assert sleeps == []

    def test_consecutive_requests_are_spaced_by_the_delay(self, sleeps):
        client = BaseEnrichmentClient(base_url="https://api.example.org", rate_limit_delay=DELAY)
        with patch.object(requests.Session, "get", return_value=_json_response()) as mock_get:
            for endpoint in ("a", "b", "c"):
                client._make_request(endpoint)

        assert mock_get.call_count == 3
        assert sleeps == [pytest.approx(DELAY, abs=0.05)] * 2

    def test_only_the_remainder_is_waited(self, sleeps):
        client = BaseEnrichmentClient(base_url="https://api.example.org", rate_limit_delay=DELAY)
        with (
            patch.object(requests.Session, "get", return_value=_json_response()),
            patch("time.monotonic", side_effect=[100.0, 100.3, 100.5]),
        ):
            client._make_request("a")  # records 100.0
            client._make_request("b")  # 0.3s later: waits 0.2s, records 100.5

        assert sleeps == [pytest.approx(0.2)]

    def test_no_wait_when_the_delay_has_already_passed(self, sleeps):
        client = BaseEnrichmentClient(base_url="https://api.example.org", rate_limit_delay=DELAY)
        with (
            patch.object(requests.Session, "get", return_value=_json_response()),
            patch("time.monotonic", side_effect=[100.0, 101.0, 101.0]),
        ):
            client._make_request("a")
            client._make_request("b")

        assert sleeps == []

    def test_zero_delay_never_waits(self, sleeps):
        client = BaseEnrichmentClient(base_url="https://api.example.org", rate_limit_delay=0)
        with patch.object(requests.Session, "get", return_value=_json_response()):
            for endpoint in ("a", "b", "c"):
                client._make_request(endpoint)

        assert sleeps == []

    def test_cache_hits_are_not_throttled(self, sleeps):
        client = BaseEnrichmentClient(
            base_url="https://api.example.org",
            rate_limit_delay=DELAY,
            cache_config=CacheConfig(enabled=True),
        )
        with patch.object(requests.Session, "get", return_value=_json_response()) as mock_get:
            for _ in range(3):
                client._make_request("same", use_cache=True)

        assert mock_get.call_count == 1
        assert sleeps == []

    def test_a_failed_request_still_counts(self, sleeps):
        """The server saw the attempt, so the next request keeps its distance."""
        client = BaseEnrichmentClient(base_url="https://api.example.org", rate_limit_delay=DELAY)
        with patch.object(
            requests.Session,
            "get",
            side_effect=[requests.ConnectionError("down"), _json_response()],
        ):
            with pytest.raises(APIClientError):
                client._make_request("a")
            client._make_request("b")

        assert sleeps == [pytest.approx(DELAY, abs=0.05)]


# (client factory, call that makes one request)
CLIENTS: list[tuple[str, Callable[[], Any], Callable[[Any], Any]]] = [
    (
        "CrossRef",
        lambda: CrossRefClient(rate_limit_delay=DELAY),
        lambda c: c.enrich("10.1000/xyz123"),
    ),
    (
        "OpenAlex",
        lambda: OpenAlexClient(rate_limit_delay=DELAY, enable_ror_enrichment=False),
        lambda c: c.enrich("10.1000/xyz123"),
    ),
    (
        "Unpaywall",
        lambda: UnpaywallClient(email="me@example.org", rate_limit_delay=DELAY),
        lambda c: c.enrich("10.1000/xyz123"),
    ),
    # ICiteClient.enrich is stubbed by this directory's conftest; enrich_many
    # goes through the same _make_request.
    ("iCite", lambda: ICiteClient(rate_limit_delay=DELAY), lambda c: c.enrich_many(["12345"])),
    (
        "ROR",
        lambda: RorClient(rate_limit_delay=DELAY),
        lambda c: c.enrich("https://ror.org/02mhbdp94"),
    ),
    (
        "DataCite",
        lambda: DataCiteClient(rate_limit_delay=DELAY),
        lambda c: c.enrich("10.1000/xyz123"),
    ),
    (
        "ORCID",
        lambda: OrcidClient(rate_limit_delay=DELAY),
        lambda c: c.enrich("0000-0002-1825-0097"),
    ),
]


@pytest.mark.parametrize(
    ("name", "make_client", "call"), CLIENTS, ids=[name for name, _, _ in CLIENTS]
)
def test_every_enrichment_client_waits_between_requests(sleeps, name, make_client, call):
    client = make_client()
    with patch.object(requests.Session, "get", return_value=_json_response()) as mock_get:
        call(client)
        call(client)

    requests_made = mock_get.call_count
    assert requests_made >= 2, f"{name} made {requests_made} request(s)"
    assert len(sleeps) == requests_made - 1
    assert all(wait == pytest.approx(DELAY, abs=0.05) for wait in sleeps)


class TestRorErrors:
    def test_network_error_raises_like_the_other_clients(self, sleeps):
        client = RorClient(rate_limit_delay=0)
        with (
            patch.object(requests.Session, "get", side_effect=requests.ConnectionError("down")),
            pytest.raises(APIClientError),
        ):
            client.enrich("https://ror.org/02mhbdp94")

    def test_http_error_raises(self, sleeps):
        client = RorClient(rate_limit_delay=0)
        with (
            patch.object(requests.Session, "get", return_value=_json_response(500)),
            pytest.raises(APIClientError),
        ):
            client.enrich("https://ror.org/02mhbdp94")

    def test_not_found_is_none(self, sleeps):
        client = RorClient(rate_limit_delay=0)
        with patch.object(requests.Session, "get", return_value=_json_response(404)):
            assert client.enrich("https://ror.org/02mhbdp94") is None

    def test_unparseable_record_is_none(self, sleeps):
        client = RorClient(rate_limit_delay=0)
        with (
            patch.object(requests.Session, "get", return_value=_json_response(200, b'{"id": 1}')),
            patch.object(client, "_parse_ror_response", side_effect=KeyError("names")),
        ):
            assert client.enrich("https://ror.org/02mhbdp94") is None


class TestOpenAlexKeepsInstitutionsWhenRorFails:
    def test_ror_error_keeps_the_openalex_institution(self):
        client = OpenAlexClient(rate_limit_delay=0, enable_ror_enrichment=True)
        institution = {
            "id": "I1",
            "display_name": "University of Test",
            "ror_id": "https://ror.org/012345678",
        }
        error = APIClientError(message="Failed to connect to API.")

        with patch.object(client.ror_client, "enrich", side_effect=error):
            enriched = client._enrich_institutions_with_ror([institution])

        assert enriched == [institution]
