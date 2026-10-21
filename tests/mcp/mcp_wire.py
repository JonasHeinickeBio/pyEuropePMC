"""Version-neutral reads of MCP SDK objects, for tests that run under mcp 1.x and 2.x.

SDK 2.x renamed the Python attributes of its protocol types to snake_case
(``input_schema``, ``read_only_hint``, ``structured_content``, ``is_error``) while the wire
format stays camelCase. ``model_dump(by_alias=True)`` gives the wire shape in both
generations, so tests assert on that.
"""

from __future__ import annotations

from typing import Any


def wire(obj: Any) -> dict[str, Any]:
    """The camelCase JSON shape of a protocol object (a Tool, ToolAnnotations, CallToolResult)."""
    return obj.model_dump(by_alias=True, mode="json")  # type: ignore[no-any-return]


def schema_of(tool: Any) -> dict[str, Any]:
    return wire(tool)["inputSchema"]  # type: ignore[no-any-return]


def hint(annotations: Any, name: str) -> Any:
    """One annotation hint by its wire name (``readOnlyHint``); ``None`` when unset."""
    return wire(annotations).get(name)


def structured(result: Any) -> Any:
    """``structuredContent`` of a tool result."""
    return wire(result).get("structuredContent")


def is_error(result: Any) -> bool:
    """``isError`` of a tool result."""
    return bool(wire(result).get("isError"))
