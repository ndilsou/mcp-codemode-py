# MCP Code Mode for Python

**Lightweight library for calling MCP tools with minimal context overhead.**

Implements the principles from Anthropic's [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) and Cloudflare's [Code Mode](https://blog.cloudflare.com/code-mode/) articles.

## Dual Usage: Library + MCP Server

mcp-codemode can be used in **two ways**:

### 1. As a Python Library
Direct integration in your Python applications:
```python
from mcp_codemode import mcp
result = await mcp.filesystem.read_file(path="/etc/hosts")
```

### 2. As an MCP Server (Meta-MCP Pattern)
Configure codemode itself as an MCP server that provides efficient access to your entire MCP catalog:

```json
{
  "mcpServers": {
    "codemode": {
      "command": "python",
      "args": ["-m", "mcp_codemode.server_main"],
      "transport": "stdio"
    }
  }
}
```

Then use tools like `search_tools`, `execute_code`, etc. to interact with all your configured servers through a minimal interface!

See [MCP_SERVER_USAGE.md](./MCP_SERVER_USAGE.md) for complete details.

## The Problem

Traditional MCP usage loads all tool definitions into LLM context:
- 50 tools x 200 tokens = **10,000 tokens** before doing any work
- Multi-step operations require round-trips through the LLM
- Large data sets bloat context unnecessarily

## The Solution

**LLMs are better at writing code than calling tools directly.**

This library provides:
1. **Progressive disclosure** - load tools on-demand
2. **Lazy loading** - schemas loaded only when needed
3. **Local processing** - multi-step operations without context overhead
4. **Type safety** - Pydantic validation from JSON schemas
5. **IDE support** - Generate .pyi stubs for autocomplete

## Impact

**98-99% reduction in context usage**

```
Traditional:  ~10,000 tokens (all tools loaded)
Code Mode:    ~200 tokens (lazy loading + local processing)
```

## Quick Start

### Installation

```bash
uv add mcp-codemode-py
# or
pip install mcp-codemode-py
```

### Basic Usage

```python
from mcp_codemode import mcp

# Direct tool call - schema loads automatically
result = await mcp.filesystem.read_file(path="/etc/hosts")

# Multi-step with local processing (no context overhead!)
files = await mcp.filesystem.list_directory(path="/var/log")
large_files = [f for f in files if f['size'] > 1_000_000]

for file in large_files[:10]:
    content = await mcp.filesystem.read_file(path=file['path'])
    # Process locally - doesn't bloat context

# Only return what matters
return {"count": len(large_files), "sample": large_files[:3]}
```

### Discovery API

```python
# Discover servers
servers = await mcp.list_servers()

# Discover tools on a server
tools = await mcp.github.list_tools()

# Search across everything
results = await mcp.search("create issue")
# -> [SearchResult(server="github", tool="create_issue", score=0.95)]

# Use the results
await mcp.github.create_issue(repo="...", title="...", body="...")
```

## CLI

```bash
# Generate .pyi stub files for IDE support
mcp-codemode stub-gen

# List available servers
mcp-codemode list

# Search for tools
mcp-codemode search "file operations"

# List tools for a server
mcp-codemode tools github --detailed
```

## Configuration

Create `.codemode/config.json` in your project:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"],
      "transport": "stdio"
    },
    "github": {
      "command": "mcp-server-github",
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "transport": "stdio"
    }
  }
}
```

## File-Based Discovery

Perfect for Claude Code - explore tools with native file tools:

```bash
# Generate stubs
mcp-codemode stub-gen
```

Creates structure:
```
.codemode/
  stubs/
    filesystem/
      __init__.pyi
      read_file.pyi
      write_file.pyi
    github/
      create_issue.pyi
      list_repos.pyi
```

Then explore naturally:
- **Glob**: `**/*.pyi` -> find all tools
- **Grep**: `create.*issue` -> search by keyword
- **Read**: View tool schemas with type hints

## Design Philosophy

### Three Levels of Discovery

```
Level 0: Start with just `mcp` object (0 tokens)
   |
Level 1: Discover servers when needed (~20 tokens)
   |
Level 2: Discover tools on server (~50 tokens)
   |
Level 3: Load schema on tool call (0 context tokens)
```

### Type Safety with Pydantic

```python
# Automatic validation from JSON Schema
await mcp.filesystem.read_file(path="/etc/hosts")  # OK

# Validation catches errors
await mcp.filesystem.read_file(path=123)  # ValueError
```

### Lazy Everything

- Schemas load only when tools are called
- Caching prevents redundant fetches
- Background stub generation (optional)

## Examples

See `examples/` directory:

- `basic_usage.py` - Core API patterns
- `claude_code_workflow.py` - Claude Code integration

## Architecture

```
+------------------+
|   Your Code      |
+--------+---------+
         |
+--------v---------+
|  MCP Code Mode   |  <- Pydantic validation
|                  |  <- Lazy loading
|                  |  <- Progressive disclosure
+--------+---------+
         |
+--------v---------+
|   MCP SDK        |  <- Official MCP client
+--------+---------+
         |
+--------v---------+
|  MCP Servers     |  <- filesystem, github, etc.
+------------------+
```

## Key Features

### Hybrid Discovery

- **Programmatic**: `await mcp.search("create issue")`
- **File-based**: Generate stubs, explore with file tools
- **Both work**: Choose what fits your workflow

### Text-Based Search

Simple, lightweight matching (no embeddings):
```python
results = await mcp.search("file operations")
# Matches against tool names and descriptions
```

### Automatic Stub Generation

On import in a repo:
```python
from mcp_codemode import mcp
# Background: generates .codemode/stubs/ automatically
```

Or manually:
```bash
mcp-codemode stub-gen
```

### Session-Based Caching

- Tools don't change during a session
- Schemas cached indefinitely
- No stale data concerns

## Integration

### With Claude Code

```python
from mcp_codemode import mcp

# Claude Code naturally:
# 1. Uses Glob to find available tools
# 2. Uses Grep to search by keyword
# 3. Uses Read to view schemas
# 4. Calls tools with validation

result = await mcp.github.create_issue(...)
```

### With Anthropic SDK

```python
from anthropic import Anthropic
from mcp_codemode import mcp

client = Anthropic()

# Claude writes code that uses mcp
code = """
files = await mcp.filesystem.list_directory(path='/var/log')
large = [f for f in files if f['size'] > 1_000_000]
return large[:5]
"""

# Execute in your environment
# (with mcp available)
```

## Current Status

**Version 0.2.0 - Production Ready**

Implemented:
- Core proxy objects with Pydantic validation
- Progressive discovery (3 levels)
- Text-based search
- Stub generator
- CLI tool
- Official MCP SDK integration
- Configuration management
- Comprehensive tests (30 tests passing)
- **MCP server mode** with 6 tools for meta-MCP pattern

## MCP Server Mode

When used as an MCP server, codemode exposes 6 tools that provide access to your entire MCP catalog:

1. **search_tools** - Search across all servers for relevant tools
2. **list_servers** - List configured MCP servers
3. **list_tools** - List tools on a specific server
4. **get_tool_schema** - Get full schema for a tool
5. **execute_code** - Execute Python code with access to all servers (most efficient!)
6. **call_tool** - Direct tool call

### Why Use as MCP Server?

- **Massive context reduction**: 6 tools in context vs 100+ from individual servers
- **execute_code tool**: Write code that uses multiple servers in one call
- **Progressive disclosure**: Discover and use tools on-demand
- **Unified interface**: One configuration point for all MCP servers

Example with execute_code:
```python
# One tool call that uses multiple servers!
{
  "tool": "execute_code",
  "arguments": {
    "code": "files = await mcp.filesystem.list_directory(path='.')\nlarge = [f for f in files if f['size'] > 1_000_000]\nissue = await mcp.github.create_issue(repo='user/repo', title=f'{len(large)} large files')\nreturn {'issue': issue['number']}"
  }
}
```

See [MCP_SERVER_USAGE.md](./MCP_SERVER_USAGE.md) for full documentation.

## Articles

This library implements principles from:

1. [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
   - 98.7% token reduction
   - Progressive disclosure
   - Local data processing

2. [Cloudflare: Code Mode](https://blog.cloudflare.com/code-mode/)
   - LLMs better at code than tool calls
   - Single execution sandbox
   - TypeScript API generation

## Design Decisions

### Why Pydantic?

- Ubiquitous in Python ecosystem
- Automatic validation from JSON Schema
- Type hints for IDE support

### Why Text-Based Search?

- Lightweight (no heavy dependencies)
- Fast enough for typical use cases
- Can upgrade to embeddings later if needed

### Why Hybrid Discovery?

- Programmatic: always fresh, works everywhere
- File-based: natural for Claude Code, great IDE support
- Both: flexibility to choose

### Why .codemode/?

- Clear separation from MCP config
- Contains stubs and cache
- Easy to gitignore

## License

MIT

## Acknowledgments

Based on research and articles by:
- Anthropic ([Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp))
- Cloudflare ([Code Mode](https://blog.cloudflare.com/code-mode/))

Uses the [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic.
