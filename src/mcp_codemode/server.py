"""
MCP server implementation for mcp-codemode.

This allows mcp-codemode to be used as an MCP server itself,
exposing tools that provide efficient access to other MCP servers.

Key tools:
- search_tools: Search across all MCP servers
- list_servers: List available servers
- list_tools: List tools on a server
- get_tool_schema: Get tool schema
- execute_code: Execute Python code that calls MCP tools (minimal context!)
- call_tool: Direct tool call
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

from .core import mcp
from .runtime import get_runtime
from .models import SearchResult

logger = logging.getLogger(__name__)


# Tool definitions
SEARCH_TOOLS_TOOL = Tool(
    name="search_tools",
    description="""
Search for tools across all configured MCP servers.

This uses lightweight text-based search to find relevant tools by name
or description. Returns ranked results with server, tool name, and relevance score.

Use this when you don't know which tool to use for a task.
""".strip(),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (keywords or natural language)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 10
            }
        },
        "required": ["query"]
    }
)

LIST_SERVERS_TOOL = Tool(
    name="list_servers",
    description="""
List all configured MCP servers.

Returns a list of server names that are available in the catalog.
Use this to discover what servers you have access to.
""".strip(),
    inputSchema={
        "type": "object",
        "properties": {
            "detailed": {
                "type": "boolean",
                "description": "Include detailed information about each server",
                "default": False
            }
        }
    }
)

LIST_TOOLS_TOOL = Tool(
    name="list_tools",
    description="""
List all tools available on a specific MCP server.

Returns tool names and optionally descriptions and parameters.
Use this after you've identified a relevant server.
""".strip(),
    inputSchema={
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "Name of the server"
            },
            "detailed": {
                "type": "boolean",
                "description": "Include descriptions and parameters",
                "default": False
            }
        },
        "required": ["server"]
    }
)

GET_TOOL_SCHEMA_TOOL = Tool(
    name="get_tool_schema",
    description="""
Get the JSON schema for a specific tool.

Returns the complete schema including description, input schema, and output schema.
Use this when you need to understand exactly what arguments a tool accepts.
""".strip(),
    inputSchema={
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "Name of the server"
            },
            "tool": {
                "type": "string",
                "description": "Name of the tool"
            }
        },
        "required": ["server", "tool"]
    }
)

EXECUTE_CODE_TOOL = Tool(
    name="execute_code",
    description="""
Execute Python code with access to MCP servers via the `mcp` object.

This is the most efficient way to use multiple tools in a single operation.
The code can call multiple tools, process data locally, and return only the
final results - dramatically reducing context overhead.

The `mcp` object is available in the execution context with access to all
configured servers:
- mcp.filesystem.read_file(path="...")
- mcp.github.create_issue(repo="...", title="...", body="...")
- mcp.slack.send_message(channel="...", text="...")

Example:
```python
# Multi-step operation with local processing
files = await mcp.filesystem.list_directory(path="/var/log")
large_files = [f for f in files if f['size'] > 1_000_000]

# Process locally - no context overhead
for file in large_files[:5]:
    content = await mcp.filesystem.read_file(path=file['path'])
    # Analyze...

# Return only final results
return {"count": len(large_files), "sample": large_files[:3]}
```

Context efficiency: 98-99% reduction vs traditional tool calling!
""".strip(),
    inputSchema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Use 'await' for async operations. Access MCP via the 'mcp' object."
            }
        },
        "required": ["code"]
    }
)

CALL_TOOL_TOOL = Tool(
    name="call_tool",
    description="""
Directly call a tool on an MCP server.

This provides direct access to any tool, but is less efficient than execute_code
for multi-step operations. Use execute_code when possible for better context efficiency.
""".strip(),
    inputSchema={
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "Name of the server"
            },
            "tool": {
                "type": "string",
                "description": "Name of the tool"
            },
            "arguments": {
                "type": "object",
                "description": "Tool arguments as a dictionary"
            }
        },
        "required": ["server", "tool", "arguments"]
    }
)


class MCPCodeModeServer:
    """MCP server for mcp-codemode."""

    def __init__(self):
        self.server = Server("mcp-codemode")
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up request handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                SEARCH_TOOLS_TOOL,
                LIST_SERVERS_TOOL,
                LIST_TOOLS_TOOL,
                GET_TOOL_SCHEMA_TOOL,
                EXECUTE_CODE_TOOL,
                CALL_TOOL_TOOL,
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "search_tools":
                    result = await self._search_tools(arguments)
                elif name == "list_servers":
                    result = await self._list_servers(arguments)
                elif name == "list_tools":
                    result = await self._list_tools(arguments)
                elif name == "get_tool_schema":
                    result = await self._get_tool_schema(arguments)
                elif name == "execute_code":
                    result = await self._execute_code(arguments)
                elif name == "call_tool":
                    result = await self._call_tool(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")

                # Return as TextContent
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except Exception as e:
                logger.error(f"Error in tool {name}: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e),
                        "type": type(e).__name__
                    }, indent=2)
                )]

    async def _search_tools(self, args: dict) -> dict:
        """Search for tools across all servers."""
        query = args["query"]
        limit = args.get("limit", 10)

        results = await mcp.search(query, limit=limit)

        return {
            "query": query,
            "results": [
                {
                    "server": r.server,
                    "tool": r.tool,
                    "description": r.description,
                    "score": r.score
                }
                for r in results
            ]
        }

    async def _list_servers(self, args: dict) -> dict:
        """List available servers."""
        detailed = args.get("detailed", False)
        servers = await mcp.list_servers(detailed=detailed)

        if detailed:
            return {
                "servers": [
                    {
                        "name": s.name,
                        "description": s.description,
                        "capabilities": s.capabilities
                    }
                    for s in servers
                ]
            }
        else:
            return {"servers": servers}

    async def _list_tools(self, args: dict) -> dict:
        """List tools on a server."""
        server_name = args["server"]
        detailed = args.get("detailed", False)

        server = getattr(mcp, server_name)
        tools = await server.list_tools(detailed=detailed)

        return {
            "server": server_name,
            "tools": tools
        }

    async def _get_tool_schema(self, args: dict) -> dict:
        """Get tool schema."""
        server_name = args["server"]
        tool_name = args["tool"]

        runtime = await get_runtime()
        schema = await runtime.get_tool_schema(server_name, tool_name)

        return schema

    async def _execute_code(self, args: dict) -> dict:
        """Execute Python code with MCP access."""
        code = args["code"]

        # Import necessary modules for execution context
        import asyncio
        from io import StringIO
        import sys

        # Capture stdout
        stdout_capture = StringIO()
        original_stdout = sys.stdout

        result = {
            "success": False,
            "stdout": "",
            "result": None,
            "error": None
        }

        try:
            # Redirect stdout
            sys.stdout = stdout_capture

            # Build execution namespace
            exec_globals = {
                "__builtins__": __builtins__,
                "mcp": mcp,
                "asyncio": asyncio,
            }

            # Compile and execute
            compiled = compile(code, "<execute_code>", "exec")
            exec_locals = {}
            exec(compiled, exec_globals, exec_locals)

            # Handle async execution
            # Look for 'main' function or last defined coroutine
            if "main" in exec_locals and asyncio.iscoroutinefunction(exec_locals["main"]):
                return_value = await exec_locals["main"]()
            elif exec_locals:
                # Check if last value is a coroutine
                last_value = list(exec_locals.values())[-1]
                if asyncio.iscoroutine(last_value):
                    return_value = await last_value
                else:
                    return_value = exec_locals.get("result")
            else:
                return_value = None

            result["success"] = True
            result["result"] = return_value
            result["stdout"] = stdout_capture.getvalue()

        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}"
            result["stdout"] = stdout_capture.getvalue()

        finally:
            # Restore stdout
            sys.stdout = original_stdout

        return result

    async def _call_tool(self, args: dict) -> Any:
        """Direct tool call."""
        server_name = args["server"]
        tool_name = args["tool"]
        tool_args = args["arguments"]

        runtime = await get_runtime()
        result = await runtime.call_tool(server_name, tool_name, tool_args)

        return {
            "server": server_name,
            "tool": tool_name,
            "result": result
        }

    async def run(self):
        """Run the server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for the MCP server."""
    server = MCPCodeModeServer()
    await server.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
