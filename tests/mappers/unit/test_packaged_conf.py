"""The mapping files ship inside the package.

They used to sit in a ``conf/`` directory at the repository root and were found
by walking up from ``__file__``. After ``pip install`` that walk ended in the
interpreter's ``lib/`` directory: ``RDFMapper()`` and ``PaperProcessingPipeline``
raised ``FileNotFoundError``, and ``load_rdf_config()`` silently fell back to a
built-in configuration instead of ``rdf_map.yml``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pyeuropepmc
from pyeuropepmc.conf import config_file

PACKAGE_DIR = Path(pyeuropepmc.__file__).resolve().parent


@pytest.mark.parametrize(
    "name",
    ["rdf_map.yml", "rml_mappings.ttl", "rdfizer_config.ini", "pyeuropepmc-vocab.ttl"],
)
def test_file_is_inside_the_package(name: str) -> None:
    path = config_file(name)
    assert path.is_file()
    # Inside the package, so the wheel carries it; not the repository root.
    assert path.resolve().is_relative_to(PACKAGE_DIR)


def test_rdf_mapper_default_is_the_packaged_file() -> None:
    from pyeuropepmc.mappers import RDFMapper

    mapper = RDFMapper()
    packaged = RDFMapper(config_path=str(config_file("rdf_map.yml")))
    assert mapper.config == packaged.config


def test_load_rdf_config_reads_the_packaged_file() -> None:
    """Not the built-in fallback, which differs from rdf_map.yml."""
    import yaml

    from pyeuropepmc.mappers.config_utils import load_rdf_config

    with config_file("rdf_map.yml").open(encoding="utf-8") as handle:
        packaged = yaml.safe_load(handle)

    assert load_rdf_config()["base_uri"] == packaged["_base_uri"]
