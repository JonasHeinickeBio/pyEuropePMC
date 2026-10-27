"""Reading the ``Retry-After`` response header."""

from __future__ import annotations

import datetime
import email.utils
import math
import re
from typing import Any

__all__ = ["parse_retry_after", "retry_after_of"]

#: Longest advice reported: a year. A ``delay-seconds`` with more digits than a float holds is
#: still a valid header (RFC 9110) and means "far beyond any wait limit", not "no header".
_CEILING = 365 * 24 * 3600.0
_DELAY_SECONDS = re.compile(r"[0-9]+")


def parse_retry_after(value: str | None, now: datetime.datetime | None = None) -> float | None:
    """Seconds a server asks us to wait, from a ``Retry-After`` header value.

    The header is a number of seconds or an HTTP date. A value that is empty, negative, not a
    number or a date, or a date already past counts as absent (``None``), so the caller falls
    back to its own backoff.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        seconds = float(text)
        if _DELAY_SECONDS.fullmatch(text) and not math.isfinite(seconds):
            seconds = _CEILING  # digits beyond float range
    except ValueError:
        try:
            due = email.utils.parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        current = now or datetime.datetime.now(datetime.timezone.utc)
        seconds = (due - current).total_seconds()
    return min(seconds, _CEILING) if math.isfinite(seconds) and seconds >= 0 else None


def retry_after_of(exc: BaseException) -> float | None:
    """The ``Retry-After`` an HTTP error response carried, in seconds, if it carried one."""
    response: Any = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    return parse_retry_after(headers.get("Retry-After"))
