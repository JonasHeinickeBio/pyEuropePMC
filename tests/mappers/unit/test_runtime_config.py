"""
Tests for runtime configuration module.

These tests verify that runtime configuration can be loaded and provides
proper access to operational settings.
"""

import pytest

from pyeuropepmc.mappers.runtime_config import (
    RuntimeConfig,
    get_config,
    load_runtime_config,
)


class TestRuntimeConfig:
    """Tests for the RuntimeConfig class."""

    @pytest.fixture
    def config(self) -> RuntimeConfig:
        """Get a runtime config instance."""
        return RuntimeConfig()

    def test_config_loads(self, config: RuntimeConfig) -> None:
        """Test that configuration loads without errors."""
        assert config is not None
        assert isinstance(config.to_dict(), dict)

    def test_get_base_uri(self, config: RuntimeConfig) -> None:
        """Test getting the base URI."""
        base_uri = config.get_base_uri()
        assert base_uri is not None
        assert isinstance(base_uri, str)
        assert base_uri.startswith("http")

    def test_named_graphs_enabled(self, config: RuntimeConfig) -> None:
        """Test checking if named graphs are enabled."""
        enabled = config.are_named_graphs_enabled()
        assert isinstance(enabled, bool)

    def test_get_named_graph_uri(self, config: RuntimeConfig) -> None:
        """Test getting a named graph URI."""
        uri = config.get_named_graph_uri("publications")
        # URI may be None if not configured, but should not error
        if uri is not None:
            assert isinstance(uri, str)

    def test_get_enabled_named_graphs(self, config: RuntimeConfig) -> None:
        """Test getting all enabled named graphs."""
        graphs = config.get_enabled_named_graphs()
        assert isinstance(graphs, dict)

    def test_get_kg_structure(self, config: RuntimeConfig) -> None:
        """Test getting KG structure configuration."""
        kg_structure = config.get_kg_structure()
        assert isinstance(kg_structure, dict)

    def test_should_include_content(self, config: RuntimeConfig) -> None:
        """Test checking if content should be included."""
        include = config.should_include_content()
        assert isinstance(include, bool)

    def test_get_quality_threshold(self, config: RuntimeConfig) -> None:
        """Test getting quality threshold values."""
        high = config.get_quality_threshold("high")
        assert isinstance(high, (int, float))
        assert 0 <= high <= 1

    def test_is_validation_enabled(self, config: RuntimeConfig) -> None:
        """Test checking if validation is enabled."""
        enabled = config.is_validation_enabled()
        assert isinstance(enabled, bool)

    def test_get_batch_size(self, config: RuntimeConfig) -> None:
        """Test getting batch size."""
        size = config.get_batch_size()
        assert isinstance(size, int)
        assert size > 0

    def test_get_default_format(self, config: RuntimeConfig) -> None:
        """Test getting default serialization format."""
        fmt = config.get_default_format()
        assert isinstance(fmt, str)
        assert fmt in ["turtle", "trig", "json-ld", "nquads", "xml"]

    def test_get_filename_template(self, config: RuntimeConfig) -> None:
        """Test getting filename template."""
        template = config.get_filename_template()
        assert isinstance(template, str)
        assert "{" in template  # Should contain placeholders

    def test_get_log_level(self, config: RuntimeConfig) -> None:
        """Test getting log level."""
        level = config.get_log_level()
        assert level in ["DEBUG", "INFO", "WARNING", "ERROR"]

    def test_get_with_default(self, config: RuntimeConfig) -> None:
        """Test getting config value with default."""
        # Should return default for non-existent key
        value = config.get("nonexistent.key", "default_value")
        assert value == "default_value"

    def test_get_nested_value(self, config: RuntimeConfig) -> None:
        """Test getting nested config value."""
        # uri.base should exist
        value = config.get("uri.base")
        if value is not None:
            assert isinstance(value, str)


class TestEnvironmentOverrides:
    """Tests for environment-specific configuration overrides."""

    def test_development_environment(self) -> None:
        """Test configuration with development environment."""
        config = RuntimeConfig(environment="development")
        # Development should have DEBUG logging
        assert config.environment == "development"

    def test_production_environment(self) -> None:
        """Test configuration with production environment."""
        config = RuntimeConfig(environment="production")
        assert config.environment == "production"

    def test_testing_environment(self) -> None:
        """Test configuration with testing environment."""
        config = RuntimeConfig(environment="testing")
        assert config.environment == "testing"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_load_runtime_config(self) -> None:
        """Test cached config loading function."""
        config = load_runtime_config()
        assert config is not None
        assert isinstance(config, RuntimeConfig)

    def test_get_config(self) -> None:
        """Test default config getter."""
        config = get_config()
        assert config is not None
        assert isinstance(config, RuntimeConfig)


class TestLinkMLIntegration:
    """Tests for LinkML integration in runtime config."""

    @pytest.fixture
    def config(self) -> RuntimeConfig:
        """Get a runtime config instance."""
        return RuntimeConfig()

    def test_use_linkml_property(self, config: RuntimeConfig) -> None:
        """Test checking if LinkML should be used."""
        use_linkml = config.use_linkml
        assert isinstance(use_linkml, bool)

    def test_get_class_mapping(self, config: RuntimeConfig) -> None:
        """Test getting class mapping via config."""
        if config.use_linkml:
            mapping = config.get_class_mapping("PaperEntity")
            assert isinstance(mapping, dict)

    def test_get_namespaces(self, config: RuntimeConfig) -> None:
        """Test getting namespaces via config."""
        if config.use_linkml:
            namespaces = config.get_namespaces()
            assert isinstance(namespaces, dict)
