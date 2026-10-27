"""Reading the ``Retry-After`` response header."""

from __future__ import annotations

import datetime
import email.utils
import math
from typing import Any

__all__ = ["parse_retry_after", "retry_after_of"]


def parse_retry_after(value: str | None, now: datetime.datetime | None = None) -> float | None:
    """Seconds a server asks us to wait, from a ``Retry-After`` header value.

    The header is a number of seconds or an HTTP date. A value that is empty, negative, not a
    number or a date, or a date already past counts as absent (``None``), so the caller falls
    back to its own backoff.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        try:
            due = email.utils.parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        current = now or datetime.datetime.now(datetime.timezone.utc)
        seconds = (due - current).total_seconds()
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def retry_after_of(exc: BaseException) -> float | None:
    """The ``Retry-After`` an HTTP error response carried, in seconds, if it carried one."""
    response: Any = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    return parse_retry_after(headers.get("Retry-After"))
