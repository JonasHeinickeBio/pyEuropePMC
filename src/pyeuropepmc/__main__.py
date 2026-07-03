"""
Entry point for ``python -m pyeuropepmc``.

Delegates to the CLI app defined in :mod:`pyeuropepmc.cli`.
"""

from pyeuropepmc.cli import app

if __name__ == "__main__":
    app()
