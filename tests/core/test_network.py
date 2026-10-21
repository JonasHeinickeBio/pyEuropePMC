"""Tests for the connection fallback in ``pyeuropepmc.core.network``.

They use real loopback sockets. A "dead" address is a listening socket whose accept queue is
full: further connection attempts get no answer, which is what an unreachable IPv6 address
looks like to the client. Tests that need that behaviour run on Linux only.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import http.server
import socket
import sys
import threading
import time

import pytest
import requests

from pyeuropepmc.core import network
from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.features.common.base import BaseHTTPClient

pytestmark = pytest.mark.enable_socket

LOOPBACK = "127.0.0.1"
linux_only = pytest.mark.skipif(sys.platform != "linux", reason="needs a full accept queue")


def info(port: int, family: int = socket.AF_INET) -> network.AddrInfo:
    address = (LOOPBACK, port) if family == socket.AF_INET else ("::1", port, 0, 0)
    return (family, socket.SOCK_STREAM, 6, "", address)


def resolver(*infos: network.AddrInfo):
    return lambda *args, **kwargs: list(infos)


@contextmanager
def server() -> Iterator[tuple[int, list[socket.socket]]]:
    """A loopback server that accepts connections and keeps them open."""
    srv = socket.socket()
    srv.bind((LOOPBACK, 0))
    srv.listen(8)
    accepted: list[socket.socket] = []

    def accept() -> None:
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            accepted.append(conn)

    threading.Thread(target=accept, daemon=True).start()
    try:
        yield srv.getsockname()[1], accepted
    finally:
        srv.close()
        for conn in accepted:
            conn.close()


@contextmanager
def dead_endpoint() -> Iterator[int]:
    """A port that never answers: a listener with a full accept queue (nothing accepts)."""
    srv = socket.socket()
    srv.bind((LOOPBACK, 0))
    srv.listen(0)
    port = srv.getsockname()[1]
    fillers = []
    for _ in range(4):
        filler = socket.socket()
        filler.setblocking(False)
        filler.connect_ex((LOOPBACK, port))
        fillers.append(filler)
    time.sleep(0.2)
    try:
        yield port
    finally:
        for filler in fillers:
            filler.close()
        srv.close()


def closed_port() -> int:
    probe = socket.socket()
    probe.bind((LOOPBACK, 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class TestInterleave:
    def test_families_alternate_starting_with_the_first_address(self):
        v6a, v6b, v4a, v4b = (info(1, socket.AF_INET6), info(2, socket.AF_INET6), info(3), info(4))
        assert network._interleave([v6a, v6b, v4a, v4b]) == [v6a, v4a, v6b, v4b]
        assert network._interleave([v4a, v6a, v4b]) == [v4a, v6a, v4b]

    def test_one_family_and_nothing(self):
        assert network._interleave([info(1), info(2)]) == [info(1), info(2)]
        assert network._interleave([]) == []


class TestConnect:
    def test_the_first_address_wins_when_it_works_and_the_second_is_never_tried(self):
        with server() as (port_a, got_a), server() as (port_b, got_b):
            sock = network.happy_eyeballs_connect(
                ("x", 1), 5, resolve=resolver(info(port_a), info(port_b))
            )
            time.sleep(0.4)
            sock.close()
        assert len(got_a) == 1 and got_b == []

    def test_a_refused_address_is_followed_by_the_next_at_once(self):
        with server() as (port, _):
            started = time.monotonic()
            sock = network.happy_eyeballs_connect(
                ("x", 1), 5, stagger=10, resolve=resolver(info(closed_port()), info(port))
            )
            assert sock.getpeername()[1] == port
            sock.close()
        assert time.monotonic() - started < 2  # not the stagger, and not a timeout

    @linux_only
    def test_a_dead_first_address_costs_the_stagger_not_the_timeout(self):
        with dead_endpoint() as dead, server() as (port, _):
            started = time.monotonic()
            sock = network.happy_eyeballs_connect(
                ("x", 1), 30, stagger=0.2, resolve=resolver(info(dead), info(port))
            )
            elapsed = time.monotonic() - started
            assert sock.getpeername()[1] == port
            sock.close()
        assert 0.15 <= elapsed < 3

    @linux_only
    def test_without_a_timeout_the_next_address_still_starts(self):
        with dead_endpoint() as dead, server() as (port, _):
            sock = network.happy_eyeballs_connect(
                ("x", 1), None, stagger=0.1, resolve=resolver(info(dead), info(port))
            )
            assert sock.getpeername()[1] == port
            assert sock.gettimeout() is None
            sock.close()

    def test_every_address_refused_raises_the_last_error(self):
        with pytest.raises(ConnectionRefusedError):
            network.happy_eyeballs_connect(
                ("x", 1), 2, resolve=resolver(info(closed_port()), info(closed_port()))
            )

    @linux_only
    def test_every_address_dead_times_out(self):
        with dead_endpoint() as one, dead_endpoint() as two:
            started = time.monotonic()
            with pytest.raises(socket.timeout):
                network.happy_eyeballs_connect(
                    ("x", 1), 0.4, stagger=0.1, resolve=resolver(info(one), info(two))
                )
            assert time.monotonic() - started < 3

    def test_no_address_and_a_failed_lookup(self):
        with pytest.raises(OSError, match="no address"):
            network.happy_eyeballs_connect(("x", 1), 1, resolve=resolver())

        def broken(*args, **kwargs):
            raise socket.gaierror(-2, "Name or service not known")

        with pytest.raises(socket.gaierror):
            network.happy_eyeballs_connect(("x", 1), 1, resolve=broken)

    def test_the_winner_is_blocking_with_the_timeout_and_the_options(self):
        with server() as (port, _):
            sock = network.happy_eyeballs_connect(
                ("x", 1),
                7,
                socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
                resolve=resolver(info(port)),
            )
            assert sock.gettimeout() == 7
            assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY) != 0
            sock.close()

    def test_an_ipv6_literal_is_resolved_without_brackets(self):
        seen = []

        def resolve(host, port, family, type_):
            seen.append(host)
            return []

        with pytest.raises(OSError):
            network.happy_eyeballs_connect(("[::1]", 80), 1, resolve=resolve)
        assert seen == ["::1"]

    def test_a_real_localhost_connection(self):
        with server() as (port, _):
            sock = network.happy_eyeballs_connect(("localhost", port), 5)
            sock.close()

    def test_nothing_is_left_open_after_a_win(self):
        before = len(_open_descriptors())
        with server() as (port, _):
            for _ in range(5):
                network.happy_eyeballs_connect(
                    ("x", 1), 5, resolve=resolver(info(closed_port()), info(port))
                ).close()
        assert len(_open_descriptors()) <= before + 1


def _open_descriptors() -> list[str]:
    import os

    try:
        return os.listdir("/proc/self/fd")
    except OSError:  # pragma: no cover - not Linux
        return []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


@contextmanager
def http_server() -> Iterator[int]:
    httpd = http.server.ThreadingHTTPServer((LOOPBACK, 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


class TestAdapter:
    def test_a_request_goes_through_the_fallback(self, monkeypatch):
        with http_server() as port:
            monkeypatch.setattr(
                network.socket, "getaddrinfo", resolver(info(closed_port()), info(port))
            )
            response = network.new_session().get("http://fallback.invalid/", timeout=5)
        assert response.status_code == 200 and response.json() == {"ok": True}

    @linux_only
    def test_a_dead_address_does_not_stall_the_request(self, monkeypatch):
        with dead_endpoint() as dead, http_server() as port:
            monkeypatch.setattr(network, "STAGGER_SECONDS", 0.2)
            monkeypatch.setattr(network.socket, "getaddrinfo", resolver(info(dead), info(port)))
            started = time.monotonic()
            response = network.new_session().get("http://fallback.invalid/", timeout=30)
            assert response.status_code == 200
        assert time.monotonic() - started < 5

    def test_errors_keep_the_requests_types(self, monkeypatch):
        session = network.new_session()
        monkeypatch.setattr(network.socket, "getaddrinfo", resolver(info(closed_port())))
        with pytest.raises(requests.ConnectionError):
            session.get("http://refused.invalid/", timeout=2)

        def broken(*args, **kwargs):
            raise socket.gaierror(-2, "Name or service not known")

        monkeypatch.setattr(network.socket, "getaddrinfo", broken)
        with pytest.raises(requests.ConnectionError):
            session.get("http://nxdomain.invalid/", timeout=2)

    @linux_only
    def test_a_connect_timeout_is_a_requests_connect_timeout(self, monkeypatch):
        with dead_endpoint() as dead:
            monkeypatch.setattr(network.socket, "getaddrinfo", resolver(info(dead)))
            with pytest.raises(requests.ConnectTimeout):
                network.new_session().get("http://dead.invalid/", timeout=(0.5, 5))

    def test_https_and_proxy_pools_use_the_fallback_connections(self):
        adapter = network.HappyEyeballsAdapter()
        for scheme in ("http", "https"):
            pool_class = adapter.poolmanager.pool_classes_by_scheme[scheme]
            assert issubclass(pool_class.ConnectionCls, network._Connect)
        proxy = adapter.proxy_manager_for("http://proxy.invalid:3128")
        assert issubclass(proxy.pool_classes_by_scheme["https"].ConnectionCls, network._Connect)


class TestMounting:
    def test_the_switch_reads_the_environment(self, monkeypatch):
        monkeypatch.delenv(network.ENV_SWITCH, raising=False)
        assert network.enabled() is True
        for value in ("0", "false", "OFF", " no "):
            monkeypatch.setenv(network.ENV_SWITCH, value)
            assert network.enabled() is False
        monkeypatch.setenv(network.ENV_SWITCH, "1")
        assert network.enabled() is True

    def test_switched_off_the_standard_adapter_stays(self, monkeypatch):
        monkeypatch.setenv(network.ENV_SWITCH, "0")
        session = network.new_session()
        assert not isinstance(
            session.get_adapter("https://x.invalid/"), network.HappyEyeballsAdapter
        )

    def test_switched_off_adapter_options_still_apply(self, monkeypatch):
        monkeypatch.setenv(network.ENV_SWITCH, "0")
        session = network.new_session(max_retries=5)
        assert session.get_adapter("https://x.invalid/").max_retries.total == 5

    def test_the_clients_mount_it(self):
        europe_pmc = BaseAPIClient()
        enrichment = BaseHTTPClient(base_url="https://api.example.org")
        for client in (europe_pmc, enrichment):
            assert isinstance(
                client.session.get_adapter("https://x.invalid/"), network.HappyEyeballsAdapter
            )
        assert enrichment.session.get_adapter("https://x.invalid/").max_retries.total == 3

    def test_the_mcp_nlm_session_mounts_it(self):
        from pyeuropepmc.mcp import server as srv

        adapter = srv._nlm_session_cache.get().get_adapter("https://id.nlm.nih.gov/")
        assert isinstance(adapter, network.HappyEyeballsAdapter)
