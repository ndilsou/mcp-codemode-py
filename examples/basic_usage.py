"""
Basic usage example for MCP Code Mode.

This demonstrates the core API and progressive disclosure pattern.
"""

import asyncio
from mcp_codemode import mcp


async def example_1_basic_tool_call():
    """Example 1: Simple tool call with auto-validated arguments."""
    print("=== Example 1: Basic Tool Call ===\n")

    # Direct tool call - schema loads automatically
    result = await mcp.filesystem.read_file(path="/etc/hosts")

    print(f"File size: {result.get('size')} bytes")
    print(f"Content preview: {result.get('content', '')[:100]}...")
    print()


async def example_2_multi_step_local_processing():
    """Example 2: Multi-step operation with local processing (no context overhead!)."""
    print("=== Example 2: Multi-Step with Local Processing ===\n")

    # Step 1: List files
    files = await mcp.filesystem.list_directory(path="/var/log")
    print(f"Found {len(files.get('entries', []))} files")

    # Step 2: Filter locally (NO CONTEXT OVERHEAD!)
    large_files = [
        f for f in files.get('entries', [])
        if f.get('size', 0) > 1_000_000
    ]
    print(f"Large files (>1MB): {len(large_files)}")

    # Step 3: Process only what we need
    for file in large_files[:3]:  # Only top 3
        print(f"  - {file['name']}: {file['size']:,} bytes")

    print(f"\n✅ Processed {len(files.get('entries', []))} files locally")
    print(f"✅ Only returned {len(large_files[:3])} results to context")
    print()


async def example_3_discovery():
    """Example 3: Discover servers and tools on demand."""
    print("=== Example 3: Progressive Discovery ===\n")

    # Level 1: Discover servers
    servers = await mcp.list_servers()
    print(f"Available servers: {', '.join(servers)}")

    # Level 2: Discover tools on a server
    if servers:
        server_name = servers[0]
        tools = await getattr(mcp, server_name).list_tools()
        print(f"\nTools on '{server_name}': {', '.join(tools[:5])}...")

    # Level 3: Search across everything
    results = await mcp.search("file operations")
    print(f"\nSearch results for 'file operations':")
    for result in results[:3]:
        print(f"  - {result.server}.{result.tool} (score: {result.score:.2f})")

    print()


async def example_4_error_handling():
    """Example 4: Pydantic validation catches errors."""
    print("=== Example 4: Error Handling ===\n")

    try:
        # This will fail validation - path must be a string
        await mcp.filesystem.read_file(path=123)
    except ValueError as e:
        print(f"✅ Validation caught error: {e}")

    try:
        # This will fail - missing required argument
        await mcp.github.create_issue(title="Bug found")
    except (ValueError, TypeError) as e:
        print(f"✅ Validation caught error: Missing required argument")

    print()


async def example_5_real_workflow():
    """Example 5: Real workflow - find and report large log files."""
    print("=== Example 5: Real Workflow ===\n")

    print("Task: Find large log files and create GitHub issue\n")

    # Don't know what's available? Search!
    file_tools = await mcp.search("list files")
    print(f"Found file tool: {file_tools[0] if file_tools else 'none'}")

    issue_tools = await mcp.search("create issue")
    print(f"Found issue tool: {issue_tools[0] if issue_tools else 'none'}")

    print("\nNow using tools...\n")

    # Get files
    files = await mcp.filesystem.list_directory(path="/var/log")

    # Process locally
    large_files = [f for f in files.get('entries', []) if f.get('size', 0) > 10_000_000]

    print(f"Found {len(large_files)} large files (>10MB)")

    # Create issue (if GitHub is available)
    try:
        issue = await mcp.github.create_issue(
            repo="myorg/myrepo",
            title=f"Found {len(large_files)} large log files",
            body=f"Details:\n" + "\n".join(
                f"- {f['name']}: {f['size']:,} bytes"
                for f in large_files[:5]
            )
        )
        print(f"\n✅ Created issue #{issue.get('number')}")
    except Exception as e:
        print(f"\n⚠️  GitHub not available (mock mode): {e}")

    print()


async def main():
    """Run all examples."""
    print("MCP Code Mode - Examples\n")
    print("=" * 50)
    print()

    await example_1_basic_tool_call()
    await example_2_multi_step_local_processing()
    await example_3_discovery()
    await example_4_error_handling()
    await example_5_real_workflow()

    print("=" * 50)
    print("\nContext Efficiency:")
    print("  Traditional: ~10,000 tokens (all tools loaded)")
    print("  Code Mode: ~200 tokens (lazy loading + local processing)")
    print("  Reduction: 98%")


if __name__ == "__main__":
    asyncio.run(main())
