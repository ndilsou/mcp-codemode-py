"""
Tests for core functionality.
"""

import pytest
from mcp_codemode.core import ToolProxy, ServerProxy, MCPCodeMode


def test_server_proxy_creation():
    """Test ServerProxy creation."""
    proxy = ServerProxy("test_server")
    assert proxy._server == "test_server"


def test_tool_proxy_creation():
    """Test ToolProxy creation."""
    proxy = ToolProxy("test_server", "test_tool")
    assert proxy._server == "test_server"
    assert proxy._tool == "test_tool"


def test_mcp_code_mode_init():
    """Test MCPCodeMode initialization."""
    mcp = MCPCodeMode()
    assert mcp._stub_dir == ".codemode/stubs"


def test_server_attribute_access():
    """Test dynamic server access."""
    mcp = MCPCodeMode()

    # Access should create ServerProxy
    server = mcp.test_server
    assert isinstance(server, ServerProxy)
    assert server._server == "test_server"


def test_tool_attribute_access():
    """Test dynamic tool access."""
    mcp = MCPCodeMode()

    # Access chain
    tool = mcp.test_server.test_tool
    assert isinstance(tool, ToolProxy)
    assert tool._server == "test_server"
    assert tool._tool == "test_tool"


def test_json_schema_to_pydantic_simple():
    """Test converting simple JSON schema to Pydantic."""
    from pydantic import BaseModel

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The name"},
            "age": {"type": "integer"}
        },
        "required": ["name"]
    }

    model = ToolProxy._json_schema_to_pydantic(schema, "TestModel")

    assert issubclass(model, BaseModel)

    # Test validation
    instance = model(name="Alice", age=30)
    assert instance.name == "Alice"
    assert instance.age == 30

    # Test optional field
    instance2 = model(name="Bob")
    assert instance2.name == "Bob"
    assert instance2.age is None


def test_json_schema_to_pydantic_types():
    """Test type mapping in schema conversion."""
    schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "count": {"type": "integer"},
            "ratio": {"type": "number"},
            "active": {"type": "boolean"},
            "items": {"type": "array"},
            "metadata": {"type": "object"}
        },
        "required": ["text"]
    }

    model = ToolProxy._json_schema_to_pydantic(schema, "TypeTest")

    # Should not raise
    instance = model(
        text="hello",
        count=42,
        ratio=3.14,
        active=True,
        items=[1, 2, 3],
        metadata={"key": "value"}
    )

    assert instance.text == "hello"
    assert instance.count == 42
