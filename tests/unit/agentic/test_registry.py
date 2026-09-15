"""
Tests for ToolRegistry.

This module tests:
- Tool registration and management
- Tool type classification
- Enable/disable functionality
- Tool execution
- Callback system
"""

import pytest

from pyeuropepmc.agentic.registry import (
    BaseTool,
    ToolInfo,
    ToolRegistry,
    ToolType,
    register,
)


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def test_init(self):
        """Test registry initialization."""
        registry = ToolRegistry()

        assert registry.tools == {}
        assert registry._registry == {}
        assert registry._callbacks == []

    def test_register_decorator(self):
        """Test tool registration using decorator."""
        registry = ToolRegistry()

        @registry.register("test_tool", description="Test tool", tool_type=ToolType.SEARCH)
        def test_tool_function(param1: str, param2: int = 10) -> str:
            """Test tool docstring."""
            return f"{param1}_{param2}"

        assert "test_tool" in registry.tools
        tool_info = registry.tools["test_tool"]

        assert tool_info.name == "test_tool"
        assert tool_info.description == "Test tool"
        assert tool_info.tool_type == ToolType.SEARCH
        assert tool_info.enabled is True
        assert "param1" in tool_info.parameters
        assert "param2" in tool_info.parameters

    def test_execute_registered_tool(self):
        """Test executing a registered tool."""
        registry = ToolRegistry()

        @registry.register("math_tool", tool_type=ToolType.ANALYSIS)
        def add(a: int, b: int) -> int:
            return a + b

        result = registry.execute("math_tool", a=5, b=3)

        assert result == 8

    def test_execute_disabled_tool(self):
        """Test executing a disabled tool raises error."""
        registry = ToolRegistry()

        @registry.register("disabled_tool", enabled=False)
        def disabled_func():
            return "should not execute"

        with pytest.raises(RuntimeError, match="disabled"):
            registry.execute("disabled_tool")

    def test_enable_disable_tool(self):
        """Test enabling and disabling a tool."""
        registry = ToolRegistry()

        @registry.register("toggle_tool", enabled=False)
        def toggle_func():
            return "result"

        # Initially disabled
        with pytest.raises(RuntimeError):
            registry.execute("toggle_tool")

        # Enable
        assert registry.enable("toggle_tool") is True
        result = registry.execute("toggle_tool")
        assert result == "result"

        # Disable
        assert registry.disable("toggle_tool") is True
        with pytest.raises(RuntimeError):
            registry.execute("toggle_tool")

    def test_enable_disable_nonexistent_tool(self):
        """Test enable/disable on non-existent tool."""
        registry = ToolRegistry()

        assert registry.enable("nonexistent") is False
        assert registry.disable("nonexistent") is False

    def test_get_tool_info(self):
        """Test getting tool information."""
        registry = ToolRegistry()

        @registry.register("info_tool", description="Info test")
        def info_func(x: int) -> str:
            return str(x)

        tool_info = registry.get("info_tool")

        assert tool_info is not None
        assert tool_info.name == "info_tool"
        assert tool_info.description == "Info test"
        assert tool_info.return_type == str

    def test_get_nonexistent_tool(self):
        """Test getting non-existent tool."""
        registry = ToolRegistry()

        assert registry.get("nonexistent") is None

    def test_get_by_type(self):
        """Test filtering tools by type."""
        registry = ToolRegistry()

        @registry.register("tool1", tool_type=ToolType.SEARCH)
        def search1():
            pass

        @registry.register("tool2", tool_type=ToolType.ANALYSIS)
        def analysis1():
            pass

        @registry.register("tool3", tool_type=ToolType.SEARCH)
        def search2():
            pass

        search_tools = registry.get_by_type(ToolType.SEARCH)

        assert len(search_tools) == 2
        tool_names = [t.name for t in search_tools]
        assert "tool1" in tool_names
        assert "tool3" in tool_names
        assert "tool2" not in tool_names

    def test_list_enabled(self):
        """Test listing enabled tools."""
        registry = ToolRegistry()

        @registry.register("enabled1", enabled=True)
        def func1():
            pass

        @registry.register("enabled2", enabled=True)
        def func2():
            pass

        @registry.register("disabled1", enabled=False)
        def func3():
            pass

        enabled = registry.list_enabled()

        assert len(enabled) == 2
        names = [t.name for t in enabled]
        assert "enabled1" in names
        assert "enabled2" in names
        assert "disabled1" not in names

    def test_list_all(self):
        """Test listing all tools."""
        registry = ToolRegistry()

        @registry.register("tool1", enabled=True)
        def func1():
            pass

        @registry.register("tool2", enabled=False)
        def func2():
            pass

        all_tools = registry.list_all()

        assert len(all_tools) == 2

    def test_get_summary(self):
        """Test getting registry summary."""
        registry = ToolRegistry()

        @registry.register("search1", tool_type=ToolType.SEARCH)
        def s1():
            pass

        @registry.register("search2", tool_type=ToolType.SEARCH)
        def s2():
            pass

        @registry.register("analysis1", tool_type=ToolType.ANALYSIS)
        def a1():
            pass

        summary = registry.get_summary()

        assert summary["total_tools"] == 3
        assert summary["enabled_tools"] == 3
        assert summary["by_type"]["search"] == 2
        assert summary["by_type"]["analysis"] == 1

    def test_clear_registry(self):
        """Test clearing all tools."""
        registry = ToolRegistry()

        @registry.register("tool1")
        def func1():
            pass

        @registry.register("tool2")
        def func2():
            pass

        registry.clear()

        assert registry.tools == {}
        assert registry._registry == {}

    def test_callback_on_register(self):
        """Test callback for tool registration."""
        registry = ToolRegistry()

        callback_log = []

        def on_register(name: str, info: ToolInfo):
            callback_log.append((name, info))

        registry.register_callback(on_register)

        @registry.register("callback_tool")
        def callback_func():
            pass

        assert len(callback_log) == 1
        assert callback_log[0][0] == "callback_tool"
        assert callback_log[0][1].name == "callback_tool"

    def test_unregister_callback(self):
        """Test removing a callback."""
        registry = ToolRegistry()

        def callback(name: str, info: ToolInfo):
            pass

        registry.register_callback(callback)
        registry.unregister_callback(callback)

        # Should not raise
        @registry.register("test")
        def test_func():
            pass


class TestToolType:
    """Tests for ToolType enum."""

    def test_all_tool_types_exist(self):
        """Test that all expected tool types are defined."""
        tool_types = [t for t in ToolType]
        type_names = [t.value for t in tool_types]

        assert "search" in type_names
        assert "analysis" in type_names
        assert "extraction" in type_names
        assert "conversion" in type_names
        assert "validation" in type_names
        assert "agent" in type_names
        assert "utility" in type_names


class TestBaseTool:
    """Tests for BaseTool abstract class."""

    def test_cannot_instantiate_abstract(self):
        """Test that BaseTool cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseTool()

    def test_concrete_implementation(self):
        """Test concrete implementation of BaseTool."""

        class ConcreteTool(BaseTool):
            name = "concrete"
            description = "Concrete tool"
            tool_type = ToolType.ANALYSIS

            def execute(self, **kwargs):
                return "executed"

        tool = ConcreteTool()

        assert tool.name == "concrete"
        assert tool.description == "Concrete tool"
        assert tool.tool_type == ToolType.ANALYSIS

        result = tool.execute(value=42)
        assert result == "executed"

    def test_tool_info_from_class(self):
        """Test getting tool info from BaseTool subclass."""

        class InfoTool(BaseTool):
            name = "info"
            description = "Info tool"
            tool_type = ToolType.EXTRACTION

            def execute(self, value: int) -> str:
                return str(value)

        tool = InfoTool()
        info = tool.get_info()

        assert info.name == "info"
        assert info.description == "Info tool"
        assert info.tool_type == ToolType.EXTRACTION


class TestRegisterDecorator:
    """Tests for module-level register decorator."""

    def test_module_decorator(self):
        """Test that module-level register works."""
        from pyeuropepmc.agentic.registry import registry

        @register("module_tool", tool_type=ToolType.UTILITY)
        def module_tool_func(x: int) -> int:
            return x * 2

        assert "module_tool" in registry.tools
