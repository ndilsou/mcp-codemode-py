"""
Approach 3: Pydantic Hybrid (MY FAVORITE)

Philosophy:
- Use Pydantic models generated from JSON Schema for validation & types
- Proxy objects for lazy loading (like Approach 2)
- Generate .pyi stubs for IDE autocomplete (like Approach 1)
- Best of both worlds: Pythonic + performant + type-safe

Key Cloudflare insights applied:
1. LLMs are better at code than tool calls (they've seen tons of Python)
2. Single "execute code" tool instead of exposing all tools
3. Lazy loading - only load schemas when needed
4. Type definitions generated from MCP schemas

Pros:
- Type-safe with Pydantic validation
- Lazy loading - minimal context overhead
- IDE autocomplete via .pyi stubs
- Clean, Pythonic API
- Runtime validation catches errors early

Cons:
- Slightly more complex implementation
- Pydantic dependency (but it's ubiquitous in Python)
"""

from typing import Any, TypeVar, Generic
from pydantic import BaseModel, Field, create_model
from functools import cached_property
import json


# === Library Implementation ===

class ToolCall(BaseModel):
    """Represents a tool call with validated inputs."""
    server: str
    tool: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Represents a tool result."""
    success: bool
    data: Any | None = None
    error: str | None = None


class ToolProxy:
    """Lazy-loading proxy for MCP tools with Pydantic validation."""

    def __init__(self, server_name: str, tool_name: str):
        self._server = server_name
        self._tool = tool_name
        self._schema: dict | None = None
        self._input_model: type[BaseModel] | None = None
        self._output_model: type[BaseModel] | None = None

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with Pydantic-validated arguments."""
        # Lazy load schema and models on first call
        if self._input_model is None:
            await self._initialize()

        # Validate input with Pydantic
        try:
            validated_input = self._input_model(**kwargs)
        except Exception as e:
            raise ValueError(f"Invalid arguments for {self._tool}: {e}")

        # Execute via MCP runtime
        from mcp_codemode._runtime import call_tool
        result = await call_tool(
            self._server,
            self._tool,
            validated_input.model_dump()
        )

        # Optionally validate output
        if self._output_model:
            try:
                validated_output = self._output_model(**result)
                return validated_output.model_dump()
            except Exception:
                # If output doesn't match schema, return raw
                return result

        return result

    async def _initialize(self):
        """Lazy initialize schema and Pydantic models."""
        from mcp_codemode._runtime import get_tool_schema
        self._schema = await get_tool_schema(self._server, self._tool)

        # Generate Pydantic models from JSON Schema
        input_schema = self._schema.get("inputSchema", {})
        output_schema = self._schema.get("outputSchema", {})

        self._input_model = self._json_schema_to_pydantic(
            input_schema,
            f"{self._tool}_Input"
        )

        if output_schema:
            self._output_model = self._json_schema_to_pydantic(
                output_schema,
                f"{self._tool}_Output"
            )

    @staticmethod
    def _json_schema_to_pydantic(
        schema: dict,
        model_name: str
    ) -> type[BaseModel]:
        """Convert JSON Schema to Pydantic model."""
        if not schema or schema.get("type") != "object":
            # Simple passthrough model
            return create_model(model_name, __base__=BaseModel)

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        field_definitions = {}
        for field_name, field_schema in properties.items():
            field_type = Any  # Default
            field_kwargs = {
                "description": field_schema.get("description", "")
            }

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
                field_type = list
            elif json_type == "object":
                field_type = dict

            # Handle optional fields
            if field_name not in required:
                field_type = field_type | None
                field_kwargs["default"] = None

            field_definitions[field_name] = (field_type, Field(**field_kwargs))

        return create_model(model_name, **field_definitions)

    @property
    def __doc__(self) -> str:
        """Return tool description."""
        if self._schema:
            return self._schema.get("description", "")
        return f"MCP tool: {self._server}.{self._tool}"


class ServerProxy:
    """Proxy for accessing tools on an MCP server."""

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

    async def list_tools(self) -> list[str]:
        """List available tools."""
        from mcp_codemode._runtime import list_server_tools
        return await list_server_tools(self._server)


class MCPCodeMode:
    """Main entry point for MCP Code Mode."""

    def __init__(self, stub_dir: str = ".mcp_stubs"):
        self._servers_cache: dict[str, ServerProxy] = {}
        self._stub_dir = stub_dir

    def __getattr__(self, server_name: str) -> ServerProxy:
        """Dynamically access MCP servers."""
        if server_name.startswith("_"):
            raise AttributeError(f"No attribute {server_name}")

        if server_name not in self._servers_cache:
            self._servers_cache[server_name] = ServerProxy(server_name)

        return self._servers_cache[server_name]

    async def generate_stubs(self, server_name: str | None = None):
        """Generate .pyi stub files for IDE support."""
        from pathlib import Path
        from mcp_codemode._stub_generator import StubGenerator

        stub_gen = StubGenerator(Path(self._stub_dir))

        if server_name:
            await stub_gen.generate_server_stub(server_name)
        else:
            # Generate for all connected servers
            from mcp_codemode._runtime import list_servers
            servers = await list_servers()
            for server in servers:
                await stub_gen.generate_server_stub(server)


# Global singleton
mcp = MCPCodeMode()


# === How the LLM would use it (same as Approach 2, but with validation!) ===

async def example_usage():
    """This is the code Claude would write."""
    from mcp_codemode import mcp

    # Pydantic validates arguments automatically!
    result = await mcp.filesystem.read_file(path="/etc/hosts")

    # This would raise a validation error:
    # await mcp.filesystem.read_file(path=123)  # path must be string!

    # Multi-step operations
    files = await mcp.filesystem.list_directory(path="/var/log")
    large_files = [f for f in files['entries'] if f['size'] > 1_000_000]

    for file in large_files[:5]:
        content = await mcp.filesystem.read_file(path=file['path'])
        # Process locally - no context overhead

    # Type hints work in IDE if stubs are generated
    await mcp.github.create_issue(
        repo="my/repo",
        title="Bug found",
        body="Details here"
    )

    return {"large_files": len(large_files), "sample": large_files[:3]}


# === Example generated .pyi stub for IDE support ===

EXAMPLE_PYI_STUB = """
# Generated stub for filesystem MCP server
from typing import Any, TypedDict

class ReadFileResult(TypedDict):
    content: str
    size: int
    modified: str

class ListDirectoryResult(TypedDict):
    entries: list[dict[str, Any]]
    total: int

class FilesystemServer:
    async def read_file(self, path: str) -> ReadFileResult:
        '''Read contents of a file.

        Args:
            path: Path to the file to read

        Returns:
            File content and metadata
        '''
        ...

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        '''Write content to a file.

        Args:
            path: Path to the file to write
            content: Content to write
        '''
        ...

    async def list_directory(self, path: str) -> ListDirectoryResult:
        '''List files in a directory.

        Args:
            path: Path to directory
        '''
        ...

filesystem: FilesystemServer
"""


if __name__ == "__main__":
    print(__doc__)
    print("\n=== Example .pyi stub ===")
    print(EXAMPLE_PYI_STUB)
