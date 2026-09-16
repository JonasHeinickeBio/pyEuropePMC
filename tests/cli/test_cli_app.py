"""
Tests for CLI __init__: the main Typer app structure.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from typer.testing import CliRunner

from pyeuropepmc.cli import app
from pyeuropepmc.utils.dependencies import is_dependency_available

pytestmark = pytest.mark.skipif(
    not is_dependency_available("typer"), reason="skipped due to missing typer"
)


class TestCLIApp:
    """Tests for the main CLI application."""

    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_app_help(self) -> None:
        """--help shows app name and subcommands."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "pyeuropepmc" in result.output
        assert "benchmark" in result.output
        assert "normalize" in result.output

    def test_app_no_args_shows_help(self) -> None:
        """No args triggers help (no_args_is_help=True)."""
        result = self.runner.invoke(app, [])
        # Typer/Click >= 0.12 exits 2 when no_args_is_help shows usage for a
        # command group invoked without a subcommand.
        assert result.exit_code == 2
        assert "benchmark" in result.output
        assert "normalize" in result.output

    def test_app_benchmark_help(self) -> None:
        """benchmark subcommand has its own help."""
        result = self.runner.invoke(app, ["benchmark", "--help"])
        assert result.exit_code == 0
        assert "benchmark" in result.output.lower()

    def test_app_normalize_help(self) -> None:
        """normalize subcommand has its own help."""
        result = self.runner.invoke(app, ["normalize", "--help"])
        assert result.exit_code == 0
        assert "normalize" in result.output.lower()

    @pytest.mark.slow
    def test_main_block(self) -> None:
        """The ``if __name__ == '__main__'`` block executes without error."""
        result = subprocess.run(
            [sys.executable, "-m", "pyeuropepmc.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "pyeuropepmc" in result.stdout


class TestMCPCommand:
    """``pyeuropepmc mcp`` runs the MCP server.

    A client that launches the package with ``uvx pyeuropepmc`` gets the
    console script named after the distribution, which is this CLI. Without
    this subcommand such a client starts the CLI, is shown its help text and
    never speaks MCP - which is what ``server.json`` used to ask clients to do.
    """

    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_command_is_registered(self) -> None:
        """The subcommand server.json points at exists."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "mcp" in result.output

    def test_arguments_reach_the_server(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Options after ``mcp`` are passed on unchanged, not parsed by click."""
        from pyeuropepmc.mcp import server

        seen: list[list[str]] = []
        monkeypatch.setattr(server, "_main_entry", lambda argv=None: seen.append(list(argv or [])))

        result = self.runner.invoke(app, ["mcp", "--transport", "sse", "--port", "9999"])

        assert result.exit_code == 0
        assert seen == [["--transport", "sse", "--port", "9999"]]

    def test_help_comes_from_the_server(self) -> None:
        """``--help`` describes the server's options, not an empty click command."""
        result = self.runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == 0
        assert "--transport" in result.output
        assert "--log-level" in result.output
