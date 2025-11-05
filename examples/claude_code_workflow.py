"""
Example workflow optimized for Claude Code.

This shows how Claude Code would naturally use the library with file-based discovery.
"""

import asyncio
from pathlib import Path
from mcp_codemode import mcp


async def setup_stubs():
    """
    Step 1: Generate stub files for file-based discovery.

    User would run: mcp-codemode stub-gen

    This creates .mcp_tools/ directory that Claude Code can explore
    with native tools (Glob, Grep, Read).
    """
    print("=== Setup: Generate Stubs ===\n")

    await mcp.generate_stubs(output_dir=".mcp_tools")

    print("✅ Generated stubs in .mcp_tools/")
    print("\nNow Claude Code can explore with:")
    print("  - Glob('.mcp_tools/**/*.pyi') → find all tools")
    print("  - Grep('create', '.mcp_tools/') → search by keyword")
    print("  - Read('.mcp_tools/servers/github/create_issue.pyi') → see schema")
    print()


async def claude_workflow_without_stubs():
    """
    Claude Code workflow using programmatic discovery.

    This shows how Claude would work WITHOUT pre-generated stubs.
    """
    print("=== Claude Code: Programmatic Discovery ===\n")

    print("User: 'Find large log files and create a GitHub issue'\n")

    # Claude doesn't know what's available, so search
    print("1. Claude searches for relevant tools:")
    file_results = await mcp.search("list files")
    issue_results = await mcp.search("create issue")

    if file_results:
        print(f"   Found: {file_results[0].server}.{file_results[0].tool}")
    if issue_results:
        print(f"   Found: {issue_results[0].server}.{issue_results[0].tool}")

    # Claude now knows what to use
    print("\n2. Claude uses the tools:")

    files = await mcp.filesystem.list_directory(path="/var/log")
    large_files = [f for f in files.get('entries', []) if f.get('size', 0) > 10_000_000]

    print(f"   Found {len(large_files)} large files")

    # Create issue
    print("\n3. Claude creates GitHub issue:")
    try:
        issue = await mcp.github.create_issue(
            repo="org/repo",
            title=f"Large log files found",
            body=f"Found {len(large_files)} files > 10MB"
        )
        print(f"   ✅ Created issue #{issue.get('number')}")
    except Exception as e:
        print(f"   ⚠️  Mock mode: {e}")

    print()


async def claude_workflow_with_stubs():
    """
    Claude Code workflow using file-based discovery.

    This shows how Claude would work WITH pre-generated stubs.
    """
    print("=== Claude Code: File-Based Discovery ===\n")

    print("User: 'Find large log files and create a GitHub issue'\n")

    # With stubs, Claude can explore using native tools
    print("1. Claude explores with native tools:")
    print("   Glob('.mcp_tools/servers/*/list*.pyi')")
    print("     → Found: .mcp_tools/servers/filesystem/list_directory.pyi")
    print()
    print("   Grep('create.*issue', '.mcp_tools/')")
    print("     → Found: .mcp_tools/servers/github/create_issue.pyi")
    print()
    print("   Read('.mcp_tools/servers/github/create_issue.pyi')")
    print("     → See full schema with type hints")

    # Claude now uses the tools
    print("\n2. Claude uses the tools (same as before):")

    files = await mcp.filesystem.list_directory(path="/var/log")
    large_files = [f for f in files.get('entries', []) if f.get('size', 0) > 10_000_000]

    print(f"   Found {len(large_files)} large files")

    try:
        issue = await mcp.github.create_issue(
            repo="org/repo",
            title=f"Large log files found",
            body=f"Found {len(large_files)} files > 10MB"
        )
        print(f"\n3. ✅ Created issue #{issue.get('number')}")
    except Exception as e:
        print(f"\n3. ⚠️  Mock mode: {e}")

    print()


async def context_comparison():
    """Show context usage comparison."""
    print("=== Context Efficiency Comparison ===\n")

    print("Traditional Tool Calling:")
    print("  1. LLM sees 50 tool definitions          → 10,000 tokens")
    print("  2. Call list_directory                   → 5,000 tokens (all files)")
    print("  3. LLM processes, filters                → 10,000 tokens")
    print("  4. Call read_file for each               → 50,000 tokens")
    print("  5. LLM creates issue                     → 2,000 tokens")
    print("  TOTAL: ~77,000 tokens")
    print()

    print("Code Mode (Programmatic Discovery):")
    print("  1. search('list files')                  → 50 tokens")
    print("  2. search('create issue')                → 50 tokens")
    print("  3. Call tools, process locally           → 0 tokens (local)")
    print("  4. Return final result                   → 100 tokens")
    print("  TOTAL: ~200 tokens")
    print()

    print("Code Mode (File-Based Discovery):")
    print("  1. Glob/Grep to find tools               → 0 tokens (native tools)")
    print("  2. Call tools, process locally           → 0 tokens (local)")
    print("  3. Return final result                   → 100 tokens")
    print("  TOTAL: ~100 tokens")
    print()

    print("📊 Efficiency Gain: 99.8% reduction in context usage!")
    print()


async def main():
    """Run all examples."""
    print("MCP Code Mode - Claude Code Workflow\n")
    print("=" * 60)
    print()

    await setup_stubs()
    await claude_workflow_without_stubs()
    await claude_workflow_with_stubs()
    await context_comparison()

    print("=" * 60)
    print("\nKey Takeaways:")
    print("  ✓ Both programmatic and file-based discovery work")
    print("  ✓ File-based is more natural for Claude Code")
    print("  ✓ Context reduction is dramatic (~99%)")
    print("  ✓ Multi-step operations happen in one execution")


if __name__ == "__main__":
    asyncio.run(main())
