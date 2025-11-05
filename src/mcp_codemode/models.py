"""
Pydantic models for MCP Code Mode.
"""

from typing import Any
from pydantic import BaseModel, Field


class ServerInfo(BaseModel):
    """Information about an MCP server."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    capabilities: list[str] = Field(default_factory=list)


class ToolInfo(BaseModel):
    """Information about a tool."""
    name: str
    description: str = ""
    parameters: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Result from searching for tools."""
    server: str
    tool: str
    description: str
    score: float = Field(ge=0.0, le=1.0, default=1.0)

    def __str__(self) -> str:
        return f"{self.server}.{self.tool} (score: {self.score:.2f})"


class ToolResult(BaseModel):
    """Result from calling a tool."""
    success: bool
    data: Any = None
    error: str | None = None

    @classmethod
    def ok(cls, data: Any) -> "ToolResult":
        """Create a successful result."""
        return cls(success=True, data=data)

    @classmethod
    def err(cls, error: str) -> "ToolResult":
        """Create an error result."""
        return cls(success=False, error=error)
