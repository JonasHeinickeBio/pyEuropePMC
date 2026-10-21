"""Connecting over IPv4 when IPv6 does not work (RFC 8305, "Happy Eyeballs").

A host with both an IPv6 and an IPv4 address is tried by Python's HTTP stack one address at a
time, IPv6 first, each for the full connect timeout. On a network that has an IPv6 address
but no working IPv6 route that costs the whole timeout on every new connection: 30 to 60
seconds per request in practice, which looks like a service that is down. ``curl`` and
browsers start the second address after a quarter of a second instead.

:func:`happy_eyeballs_connect` does the same: it starts an attempt per address, the next one
``stagger`` seconds after the previous one (or at once when the previous one failed), uses the
first connection that completes and closes the others. On a network where IPv6 works the
first attempt wins and nothing changes. :class:`HappyEyeballsAdapter` plugs it into a
``requests`` session; every client of this library that owns a session mounts it.

Set ``PYEUROPEPMC_HAPPY_EYEBALLS=0`` to use the standard behaviour of ``requests`` instead.
"""

from __future__ import annotations

from collections import deque
import errno
import os
import selectors
import socket
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError

try:  # urllib3 2.x names a failed lookup; 1.26 reports it as a failed connection
    from urllib3.exceptions import NameResolutionError
except ImportError:  # pragma: no cover - exercised only with urllib3 1.26
    NameResolutionError = None  # type: ignore[assignment]

__all__ = [
    "ENV_SWITCH",
    "STAGGER_SECONDS",
    "HappyEyeballsAdapter",
    "enabled",
    "happy_eyeballs_connect",
    "mount",
    "new_session",
]

ENV_SWITCH = "PYEUROPEPMC_HAPPY_EYEBALLS"
#: The sentinel ``socket.create_connection`` and urllib3 use for "no timeout was given".
_DEFAULT_TIMEOUT: Any = getattr(socket, "_GLOBAL_DEFAULT_TIMEOUT", object())
#: Delay before the next address is tried while an earlier attempt is still pending.
STAGGER_SECONDS = 0.25

_IN_PROGRESS = {
    code
    for code in (
        errno.EINPROGRESS,
        errno.EWOULDBLOCK,
        errno.EAGAIN,
        errno.EALREADY,
        getattr(errno, "WSAEWOULDBLOCK", None),
    )
    if code is not None
}

#: ``getaddrinfo`` result: ``(family, type, proto, canonname, sockaddr)``
AddrInfo = tuple[int, int, int, str, Any]


def enabled() -> bool:
    """True unless ``PYEUROPEPMC_HAPPY_EYEBALLS`` is set to 0, false, off or no."""
    return os.environ.get(ENV_SWITCH, "1").strip().lower() not in {"0", "false", "off", "no"}


def _interleave(infos: list[AddrInfo]) -> list[AddrInfo]:
    """The first address's family first, then the families alternating (RFC 8305, 4)."""
    if not infos:
        return []
    first = infos[0][0]
    same = deque(i for i in infos if i[0] == first)
    other = deque(i for i in infos if i[0] != first)
    out: list[AddrInfo] = []
    while same or other:
        if same:
            out.append(same.popleft())
        if other:
            out.append(other.popleft())
    return out


def _start(
    info: AddrInfo,
    source_address: tuple[str, int] | None,
    socket_options: list[tuple[int, int, int]] | None,
) -> tuple[socket.socket, bool]:
    """A non-blocking socket with the connection started; ``True`` when it is already done."""
    family, type_, proto, _, sockaddr = info
    sock = socket.socket(family, type_, proto)
    try:
        for level, name, value in socket_options or ():
            sock.setsockopt(level, name, value)
        if source_address:
            sock.bind(source_address)
        sock.setblocking(False)
        code = sock.connect_ex(sockaddr)
        if code == 0:
            return sock, True
        if code not in _IN_PROGRESS:
            raise OSError(code, os.strerror(code))
        return sock, False
    except BaseException:
        sock.close()
        raise


class _Race:
    """The attempts of one :func:`happy_eyeballs_connect` call and the state they share."""

    def __init__(
        self,
        infos: list[AddrInfo],
        attempt_timeout: float | None,
        stagger: float,
        source_address: tuple[str, int] | None,
        socket_options: list[tuple[int, int, int]] | None,
        clock: Any,
    ) -> None:
        self.pending = deque(infos)
        self.inflight: dict[socket.socket, float | None] = {}
        self.errors: list[BaseException] = []
        self.winner: socket.socket | None = None
        self.selector = selectors.DefaultSelector()
        self.next_start = 0.0
        self.attempt_timeout = attempt_timeout
        self.stagger = stagger
        self.source_address = source_address
        self.socket_options = socket_options
        self.clock = clock

    def _start_next(self, moment: float) -> None:
        try:
            sock, done = _start(self.pending.popleft(), self.source_address, self.socket_options)
        except OSError as exc:
            self.errors.append(exc)
            return
        if done:
            self.winner = sock
            return
        limit = None if self.attempt_timeout is None else moment + self.attempt_timeout
        self.inflight[sock] = limit
        self.selector.register(sock, selectors.EVENT_WRITE)
        self.next_start = moment + self.stagger

    def _wait(self, moment: float) -> float | None:
        wakeups = [d for d in self.inflight.values() if d is not None]
        if self.pending:
            wakeups.append(self.next_start)
        return max(0.0, min(wakeups) - moment) if wakeups else None

    def _drop(self, sock: socket.socket, error: BaseException) -> None:
        self.selector.unregister(sock)
        del self.inflight[sock]
        sock.close()
        self.errors.append(error)

    def _collect(self) -> None:
        """Take the sockets that are ready: the first without an error wins."""
        for key, _ in self.selector.select(self._wait(self.clock())):
            sock = key.fileobj
            assert isinstance(sock, socket.socket)
            code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if code == 0:
                self.selector.unregister(sock)
                del self.inflight[sock]
                self.winner = sock
                return
            self._drop(sock, OSError(code, os.strerror(code)))

    def _expire(self) -> None:
        moment = self.clock()
        for sock, limit in list(self.inflight.items()):
            if limit is not None and moment >= limit:
                self._drop(sock, TimeoutError("timed out"))

    def run(self) -> socket.socket | None:
        while self.winner is None:
            moment = self.clock()
            if self.pending and (not self.inflight or moment >= self.next_start):
                self._start_next(moment)
            elif not self.inflight:
                break
            else:
                self._collect()
                if self.winner is None:
                    self._expire()
        return self.winner

    def close(self) -> None:
        for sock in self.inflight:
            sock.close()
        self.selector.close()


def happy_eyeballs_connect(
    address: tuple[str, int],
    timeout: Any = _DEFAULT_TIMEOUT,
    source_address: tuple[str, int] | None = None,
    socket_options: list[tuple[int, int, int]] | None = None,
    *,
    stagger: float | None = None,
    resolve: Any = None,
    clock: Any = None,
) -> socket.socket:
    """A connected socket to ``address``, like ``socket.create_connection`` but without waiting
    for a dead address: see the module docstring.

    ``timeout`` bounds each attempt (``None`` or the default: no bound, the next address still
    starts after ``stagger``). Raises the last error when every address fails, which is a
    ``socket.timeout`` if the last failure was a timeout. ``resolve`` and ``clock`` exist for
    tests.
    """
    host, port = address
    attempt_timeout = None if timeout is _DEFAULT_TIMEOUT else timeout
    infos = _interleave(
        list((resolve or socket.getaddrinfo)(host.strip("[]"), port, 0, socket.SOCK_STREAM))
    )
    race = _Race(
        infos,
        None if attempt_timeout is None else float(attempt_timeout),
        STAGGER_SECONDS if stagger is None else stagger,
        source_address,
        socket_options,
        clock or time.monotonic,
    )
    try:
        winner = race.run()
    except BaseException:
        if race.winner is not None:
            race.winner.close()
        raise
    finally:
        race.close()
    if winner is None:
        if race.errors:
            raise race.errors[-1]
        raise OSError(f"getaddrinfo returned no address for {host}")
    winner.setblocking(True)
    winner.settimeout(None if attempt_timeout is None else float(attempt_timeout))
    return winner


# ---------------------------------------------------------------------------
# urllib3 / requests
# ---------------------------------------------------------------------------


class _Connect:
    """``_new_conn`` for urllib3's connection classes, with urllib3's own error types."""

    def _new_conn(self: Any) -> socket.socket:
        try:
            return happy_eyeballs_connect(
                (self._dns_host, self.port), self.timeout, self.source_address, self.socket_options
            )
        except socket.gaierror as exc:
            if NameResolutionError is not None:
                raise NameResolutionError(self.host, self, exc) from exc
            raise NewConnectionError(self, f"Failed to resolve {self.host}: {exc}") from exc
        except TimeoutError as exc:
            raise ConnectTimeoutError(
                self, f"Connection to {self.host} timed out. (connect timeout={self.timeout})"
            ) from exc
        except OSError as exc:
            raise NewConnectionError(self, f"Failed to establish a new connection: {exc}") from exc


class _HTTPConnection(_Connect, HTTPConnection):
    pass


class _HTTPSConnection(_Connect, HTTPSConnection):
    pass


class _HTTPPool(HTTPConnectionPool):
    ConnectionCls = _HTTPConnection


class _HTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _HTTPSConnection


_POOLS = {"http": _HTTPPool, "https": _HTTPSPool}


class HappyEyeballsAdapter(HTTPAdapter):
    """An ``HTTPAdapter`` whose new connections use :func:`happy_eyeballs_connect`."""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = dict(_POOLS)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:
        manager = super().proxy_manager_for(proxy, **proxy_kwargs)
        manager.pool_classes_by_scheme = dict(_POOLS)
        return manager


def mount(session: requests.Session, **adapter_kwargs: Any) -> requests.Session:
    """Mount :class:`HappyEyeballsAdapter` for http and https on ``session`` (unless switched
    off with ``PYEUROPEPMC_HAPPY_EYEBALLS=0``); ``adapter_kwargs`` go to the adapter, for
    example ``max_retries``. Returns the session."""
    adapter: HTTPAdapter
    if enabled():
        adapter = HappyEyeballsAdapter(**adapter_kwargs)
    elif adapter_kwargs:
        adapter = HTTPAdapter(**adapter_kwargs)
    else:
        return session
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def new_session(**adapter_kwargs: Any) -> requests.Session:
    """A ``requests.Session`` that does not wait for a dead IPv6 address."""
    return mount(requests.Session(), **adapter_kwargs)
