"""
Tests for CLI __init__: the main Typer app structure.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from typer.testing import CliRunner

from pyeuropepmc.cli import app


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
        assert result.exit_code == 0
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
