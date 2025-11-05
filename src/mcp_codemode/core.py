"""
Core MCP Code Mode implementation with Pydantic proxy objects.

This implements Approach 3: Pydantic Hybrid
- Lazy-loading proxy objects
- Pydantic validation from JSON Schema
- .pyi stub generation for IDE support
"""

from typing import Any
from pydantic import BaseModel, Field, create_model
from functools import cached_property

from .runtime import get_runtime
from .models import SearchResult, ServerInfo


class ToolProxy:
    """
    Lazy-loading proxy for MCP tools with Pydantic validation.

    This class dynamically loads tool schemas and validates inputs.
    """

    def __init__(self, server_name: str, tool_name: str):
        self._server = server_name
        self._tool = tool_name
        self._schema: dict | None = None
        self._input_model: type[BaseModel] | None = None
        self._output_model: type[BaseModel] | None = None
        self._initialized = False

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with Pydantic-validated arguments."""
        # Lazy load schema and models on first call
        if not self._initialized:
            await self._initialize()

        # Validate input with Pydantic
        try:
            validated_input = self._input_model(**kwargs)
        except Exception as e:
            raise ValueError(
                f"Invalid arguments for {self._server}.{self._tool}: {e}"
            ) from e

        # Execute via MCP runtime
        runtime = await get_runtime()
        result = await runtime.call_tool(
            self._server,
            self._tool,
            validated_input.model_dump(exclude_none=True)
        )

        # Optionally validate output
        if self._output_model and isinstance(result, dict):
            try:
                validated_output = self._output_model(**result)
                return validated_output.model_dump()
            except Exception:
                # If output doesn't match schema, return raw
                # This is lenient - real data might be messier than schema
                pass

        return result

    async def _initialize(self):
        """Lazy initialize schema and Pydantic models."""
        runtime = await get_runtime()
        self._schema = await runtime.get_tool_schema(self._server, self._tool)

        # Generate Pydantic models from JSON Schema
        input_schema = self._schema.get("inputSchema", {})
        output_schema = self._schema.get("outputSchema", {})

        self._input_model = self._json_schema_to_pydantic(
            input_schema,
            f"{self._tool}_Input"
        )

        if output_schema and output_schema.get("type") == "object":
            self._output_model = self._json_schema_to_pydantic(
                output_schema,
                f"{self._tool}_Output"
            )

        self._initialized = True

    @staticmethod
    def _json_schema_to_pydantic(
        schema: dict,
        model_name: str
    ) -> type[BaseModel]:
        """
        Convert JSON Schema to Pydantic model.

        This is a simplified converter that handles basic types.
        A production version might use a library like datamodel-code-generator.
        """
        if not schema or schema.get("type") != "object":
            # Simple passthrough model for non-object schemas
            return create_model(model_name, __base__=BaseModel)

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        field_definitions = {}
        for field_name, field_schema in properties.items():
            field_type = Any  # Default
            field_kwargs = {}

            description = field_schema.get("description", "")
            if description:
                field_kwargs["description"] = description

            # Map JSON Schema types to Python types
            json_type = field_schema.get("type")
            if json_type == "string":
                field_type = str
            elif json_type == "integer":
                field_type = int
            elif json_type == "number":
                field_type = float
            elif json_type == "boolean":
                field_type = bool
            elif json_type == "array":
                # Simple list type - could be more sophisticated
                field_type = list
            elif json_type == "object":
                field_type = dict

            # Handle optional fields
            if field_name not in required:
                field_type = field_type | None
                field_kwargs["default"] = None

            field_definitions[field_name] = (field_type, Field(**field_kwargs))

        return create_model(model_name, **field_definitions)

    async def get_info(self) -> dict:
        """Get tool information without full schema."""
        if not self._initialized:
            await self._initialize()

        return {
            "name": self._tool,
            "description": self._schema.get("description", ""),
            "parameters": list(
                self._schema.get("inputSchema", {}).get("properties", {}).keys()
            )
        }

    async def get_schema(self) -> dict:
        """Get the full JSON schema for this tool."""
        if not self._initialized:
            await self._initialize()
        return self._schema

    @property
    def __doc__(self) -> str:
        """Return tool description (if schema loaded)."""
        if self._schema:
            return self._schema.get("description", "")
        return f"MCP tool: {self._server}.{self._tool}"


class ServerProxy:
    """
    Proxy for accessing tools on an MCP server.

    Dynamically creates ToolProxy instances on attribute access.
    """

    def __init__(self, server_name: str):
        self._server = server_name
        self._tools_cache: dict[str, ToolProxy] = {}

    def __getattr__(self, tool_name: str) -> ToolProxy:
        """Dynamically create tool proxies."""
        if tool_name.startswith("_"):
            raise AttributeError(f"No attribute {tool_name}")

        if tool_name not in self._tools_cache:
            self._tools_cache[tool_name] = ToolProxy(self._server, tool_name)

        return self._tools_cache[tool_name]

    async def list_tools(self, detailed: bool = False) -> list[str] | list[dict]:
        """
        List tools available on this server.

        Args:
            detailed: If True, return detailed info. If False, just names.

        Returns:
            List of tool names or ToolInfo dicts
        """
        runtime = await get_runtime()

        if detailed:
            tools = await runtime.list_server_tools_detailed(self._server)
            return [tool.model_dump() for tool in tools]
        else:
            return await runtime.list_server_tools(self._server)

    async def search_tools(self, query: str) -> list[str]:
        """
        Search for tools on this server matching a query.

        Args:
            query: Search query

        Returns:
            List of matching tool names
        """
        from .search import simple_search

        tools = await self.list_tools(detailed=True)
        results = simple_search(query, tools, server_name=self._server)
        return [r.tool for r in results]


class MCPCodeMode:
    """
    Main entry point for MCP Code Mode.

    Usage:
        from mcp_codemode import mcp

        # Access servers and tools dynamically
        result = await mcp.filesystem.read_file(path="/etc/hosts")

        # Discover what's available
        servers = await mcp.list_servers()
        tools = await mcp.filesystem.list_tools()

        # Search across everything
        results = await mcp.search("create issue")
    """

    def __init__(self, stub_dir: str = ".codemode/stubs"):
        self._servers_cache: dict[str, ServerProxy] = {}
        self._stub_dir = stub_dir
        self._stub_gen_started = False

    def __getattr__(self, server_name: str) -> ServerProxy:
        """Dynamically access MCP servers."""
        if server_name.startswith("_"):
            raise AttributeError(f"No attribute {server_name}")

        if server_name not in self._servers_cache:
            self._servers_cache[server_name] = ServerProxy(server_name)

        return self._servers_cache[server_name]

    async def list_servers(self, detailed: bool = False) -> list[str] | list[ServerInfo]:
        """
        List available MCP servers.

        Args:
            detailed: If True, return detailed info. If False, just names.

        Returns:
            List of server names or ServerInfo objects
        """
        runtime = await get_runtime()

        if detailed:
            return await runtime.list_servers_detailed()
        else:
            return await runtime.list_servers()

    async def search(
        self,
        query: str,
        *,
        server: str | None = None,
        limit: int = 10
    ) -> list[SearchResult]:
        """
        Search for tools across all (or specific) servers.

        Args:
            query: Search query (keywords or natural language)
            server: Optionally limit to specific server
            limit: Maximum results to return

        Returns:
            List of SearchResult objects, sorted by relevance
        """
        from .search import search_all_servers

        return await search_all_servers(
            query,
            server_filter=server,
            limit=limit
        )

    async def search_servers(self, query: str) -> list[str]:
        """
        Search for servers by capability.

        Args:
            query: Search query

        Returns:
            List of matching server names
        """
        from .search import search_servers

        return await search_servers(query)

    async def generate_stubs(
        self,
        output_dir: str | None = None,
        server: str | None = None
    ):
        """
        Generate .pyi stub files for IDE support.

        Args:
            output_dir: Directory to write stubs to (default: .mcp_tools)
            server: Optionally generate for specific server only
        """
        from .stub_generator import StubGenerator
        from pathlib import Path

        output_path = Path(output_dir or self._stub_dir)
        generator = StubGenerator(output_path)

        if server:
            await generator.generate_server_stub(server)
        else:
            await generator.generate_all_stubs()

    def _start_background_stub_gen(self):
        """Start background stub generation (non-blocking)."""
        if not self._stub_gen_started:
            import asyncio
            try:
                # Only start if there's a running event loop
                loop = asyncio.get_running_loop()
                loop.create_task(self.generate_stubs())
                self._stub_gen_started = True
            except RuntimeError:
                # No event loop running, skip background generation
                # Will be generated on-demand when needed
                pass


# Global singleton instance
mcp = MCPCodeMode()

# Note: Background stub generation happens lazily on first use
# Not at import time to avoid event loop issues
