"""
Tool Discovery: Progressive Disclosure for Minimal Context

Key insight from Anthropic article:
"Rather than loading all tool definitions upfront, agents can:
- List available servers dynamically
- Read specific tool files as needed
- Use optional search_tools mechanisms to find relevant capabilities
- Request varying detail levels (name only, full schemas, etc.)"

Philosophy:
- Start with zero context (just the mcp object)
- Discover servers on demand
- Discover tools on demand
- Load schemas only when calling
- Search when you don't know what exists

Three levels of discovery:
1. Server discovery - what MCP servers are available?
2. Tool discovery - what tools does a server have?
3. Schema discovery - what arguments does a tool need?
"""

from typing import Literal, TypedDict
from pydantic import BaseModel, Field


# === Level 1: Server Discovery ===

class ServerInfo(BaseModel):
    """Information about an available MCP server."""
    name: str
    description: str = ""
    version: str = "unknown"
    capabilities: list[str] = []


async def discover_servers_example():
    """How an LLM would discover what servers exist."""
    from mcp_codemode import mcp

    # Method 1: List all servers
    servers = await mcp.list_servers()
    # Returns: ["filesystem", "github", "slack", "database"]

    # Method 2: Get detailed info
    servers_detailed = await mcp.list_servers(detailed=True)
    # Returns: [
    #   ServerInfo(name="filesystem", description="File system operations", ...),
    #   ServerInfo(name="github", description="GitHub API access", ...),
    # ]

    # Method 3: Search for servers by capability
    search_results = await mcp.search_servers(query="file operations")
    # Returns: ["filesystem", "s3", "dropbox"]

    return servers


# === Level 2: Tool Discovery ===

class ToolInfo(TypedDict):
    """Information about a tool (minimal context)."""
    name: str
    description: str
    # Note: NO schema here yet - that's Level 3


async def discover_tools_example():
    """How an LLM would discover what tools a server has."""
    from mcp_codemode import mcp

    # Method 1: List tool names only (minimal context)
    tools = await mcp.filesystem.list_tools()
    # Returns: ["read_file", "write_file", "list_directory", "delete_file"]

    # Method 2: List with descriptions (more context)
    tools_detailed = await mcp.filesystem.list_tools(detailed=True)
    # Returns: [
    #   {"name": "read_file", "description": "Read contents of a file"},
    #   {"name": "write_file", "description": "Write content to a file"},
    #   ...
    # ]

    # Method 3: Search tools by keyword
    search_results = await mcp.filesystem.search_tools(query="read")
    # Returns: ["read_file"]

    # Method 4: Inspect a specific tool (lazy schema loading)
    tool_info = await mcp.filesystem.read_file.get_info()
    # Returns: {
    #   "name": "read_file",
    #   "description": "Read contents of a file",
    #   "parameters": ["path"],  # Just names, no full schema yet
    # }

    return tools


# === Level 3: Schema Discovery (Lazy Loading) ===

async def discover_schema_example():
    """Schema is loaded only when needed."""
    from mcp_codemode import mcp

    # Schema loads automatically on first call
    # No explicit loading needed!
    result = await mcp.filesystem.read_file(path="/etc/hosts")
    # Behind the scenes:
    # 1. Check if schema cached
    # 2. If not, fetch from MCP server
    # 3. Generate Pydantic model
    # 4. Validate arguments
    # 5. Execute tool

    # Or explicitly get schema if needed
    schema = await mcp.filesystem.read_file.get_schema()
    # Returns: {
    #   "inputSchema": {
    #     "type": "object",
    #     "properties": {
    #       "path": {"type": "string", "description": "File path"}
    #     },
    #     "required": ["path"]
    #   },
    #   "outputSchema": {...}
    # }

    return schema


# === Smart Discovery: Context-Aware Search ===

class SearchResult(BaseModel):
    """Result from searching across all MCP servers."""
    server: str
    tool: str
    description: str
    relevance_score: float = 1.0


async def smart_search_example():
    """Search across ALL servers for relevant tools."""
    from mcp_codemode import mcp

    # High-level search across everything
    results = await mcp.search(query="create issue")
    # Returns: [
    #   SearchResult(server="github", tool="create_issue", ...),
    #   SearchResult(server="jira", tool="create_ticket", ...),
    #   SearchResult(server="linear", tool="create_issue", ...),
    # ]

    # Then use the most relevant
    await mcp.github.create_issue(repo="...", title="...", body="...")

    return results


# === File-Based Discovery (Anthropic's Approach) ===

"""
Anthropic's approach: Organize tools as a file tree

Structure:
.mcp_tools/
├── servers/
│   ├── filesystem/
│   │   ├── __init__.pyi        # Server info
│   │   ├── read_file.pyi       # Tool signature
│   │   ├── write_file.pyi
│   │   └── list_directory.pyi
│   ├── github/
│   │   ├── __init__.pyi
│   │   ├── create_issue.pyi
│   │   └── list_repos.pyi
│   └── ...

Then LLM can:
1. ls .mcp_tools/servers/ → see available servers
2. ls .mcp_tools/servers/github/ → see available tools
3. cat .mcp_tools/servers/github/create_issue.pyi → see schema
"""


async def filesystem_based_discovery():
    """
    Generate filesystem structure for LLM to explore.

    This is great for Claude Code because I can:
    - Use Glob to find servers: "**/*.pyi"
    - Use Read to see tool schemas
    - Use Grep to search: "create.*issue"
    """
    from pathlib import Path
    from mcp_codemode import mcp

    # Generate stub files
    await mcp.generate_stubs(output_dir=".mcp_tools")

    # Now I can explore with my native tools!
    # This is VERY natural for me as Claude Code

    # Example .pyi stub file:
    EXAMPLE_STUB = '''
# .mcp_tools/servers/github/create_issue.pyi
"""GitHub: Create a new issue in a repository."""

from typing import TypedDict

class CreateIssueInput(TypedDict):
    repo: str  # Repository in format "owner/repo"
    title: str  # Issue title
    body: str  # Issue description
    labels: list[str] | None  # Optional labels

class CreateIssueOutput(TypedDict):
    number: int  # Issue number
    url: str  # Issue URL

async def create_issue(
    repo: str,
    title: str,
    body: str,
    labels: list[str] | None = None
) -> CreateIssueOutput:
    """Create a new issue in a GitHub repository.

    Args:
        repo: Repository in format "owner/repo"
        title: Issue title
        body: Issue description
        labels: Optional list of label names

    Returns:
        Issue number and URL
    """
    ...
'''

    return EXAMPLE_STUB


# === Hybrid Approach: Best of Both Worlds ===

class MCPDiscovery:
    """
    Combines programmatic and file-based discovery.

    Programmatic (fast, always up-to-date):
    - await mcp.list_servers()
    - await mcp.search("query")
    - await mcp.filesystem.list_tools()

    File-based (great for Claude Code):
    - Generate .mcp_tools/ stubs
    - Use Glob/Grep/Read to explore
    - Full IDE autocomplete
    """

    def __init__(self):
        self.stub_dir = ".mcp_tools"
        self._servers_cache: dict = {}

    async def ensure_stubs(self, server: str | None = None):
        """Generate stub files for exploration."""
        # Generate on first access or on demand
        pass

    async def list_servers(
        self,
        detailed: bool = False
    ) -> list[str] | list[ServerInfo]:
        """List available MCP servers.

        Args:
            detailed: Include full server info vs just names

        Returns:
            Server names or detailed info
        """
        pass

    async def search(
        self,
        query: str,
        *,
        server: str | None = None,
        limit: int = 10
    ) -> list[SearchResult]:
        """Search for tools across all servers.

        Args:
            query: Search query (natural language or keywords)
            server: Optionally limit to specific server
            limit: Max results to return

        Returns:
            Ranked list of matching tools
        """
        pass

    async def search_servers(self, query: str) -> list[str]:
        """Search for servers by capability."""
        pass


# === Usage Examples for Claude Code ===

async def claude_code_workflow():
    """
    How I (Claude Code) would actually use this for a user request:

    User: "Find large log files and create a GitHub issue about them"
    """
    from mcp_codemode import mcp

    # Step 1: I don't know what's available, so search
    file_tools = await mcp.search("list files")
    # → [{"server": "filesystem", "tool": "list_directory", ...}]

    github_tools = await mcp.search("create issue")
    # → [{"server": "github", "tool": "create_issue", ...}]

    # Step 2: Now I know what to use, call them
    files = await mcp.filesystem.list_directory(path="/var/log")

    # Step 3: Process locally (no context overhead!)
    large_files = [f for f in files['entries'] if f['size'] > 10_000_000]

    # Step 4: Create issue
    issue = await mcp.github.create_issue(
        repo="myorg/myrepo",
        title=f"Found {len(large_files)} large log files",
        body=f"Details:\n" + "\n".join(f"- {f['name']}: {f['size']} bytes" for f in large_files[:5])
    )

    return f"Created issue #{issue['number']}"


async def claude_code_with_stubs():
    """
    Alternative: User runs setup first to generate stubs.

    User: "mcp-codemode setup"  # Generates .mcp_tools/
    """
    # Now I can use my native tools!

    # Find all GitHub-related tools
    # await glob(".mcp_tools/servers/github/*.pyi")

    # Search for "issue" tools across all servers
    # await grep("issue", pattern="*.pyi", path=".mcp_tools")

    # Read a specific tool schema
    # await read(".mcp_tools/servers/github/create_issue.pyi")

    # Then use it
    from mcp_codemode import mcp
    await mcp.github.create_issue(repo="...", title="...", body="...")


# === Context Overhead Comparison ===

CONTEXT_COMPARISON = """
❌ Loading All Tools Upfront:
- 5 servers × 10 tools × 200 tokens = 10,000 tokens
- Before doing ANY work!

✅ Progressive Discovery:
- list_servers(): ["filesystem", "github", "slack"] = 20 tokens
- search("create issue"): [{"github": "create_issue"}] = 30 tokens
- Call tool: await mcp.github.create_issue(...) = auto-loads schema
- Total context: ~50 tokens vs 10,000 tokens

✅ File-Based (for Claude Code):
- Generate .mcp_tools/ once (user command)
- I use Glob/Grep/Read (my native tools)
- Zero context overhead - I explore as needed
- Perfect fit for my workflow!

Key insight: The LLM doesn't need to see all schemas upfront.
Just like a human developer doesn't memorize every API before coding.
"""


if __name__ == "__main__":
    print(__doc__)
    print("\n" + CONTEXT_COMPARISON)
