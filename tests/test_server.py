"""
Tests for MCP server functionality.
"""

import pytest
import json
from mcp_codemode.server import MCPCodeModeServer, EXECUTE_CODE_TOOL, SEARCH_TOOLS_TOOL


def test_server_initialization():
    """Test server can be initialized."""
    server = MCPCodeModeServer()
    assert server.server.name == "mcp-codemode"


def test_tool_definitions():
    """Test tool definitions are valid."""
    # Check execute_code tool
    assert EXECUTE_CODE_TOOL.name == "execute_code"
    assert "code" in EXECUTE_CODE_TOOL.inputSchema["properties"]
    assert "mcp" in EXECUTE_CODE_TOOL.description

    # Check search_tools tool
    assert SEARCH_TOOLS_TOOL.name == "search_tools"
    assert "query" in SEARCH_TOOLS_TOOL.inputSchema["properties"]


@pytest.mark.asyncio
async def test_search_tools():
    """Test search_tools handler."""
    server = MCPCodeModeServer()

    # This will work even without real servers configured
    # as it uses the global mcp instance
    result = await server._search_tools({"query": "test", "limit": 5})

    assert "query" in result
    assert "results" in result
    assert result["query"] == "test"
    assert isinstance(result["results"], list)


@pytest.mark.asyncio
async def test_list_servers():
    """Test list_servers handler."""
    server = MCPCodeModeServer()

    result = await server._list_servers({"detailed": False})

    assert "servers" in result
    assert isinstance(result["servers"], list)


@pytest.mark.asyncio
async def test_execute_code_simple():
    """Test execute_code with simple Python."""
    server = MCPCodeModeServer()

    code = """
x = 1 + 1
result = x
"""

    result = await server._execute_code({"code": code})

    assert result["success"] is True
    assert result["result"] == 2
    assert result["error"] is None


@pytest.mark.asyncio
async def test_execute_code_async():
    """Test execute_code with async code."""
    server = MCPCodeModeServer()

    code = """
import asyncio

async def main():
    await asyncio.sleep(0.001)
    return "async result"
"""

    result = await server._execute_code({"code": code})

    assert result["success"] is True
    assert result["result"] == "async result"


@pytest.mark.asyncio
async def test_execute_code_error():
    """Test execute_code error handling."""
    server = MCPCodeModeServer()

    code = """
raise ValueError("Test error")
"""

    result = await server._execute_code({"code": code})

    assert result["success"] is False
    assert result["error"] is not None
    assert "ValueError" in result["error"]


@pytest.mark.asyncio
async def test_execute_code_stdout():
    """Test execute_code captures stdout."""
    server = MCPCodeModeServer()

    code = """
print("Hello from code")
result = "done"
"""

    result = await server._execute_code({"code": code})

    assert result["success"] is True
    assert "Hello from code" in result["stdout"]


@pytest.mark.asyncio
async def test_execute_code_with_mcp_object():
    """Test execute_code has access to mcp object."""
    server = MCPCodeModeServer()

    code = """
# The mcp object should be available
result = type(mcp).__name__
"""

    result = await server._execute_code({"code": code})

    assert result["success"] is True
    assert result["result"] == "MCPCodeMode"
