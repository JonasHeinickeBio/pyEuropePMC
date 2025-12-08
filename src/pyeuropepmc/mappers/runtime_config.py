"""
Runtime Configuration Manager for PyEuropePMC RDF conversion.

This module provides:
- Loading and merging of runtime configuration from rdf_config.yaml
- Environment-specific configuration overrides
- Validation of configuration against JSON Schema
- Integration with LinkML schema for mapping definitions

The runtime configuration is SEPARATE from the schema/mapping definitions:
- Schema/mappings: schemas/pyeuropepmc_schema.yaml (LinkML - source of truth)
- Runtime config: conf/rdf_config.yaml (operational settings)
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from pyeuropepmc.mappers.linkml_introspection import (
    LINKML_AVAILABLE,
    LinkMLSchemaIntrospector,
)

logger = logging.getLogger(__name__)

__all__ = [
    "RuntimeConfig",
    "load_runtime_config",
    "get_config",
]


def _get_default_config_path() -> Path:
    """Get the default path to the runtime configuration file."""
    base_path = Path(__file__).parent.parent.parent.parent
    return base_path / "conf" / "rdf_config.yaml"


def _get_legacy_config_path() -> Path:
    """Get the path to the legacy rdf_map.yml file."""
    base_path = Path(__file__).parent.parent.parent.parent
    return base_path / "conf" / "rdf_map.yml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries, with override taking precedence.

    Parameters
    ----------
    base : dict
        Base dictionary
    override : dict
        Override dictionary (values take precedence)

    Returns
    -------
    dict
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class RuntimeConfig:
    """
    Runtime configuration manager for RDF conversion.

    This class manages operational settings for RDF conversion, separate from
    the schema/mapping definitions which are handled by LinkML.

    Attributes
    ----------
    config : dict
        The loaded configuration dictionary
    environment : str
        Current environment (development, production, testing)
    linkml_introspector : LinkMLSchemaIntrospector
        Introspector for schema access

    Examples
    --------
    >>> config = RuntimeConfig()
    >>> print(config.get_named_graph_uri("publications"))
    https://w3id.org/pyeuropepmc#publications
    """

    def __init__(
        self,
        config_path: str | None = None,
        environment: str | None = None,
    ):
        """
        Initialize the runtime configuration.

        Parameters
        ----------
        config_path : Optional[str]
            Path to the runtime configuration file. If None, uses default.
        environment : Optional[str]
            Environment name for config overrides. If None, detected from env var.
        """
        self.config_path = config_path or str(_get_default_config_path())
        self.environment = environment or os.environ.get("PYEUROPEPMC_ENV", "development")
        self._config: dict[str, Any] = {}
        self._linkml_introspector: LinkMLSchemaIntrospector | None = None

        self._load_config()

    def _load_config(self) -> None:
        """Load and merge configuration from file and environment."""
        # Try to load the new runtime config
        if os.path.exists(self.config_path):
            with open(self.config_path, encoding="utf-8") as f:
                base_config = yaml.safe_load(f) or {}
        else:
            logger.warning(
                f"Runtime config not found at {self.config_path}, using defaults"
            )
            base_config = self._get_default_config()

        # Apply environment-specific overrides
        env_overrides = base_config.get("environments", {}).get(self.environment, {})
        self._config = _deep_merge(base_config, env_overrides)

        # Remove environments section from final config
        self._config.pop("environments", None)

        logger.debug(f"Loaded runtime config for environment: {self.environment}")

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration when config file is not available."""
        return {
            "schema": {
                "path": "schemas/pyeuropepmc_schema.yaml",
                "version": "1.0.0",
                "use_linkml_introspection": True,
            },
            "uri": {
                "base": "https://w3id.org/pyeuropepmc/",
                "data": "https://w3id.org/pyeuropepmc/data#",
                "vocab": "https://w3id.org/pyeuropepmc/vocab#",
            },
            "named_graphs": {
                "enabled": True,
                "publications": {
                    "uri_base": "https://w3id.org/pyeuropepmc#publications",
                    "enabled": True,
                },
                "authors": {
                    "uri_base": "https://w3id.org/pyeuropepmc#authors",
                    "enabled": True,
                },
                "institutions": {
                    "uri_base": "https://w3id.org/pyeuropepmc#institutions",
                    "enabled": True,
                },
                "provenance": {
                    "uri_base": "https://w3id.org/pyeuropepmc#provenance",
                    "enabled": True,
                },
            },
            "kg_structure": {
                "include_content": True,
                "include_metadata": True,
                "default_type": "complete",
                "enable_citation_networks": True,
                "enable_collaboration_networks": True,
                "enable_institutional_hierarchies": True,
                "enable_quality_metrics": True,
                "enable_shacl_validation": False,
            },
            "quality": {
                "thresholds": {"high": 0.8, "medium": 0.6, "low": 0.0},
                "validation": {"enabled": True, "strict_mode": False},
            },
            "output": {
                "default_format": "turtle",
                "filename_template": "{prefix}{entity_type}_{identifier}.{extension}",
            },
        }

    @property
    def linkml_introspector(self) -> LinkMLSchemaIntrospector:
        """Get the LinkML schema introspector."""
        if self._linkml_introspector is None:
            schema_path = self._config.get("schema", {}).get("path")
            if schema_path:
                base_path = Path(__file__).parent.parent.parent.parent
                full_path = str(base_path / schema_path)
                self._linkml_introspector = LinkMLSchemaIntrospector(full_path)
            else:
                self._linkml_introspector = LinkMLSchemaIntrospector()
        return self._linkml_introspector

    @property
    def use_linkml(self) -> bool:
        """Check if LinkML introspection should be used."""
        use_linkml = self._config.get("schema", {}).get("use_linkml_introspection", True)
        return use_linkml and LINKML_AVAILABLE

    # Named Graphs Configuration
    def get_named_graphs_config(self) -> dict[str, Any]:
        """Get the named graphs configuration."""
        return self._config.get("named_graphs", {})

    def get_named_graph_uri(self, graph_name: str) -> str | None:
        """Get the URI for a specific named graph."""
        graphs = self.get_named_graphs_config()
        graph_config = graphs.get(graph_name, {})
        if isinstance(graph_config, dict) and graph_config.get("enabled", True):
            return graph_config.get("uri_base")
        return None

    def get_enabled_named_graphs(self) -> dict[str, str]:
        """Get all enabled named graph URIs."""
        graphs = self.get_named_graphs_config()
        enabled = {}
        for name, config in graphs.items():
            if isinstance(config, dict) and config.get("enabled", True):
                uri = config.get("uri_base")
                if uri:
                    enabled[name] = uri
        return enabled

    def are_named_graphs_enabled(self) -> bool:
        """Check if named graphs are enabled globally."""
        return self._config.get("named_graphs", {}).get("enabled", True)

    # URI Configuration
    def get_base_uri(self) -> str:
        """Get the base URI for data."""
        return self._config.get("uri", {}).get("base", "https://w3id.org/pyeuropepmc/")

    def get_data_uri(self) -> str:
        """Get the data namespace URI."""
        return self._config.get("uri", {}).get("data", "https://w3id.org/pyeuropepmc/data#")

    def get_vocab_uri(self) -> str:
        """Get the vocabulary namespace URI."""
        return self._config.get("uri", {}).get("vocab", "https://w3id.org/pyeuropepmc/vocab#")

    # Knowledge Graph Structure
    def get_kg_structure(self) -> dict[str, Any]:
        """Get the knowledge graph structure configuration."""
        return self._config.get("kg_structure", {})

    def should_include_content(self) -> bool:
        """Check if content entities should be included."""
        return self.get_kg_structure().get("include_content", True)

    def should_include_metadata(self) -> bool:
        """Check if metadata entities should be included."""
        return self.get_kg_structure().get("include_metadata", True)

    def get_default_kg_type(self) -> str:
        """Get the default knowledge graph type."""
        return self.get_kg_structure().get("default_type", "complete")

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a KG feature is enabled."""
        return self.get_kg_structure().get(feature_name, False)

    # Quality Configuration
    def get_quality_config(self) -> dict[str, Any]:
        """Get the quality configuration."""
        return self._config.get("quality", {})

    def get_quality_threshold(self, level: str) -> float:
        """Get a quality threshold value."""
        thresholds = self.get_quality_config().get("thresholds", {})
        return thresholds.get(level, 0.0)

    def is_validation_enabled(self) -> bool:
        """Check if validation is enabled."""
        validation = self.get_quality_config().get("validation", {})
        return validation.get("enabled", True)

    def is_strict_mode(self) -> bool:
        """Check if strict validation mode is enabled."""
        validation = self.get_quality_config().get("validation", {})
        return validation.get("strict_mode", False)

    # Performance Configuration
    def get_performance_config(self) -> dict[str, Any]:
        """Get the performance configuration."""
        return self._config.get("performance", {})

    def get_batch_size(self) -> int:
        """Get the batch processing size."""
        return self.get_performance_config().get("batch_size", 100)

    def is_caching_enabled(self) -> bool:
        """Check if caching is enabled."""
        caching = self.get_performance_config().get("caching", {})
        return caching.get("enabled", True)

    # Output Configuration
    def get_output_config(self) -> dict[str, Any]:
        """Get the output configuration."""
        return self._config.get("output", {})

    def get_default_format(self) -> str:
        """Get the default serialization format."""
        return self.get_output_config().get("default_format", "turtle")

    def get_filename_template(self) -> str:
        """Get the filename template."""
        return self.get_output_config().get(
            "filename_template",
            "{prefix}{entity_type}_{identifier}.{extension}"
        )

    # Debugging Configuration
    def get_debugging_config(self) -> dict[str, Any]:
        """Get the debugging configuration."""
        return self._config.get("debugging", {})

    def get_log_level(self) -> str:
        """Get the configured log level."""
        logging_config = self.get_debugging_config().get("logging", {})
        return logging_config.get("level", "INFO")

    # Schema/Mapping Access (via LinkML)
    def get_class_mapping(self, class_name: str) -> dict[str, Any]:
        """
        Get mapping for a class from the LinkML schema.

        Parameters
        ----------
        class_name : str
            Name of the entity class

        Returns
        -------
        dict[str, Any]
            Class mapping including fields, relationships, etc.
        """
        if self.use_linkml:
            return self.linkml_introspector.get_class_mapping(class_name)
        return {}

    def get_namespaces(self) -> dict[str, str]:
        """
        Get namespace prefixes from the schema.

        Returns
        -------
        dict[str, str]
            Dictionary mapping prefix to URI.
        """
        if self.use_linkml:
            return self.linkml_introspector.get_namespaces()
        return {}

    def validate_entity(self, entity: Any) -> list[str]:
        """
        Validate an entity against the schema.

        Parameters
        ----------
        entity : Any
            Entity instance to validate

        Returns
        -------
        list[str]
            List of validation error messages (empty if valid).
        """
        if self.use_linkml and self.is_validation_enabled():
            class_name = entity.__class__.__name__
            return self.linkml_introspector.validate_entity(entity, class_name)
        return []

    # Raw config access
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key path."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def to_dict(self) -> dict[str, Any]:
        """Get the full configuration as a dictionary."""
        return self._config.copy()


@lru_cache(maxsize=1)
def load_runtime_config(
    config_path: str | None = None,
    environment: str | None = None,
) -> RuntimeConfig:
    """
    Load and cache the runtime configuration.

    Parameters
    ----------
    config_path : Optional[str]
        Path to the configuration file
    environment : Optional[str]
        Environment name

    Returns
    -------
    RuntimeConfig
        Cached configuration instance
    """
    return RuntimeConfig(config_path, environment)


def get_config() -> RuntimeConfig:
    """
    Get the default runtime configuration instance.

    Returns
    -------
    RuntimeConfig
        The default configuration instance.
    """
    return load_runtime_config()
