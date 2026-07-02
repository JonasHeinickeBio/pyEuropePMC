"""
Tests for pyeuropepmc.__main__: entry point for python -m pyeuropepmc.
"""

from __future__ import annotations

import subprocess
import sys


class TestMainEntry:
    """Tests for the __main__ entry point."""

    def test_main_module_invocation(self) -> None:
        """Running as module shows help."""
        result = subprocess.run(
            [sys.executable, "-m", "pyeuropepmc", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "pyeuropepmc" in result.stdout

    def test_main_module_benchmark_help(self) -> None:
        """Benchmark subcommand help via module."""
        result = subprocess.run(
            [sys.executable, "-m", "pyeuropepmc", "benchmark", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "benchmark" in result.stdout.lower()

    def test_main_module_normalize_help(self) -> None:
        """Normalize subcommand help via module."""
        result = subprocess.run(
            [sys.executable, "-m", "pyeuropepmc", "normalize", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "normalize" in result.stdout.lower()
