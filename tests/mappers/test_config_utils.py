"""
Tests for mappers/config_utils.py.

Covers load_rdf_config, get_namespace_from_config, rebind_namespaces,
setup_graph, setup_dataset, _bind_fallback_namespaces, and create_named_graph.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.mappers.config_utils import (
    _bind_fallback_namespaces,
    _get_default_rdf_config,
    create_named_graph,
    get_namespace_from_config,
    load_rdf_config,
    rebind_namespaces,
    setup_dataset,
    setup_graph,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_graph() -> MagicMock:
    """Mock an rdflib Graph with bind tracking."""
    g = MagicMock()
    g.bind = MagicMock()
    return g


@pytest.fixture
def mock_dataset() -> MagicMock:
    """Mock an rdflib Dataset with default_graph and graphs."""
    g = MagicMock()
    g.bind = MagicMock()
    g.default_graph = MagicMock()
    g.default_graph.bind = MagicMock()
    g.graphs = MagicMock(return_value=[MagicMock(), MagicMock()])
    return g


# ---------------------------------------------------------------------------
# load_rdf_config
# ---------------------------------------------------------------------------

class TestLoadRdfConfig:
    """Tests for load_rdf_config()."""

    def _setup_conf(self, tmp_path: Path, yaml_content: str) -> None:
        """Create conf/rdf_map.yml in the path where load_rdf_config expects it.

        load_rdf_config() does::
            Path(__file__).parent.parent.parent.parent / "conf" / "rdf_map.yml"

        With ``__file__ = tmp_path/l1/l2/l3/l4/dummy.py`` (depth 4)::
            .parent * 4 = tmp_path/l1
            config path = tmp_path/l1/conf/rdf_map.yml
        """
        conf_dir = tmp_path / "l1" / "conf"
        conf_dir.mkdir(parents=True, exist_ok=True)
        conf_dir.joinpath("rdf_map.yml").write_text(yaml_content)

    def _patch_file(self, tmp_path: Path) -> str:
        """Return a __file__ path 4 levels deep above tmp_path/l1.

        Path(__file__).parent.parent.parent.parent resolves to tmp_path/l1,
        matching the project root where conf/ lives.
        """
        return str(tmp_path / "l1" / "l2" / "l3" / "l4" / "dummy.py")

    def test_config_file_not_found(self, tmp_path: Path) -> None:
        """Fallback to default config when YAML does not exist."""
        with patch(
            "pyeuropepmc.mappers.config_utils.__file__",
            self._patch_file(tmp_path),
        ):
            config = load_rdf_config()
        assert config["named_graphs"] is not None
        assert "publications" in config["named_graphs"]
        assert config["base_uri"] == _get_default_rdf_config()["base_uri"]

    def test_config_file_parse_error(self, tmp_path: Path) -> None:
        """Fallback to default config when YAML is malformed."""
        self._setup_conf(tmp_path, ": bad yaml\n  broken")
        with patch(
            "pyeuropepmc.mappers.config_utils.__file__",
            self._patch_file(tmp_path),
        ):
            config = load_rdf_config()
        assert config["named_graphs"] is not None
        assert config["base_uri"] == _get_default_rdf_config()["base_uri"]

    def test_config_file_disabled_graph(self, tmp_path: Path) -> None:
        """Disabled named graph is filtered out."""
        self._setup_conf(
            tmp_path,
            """
_named_graphs:
  authors:
    title: Author Graph
    description: Test
    enabled: true
  institutions:
    title: Institution Graph
    description: Test
    enabled: false
_required_named_graphs:
  - authors
_@prefix:
  dcterms: "http://purl.org/dc/terms/"
_base_uri: "http://example.org/data/"
""",
        )
        with patch(
            "pyeuropepmc.mappers.config_utils.__file__",
            self._patch_file(tmp_path),
        ):
            config = load_rdf_config()
        assert "authors" in config["named_graphs"]
        assert "institutions" not in config["named_graphs"]

    def test_config_file_all_enabled_by_default(self, tmp_path: Path) -> None:
        """Graph without 'enabled' key defaults to enabled."""
        self._setup_conf(
            tmp_path,
            """
_named_graphs:
  test_graph:
    title: Test
    description: Test
_@prefix: {}
""",
        )
        with patch(
            "pyeuropepmc.mappers.config_utils.__file__",
            self._patch_file(tmp_path),
        ):
            config = load_rdf_config()
        assert "test_graph" in config["named_graphs"]

    def test_config_file_with_quality_thresholds(self, tmp_path: Path) -> None:
        """Config with quality_thresholds section."""
        self._setup_conf(
            tmp_path,
            """
_named_graphs: {}
_@prefix: {}
_quality_thresholds:
  high: 0.9
  medium: 0.5
  low: 0.0
""",
        )
        with patch(
            "pyeuropepmc.mappers.config_utils.__file__",
            self._patch_file(tmp_path),
        ):
            config = load_rdf_config()
        assert config["quality_thresholds"]["high"] == 0.9
        assert config["quality_thresholds"]["medium"] == 0.5
        assert config["quality_thresholds"]["low"] == 0.0

    def test_config_file_with_defaults(self, tmp_path: Path) -> None:
        """Config with _defaults section."""
        self._setup_conf(
            tmp_path,
            """
_named_graphs: {}
_@prefix: {}
_defaults:
  include_content: false
""",
        )
        with patch(
            "pyeuropepmc.mappers.config_utils.__file__",
            self._patch_file(tmp_path),
        ):
            config = load_rdf_config()
        assert config["defaults"]["include_content"] is False

    def test_default_rdf_config(self) -> None:
        """_get_default_rdf_config returns a complete config dict."""
        config = _get_default_rdf_config()
        assert "named_graphs" in config
        assert "required_named_graphs" in config
        assert "ontologies" in config
        assert "base_uri" in config
        assert config["base_uri"] == "http://example.org/data/"
        assert len(config["named_graphs"]) == 4


# ---------------------------------------------------------------------------
# get_namespace_from_config
# ---------------------------------------------------------------------------

class TestGetNamespaceFromConfig:
    """Tests for get_namespace_from_config()."""

    def test_prefix_found_in_config(self) -> None:
        """Return Namespace from _@prefix section."""
        config: dict[str, Any] = {
            "_@prefix": {"dcterms": "http://purl.org/dc/terms/"},
        }
        ns = get_namespace_from_config(config, "dcterms")
        assert str(ns) == "http://purl.org/dc/terms/"

    def test_prefix_not_found(self) -> None:
        """Fallback Namespace for unknown prefix."""
        config: dict[str, Any] = {"_@prefix": {}}
        ns = get_namespace_from_config(config, "unknown")
        assert str(ns) == "http://example.org/unknown#"


# ---------------------------------------------------------------------------
# rebind_namespaces
# ---------------------------------------------------------------------------

class TestRebindNamespaces:
    """Tests for rebind_namespaces()."""

    def test_rebind_graph(self, mock_graph: MagicMock) -> None:
        """Rebind namespaces on a simple Graph."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            return_value={
                "_@prefix": {"dcterms": "http://purl.org/dc/terms/"},
            },
        ):
            rebind_namespaces(mock_graph)
        mock_graph.bind.assert_called_once_with(
            "dcterms",
            pytest.importorskip("rdflib").Namespace("http://purl.org/dc/terms/"),
            override=True,
            replace=True,
        )

    def test_rebind_dataset(self, mock_dataset: MagicMock) -> None:
        """Rebind namespaces on a Dataset (default_graph + graphs)."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            return_value={
                "_@prefix": {"foaf": "http://xmlns.com/foaf/0.1/"},
            },
        ):
            rebind_namespaces(mock_dataset)
        # Main dataset bound
        mock_dataset.bind.assert_called_once()
        # Default graph bound
        mock_dataset.default_graph.bind.assert_called_once()
        # Each named graph must be rebound (not zero)
        for named_graph in mock_dataset.graphs():
            named_graph.bind.assert_called_once()

    def test_rebind_failure_handled(self, mock_graph: MagicMock) -> None:
        """Exception during rebind is caught gracefully."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            side_effect=Exception("fail"),
        ):
            # Should not raise
            rebind_namespaces(mock_graph)


# ---------------------------------------------------------------------------
# setup_graph
# ---------------------------------------------------------------------------

class TestSetupGraph:
    """Tests for setup_graph()."""

    rdflib = pytest.importorskip("rdflib")

    def test_setup_graph_basic(self) -> None:
        """Graph created with namespaces from config."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            return_value={
                "_@prefix": {"dcterms": "http://purl.org/dc/terms/"},
            },
        ):
            g = setup_graph()
        assert isinstance(g, self.rdflib.Graph)
        ns = g.store.namespace("dcterms")
        assert str(ns) == "http://purl.org/dc/terms/"

    def test_setup_graph_with_additional_namespaces(self) -> None:
        """Graph with additional namespaces."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            return_value={"_@prefix": {}},
        ):
            g = setup_graph(namespaces={"ex": "http://example.org/"})
        assert isinstance(g, self.rdflib.Graph)
        ns = g.store.namespace("ex")
        assert str(ns) == "http://example.org/"

    def test_setup_graph_fallback(self) -> None:
        """Graph uses fallback namespaces when config fails."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            side_effect=Exception("fail"),
        ):
            g = setup_graph()
        assert isinstance(g, self.rdflib.Graph)
        # Fallback namespaces should be bound
        ns = g.store.namespace("foaf")
        assert str(ns) == "http://xmlns.com/foaf/0.1/"


# ---------------------------------------------------------------------------
# setup_dataset
# ---------------------------------------------------------------------------

class TestSetupDataset:
    """Tests for setup_dataset()."""

    rdflib = pytest.importorskip("rdflib")

    def test_setup_dataset_basic(self) -> None:
        """Dataset created with namespaces from config."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            return_value={
                "_@prefix": {"dcterms": "http://purl.org/dc/terms/"},
            },
        ):
            g = setup_dataset()
        assert isinstance(g, self.rdflib.Dataset)
        ns = g.store.namespace("dcterms")
        assert str(ns) == "http://purl.org/dc/terms/"

    def test_setup_dataset_with_additional(self) -> None:
        """Dataset with additional namespaces."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            return_value={"_@prefix": {}},
        ):
            g = setup_dataset(namespaces={"ex": "http://example.org/"})
        assert isinstance(g, self.rdflib.Dataset)
        ns = g.store.namespace("ex")
        assert str(ns) == "http://example.org/"

    def test_setup_dataset_fallback(self) -> None:
        """Dataset uses fallback when config fails."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            side_effect=Exception("fail"),
        ):
            g = setup_dataset()
        assert isinstance(g, self.rdflib.Dataset)
        ns = g.store.namespace("foaf")
        assert str(ns) == "http://xmlns.com/foaf/0.1/"


# ---------------------------------------------------------------------------
# _bind_fallback_namespaces
# ---------------------------------------------------------------------------

class TestBindFallbackNamespaces:
    """Tests for _bind_fallback_namespaces()."""

    rdflib = pytest.importorskip("rdflib")

    def test_binds_all_fallback_prefixes(self) -> None:
        """All fallback namespaces are bound to the graph."""
        g = self.rdflib.Graph()
        _bind_fallback_namespaces(g)
        # Spot-check a few well-known prefixes
        for prefix in ("dcterms", "foaf", "rdf", "owl", "xsd", "skos"):
            ns = g.store.namespace(prefix)
            assert ns is not None, f"Prefix {prefix} should be bound"
            assert str(ns).startswith("http://")


# ---------------------------------------------------------------------------
# create_named_graph
# ---------------------------------------------------------------------------

class TestCreateNamedGraph:
    """Tests for create_named_graph()."""

    rdflib = pytest.importorskip("rdflib")

    def test_create_named_graph_basic(self) -> None:
        """Named graph created with standard namespaces bound."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            return_value={
                "ontologies": {"ex": "http://example.org/"},
            },
        ):
            ng = create_named_graph("test", "Test", "Test graph")
        assert isinstance(ng, self.rdflib.Graph)
        # Standard namespaces
        assert ng.store.namespace("rdf") is not None
        assert ng.store.namespace("rdfs") is not None
        assert ng.store.namespace("xsd") is not None
        # Custom ontology
        ns = ng.store.namespace("ex")
        assert str(ns) == "http://example.org/"

    def test_create_named_graph_empty_ontologies(self) -> None:
        """Named graph with no ontologies in config."""
        with patch(
            "pyeuropepmc.mappers.config_utils.load_rdf_config",
            return_value={"ontologies": {}},
        ):
            ng = create_named_graph("test", "Test", "Test graph")
        assert isinstance(ng, self.rdflib.Graph)
        # Standard namespaces still bound
        assert ng.store.namespace("rdf") is not None
        assert ng.store.namespace("rdfs") is not None
        assert ng.store.namespace("xsd") is not None
