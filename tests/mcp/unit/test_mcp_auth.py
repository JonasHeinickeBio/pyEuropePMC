"""Unit tests for the bearer-token authentication of the HTTP transports (hermetic).

The middleware is driven as a bare ASGI app, and the serving logic is tested with the two
places that start a server (``mcp.run`` and uvicorn) replaced; a test that starts a real HTTP
server is in ``tests/mcp/e2e``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

import pytest

from pyeuropepmc.mcp import _auth as au, server as srv

GOOD = "a" * 20
OTHER = "b" * 20


def _run(coro):
    return asyncio.run(coro)


async def _call(app, headers: list[tuple[bytes, bytes]], scope_type: str = "http"):
    """``(status, headers, body)`` the app answered with, or the list of sent messages."""
    sent: list[dict[str, Any]] = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    await app(
        {"type": scope_type, "method": "POST", "path": "/mcp", "headers": headers}, receive, send
    )
    return sent


class _Downstream:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, scope, receive, send):
        self.calls.append(scope["type"])
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})


def _status(sent) -> int | None:
    return next((m["status"] for m in sent if m["type"] == "http.response.start"), None)


def _bearer(token: str) -> list[tuple[bytes, bytes]]:
    return [(b"authorization", f"Bearer {token}".encode())]


class TestLoadTokens:
    def test_nothing_configured_means_no_authentication(self):
        assert au.load_tokens(environ={}) == []

    def test_tokens_from_the_environment_are_split_and_trimmed(self):
        env = {au.ENV_TOKEN: f" {GOOD} , {OTHER},{GOOD}"}
        assert au.load_tokens(environ=env) == [GOOD, OTHER]

    def test_tokens_from_a_file_skip_blank_lines_and_comments(self, tmp_path):
        path = tmp_path / "tokens"
        path.write_text(f"# current\n{GOOD}\n\n  {OTHER}  \n", encoding="utf-8")
        assert au.load_tokens(str(path), environ={}) == [GOOD, OTHER]

    def test_the_file_may_come_from_the_environment_and_both_sources_add_up(self, tmp_path):
        path = tmp_path / "tokens"
        path.write_text(GOOD + "\n", encoding="utf-8")
        env = {au.ENV_TOKEN_FILE: str(path), au.ENV_TOKEN: OTHER}
        assert au.load_tokens(environ=env) == [GOOD, OTHER]

    @pytest.mark.parametrize("value", ["", "  ", " , "])
    def test_a_variable_that_is_set_but_empty_does_not_open_the_server(self, value):
        with pytest.raises(au.AuthConfigError, match="set but empty"):
            au.load_tokens(environ={au.ENV_TOKEN: value})

    def test_a_weak_token_is_refused_with_the_way_to_make_one(self):
        with pytest.raises(au.AuthConfigError, match=r"at least 16 characters.*--generate-token"):
            au.load_tokens(environ={au.ENV_TOKEN: "short"})

    def test_a_token_with_spaces_or_non_ascii_is_refused(self):
        for bad in ("two words are not a token", "tökentökentökentöken"):
            with pytest.raises(au.AuthConfigError, match="printable ASCII"):
                au.load_tokens(environ={au.ENV_TOKEN: bad.replace(",", "")})

    def test_a_missing_or_empty_file_is_an_error(self, tmp_path):
        with pytest.raises(au.AuthConfigError, match="cannot read the token file"):
            au.load_tokens(str(tmp_path / "nope"), environ={})
        empty = tmp_path / "empty"
        empty.write_text("# nothing\n", encoding="utf-8")
        with pytest.raises(au.AuthConfigError, match="holds no token"):
            au.load_tokens(str(empty), environ={})

    def test_the_error_never_contains_the_token(self):
        token = "xysec"
        with pytest.raises(au.AuthConfigError) as caught:
            au.load_tokens(environ={au.ENV_TOKEN: token})
        assert token not in str(caught.value)

    def test_generated_tokens_are_strong_and_accepted(self):
        first, second = au.generate_token(), au.generate_token()
        assert first != second and len(first) >= au.MIN_TOKEN_CHARS
        assert au.load_tokens(environ={au.ENV_TOKEN: first}) == [first]


class TestMiddleware:
    def test_a_valid_token_reaches_the_app(self):
        app = _Downstream()
        sent = _run(_call(au.BearerAuthMiddleware(app, [GOOD]), _bearer(GOOD)))
        assert _status(sent) == 200 and app.calls == ["http"]

    def test_the_scheme_is_case_insensitive(self):
        app = _Downstream()
        headers = [(b"authorization", f"bearer {GOOD}".encode())]
        assert _status(_run(_call(au.BearerAuthMiddleware(app, [GOOD]), headers))) == 200

    def test_any_of_several_tokens_is_accepted(self):
        mw = au.BearerAuthMiddleware(_Downstream(), [GOOD, OTHER])
        assert _status(_run(_call(mw, _bearer(OTHER)))) == 200
        assert _status(_run(_call(mw, _bearer(GOOD)))) == 200

    @pytest.mark.parametrize(
        "headers",
        [
            [],
            [(b"authorization", b"Bearer")],
            [(b"authorization", b"Bearer ")],
            [(b"authorization", f"Basic {GOOD}".encode())],
            [(b"authorization", GOOD.encode())],
            _bearer(OTHER),
            _bearer(GOOD[:-1]),
            _bearer(GOOD + "x"),
            [(b"x-api-key", GOOD.encode())],
        ],
    )
    def test_everything_else_is_a_401_and_never_reaches_the_app(self, headers):
        app = _Downstream()
        sent = _run(_call(au.BearerAuthMiddleware(app, [GOOD]), headers))
        assert _status(sent) == 401 and app.calls == []
        start, body = sent
        assert dict(start["headers"])[b"www-authenticate"] == b'Bearer realm="pyeuropepmc-mcp"'
        assert dict(start["headers"])[b"cache-control"] == b"no-store"
        assert json.loads(body["body"])["error"] == "unauthorized"

    def test_the_answer_does_not_say_why(self):
        mw = au.BearerAuthMiddleware(_Downstream(), [GOOD])
        missing = _run(_call(mw, []))[1]["body"]
        wrong = _run(_call(mw, _bearer(OTHER)))[1]["body"]
        assert missing == wrong

    def test_lifespan_events_pass_through(self):
        app = _Downstream()
        _run(_call(au.BearerAuthMiddleware(app, [GOOD]), [], scope_type="lifespan"))
        assert app.calls == ["lifespan"]

    def test_websockets_are_refused(self):
        app = _Downstream()
        sent = _run(_call(au.BearerAuthMiddleware(app, [GOOD]), _bearer(GOOD), "websocket"))
        assert sent == [{"type": "websocket.close", "code": 1008}] and app.calls == []

    def test_a_refusal_is_logged_without_the_token(self, caplog):
        caplog.set_level(logging.WARNING, logger="pyeuropepmc.mcp")
        _run(_call(au.BearerAuthMiddleware(_Downstream(), [GOOD]), _bearer(OTHER)))
        assert "refused POST '/mcp'" in caplog.text
        assert OTHER not in caplog.text and GOOD not in caplog.text

    def test_it_cannot_be_built_without_a_token(self):
        with pytest.raises(au.AuthConfigError):
            au.BearerAuthMiddleware(_Downstream(), [])

    def test_the_token_is_not_kept_in_clear_text(self):
        mw = au.BearerAuthMiddleware(_Downstream(), [GOOD])
        assert GOOD not in repr(vars(mw)) and GOOD.encode() not in b"".join(mw._digests)


class TestLoopback:
    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "[::1]", "127.1.2.3"])
    def test_loopback(self, host):
        assert au.is_loopback(host)

    @pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "::", "mcp.example.org", ""])
    def test_not_loopback(self, host):
        assert not au.is_loopback(host)


class TestServing:
    @pytest.fixture
    def started(self, monkeypatch):
        """Replace the two places that start a server; record how each was called."""
        record: dict[str, Any] = {}
        monkeypatch.setattr(srv.mcp, "run", lambda **kw: record.setdefault("run", kw))

        import uvicorn

        class FakeServer:
            def __init__(self, config):
                record["config"] = config

            def run(self):
                record["served"] = True

        monkeypatch.setattr(uvicorn, "Server", FakeServer)
        for name in (au.ENV_TOKEN, au.ENV_TOKEN_FILE):
            monkeypatch.delenv(name, raising=False)
        return record

    @staticmethod
    def _args(*argv: str) -> argparse.Namespace:
        return srv._build_arg_parser().parse_args(list(argv))

    def test_the_options_and_their_defaults(self):
        args = self._args()
        assert args.auth_token_file == "" and args.generate_token is False
        assert self._args("--auth-token-file", "/x").auth_token_file == "/x"

    def test_a_token_on_the_command_line_is_refused_and_not_echoed(self, capsys):
        for argv in (["--auth-token", GOOD], ["--auth-token=" + GOOD]):
            with pytest.raises(SystemExit) as caught:
                self._args(*argv)
            assert caught.value.code == 2
            err = capsys.readouterr().err
            assert GOOD not in err and au.ENV_TOKEN in err and "process list" in err
        assert "--auth-token " not in srv._build_arg_parser().format_help()

    def test_without_a_token_the_sdk_serves_exactly_as_before(self, started):
        srv._serve(self._args("--transport", "streamable-http"))
        assert "config" not in started
        assert started["run"]["transport"] == "streamable-http" if srv._MCP_SDK_2 else True

    def test_with_a_token_the_app_is_wrapped_and_served_by_uvicorn(self, started, monkeypatch):
        monkeypatch.setenv(au.ENV_TOKEN, GOOD)
        srv._serve(self._args("--transport", "streamable-http", "--port", "8123"))
        config = started["config"]
        assert started["served"] is True and "run" not in started
        assert isinstance(config.app, au.BearerAuthMiddleware)
        assert (config.host, config.port) == ("127.0.0.1", 8123)

    def test_the_sse_transport_is_wrapped_too(self, started, monkeypatch):
        monkeypatch.setenv(au.ENV_TOKEN, GOOD)
        srv._serve(self._args("--transport", "sse"))
        assert isinstance(started["config"].app, au.BearerAuthMiddleware)

    def test_a_token_file_works_like_the_variable(self, started, tmp_path):
        path = tmp_path / "t"
        path.write_text(GOOD, encoding="utf-8")
        srv._serve(self._args("--transport", "streamable-http", "--auth-token-file", str(path)))
        assert isinstance(started["config"].app, au.BearerAuthMiddleware)

    @pytest.mark.parametrize(
        ("variable", "value"),
        [(au.ENV_TOKEN, "short"), (au.ENV_TOKEN, ""), (au.ENV_TOKEN_FILE, "/no/such/file")],
    )
    def test_stdio_starts_even_with_a_broken_token_setting(
        self, started, monkeypatch, caplog, variable, value
    ):
        monkeypatch.setenv(variable, value)
        caplog.set_level(logging.WARNING, logger="pyeuropepmc.mcp")
        srv._serve(self._args())
        assert started["run"] == {"transport": "stdio"}
        assert "ignored" in caplog.text

    def test_a_forged_path_cannot_write_a_log_line(self, caplog):
        caplog.set_level(logging.WARNING, logger="pyeuropepmc.mcp")
        app = au.BearerAuthMiddleware(_Downstream(), [GOOD])
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/mcp\nERROR forged line",
            "headers": [],
        }

        async def send(_message):
            return None

        async def receive():
            return {}

        _run(app(scope, receive, send))
        assert "\n" not in caplog.records[0].getMessage()

    def test_stdio_ignores_tokens_and_says_so(self, started, monkeypatch, caplog):
        monkeypatch.setenv(au.ENV_TOKEN, GOOD)
        caplog.set_level(logging.WARNING, logger="pyeuropepmc.mcp")
        srv._serve(self._args())
        assert started["run"] == {"transport": "stdio"} and "config" not in started
        assert "ignored" in caplog.text

    def test_a_bad_configuration_stops_the_server_before_it_starts(self, started, monkeypatch):
        monkeypatch.setenv(au.ENV_TOKEN, "short")
        with pytest.raises(SystemExit, match="at least 16 characters"):
            srv._serve(self._args("--transport", "streamable-http"))
        assert not started

    def test_an_open_server_on_a_network_address_is_warned_about(self, started, caplog):
        caplog.set_level(logging.WARNING, logger="pyeuropepmc.mcp")
        srv._serve(self._args("--transport", "streamable-http", "--host", "0.0.0.0"))
        assert "without authentication" in caplog.text and au.ENV_TOKEN in caplog.text

    def test_no_warning_on_loopback_or_with_a_token(self, started, monkeypatch, caplog):
        caplog.set_level(logging.WARNING, logger="pyeuropepmc.mcp")
        srv._serve(self._args("--transport", "streamable-http"))
        monkeypatch.setenv(au.ENV_TOKEN, GOOD)
        srv._serve(self._args("--transport", "streamable-http", "--host", "0.0.0.0"))
        assert "without authentication" not in caplog.text

    def test_generate_token_prints_a_usable_token_and_serves_nothing(self, started, capsys):
        srv._main_entry(["--generate-token"])
        token = capsys.readouterr().out.strip()
        assert au.load_tokens(environ={au.ENV_TOKEN: token}) == [token]
        assert not started
