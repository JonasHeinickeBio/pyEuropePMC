# pyeuropepmc MCP Module

This module provides Model Context Protocol (MCP) integration for the pyeuropepmc package, allowing you to use Europe PMC API tools in MCP-compatible clients.

## Overview

The Model Context Protocol (MCP) enables AI applications to discover and use tools, resources, and prompts from external services. This MCP server exposes Europe PMC API functionality as tools that can be invoked by LLMs and AI assistants.

### Architecture

```
┌─────────────────┐     MCP Protocol      ┌──────────────────┐
│   AI Host       │◄─── JSON-RPC 2.0 ────►│  pyeuropepmc MCP │
│ (Claude, etc.)  │    STDIO Transport    │     Server       │
└─────────────────┘                        └──────────────────┘
                                                      │
                                                      ▼
                                              ┌──────────────┐
                                              │ Europe PMC API │
                                              └──────────────┘
```

## Installation

The MCP server is included as part of the pyeuropepmc package:

```bash
pip install pyeuropepmc
```

## Usage

### As an MCP Server

Run the MCP server:

```bash
pyeuropepmc-mcp
```

Or using Python directly:

```bash
python -m pyeuropepmc.mcp.server
```

### Available Tools

The server exposes the following tools:

| Tool Name | Description | Input Parameters |
|-----------|-------------|------------------|
| `search_papers` | Search for papers in Europe PMC | `query` (string, required), `limit` (integer, optional, default: 25), `sort` (string, optional), `result_type` (string, optional) |
| `get_paper_details` | Get detailed information about a paper by PMID, PMCID, or DOI | `pmid` (string, optional), `pmcid` (string, optional), `doi` (string, optional) |
| `search_authors` | Search for authors in Europe PMC | `query` (string, required) |
| `get_paper_citations` | Get citations for a paper | `pmid` (string, required), `limit` (integer, optional, default: 100) |

## Configuration

### Claude Desktop / MCP Client Configuration

Configure in your MCP client configuration file:

```json
{
  "mcpServers": {
    "pyeuropepmc": {
      "command": "pyeuropepmc-mcp",
      "enabled": true
    }
  }
}
```

### Programmatic Usage

```python
from pyeuropepmc.mcp.server import EuropePMCMCPServer

server = EuropePMCMCPServer()
# Run the server with your MCP client
```

## MCP Best Practices Implemented

### 1. Protocol Compliance

- **JSON-RPC 2.0**: Uses standard JSON-RPC 2.0 message format
- **Protocol Version**: Implements `2024-11-05` protocol version
- **Capability Negotiation**: Properly negotiates capabilities during initialization

### 2. Security Considerations

The server implements MCP security best practices:

- **Input Validation**: All tool inputs are validated before processing
- **Error Handling**: Proper error responses for both protocol and execution errors
- **Resource Protection**: Europe PMC API calls respect rate limits

### 3. Tool Design

- **Descriptive Names**: Tool names follow naming conventions (alphanumeric, underscore, hyphen, dot)
- **Clear Documentation**: Each tool includes detailed descriptions
- **JSON Schema**: Input schemas follow JSON Schema 2020-12 specification

### 4. Error Handling

The server distinguishes between:

- **Protocol Errors**: Issues with the request structure (e.g., unknown tool)
- **Tool Execution Errors**: Issues during tool execution (e.g., API failures)

### 5. Logging

For STDIO-based MCP servers, logging must not write to stdout (corrupts JSON-RPC messages). This server uses:

```python
# Correct pattern for STDIO servers
print("Message", file=sys.stderr)
```

## pyeuropepmc Integration

The MCP server uses the existing `pyeuropepmc.SearchClient` class, which provides:

- **Caching**: Built-in response caching to reduce API calls and improve performance
- **Rate limiting**: Automatic delay between requests to avoid hitting API limits
- **Pagination**: Proper cursor-based pagination for large result sets
- **Error handling**: Comprehensive error handling and validation
- **Robustness**: Battle-tested production code with extensive testing

### Tool Implementation Details

The MCP tools map to SearchClient methods as follows:

- **search_papers**: Uses `client.search_all()` with configurable page size
- **get_paper_details**: Uses `client.search_all()` with `ext_id:{id}` query
- **search_authors**: Uses `client.search_all()` with `AUTH:"query"` field search
- **get_paper_citations**: Uses `client.search_all()` with `CITED:{pmid}` query

This ensures the MCP server leverages all the production-ready features of pyeuropepmc.

## Response Format

All tool responses follow the MCP specification:

```json
{
  "jsonrpc": "2.0",
  "id": <request_id>,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "<json-encoded-result>"
      }
    ]
  }
}
```

## Error Responses

### Protocol Error (Unknown Tool)

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32602,
    "message": "Unknown tool: invalid_tool_name"
  }
}
```

### Tool Execution Error

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Invalid PMID format"
      }
    ],
    "isError": true
  }
}
```

## Development

### Running the Server

```bash
# Start the MCP server
python -m pyeuropepmc.mcp.server

# Or use the CLI
pyeuropepmc-mcp
```

### Testing

```bash
# Test the server with sample requests
python -c "
import asyncio
from pyeuropepmc.mcp.server import main
asyncio.run(main())
"
```

## Integration Examples

### With Claude Desktop

1. Locate your Claude Desktop config file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the pyeuropepmc server configuration:

```json
{
  "mcpServers": {
    "pyeuropepmc": {
      "command": "pyeuropepmc-mcp",
      "enabled": true
    }
  }
}
```

3. Restart Claude Desktop

### With Other MCP Clients

The server can be configured in any MCP-compatible client following the same pattern:

```json
{
  "mcp": {
    "pyeuropepmc": {
      "type": "local",
      "command": ["pyeuropepmc-mcp"],
      "enabled": true
    }
  }
}
```

## Best Practices for MCP Server Development

Based on MCP specification and implementation experience:

### 1. STDIO Transport

- **Never write to stdout** except for JSON-RPC messages
- Use `print(..., file=sys.stderr)` for logging
- Use logging libraries configured to write to stderr or files

### 2. Tool Naming

- Use snake_case or camelCase (consistent within project)
- Keep names between 1-128 characters
- Use only alphanumeric, underscore, hyphen, and dot characters
- Be specific and descriptive

### 3. Input Schemas

- Always use JSON Schema 2020-12 (or specify alternative dialect)
- Define required and optional parameters clearly
- Include descriptions for all properties
- Use appropriate types (string, integer, number, boolean, array, object)

### 4. Error Handling

- Distinguish between protocol errors and execution errors
- Provide actionable error messages for self-correction
- Validate inputs before processing

### 5. Capabilities

- Declare all supported capabilities during initialization
- Implement `listChanged` capability for dynamic tools
- Handle capability negotiation properly

### 6. Performance

- Implement timeouts for external API calls
- Handle rate limiting gracefully
- Consider pagination for large result sets

## See Also

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [MCP Documentation](https://modelcontextprotocol.io/)
- [pyeuropepmc Main Documentation](https://jonasheinickebio.github.io/pyEuropePMC/)
- [Europe PMC API Documentation](https://europepmc.org/docs/REST_API)

## License

Distributed under the MIT License. See [LICENSE](../../LICENSE) for more information.
