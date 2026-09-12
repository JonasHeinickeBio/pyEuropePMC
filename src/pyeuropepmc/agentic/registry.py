"""
Tool registry for extensible tool registration.

This module provides:
- ToolRegistry class for registering and managing tools
- Tool decorator for easy registration
- Tool discovery and documentation
- Type-safe tool invocation
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
import contextlib
from dataclasses import dataclass
from enum import Enum
import functools
import inspect
import logging
from typing import Any, get_type_hints

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Types of tools that can be registered."""

    SEARCH = "search"
    ANALYSIS = "analysis"
    EXTRACTION = "extraction"
    CONVERSION = "conversion"
    VALIDATION = "validation"
    AGENT = "agent"
    UTILITY = "utility"


@dataclass
class ToolInfo:
    """Information about a registered tool."""

    name: str
    description: str
    func: Callable
    tool_type: ToolType
    parameters: dict[str, type]
    return_type: type
    signature: inspect.Signature
    enabled: bool = True


class BaseTool(ABC):
    """Abstract base class for tools."""

    name: str = ""
    description: str = ""
    tool_type: ToolType = ToolType.UTILITY

    def __init__(self, **kwargs):
        """Initialize tool."""
        self.enabled = True

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the tool."""
        pass

    def get_info(self) -> ToolInfo:
        """Get tool information."""
        return ToolInfo(
            name=self.name,
            description=self.description,
            func=self.execute,
            tool_type=self.tool_type,
            parameters={},
            return_type=Any,
            signature=inspect.signature(self.execute),
        )


class ToolRegistry:
    """
    Registry for managing research tools and utilities.

    Inspired by AgentLaboratory, this registry:
    - Registers tools with metadata
    - Provides type-safe tool invocation
    - Enables tool discovery and documentation
    - Supports tool enable/disable toggling

    Attributes
    ----------
    tools : dict
        Registered tools by name
    tool_types : dict
        Tools grouped by type
    """

    def __init__(self, name: str = ""):
        """Initialize the tool registry."""
        self.name = name
        self.tools: dict[str, ToolInfo] = {}
        self._registry: dict[str, BaseTool] = {}
        self._enabled_states: dict[str, dict[str, bool]] = {}  # For decorator tools
        self._callbacks: list[Callable[[str, ToolInfo], None]] = []

    def register(
        self,
        name: str,
        description: str = "",
        tool_type: ToolType = ToolType.UTILITY,
        enabled: bool = True,
    ) -> Callable[[Callable], Callable]:
        """Decorator to register a tool.

        Parameters
        ----------
        name : str
            Unique name for the tool
        description : str, optional
            Description of what the tool does
        tool_type : ToolType, optional
            Type of tool
        enabled : bool, optional
            Whether tool is enabled (default: True)

        Returns
        -------
        callable
            Decorator function
        """
        # Use a mutable dict for the enabled state
        enabled_state = {"enabled": enabled}

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not enabled_state["enabled"]:
                    raise RuntimeError(f"Tool '{name}' is disabled")
                return func(*args, **kwargs)

            # Get type hints
            try:
                type_hints = get_type_hints(func)
                parameters = {
                    name: typ
                    for name, typ in type_hints.items()
                    if name not in ["return", "self", "cls"]
                }
                return_type = type_hints.get("return", Any)
            except Exception:
                parameters = {}
                return_type = Any

            # Get signature
            signature = inspect.signature(func)
            docstring = description or func.__doc__ or ""

            tool_info = ToolInfo(
                name=name,
                description=docstring,
                func=wrapper,
                tool_type=tool_type,
                parameters=parameters,
                return_type=return_type,
                signature=signature,
                enabled=enabled_state["enabled"],
            )

            self.tools[name] = tool_info

            # Store the enabled state for enable/disable to update
            self._enabled_states[name] = enabled_state

            # Invoke callbacks after tool is registered
            for callback in self._callbacks:
                # Don't fail if a callback errors
                with contextlib.suppress(Exception):
                    callback(name, tool_info)

            logger.info(f"Registered tool '{name}' (type: {tool_type.value})")

            return wrapper

        return decorator

    def register_class(self, tool_class: type[BaseTool]) -> None:
        """
        Register a tool class.

        Parameters
        ----------
        tool_class : type
            Class inheriting from BaseTool
        """
        tool_instance = tool_class()
        tool_info = tool_instance.get_info()

        self.tools[tool_instance.name] = tool_info
        self._registry[tool_instance.name] = tool_instance

        logger.info(f"Registered tool class '{tool_instance.name}'")

    def get(self, name: str) -> ToolInfo | None:
        """
        Get tool information by name.

        Parameters
        ----------
        name : str
            Tool name

        Returns
        -------
        ToolInfo or None
            Tool information or None if not found
        """
        return self.tools.get(name)

    def get_tool(self, name: str) -> BaseTool | None:
        """
        Get tool instance by name.

        Parameters
        ----------
        name : str
            Tool name

        Returns
        -------
        BaseTool or None
            Tool instance or None if not found
        """
        return self._registry.get(name)

    def execute(self, name: str, **kwargs) -> Any:
        """
        Execute a registered tool.

        Parameters
        ----------
        name : str
            Tool name
        **kwargs
            Tool arguments

        Returns
        -------
        Any
            Tool result
        """
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found")

        tool_info = self.tools[name]

        if not tool_info.enabled:
            raise RuntimeError(f"Tool '{name}' is disabled")

        return tool_info.func(**kwargs)

    def enable(self, name: str) -> bool:
        """
        Enable a tool.

        Parameters
        ----------
        name : str
            Tool name

        Returns
        -------
        bool
            True if successful
        """
        if name not in self.tools:
            return False

        self.tools[name].enabled = True

        # Update closure state for decorator-registered tools
        if name in self._enabled_states:
            self._enabled_states[name]["enabled"] = True

        if name in self._registry:
            self._registry[name].enabled = True

        logger.info(f"Enabled tool '{name}'")
        return True

    def disable(self, name: str) -> bool:
        """
        Disable a tool.

        Parameters
        ----------
        name : str
            Tool name

        Returns
        -------
        bool
            True if successful
        """
        if name not in self.tools:
            return False

        self.tools[name].enabled = False

        # Update closure state for decorator-registered tools
        if name in self._enabled_states:
            self._enabled_states[name]["enabled"] = False

        if name in self._registry:
            self._registry[name].enabled = False

        logger.info(f"Disabled tool '{name}'")
        return True

    def get_by_type(self, tool_type: ToolType) -> list[ToolInfo]:
        """
        Get all tools of a specific type.

        Parameters
        ----------
        tool_type : ToolType
            Tool type to filter by

        Returns
        -------
        list
            List of tool information
        """
        return [info for info in self.tools.values() if info.tool_type == tool_type]

    def list_enabled(self) -> list[ToolInfo]:
        """Get all enabled tools."""
        return [info for info in self.tools.values() if info.enabled]

    def list_all(self) -> list[ToolInfo]:
        """Get all registered tools."""
        return list(self.tools.values())

    def get_summary(self) -> dict[str, Any]:
        """
        Get registry summary.

        Returns
        -------
        dict
            Registry statistics
        """
        return {
            "total_tools": len(self.tools),
            "enabled_tools": len([t for t in self.tools.values() if t.enabled]),
            "by_type": {
                tool_type.value: len(self.get_by_type(tool_type)) for tool_type in ToolType
            },
        }

    def register_callback(
        self,
        callback: Callable[[str, ToolInfo], None],
    ) -> None:
        """
        Register a callback for tool registration.

        Parameters
        ----------
        callback : callable
            Function called when a tool is registered
            Signature: callback(name: str, tool_info: ToolInfo)
        """
        self._callbacks.append(callback)

    def unregister_callback(
        self,
        callback: Callable[[str, ToolInfo], None],
    ) -> None:
        """Remove a registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def clear(self) -> None:
        """Clear all registered tools."""
        self.tools.clear()
        self._registry.clear()
        logger.info("Cleared all tools from registry")


# Convenience decorator for module-level tool registration
registry = ToolRegistry()
register = registry.register
