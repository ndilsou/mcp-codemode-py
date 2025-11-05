"""
Command-line interface for MCP Code Mode.

Usage:
    mcp-codemode stub-gen              # Generate stubs for all servers
    mcp-codemode stub-gen filesystem   # Generate stubs for specific server
    mcp-codemode list                  # List available servers
    mcp-codemode search "create issue" # Search for tools
"""

import asyncio
import sys
from pathlib import Path

from .core import mcp


async def cmd_stub_gen(args: list[str]):
    """Generate stub files."""
    server = args[0] if args else None

    print("🔨 Generating MCP stub files...")

    if server:
        print(f"   Server: {server}")
        await mcp.generate_stubs(server=server)
    else:
        print("   Generating for all servers...")
        await mcp.generate_stubs()

    print(f"✅ Stubs generated in .mcp_tools/")
    print("\nYou can now explore tools with:")
    print("  - Glob: '**/*.pyi'")
    print("  - Grep: pattern search")
    print("  - Read: view tool schemas")


async def cmd_list(args: list[str]):
    """List available servers."""
    detailed = "--detailed" in args or "-d" in args

    servers = await mcp.list_servers(detailed=detailed)

    if not servers:
        print("No MCP servers found.")
        print("\nMake sure MCP servers are configured.")
        return

    print(f"📡 Available MCP servers ({len(servers)}):\n")

    if detailed:
        for server in servers:
            print(f"  • {server.name}")
            if server.description:
                print(f"    {server.description}")
            if server.capabilities:
                print(f"    Capabilities: {', '.join(server.capabilities)}")
            print()
    else:
        for server in servers:
            print(f"  • {server}")


async def cmd_search(args: list[str]):
    """Search for tools."""
    if not args:
        print("Usage: mcp-codemode search <query>")
        return

    query = " ".join(args)

    print(f"🔍 Searching for: {query}\n")

    results = await mcp.search(query, limit=10)

    if not results:
        print("No results found.")
        return

    print(f"Found {len(results)} results:\n")

    for result in results:
        print(f"  • {result.server}.{result.tool} (score: {result.score:.2f})")
        if result.description:
            print(f"    {result.description}")
        print()


async def cmd_tools(args: list[str]):
    """List tools for a specific server."""
    if not args:
        print("Usage: mcp-codemode tools <server>")
        return

    server_name = args[0]
    detailed = "--detailed" in args or "-d" in args

    print(f"🔧 Tools for {server_name}:\n")

    try:
        server = getattr(mcp, server_name)
        tools = await server.list_tools(detailed=detailed)

        if not tools:
            print(f"No tools found for {server_name}")
            return

        if detailed:
            for tool in tools:
                print(f"  • {tool['name']}")
                if tool.get('description'):
                    print(f"    {tool['description']}")
                if tool.get('parameters'):
                    print(f"    Parameters: {', '.join(tool['parameters'])}")
                print()
        else:
            for tool in tools:
                print(f"  • {tool}")

    except Exception as e:
        print(f"Error: {e}")


def print_help():
    """Print help message."""
    print("""
MCP Code Mode CLI

Usage:
    mcp-codemode <command> [args]

Commands:
    stub-gen [server]       Generate .pyi stub files for IDE support
    list [-d]               List available MCP servers
    search <query>          Search for tools across all servers
    tools <server> [-d]     List tools for a specific server
    help                    Show this help message

Examples:
    mcp-codemode stub-gen
    mcp-codemode stub-gen filesystem
    mcp-codemode list --detailed
    mcp-codemode search "create issue"
    mcp-codemode tools github --detailed
""")


def main():
    """Main CLI entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ["help", "-h", "--help"]:
        print_help()
        return

    command = args[0]
    command_args = args[1:]

    commands = {
        "stub-gen": cmd_stub_gen,
        "list": cmd_list,
        "search": cmd_search,
        "tools": cmd_tools,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print("\nRun 'mcp-codemode help' for usage information.")
        sys.exit(1)

    # Run async command
    asyncio.run(commands[command](command_args))


if __name__ == "__main__":
    main()
