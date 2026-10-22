"""A client that threads share sends one GET at a time; the delay after it still overlaps."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time
from unittest.mock import MagicMock

from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.features.literature.search import SearchClient


class _Probe:
    """A session whose ``get`` records how many calls are inside it at once."""

    def __init__(self) -> None:
        self.inside = 0
        self.peak = 0
        self.guard = threading.Lock()

    def get(self, url, params=None, timeout=None, stream=False):
        with self.guard:
            self.inside += 1
            self.peak = max(self.peak, self.inside)
        time.sleep(0.02)
        with self.guard:
            self.inside -= 1
        response = MagicMock()
        response.status_code = 200
        return response


def _peak(client: BaseAPIClient) -> int:
    probe = _Probe()
    client.session = probe  # type: ignore[assignment]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda i: client._get("search", {"q": i}), range(12)))
    return probe.peak


def test_a_search_client_sends_one_request_at_a_time():
    assert SearchClient.serialize_requests is True
    assert _peak(SearchClient(rate_limit_delay=0)) == 1


def test_other_clients_keep_their_parallel_requests():
    assert BaseAPIClient.serialize_requests is False
    assert _peak(BaseAPIClient(rate_limit_delay=0)) > 1


def test_the_delay_after_a_request_is_not_held_under_the_lock():
    client = SearchClient(rate_limit_delay=0.2)
    client.session = _Probe()  # type: ignore[assignment]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda i: client._get("search", {"q": i}), range(6)))
    # six requests of 0.02 s under the lock plus 0.2 s of delay each, overlapping: well under
    # the 1.3 s that holding the delay under the lock would take
    assert time.monotonic() - started < 0.9
