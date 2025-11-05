# Tool Discovery: Progressive Disclosure

## The Problem

Loading all tool definitions upfront is expensive:
- 5 servers × 10 tools × 200 tokens = **10,000 tokens**
- Before doing ANY work!
- LLM context filled with schemas it might never use

## The Solution: Progressive Disclosure

Discover tools on-demand in three levels:

```
Level 0: Nothing loaded (just `mcp` object available)
   ↓
Level 1: Discover servers when needed
   ↓
Level 2: Discover tools on a server
   ↓
Level 3: Load schema when calling tool
```

## Three Approaches

### 1. Programmatic Discovery (Dynamic)

```python
from mcp_codemode import mcp

# Level 1: What servers exist?
servers = await mcp.list_servers()
# → ["filesystem", "github", "slack"]

# Search across everything
results = await mcp.search("create issue")
# → [{"server": "github", "tool": "create_issue", score: 0.95}]

# Level 2: What tools on github?
tools = await mcp.github.list_tools()
# → ["create_issue", "list_repos", "create_pr"]

# Level 3: Schema loads automatically on call
await mcp.github.create_issue(repo="...", title="...")
```

**Pros:**
- Always up-to-date
- Fast
- Works for any agent

**Cons:**
- Requires API calls
- Less natural for Claude Code

### 2. File-Based Discovery (Anthropic's Approach)

Generate stub files that LLMs can explore:

```
.mcp_tools/
├── servers/
│   ├── filesystem/
│   │   ├── __init__.pyi
│   │   ├── read_file.pyi
│   │   ├── write_file.pyi
│   │   └── list_directory.pyi
│   ├── github/
│   │   ├── __init__.pyi
│   │   ├── create_issue.pyi
│   │   └── list_repos.pyi
```

Then explore naturally:

```python
# For Claude Code, use native tools!
# Glob: "**/*.pyi" → see all available tools
# Grep: "create.*issue" → search for relevant tools
# Read: ".mcp_tools/servers/github/create_issue.pyi" → see schema
```

**Pros:**
- Perfect for Claude Code (uses my native tools!)
- IDE autocomplete
- Zero API calls after generation
- Can be committed to git

**Cons:**
- Requires generation step
- Can become stale

### 3. Hybrid (Recommended)

Combine both:

```python
from mcp_codemode import mcp

# Option A: Programmatic (always fresh)
results = await mcp.search("list files")

# Option B: File-based (if stubs exist)
# Use Glob/Grep to explore .mcp_tools/

# Both lead to same usage:
await mcp.filesystem.list_directory(path="/var/log")
```

**Setup command:**
```bash
# Generate stubs for exploration
mcp-codemode stub-gen

# Or auto-generate on first import
from mcp_codemode import mcp  # Auto-generates .mcp_tools/
```

## API Design

### Global Search

```python
# Search across ALL servers
results = await mcp.search(
    query="create issue",
    limit=10
)
# Returns: [
#   SearchResult(server="github", tool="create_issue", score=0.95),
#   SearchResult(server="jira", tool="create_ticket", score=0.87),
# ]
```

### Server-Level Discovery

```python
# List servers
servers = await mcp.list_servers()
servers_detailed = await mcp.list_servers(detailed=True)

# Search servers
file_servers = await mcp.search_servers("file storage")
# → ["filesystem", "s3", "dropbox"]
```

### Tool-Level Discovery

```python
# List tools (minimal context)
tools = await mcp.github.list_tools()
# → ["create_issue", "list_repos", "create_pr"]

# List with descriptions (more context)
tools = await mcp.github.list_tools(detailed=True)
# → [{"name": "create_issue", "description": "Create..."}, ...]

# Search tools on server
results = await mcp.github.search_tools("issue")
# → ["create_issue", "close_issue", "list_issues"]

# Get tool info (no schema yet)
info = await mcp.github.create_issue.get_info()
# → {"name": "create_issue", "params": ["repo", "title", "body"]}

# Get full schema (if needed)
schema = await mcp.github.create_issue.get_schema()
# → Full JSON Schema
```

## Context Overhead Comparison

### ❌ Traditional: Load All Upfront
```
Context: 10,000 tokens (all tool definitions)
Work: Minimal
Efficiency: 0.1%
```

### ✅ Progressive Discovery
```
1. search("create issue") → 30 tokens
2. Call tool (schema auto-loads) → 0 tokens in context
3. Return result → 20 tokens

Total: 50 tokens vs 10,000 tokens
Efficiency: 99.5%
```

### ✅ File-Based (Claude Code)
```
1. User runs: mcp-codemode stub-gen
2. I use Glob/Grep/Read (native tools)
3. No context overhead!

Context: ~0 tokens (I explore with tools)
Efficiency: 100%
```

## Implementation Strategy

### For Claude Code (Me!)

**Hybrid approach:**

1. **Setup phase** (user command):
   ```bash
   mcp-codemode stub-gen
   ```
   Generates `.mcp_tools/` directory

2. **Discovery phase** (I use my tools):
   ```python
   # I naturally explore with Glob/Grep/Read
   await glob(".mcp_tools/servers/*/__init__.pyi")
   await grep("create", path=".mcp_tools", pattern="*.pyi")
   ```

3. **Execution phase** (clean API):
   ```python
   from mcp_codemode import mcp
   await mcp.github.create_issue(...)
   ```

### For Autonomous Agents

**Programmatic approach:**

```python
from mcp_codemode import mcp

# Agent doesn't know what tools exist
results = await mcp.search("what the agent needs")

# Use the results
server, tool = results[0].server, results[0].tool
await getattr(mcp, server).getattr(tool)(**args)
```

## Smart Search Implementation

Use embeddings or simple text matching:

```python
class SearchEngine:
    async def search(
        self,
        query: str,
        limit: int = 10
    ) -> list[SearchResult]:
        """Search across all servers for relevant tools."""

        # Option 1: Simple text matching
        # - Match against tool names
        # - Match against descriptions
        # - Rank by relevance

        # Option 2: Embeddings (better)
        # - Embed query
        # - Embed tool descriptions
        # - Cosine similarity
        # - Return top matches

        pass
```

## Caching Strategy

1. **Server list**: Cache for 5 minutes
2. **Tool list**: Cache per server for 5 minutes
3. **Tool schemas**: Cache indefinitely (rarely change)
4. **Stub files**: Regenerate on demand or on version change

## Discovery Flow for Real Task

**User:** "Find large log files and create a GitHub issue"

**Claude Code:**

```python
from mcp_codemode import mcp

# I don't know what's available, so search
# (Or use Glob if stubs exist)
file_tools = await mcp.search("list files")
# → filesystem.list_directory

issue_tools = await mcp.search("create issue")
# → github.create_issue

# Now I know what to use
files = await mcp.filesystem.list_directory(path="/var/log")

# Process locally (NO CONTEXT OVERHEAD!)
large = [f for f in files if f['size'] > 10_000_000]

# Create issue
await mcp.github.create_issue(
    repo="org/repo",
    title=f"Found {len(large)} large log files",
    body="..."
)
```

**Context used:**
- Search: ~50 tokens
- Tool calls: ~100 tokens (results only)
- **Total: ~150 tokens** vs 10,000+ traditional

## Key Insights

1. **LLMs don't need all schemas upfront** (just like humans don't memorize APIs)
2. **Search is powerful** (natural language → relevant tools)
3. **File-based perfect for Claude Code** (I already have Glob/Grep/Read!)
4. **Lazy loading is key** (load only what you use)
5. **Caching is critical** (schemas rarely change)

## Next Steps

1. Implement search engine (embeddings vs text matching?)
2. Implement stub generator
3. Decide: eager vs lazy stub generation?
4. Cache strategy details
