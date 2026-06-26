"""
MCP Server for Europe PMC API using pyeuropepmc client.

This server uses the pyeuropepmc.SearchClient class to interact with the Europe PMC API,
avoiding code duplication and leveraging all the existing functionality including
caching, rate limiting, error handling, and pagination.

Usage as MCP server:
    pyeuropepmc-mcp

Usage within pyeuropepmc package:
    from pyeuropepmc.mcp.server import main
    import asyncio
    asyncio.run(main())

Available tools:
    - search_papers: Search for papers in Europe PMC
    - get_paper_details: Get detailed information about a paper (by PMID, PMCID, or DOI)
    - search_authors: Search for authors in Europe PMC
    - get_paper_citations: Get citations for a paper
"""

import asyncio
import json
import sys
from typing import Any

from pyeuropepmc import SearchClient
from pyeuropepmc.cache.cache import CacheConfig


def _get_client() -> SearchClient:
    """Get a configured SearchClient instance for MCP operations."""
    # Use caching with default config for better performance
    cache_config = CacheConfig(enabled=True)
    return SearchClient(cache_config=cache_config)


def parse_mcp_request(line: str) -> dict[str, Any]:
    """Parse MCP request from stdin"""
    return json.loads(line.strip())  # type: ignore[no-any-return]


def create_response(
    request_id: int,
    result: Any = None,
    error: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create MCP response.

    Parameters
    ----------
    request_id : int
        Request ID from the JSON-RPC request.
    result : Any, optional
        Successful result payload.
    error : str or dict, optional
        Error message or a pre-built error dict with ``code`` and ``message``.
    """
    response: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
    }

    if error:
        if isinstance(error, dict):
            response["error"] = error
        else:
            response["error"] = {
                "code": -32603,
                "message": error,
            }
    else:
        response["result"] = result

    return response


def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    """Handle initialize request"""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {},
        },
        "serverInfo": {
            "name": "pyeuropepmc-mcp",
            "version": "1.0.0",
        },
    }


def handle_list_tools(params: dict[str, Any]) -> dict[str, Any]:
    """Handle listTools request"""
    return {
        "tools": [
            {
                "name": "search_papers",
                "description": "Search for papers in Europe PMC",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {
                            "type": "integer",
                            "description": "Number of results (default: 25)",
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort order (cited, date)",
                        },
                        "result_type": {
                            "type": "string",
                            "description": "Result type (default: core)",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_paper_details",
                "description": "Get detailed information about a paper (requires at least one ID)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pmid": {"type": "string", "description": "PubMed ID"},
                        "pmcid": {"type": "string", "description": "PMCID"},
                        "doi": {"type": "string", "description": "DOI"},
                    },
                    "anyOf": [
                        {"required": ["pmid"]},
                        {"required": ["pmcid"]},
                        {"required": ["doi"]},
                    ],
                },
            },
            {
                "name": "search_authors",
                "description": "Search for authors in Europe PMC",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Author name or affiliation"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_paper_citations",
                "description": "Get citations for a paper",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pmid": {"type": "string", "description": "PubMed ID"},
                        "source": {
                            "type": "string",
                            "description": "Source identifier (MED, PMC, etc.)",
                            "default": "MED",
                        },
                    },
                    "required": ["pmid"],
                },
            },
        ],
    }


def handle_call_tool(params: dict[str, Any]) -> dict[str, Any]:
    """Handle callTool request"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    try:
        client = _get_client()

        if tool_name == "search_papers":
            # Map MCP arguments to SearchClient search() parameters
            query = arguments.get("query", "")
            limit = arguments.get("limit", 25)  # Use 25 as default (minimum for SearchClient)
            sort = arguments.get("sort", "")
            result_type = arguments.get("result_type", "core")

            # Use search_all for MCP to get specified limit of results
            kwargs = {
                "pageSize": limit,
                "resultType": result_type,
            }
            if sort:
                kwargs["sort"] = sort

            results = client.search_all(query, **kwargs)
            return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}

        elif tool_name == "get_paper_details":
            pmid = arguments.get("pmid")
            pmcid = arguments.get("pmcid")
            doi = arguments.get("doi")

            # Build query from provided ID
            if pmid:
                query = f"ext_id:{pmid}"
            elif pmcid:
                query = f"ext_id:{pmcid}"
            elif doi:
                query = f"doi:{doi}"
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: At least one ID (pmid, pmcid, or doi) is required",
                        }
                    ]
                }

            # Search by ID - should return single result
            results = client.search_all(query, pageSize=1)
            if results:
                return {"content": [{"type": "text", "text": json.dumps(results[0], indent=2)}]}
            return {"content": [{"type": "text", "text": "No results found"}]}

        elif tool_name == "search_authors":
            # Europe PMC doesn't have a dedicated authors endpoint
            # Use author field search: AUTH:"query"
            query = f'AUTH:"{arguments.get("query", "")}"'
            results = client.search_all(query, pageSize=arguments.get("limit", 25))
            return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}

        elif tool_name == "get_paper_citations":
            pmid = arguments.get("pmid", "")

            # Use the CITED field to find papers citing the given PMID
            query = f"CITED:{pmid}"
            results = client.search_all(query, pageSize=arguments.get("limit", 100))
            return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}

        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}]}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


def _main_entry() -> None:
    """Entry point for console script - properly runs async main"""
    asyncio.run(main())


async def main() -> None:
    """Main entry point - reads from stdin, writes to stdout"""
    # Server logging goes to stderr to avoid interfering with JSON protocol
    print("pyeuropepmc-mcp server starting...", file=sys.stderr)
    sys.stderr.flush()

    while True:
        try:
            # Read line from stdin
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

            if not line:
                break

            line = line.strip()
            if not line:
                continue

            # Parse request
            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}", file=sys.stderr)
                sys.stderr.flush()
                continue

            # Handle request
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            # Skip response for notifications (no request_id per JSON-RPC 2.0)
            is_notification = request_id is None

            if method == "initialize":
                response_json = json.dumps(
                    create_response(request_id, result=handle_initialize(params))
                )
            elif method == "tools/list":
                response_json = json.dumps(
                    create_response(request_id, result=handle_list_tools(params))
                )
            elif method == "tools/call":
                response_json = json.dumps(
                    create_response(request_id, result=handle_call_tool(params))
                )
            else:
                response_json = json.dumps(
                    create_response(
                        request_id,
                        error={
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                    )
                )

            if not is_notification:
                print(response_json, flush=True)

        except Exception as e:
            # Send JSON-RPC error response for exceptions if we have a request_id
            import traceback

            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            if request_id is not None:
                error_response = json.dumps(
                    create_response(
                        request_id,
                        error={"code": -32603, "message": f"Internal error: {e}"},
                    )
                )
                print(error_response, flush=True)


if __name__ == "__main__":
    _main_entry()
