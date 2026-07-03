"""
Unit tests for MCP server.

These tests verify the MCP server functionality without requiring
an actual MCP client connection.
"""

import json
from unittest.mock import Mock, patch

import pytest

from pyeuropepmc.mcp.server import (
    _get_client,
    create_response,
    handle_call_tool,
    handle_initialize,
    handle_list_tools,
    parse_mcp_request,
)


class TestGetClient:
    """Test _get_client function."""

    def test_get_client_returns_search_client(self):
        """Test that _get_client returns a SearchClient instance."""
        client = _get_client()
        assert client is not None
        # Check that it's a SearchClient by verifying it has the expected method
        assert hasattr(client, "search_all")

    def test_get_client_has_caching_enabled(self):
        """Test that the client has caching enabled."""
        client = _get_client()
        # The client should be initialized with caching
        assert client._cache is not None


class TestParseMCPRequest:
    """Test parse_mcp_request function."""

    def test_parse_valid_json(self):
        """Test parsing a valid JSON request."""
        line = json.dumps({"id": 1, "method": "initialize", "params": {}})
        request = parse_mcp_request(line)
        assert request["id"] == 1
        assert request["method"] == "initialize"

    def test_parse_json_with_whitespace(self):
        """Test parsing JSON with leading/trailing whitespace."""
        line = "  " + json.dumps({"id": 1}) + "  "
        request = parse_mcp_request(line)
        assert request["id"] == 1

    def test_parse_invalid_json_raises_error(self):
        """Test that invalid JSON raises an error."""
        with pytest.raises(json.JSONDecodeError):
            parse_mcp_request("not valid json")


class TestCreateResponse:
    """Test create_response function."""

    def test_create_success_response(self):
        """Test creating a success response."""
        response = create_response(request_id=1, result={"data": "test"})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] == {"data": "test"}
        assert "error" not in response

    def test_create_error_response(self):
        """Test creating an error response."""
        response = create_response(request_id=1, error="Test error")
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["error"] is not None
        assert "code" in response["error"]
        assert "message" in response["error"]


class TestHandleInitialize:
    """Test handle_initialize function."""

    def test_initialize_returns_correct_protocol(self):
        """Test that initialize returns the correct protocol version."""
        result = handle_initialize({})
        assert result["protocolVersion"] == "2024-11-05"

    def test_initialize_returns_server_info(self):
        """Test that initialize returns server info."""
        result = handle_initialize({})
        assert "serverInfo" in result
        assert "name" in result["serverInfo"]
        assert "version" in result["serverInfo"]
        assert result["serverInfo"]["name"] == "pyeuropepmc-mcp"

    def test_initialize_returns_capabilities(self):
        """Test that initialize returns capabilities."""
        result = handle_initialize({})
        assert "capabilities" in result
        assert "tools" in result["capabilities"]


class TestHandleListTools:
    """Test handle_list_tools function."""

    def test_list_tools_returns_all_tools(self):
        """Test that all expected tools are listed."""
        result = handle_list_tools({})
        tools = result["tools"]

        tool_names = [t["name"] for t in tools]
        assert "search_papers" in tool_names
        assert "get_paper_details" in tool_names
        assert "search_authors" in tool_names
        assert "get_paper_citations" in tool_names

    def test_search_papers_tool_schema(self):
        """Test search_papers tool input schema."""
        result = handle_list_tools({})
        tools = result["tools"]
        search_papers = next(t for t in tools if t["name"] == "search_papers")

        assert "inputSchema" in search_papers
        schema = search_papers["inputSchema"]

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert "query" in schema["properties"]
        assert "query" in schema["required"]

    def test_get_paper_details_tool_schema(self):
        """Test get_paper_details tool input schema."""
        result = handle_list_tools({})
        tools = result["tools"]
        get_paper_details = next(t for t in tools if t["name"] == "get_paper_details")

        schema = get_paper_details["inputSchema"]
        assert "properties" in schema
        props = schema["properties"]
        # In JSON Schema, optional means not in "required"
        assert "required" not in schema or "pmid" not in schema.get("required", [])
        assert "required" not in schema or "pmcid" not in schema.get("required", [])
        assert "required" not in schema or "doi" not in schema.get("required", [])
        # At least one ID must be provided via anyOf
        assert "anyOf" in schema


class TestHandleCallTool:
    """Test handle_call_tool function."""

    @patch("pyeuropepmc.mcp.server.SearchClient")
    def test_search_papers_success(self, mock_search_client_class):
        """Test successful search_papers tool call."""
        # Setup mock
        mock_client = Mock()
        mock_search_client_class.return_value = mock_client
        mock_client.search_all.return_value = [
            {"id": "PMC123", "title": "Test Paper"}
        ]

        # Call tool
        result = handle_call_tool({
            "name": "search_papers",
            "arguments": {
                "query": "malaria",
                "limit": 10,
            }
        })

        # Verify
        assert "content" in result
        mock_client.search_all.assert_called_once()
        call_args = mock_client.search_all.call_args
        assert call_args[0][0] == "malaria"

    @patch("pyeuropepmc.mcp.server.SearchClient")
    def test_get_paper_details_by_pmid(self, mock_search_client_class):
        """Test get_paper_details with PMID."""
        mock_client = Mock()
        mock_search_client_class.return_value = mock_client
        mock_client.search_all.return_value = [{"id": "PMC123", "pmid": "12345"}]

        result = handle_call_tool({
            "name": "get_paper_details",
            "arguments": {"pmid": "12345"}
        })

        assert "content" in result
        call_args = mock_client.search_all.call_args
        assert call_args[0][0] == "ext_id:12345"

    @patch("pyeuropepmc.mcp.server.SearchClient")
    def test_search_authors_success(self, mock_search_client_class):
        """Test successful search_authors tool call."""
        mock_client = Mock()
        mock_search_client_class.return_value = mock_client
        mock_client.search_all.return_value = [
            {"id": "AUTH1", "authorName": "John Doe"}
        ]

        result = handle_call_tool({
            "name": "search_authors",
            "arguments": {"query": "John Doe"}
        })

        assert "content" in result
        call_args = mock_client.search_all.call_args
        query = call_args[0][0]
        assert 'AUTH:"John Doe"' in query

    @patch("pyeuropepmc.mcp.server.SearchClient")
    def test_get_paper_citations_success(self, mock_search_client_class):
        """Test successful get_paper_citations tool call."""
        mock_client = Mock()
        mock_search_client_class.return_value = mock_client
        mock_client.search_all.return_value = [
            {"id": "PMC123", "title": "Citing Paper"}
        ]

        result = handle_call_tool({
            "name": "get_paper_citations",
            "arguments": {"pmid": "12345"}
        })

        assert "content" in result
        call_args = mock_client.search_all.call_args
        query = call_args[0][0]
        assert "CITED:12345" in query

    def test_get_paper_details_missing_id(self):
        """Test get_paper_details without any ID."""
        result = handle_call_tool({
            "name": "get_paper_details",
            "arguments": {}
        })

        assert "content" in result
        text_content = result["content"][0]["text"]
        assert "Error" in text_content

    @patch("pyeuropepmc.mcp.server.SearchClient")
    def test_unknown_tool(self, mock_search_client_class):
        """Test calling an unknown tool."""
        result = handle_call_tool({
            "name": "unknown_tool",
            "arguments": {}
        })

        assert "content" in result
        text_content = result["content"][0]["text"]
        assert "Unknown tool" in text_content

    @patch("pyeuropepmc.mcp.server.SearchClient")
    def test_tool_exception_handling(self, mock_search_client_class):
        """Test that tool exceptions are handled gracefully."""
        mock_client = Mock()
        mock_search_client_class.return_value = mock_client
        mock_client.search_all.side_effect = Exception("API Error")

        result = handle_call_tool({
            "name": "search_papers",
            "arguments": {"query": "test"}
        })

        assert "content" in result
        text_content = result["content"][0]["text"]
        assert "Error" in text_content
