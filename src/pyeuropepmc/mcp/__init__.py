"""
MCP server for pyeuropepmc.

Exposes Europe PMC (and related literature-search) functionality as tools over
the Model Context Protocol, built on the official MCP Python SDK. See
:mod:`pyeuropepmc.mcp.server` for the ``FastMCP`` app, tool implementations,
and the ``pyeuropepmc-mcp`` CLI entry point.

Deliberately empty of imports: ``pyeuropepmc.mcp.server`` pulls in the
``mcp`` SDK plus every optional feature module it can find, so importing it
eagerly here would run that cost (and, when the server is launched via
``python -m pyeuropepmc.mcp.server``, trip Python's "module already imported"
warning) just for importing this lightweight package.
"""
