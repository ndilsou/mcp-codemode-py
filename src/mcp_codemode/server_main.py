#!/usr/bin/env python3
"""
Entry point for running mcp-codemode as an MCP server.

Usage:
    python -m mcp_codemode.server_main

Or via configuration in your MCP client:
{
  "mcpServers": {
    "codemode": {
      "command": "python",
      "args": ["-m", "mcp_codemode.server_main"],
      "transport": "stdio"
    }
  }
}
"""

import asyncio
import sys
import logging

from .server import main as run_server


def main():
    """Main entry point."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr  # Log to stderr, stdout is for MCP protocol
    )

    # Run the server
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
