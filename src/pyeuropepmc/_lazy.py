"""
Lazy attribute loading for package ``__init__`` modules (PEP 562).

Keeping ``import pyeuropepmc`` (and its sub-packages) cheap means *not*
importing heavy optional dependencies — pandas, rdflib, langchain, flask,
matplotlib — at module import time.  Instead each package ``__init__``
declares a map of ``public name -> "dotted.module:attribute"`` and defers
the real import until the attribute is first accessed.

Usage
-----
In ``some_package/__init__.py``::

    from typing import Any
    from pyeuropepmc._lazy import lazy_module

    _lazy_getattr, __dir__, __all__ = lazy_module(
        __name__,
        {
            "SearchClient": "pyeuropepmc.features.literature.search:SearchClient",
            "FTPDownloader": "pyeuropepmc.features.literature.ftp_downloader:FTPDownloader",
        },
        # names that are cheap and imported eagerly elsewhere in the file
        eager=("__version__",),
    )

    def __getattr__(name: str) -> Any:
        return _lazy_getattr(name)

Defining ``__getattr__`` as a real ``def`` (rather than binding it from the
tuple) is what lets type checkers treat unknown attributes as ``Any`` (PEP 562)
instead of reporting ``attr-defined`` / ``implicit-reexport`` errors.

``from pkg import SearchClient`` and ``pkg.SearchClient`` both work and only
pay the import cost on first use.  Add an ``if TYPE_CHECKING:`` block of real
``from x import Y as Y`` imports in the ``__init__`` to give IDEs / mypy the
precise types for the common names.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import importlib
from typing import Any

__all__ = ["lazy_module"]


def lazy_module(
    package_name: str,
    attr_map: dict[str, str],
    *,
    eager: Iterable[str] = (),
    optional: dict[str, str] | None = None,
) -> tuple[Callable[[str], Any], Callable[[], list[str]], list[str]]:
    """
    Build ``__getattr__``, ``__dir__`` and ``__all__`` for a lazy package.

    Parameters
    ----------
    package_name
        Always pass ``__name__`` from the calling ``__init__``.
    attr_map
        Mapping of exported attribute name to ``"module.path:attribute"``
        (or just ``"module.path"`` to return the module itself).
    eager
        Extra names already defined in the module namespace that should
        appear in ``__all__`` / ``dir()`` (e.g. ``__version__``, constants).
    optional
        Like ``attr_map`` but the target import may legitimately be missing
        (uninstalled optional dependency).  On ``ImportError`` the attribute
        resolves to ``None`` instead of raising, matching the previous
        ``try/except ImportError`` guards (used for the Flask web UI).

    Returns
    -------
    (``__getattr__``, ``__dir__``, ``__all__``)
    """
    optional = optional or {}
    cache: dict[str, Any] = {}
    all_names = sorted({*attr_map, *optional, *eager})

    def _resolve(target: str) -> Any:
        module_path, _, attr = target.partition(":")
        module = importlib.import_module(module_path)
        return getattr(module, attr) if attr else module

    def __getattr__(name: str) -> Any:
        if name in cache:
            return cache[name]
        if name in attr_map:
            value = _resolve(attr_map[name])
        elif name in optional:
            try:
                value = _resolve(optional[name])
            except ImportError:
                value = None
        else:
            raise AttributeError(f"module {package_name!r} has no attribute {name!r}")
        cache[name] = value
        return value

    def __dir__() -> list[str]:
        return all_names

    return __getattr__, __dir__, all_names
