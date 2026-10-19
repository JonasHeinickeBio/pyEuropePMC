"""Is Europe PMC up? A small probe of the endpoints the library depends on.

The same four endpoints as ``.github/workflows/europepmc-health.yml``, which files an issue
when one of them answers 5xx. ``test_mcp_status.py`` compares the two lists, so a change to one
without the other fails a test instead of drifting apart.

The probe is deliberately cheap: one request per endpoint, all at once, a short timeout, the
body never read. The result is kept for a short time so that an agent asking again and again
cannot turn a diagnostic into load on a service that may already be struggling.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import datetime
import threading
import time
from typing import Any

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"

#: ``(key, label as in the health workflow, url)``
ENDPOINTS: tuple[tuple[str, str, str], ...] = (
    ("search", "REST search", f"{BASE}/search?query=cancer&format=json&pageSize=1"),
    ("fulltext", "REST full text XML", f"{BASE}/PMC3257301/fullTextXML"),
    ("citations", "REST citations", f"{BASE}/MED/34040261/citations?format=json&pageSize=1"),
    (
        "annotations",
        "Annotations API",
        "https://www.ebi.ac.uk/europepmc/annotations_api/annotationsByArticleIds"
        "?articleIds=MED:34040261&format=JSON",
    ),
)

USER_AGENT = "pyEuropePMC-mcp-status (+https://github.com/JonasHeinickeBio/pyEuropePMC)"
DEFAULT_TIMEOUT = 8.0
DEFAULT_TTL = 30.0


@dataclass(frozen=True)
class EndpointResult:
    verdict: str  # ok | error (5xx) | unreachable (timeout, connection) | unexpected (4xx, 3xx)
    http: int | None
    ms: int
    error: str | None = None  # the exception's class name only; never a URL or a message

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"verdict": self.verdict, "http": self.http, "ms": self.ms}
        if self.error:
            out["error"] = self.error
        return out


def verdict_for(code: int) -> str:
    if 200 <= code < 300:
        return "ok"
    return "error" if code >= 500 else "unexpected"


def probe_one(
    url: str,
    get: Callable[..., Any],
    timeout: float,
    clock: Callable[[], float] = time.monotonic,
) -> EndpointResult:
    """One request; the body is never downloaded (the full-text endpoint serves an article)."""
    started = clock()
    try:
        response = get(url, timeout=timeout, stream=True, headers={"User-Agent": USER_AGENT})
    except Exception as exc:  # noqa: BLE001 - any failure to answer is the finding
        elapsed = round((clock() - started) * 1000)
        return EndpointResult("unreachable", None, elapsed, type(exc).__name__)
    ms = round((clock() - started) * 1000)
    try:
        code = int(response.status_code)
    finally:
        close = getattr(response, "close", None)
        if close:
            close()
    return EndpointResult(verdict_for(code), code, ms)


def overall(results: dict[str, EndpointResult]) -> str:
    """``ok``; ``degraded`` when some endpoint failed and some answered; ``down`` when none
    answered; ``unknown`` when the only trouble is a 4xx (a blocked probe or a moved endpoint,
    which the health workflow also does not treat as an outage)."""
    verdicts = [r.verdict for r in results.values()]
    failing = [v for v in verdicts if v in ("error", "unreachable")]
    answering = [v for v in verdicts if v == "ok"]
    if failing:
        return "down" if not answering else "degraded"
    if any(v == "unexpected" for v in verdicts):
        return "unknown"
    return "ok"


def probe(
    get: Callable[..., Any],
    timeout: float = DEFAULT_TIMEOUT,
    endpoints: tuple[tuple[str, str, str], ...] = ENDPOINTS,
) -> dict[str, EndpointResult]:
    """Probe every endpoint at once."""
    with ThreadPoolExecutor(max_workers=len(endpoints)) as pool:
        futures = {
            key: pool.submit(probe_one, url, get, timeout) for key, _label, url in endpoints
        }
        return {key: future.result() for key, future in futures.items()}


class StatusCache:
    """The last probe, kept for ``ttl`` seconds. Thread-safe; tests can replace the clock."""

    def __init__(
        self, ttl: float = DEFAULT_TTL, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._value: dict[str, Any] | None = None
        self._at = 0.0

    def get(self) -> tuple[dict[str, Any], float] | None:
        """``(result, age in seconds)`` while it is fresh, else ``None``."""
        with self._lock:
            if self._value is None:
                return None
            age = self._clock() - self._at
            return (self._value, age) if age < self.ttl else None

    def set(self, value: dict[str, Any]) -> None:
        with self._lock:
            self._value = value
            self._at = self._clock()

    def reset(self) -> None:
        with self._lock:
            self._value = None


def build_result(results: dict[str, EndpointResult], now: datetime.datetime) -> dict[str, Any]:
    return {
        "status": overall(results),
        "endpoints": {key: r.to_dict() for key, r in results.items()},
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
