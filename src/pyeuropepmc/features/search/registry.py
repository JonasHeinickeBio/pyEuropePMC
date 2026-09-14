"""
Pluggable registry of literature search sources.

Instead of a hard-coded ``dict`` inside :mod:`pyeuropepmc.features.search.unified_search`,
each source is described by a :class:`SourceSpec` and registered here.  This
makes the source set:

* **discoverable** — :func:`available_sources` (optionally filtered to what is
  actually installed) and :func:`source_capabilities`;
* **extensible** — third-party packages can call :func:`register_source` (e.g.
  from a ``pyeuropepmc.sources`` entry point) without editing this file;
* **honest about dependencies** — :func:`load_source` raises a helpful
  :class:`~pyeuropepmc._optional_imports.OptionalDependencyError` naming the
  extra to ``pip install`` when a source needs a library that is missing.

Nothing here imports a source client at module-import time; classes are resolved
lazily from their ``"module.path:ClassName"`` target on first use.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import importlib
import logging
from typing import Any

from pyeuropepmc._optional_imports import OptionalDependencyError, is_package_available

logger = logging.getLogger(__name__)

__all__ = [
    "SourceSpec",
    "register_source",
    "get_source_spec",
    "available_sources",
    "source_capabilities",
    "load_source",
    "load_entry_point_sources",
]

# Capability tokens (free-form, but keep these consistent across sources).
CAP_SEARCH = "search"
CAP_GET_PAPER = "get_paper"
CAP_CITATIONS = "citations"
CAP_FULLTEXT = "fulltext"
CAP_DATE_FILTER = "date_filter"


@dataclass(frozen=True)
class SourceSpec:
    """
    Description of one literature search source.

    Parameters
    ----------
    name
        Short identifier used in ``UnifiedSearch(sources=[...])``.
    target
        ``"module.path:ClassName"`` of the client/adapter.  Resolved lazily.
    extras
        Importable module names the client needs at runtime (e.g.
        ``("semanticscholar",)``).  Empty for pure-``requests`` sources.
    pip_extra
        The ``pip install pyeuropepmc[<pip_extra>]`` extra that provides
        ``extras``.  Defaults to ``name``.
    capabilities
        What the source can do — see the ``CAP_*`` constants.
    credential_kwargs
        Constructor keyword arguments that should be forwarded from
        caller-supplied credentials when present (e.g. ``("api_key",)`` for
        Semantic Scholar, ``("email",)`` for the NCBI / OpenAlex polite pools).
    """

    name: str
    target: str
    extras: tuple[str, ...] = ()
    pip_extra: str | None = None
    capabilities: frozenset[str] = frozenset({CAP_SEARCH})
    credential_kwargs: tuple[str, ...] = ()

    def resolve(self) -> type:
        """Import and return the client class."""
        module_path, _, class_name = self.target.partition(":")
        module = importlib.import_module(module_path)
        return getattr(module, class_name)  # type: ignore[no-any-return]

    @property
    def install_hint(self) -> str:
        return f"pip install pyeuropepmc[{self.pip_extra or self.name}]"

    def missing_extras(self) -> list[str]:
        return [mod for mod in self.extras if not is_package_available(mod)]

    @property
    def is_installed(self) -> bool:
        return not self.missing_extras()


_REGISTRY: dict[str, SourceSpec] = {}


def register_source(spec: SourceSpec, *, replace: bool = False) -> None:
    """Register (or, with ``replace=True``, override) a source."""
    if spec.name in _REGISTRY and not replace:
        raise ValueError(
            f"Source '{spec.name}' is already registered; pass replace=True to override"
        )
    _REGISTRY[spec.name] = spec
    logger.debug("Registered literature source '%s' -> %s", spec.name, spec.target)


def get_source_spec(name: str) -> SourceSpec:
    """Return the :class:`SourceSpec` for ``name`` or raise ``KeyError``."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"Unknown source '{name}'. Registered: {sorted(_REGISTRY)}") from None


def available_sources(*, installed_only: bool = False) -> list[str]:
    """
    List registered source names.

    Parameters
    ----------
    installed_only
        When ``True``, omit sources whose optional dependency is not importable.
    """
    names = sorted(_REGISTRY)
    if installed_only:
        names = [n for n in names if _REGISTRY[n].is_installed]
    return names


def source_capabilities(name: str) -> frozenset[str]:
    """Return the capability set for ``name``."""
    return get_source_spec(name).capabilities


def load_source(name: str, /, **kwargs: Any) -> Any:
    """
    Instantiate the client for ``name``.

    Unknown constructor kwargs are dropped so a single ``kwargs`` blob (e.g.
    ``rate_limit_delay``, ``timeout``, ``api_key``, ``email``) can be passed for
    every source.

    Raises
    ------
    OptionalDependencyError
        If the source needs a package that is not installed.
    KeyError
        If ``name`` is not registered.
    """
    spec = get_source_spec(name)
    missing = spec.missing_extras()
    if missing:
        raise OptionalDependencyError(missing[0], f"literature source '{name}'", spec.install_hint)

    client_cls = spec.resolve()
    accepted = _acceptable_kwargs(client_cls)
    call_kwargs = {k: v for k, v in kwargs.items() if accepted is None or k in accepted}
    return client_cls(**call_kwargs)


def load_entry_point_sources(group: str = "pyeuropepmc.sources") -> None:
    """
    Load third-party sources advertised via ``[project.entry-points]``.

    Each entry point is expected to be a zero-argument callable that performs
    its own :func:`register_source` call(s).  Failures are logged, not raised.
    """
    from importlib.metadata import entry_points

    eps: Iterable[Any] = entry_points(group=group)

    for ep in eps:
        try:
            ep.load()()
            logger.info("Loaded literature sources from entry point '%s'", ep.name)
        except Exception as exc:  # noqa: BLE001 - third-party plugin, stay resilient
            logger.warning("Failed to load source entry point '%s': %s", ep.name, exc)


def _acceptable_kwargs(cls: type) -> set[str] | None:
    """Return the set of accepted constructor kwarg names, or None if it takes **kwargs."""
    import inspect

    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return None
    names: set[str] = set()
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            return None  # accepts anything
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            names.add(p.name)
    return names


# ---------------------------------------------------------------------------
# Built-in sources
# ---------------------------------------------------------------------------

_A = "pyeuropepmc.features.literature.adapters"
_S = "pyeuropepmc.features.search.sources"

_BUILTINS: tuple[SourceSpec, ...] = (
    SourceSpec(
        "europepmc",
        f"{_A}:EuropePMCLiteratureAdapter",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER, CAP_FULLTEXT, CAP_DATE_FILTER}),
    ),
    SourceSpec(
        "pubmed",
        f"{_S}.pubmed:PubMedClient",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER, CAP_DATE_FILTER}),
        credential_kwargs=("email",),
    ),
    SourceSpec(
        "arxiv",
        f"{_S}.arxiv:ArxivClient",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER}),
    ),
    SourceSpec(
        "clinicaltrials",
        f"{_S}.clinicaltrials:ClinicalTrialsClient",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER}),
    ),
    SourceSpec(
        "semantic_scholar",
        f"{_A}:SemanticScholarLiteratureAdapter",
        extras=("semanticscholar",),
        pip_extra="semanticscholar",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER, CAP_CITATIONS}),
        credential_kwargs=("api_key",),
    ),
    SourceSpec(
        "openalex",
        f"{_A}:OpenAlexLiteratureAdapter",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER, CAP_CITATIONS, CAP_DATE_FILTER}),
        credential_kwargs=("email",),
    ),
    SourceSpec(
        "zenodo",
        f"{_S}.zenodo:ZenodoClient",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER}),
    ),
    SourceSpec(
        "doaj",
        f"{_S}.doaj:DOAJClient",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER}),
    ),
    SourceSpec(
        "dblp",
        f"{_S}.dblp:DBLPClient",
        capabilities=frozenset({CAP_SEARCH}),
    ),
    SourceSpec(
        "hal",
        f"{_S}.hal:HALClient",
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER}),
    ),
    SourceSpec(
        "core",
        f"{_S}.core:COREClient",
        extras=(),
        capabilities=frozenset({CAP_SEARCH, CAP_GET_PAPER, CAP_FULLTEXT}),
        credential_kwargs=("api_key",),
    ),
)

for _spec in _BUILTINS:
    register_source(_spec)
