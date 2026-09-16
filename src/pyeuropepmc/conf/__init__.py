"""Mapping files that ship with pyeuropepmc.

- ``rdf_map.yml``: the RDF mapping used by :class:`~pyeuropepmc.mappers.RDFMapper`,
  :class:`~pyeuropepmc.pipeline.PaperProcessingPipeline` and ``load_rdf_config()``
- ``rml_mappings.ttl`` and ``rdfizer_config.ini``: the defaults of
  :class:`~pyeuropepmc.mappers.rml_rdfizer.RMLRDFizer`
- ``pyeuropepmc-vocab.ttl``: definitions of the ``pyeuropepmc:`` vocabulary
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

__all__ = ["config_file"]


def config_file(name: str) -> Path:
    """Return the path of the packaged mapping file ``name``.

    The files used to live in a ``conf/`` directory at the repository root and
    were found by walking up from ``__file__``, which only works in a source
    checkout: after ``pip install`` that walk ends in the interpreter's ``lib/``
    directory. They now ship inside the package.
    """
    # pip and uv install wheels unpacked, so the resource is a real file.
    return Path(str(files(__name__).joinpath(name)))
