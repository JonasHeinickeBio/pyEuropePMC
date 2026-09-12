"""
Automatic ``.env`` file loader for pyEuropePMC.

Searches for a ``.env`` file in the following order (first found wins):

1. Current working directory (``.env``)
2. Parent directories of CWD (walking up to root)
3. ``~/.config/pyeuropepmc/.env``

Usage::

    from pyeuropepmc.utils.env_loader import load_env

    load_env()  # called once at CLI entry point
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_ENV_LOADED: bool = False


def _find_env_file() -> Path | None:
    """Search for a ``.env`` file in priority order.

    Returns
    -------
    Path or None
        Path to the first ``.env`` file found, or ``None``.
    """
    # 1. Current working directory
    cwd = Path.cwd()
    candidate = cwd / ".env"
    if candidate.is_file():
        return candidate.resolve()

    # 2. Walk up parent directories (up to root)
    for parent in cwd.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate.resolve()

    # 3. ~/.config/pyeuropepmc/.env
    config_dir = Path.home() / ".config" / "pyeuropepmc"
    candidate = config_dir / ".env"
    if candidate.is_file():
        return candidate.resolve()

    return None


def load_env(overwrite: bool = False) -> bool:
    """Load environment variables from a ``.env`` file.

    Searches in priority order (CWD → parents → ``~/.config/pyeuropepmc/``)
    and loads the first ``.env`` found.  By default existing environment
    variables are **not** overwritten.

    Parameters
    ----------
    overwrite : bool
        If ``True``, overwrite already-set environment variables.
        Defaults to ``False`` (safe mode).

    Returns
    -------
    bool
        ``True`` if a ``.env`` file was found and loaded, ``False`` otherwise.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return True

    env_path = _find_env_file()
    if env_path is None:
        # No .env file anywhere — that's fine
        logger.debug("No .env file found in search path")
        return False

    _do_load(env_path, overwrite=overwrite)
    _ENV_LOADED = True
    logger.info("Loaded environment from %s", env_path)
    return True


def _do_load(path: Path, overwrite: bool = False) -> None:
    """Parse and apply a single ``.env`` file.

    Supports:
    - ``KEY=VALUE``
    - ``KEY="quoted value"`` / ``KEY='quoted value'``
    - ``# comments``
    - Blank lines
    """
    with open(path) as f:
        for line in f:
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Split on first unquoted =
            if "=" not in line:
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            if not key:
                continue

            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]

            # Unset empty and skip if already set
            if not value:
                os.environ.pop(key, None)
            elif overwrite or key not in os.environ:
                os.environ[key] = value


__all__ = ["load_env", "_find_env_file"]
