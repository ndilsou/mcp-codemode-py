"""
MCP runtime for communicating with MCP servers.

Uses the official MCP SDK to connect to and interact with servers.
"""

import asyncio
import os
from typing import Any
from pathlib import Path
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

from .models import ServerInfo, ToolInfo
from .config import load_config, Config, ServerConfig

logger = logging.getLogger(__name__)


class MCPServerConnection:
    """Manages a connection to a single MCP server."""

    def __init__(self, name: str, config: ServerConfig):
        self.name = name
        self.config = config
        self.session: ClientSession | None = None
        self._read_stream = None
        self._write_stream = None
        self._tools_cache: dict[str, Tool] = {}
        self._connected = False

    async def connect(self):
        """Connect to the MCP server."""
        if self._connected:
            return

        try:
            if self.config.transport == "stdio":
                await self._connect_stdio()
            elif self.config.transport == "sse":
                await self._connect_sse()
            else:
                raise ValueError(f"Unsupported transport: {self.config.transport}")

            self._connected = True
            logger.info(f"Connected to MCP server: {self.name}")

        except Exception as e:
            logger.error(f"Failed to connect to {self.name}: {e}")
            raise

    async def _connect_stdio(self):
        """Connect via stdio transport."""
        # Build server parameters
        env = os.environ.copy()
        env.update(self.config.env)

        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=env
        )

        # Connect
        read, write = await stdio_client(server_params)
        self._read_stream = read
        self._write_stream = write

        # Create session
        self.session = ClientSession(read, write)
        await self.session.initialize()

    async def _connect_sse(self):
        """Connect via SSE transport."""
        if not self.config.url:
            raise ValueError(f"SSE transport requires 'url' in config for {self.name}")

        # Connect
        async with sse_client(self.config.url) as (read, write):
            self._read_stream = read
            self._write_stream = write

            # Create session
            self.session = ClientSession(read, write)
            await self.session.initialize()

    async def list_tools(self) -> list[Tool]:
        """List all tools available on this server."""
        if not self._connected:
            await self.connect()

        if not self._tools_cache:
            result = await self.session.list_tools()
            self._tools_cache = {tool.name: tool for tool in result.tools}

        return list(self._tools_cache.values())

    async def get_tool(self, tool_name: str) -> Tool:
        """Get a specific tool by name."""
        tools = await self.list_tools()

        if tool_name not in self._tools_cache:
            raise ValueError(f"Tool {tool_name} not found on server {self.name}")

        return self._tools_cache[tool_name]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool on this server.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool result (extracted from response)
        """
        if not self._connected:
            await self.connect()

        # Make the call
        result = await self.session.call_tool(tool_name, arguments=arguments)

        # Extract content from response
        return self._extract_content(result.content)

    def _extract_content(self, content: list) -> Any:
        """
        Extract usable content from MCP response.

        MCP returns a list of content items (TextContent, ImageContent, etc.)
        We extract the most useful representation.
        """
        if not content:
            return None

        # If single text content, return the text
        if len(content) == 1 and isinstance(content[0], TextContent):
            return content[0].text

        # If multiple items, try to parse as JSON or return list
        if len(content) == 1 and isinstance(content[0], TextContent):
            text = content[0].text
            try:
                import json
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        # For mixed content, return structured format
        result = []
        for item in content:
            if isinstance(item, TextContent):
                result.append({"type": "text", "text": item.text})
            elif isinstance(item, ImageContent):
                result.append({
                    "type": "image",
                    "data": item.data,
                    "mimeType": item.mimeType
                })
            elif isinstance(item, EmbeddedResource):
                result.append({
                    "type": "resource",
                    "resource": item.resource
                })

        return result if len(result) > 1 else result[0] if result else None

    async def close(self):
        """Close the connection."""
        if self.session:
            # MCP sessions don't have explicit close, but we can clean up
            self._connected = False
            self._tools_cache.clear()


class MCPRuntime:
    """Runtime for communicating with MCP servers."""

    def __init__(self, config: Config | None = None):
        self._config = config
        self._connections: dict[str, MCPServerConnection] = {}
        self._initialized = False

    async def initialize(self, config: Config | None = None):
        """Initialize the runtime and connect to configured servers."""
        if self._initialized:
            return

        # Load config if not provided
        if config:
            self._config = config
        elif self._config is None:
            self._config = load_config()

        # Create connections for each server (don't connect yet - lazy)
        for server_name, server_config in self._config.mcpServers.items():
            self._connections[server_name] = MCPServerConnection(
                server_name,
                server_config
            )

        self._initialized = True
        logger.info(f"Initialized MCP runtime with {len(self._connections)} servers")

    async def _ensure_connection(self, server_name: str):
        """Ensure a server connection exists and is connected."""
        if not self._initialized:
            await self.initialize()

        if server_name not in self._connections:
            raise ValueError(f"Server {server_name} not configured")

        # Connect lazily
        connection = self._connections[server_name]
        if not connection._connected:
            await connection.connect()

    async def list_servers(self) -> list[str]:
        """List all configured MCP servers."""
        if not self._initialized:
            await self.initialize()

        return list(self._connections.keys())

    async def list_servers_detailed(self) -> list[ServerInfo]:
        """List servers with detailed information."""
        if not self._initialized:
            await self.initialize()

        servers = []
        for name, connection in self._connections.items():
            # Get capabilities if connected
            capabilities = []
            if connection._connected and connection.session:
                server_caps = connection.session.get_server_capabilities()
                if server_caps:
                    # Extract capability names
                    if hasattr(server_caps, 'tools'):
                        capabilities.append('tools')
                    if hasattr(server_caps, 'resources'):
                        capabilities.append('resources')
                    if hasattr(server_caps, 'prompts'):
                        capabilities.append('prompts')

            servers.append(ServerInfo(
                name=name,
                description=f"MCP server via {connection.config.transport}",
                capabilities=capabilities
            ))

        return servers

    async def list_server_tools(self, server_name: str) -> list[str]:
        """
        List tools available on a server.

        Args:
            server_name: Name of the server

        Returns:
            List of tool names
        """
        await self._ensure_connection(server_name)
        connection = self._connections[server_name]

        tools = await connection.list_tools()
        return [tool.name for tool in tools]

    async def list_server_tools_detailed(self, server_name: str) -> list[ToolInfo]:
        """
        List tools with detailed information.

        Args:
            server_name: Name of the server

        Returns:
            List of ToolInfo objects
        """
        await self._ensure_connection(server_name)
        connection = self._connections[server_name]

        tools = await connection.list_tools()

        tool_infos = []
        for tool in tools:
            # Extract parameter names from schema
            params = []
            if tool.inputSchema:
                properties = tool.inputSchema.get("properties", {})
                params = list(properties.keys())

            tool_infos.append(ToolInfo(
                name=tool.name,
                description=tool.description or "",
                parameters=params
            ))

        return tool_infos

    async def get_tool_schema(self, server_name: str, tool_name: str) -> dict:
        """
        Get the JSON schema for a specific tool.

        Args:
            server_name: Name of the server
            tool_name: Name of the tool

        Returns:
            Tool schema dict with description, inputSchema, etc.
        """
        await self._ensure_connection(server_name)
        connection = self._connections[server_name]

        tool = await connection.get_tool(tool_name)

        return {
            "name": tool.name,
            "description": tool.description or "",
            "inputSchema": tool.inputSchema or {}
        }

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> Any:
        """
        Call a tool on an MCP server.

        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool result
        """
        await self._ensure_connection(server_name)
        connection = self._connections[server_name]

        return await connection.call_tool(tool_name, arguments)

    async def close(self):
        """Close all server connections."""
        for connection in self._connections.values():
            await connection.close()
        self._connections.clear()
        self._initialized = False


# Global runtime instance
_runtime: MCPRuntime | None = None
_runtime_lock = asyncio.Lock()


async def get_runtime() -> MCPRuntime:
    """Get or create the global runtime instance."""
    global _runtime

    async with _runtime_lock:
        if _runtime is None:
            _runtime = MCPRuntime()
            await _runtime.initialize()

    return _runtime


async def call_tool(server: str, tool: str, arguments: dict) -> Any:
    """Convenience function to call a tool."""
    runtime = await get_runtime()
    return await runtime.call_tool(server, tool, arguments)


async def get_tool_schema(server: str, tool: str) -> dict:
    """Convenience function to get a tool schema."""
    runtime = await get_runtime()
    return await runtime.get_tool_schema(server, tool)


async def list_servers() -> list[str]:
    """Convenience function to list servers."""
    runtime = await get_runtime()
    return await runtime.list_servers()


async def list_server_tools(server: str) -> list[str]:
    """Convenience function to list tools on a server."""
    runtime = await get_runtime()
    return await runtime.list_server_tools(server)
