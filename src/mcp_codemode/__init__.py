"""
MCP Code Mode for Python

A lightweight library for calling MCP tools with minimal context overhead.
Implements the principles from Anthropic and Cloudflare articles on code execution with MCP.
"""

from .core import mcp, MCPCodeMode
from .models import ToolResult, SearchResult

__version__ = "0.1.0"

__all__ = [
    "mcp",
    "MCPCodeMode",
    "ToolResult",
    "SearchResult",
]
