"""
Generate .pyi stub files for IDE support.

Creates a file tree structure that can be explored with file tools:
.mcp_tools/
  servers/
    filesystem/
      __init__.pyi
      read_file.pyi
      write_file.pyi
"""

from pathlib import Path
from typing import Any
from .runtime import get_runtime


class StubGenerator:
    """Generate .pyi stub files from MCP schemas."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    async def generate_all_stubs(self):
        """Generate stubs for all available servers."""
        runtime = await get_runtime()
        servers = await runtime.list_servers()

        # Create base directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate each server
        for server_name in servers:
            await self.generate_server_stub(server_name)

    async def generate_server_stub(self, server_name: str):
        """Generate stub files for a specific server."""
        runtime = await get_runtime()

        # Create server directory
        server_dir = self.output_dir / server_name
        server_dir.mkdir(parents=True, exist_ok=True)

        # Get all tools for this server
        tools = await runtime.list_server_tools_detailed(server_name)

        # Generate __init__.pyi with all imports
        self._generate_server_init(server_dir, tools)

        # Generate individual tool stub files
        for tool in tools:
            schema = await runtime.get_tool_schema(server_name, tool.name)
            self._generate_tool_stub(server_dir, tool.name, schema)


    def _generate_server_init(self, server_dir: Path, tools: list[Any]):
        """Generate server __init__.pyi file."""
        lines = [
            '"""MCP server tools."""',
            "",
            "from typing import Any, TypedDict",
            "",
        ]

        # Import each tool
        for tool in tools:
            lines.append(f"from .{tool.name} import {tool.name}")

        lines.append("")
        lines.append("__all__ = [")
        for tool in tools:
            lines.append(f'    "{tool.name}",')
        lines.append("]")
        lines.append("")

        content = "\n".join(lines)
        (server_dir / "__init__.pyi").write_text(content)

    def _generate_tool_stub(self, server_dir: Path, tool_name: str, schema: dict):
        """Generate stub file for a specific tool."""
        lines = [
            f'"""{schema.get("description", f"MCP tool: {tool_name}")}"""',
            "",
            "from typing import Any, TypedDict",
            "",
        ]

        # Generate input TypedDict
        input_schema = schema.get("inputSchema", {})
        if input_schema and input_schema.get("type") == "object":
            lines.extend(self._generate_typeddict(
                f"{self._to_class_name(tool_name)}Input",
                input_schema
            ))
            lines.append("")

        # Generate output TypedDict
        output_schema = schema.get("outputSchema", {})
        if output_schema and output_schema.get("type") == "object":
            lines.extend(self._generate_typeddict(
                f"{self._to_class_name(tool_name)}Output",
                output_schema
            ))
            lines.append("")

        # Generate function signature
        lines.extend(self._generate_function_signature(tool_name, schema))
        lines.append("")

        content = "\n".join(lines)
        (server_dir / f"{tool_name}.pyi").write_text(content)

    def _generate_typeddict(self, name: str, schema: dict) -> list[str]:
        """Generate a TypedDict from JSON Schema."""
        lines = [f"class {name}(TypedDict):"]

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        if not properties:
            lines.append("    pass")
            return lines

        for prop_name, prop_schema in properties.items():
            prop_type = self._json_type_to_python(prop_schema)
            description = prop_schema.get("description", "")

            # Make optional if not required
            if prop_name not in required:
                prop_type = f"{prop_type} | None"

            # Add description as comment
            if description:
                lines.append(f"    # {description}")

            lines.append(f"    {prop_name}: {prop_type}")

        return lines

    def _generate_function_signature(self, tool_name: str, schema: dict) -> list[str]:
        """Generate async function signature."""
        lines = []

        # Start function
        class_name = self._to_class_name(tool_name)
        input_schema = schema.get("inputSchema", {})
        output_schema = schema.get("outputSchema", {})

        # Build parameter list
        params = []
        properties = input_schema.get("properties", {})
        required = set(input_schema.get("required", []))

        for param_name, param_schema in properties.items():
            param_type = self._json_type_to_python(param_schema)

            if param_name in required:
                params.append(f"{param_name}: {param_type}")
            else:
                params.append(f"{param_name}: {param_type} | None = None")

        # Return type
        if output_schema and output_schema.get("type") == "object":
            return_type = f"{class_name}Output"
        else:
            return_type = "Any"

        # Build function signature
        if params:
            lines.append(f"async def {tool_name}(")
            for param in params:
                lines.append(f"    {param},")
            lines.append(f") -> {return_type}:")
        else:
            lines.append(f"async def {tool_name}() -> {return_type}:")

        # Add docstring
        description = schema.get("description", "")
        if description or params:
            lines.append('    """')
            if description:
                lines.append(f"    {description}")
            if params and description:
                lines.append("")
            if params:
                lines.append("    Args:")
                for param_name, param_schema in properties.items():
                    param_desc = param_schema.get("description", "")
                    lines.append(f"        {param_name}: {param_desc}")
            lines.append('    """')

        lines.append("    ...")

        return lines

    def _json_type_to_python(self, schema: dict) -> str:
        """Convert JSON Schema type to Python type hint."""
        json_type = schema.get("type", "any")

        type_map = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
            "null": "None",
        }

        return type_map.get(json_type, "Any")

    def _to_class_name(self, snake_case: str) -> str:
        """Convert snake_case to PascalCase."""
        return "".join(word.capitalize() for word in snake_case.split("_"))
