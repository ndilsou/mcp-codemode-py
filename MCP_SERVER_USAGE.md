# Example MCP Configuration Using Codemode as an MCP Server

## Dual Usage Modes

mcp-codemode can be used in two ways:

### 1. As a Library (Direct Python Usage)
```python
from mcp_codemode import mcp

# Configure in .codemode/config.json
result = await mcp.filesystem.read_file(path="/etc/hosts")
```

### 2. As an MCP Server (Meta-MCP Pattern)
Configure codemode itself as an MCP server that provides efficient access to other MCP servers.

## Configuration Example

In your main MCP configuration (e.g., Claude Desktop's `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "codemode": {
      "command": "python",
      "args": ["-m", "mcp_codemode.server_main"],
      "env": {
        "CODEMODE_CONFIG": "${HOME}/.codemode/config.json"
      },
      "transport": "stdio"
    }
  }
}
```

Or using uv:
```json
{
  "mcpServers": {
    "codemode": {
      "command": "uvx",
      "args": ["--from", "mcp-codemode-py", "python", "-m", "mcp_codemode.server_main"],
      "transport": "stdio"
    }
  }
}
```

## Codemode Configuration

In `.codemode/config.json` (or `~/.codemode/config.json`), configure the MCP servers that codemode will manage:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/workspace"],
      "transport": "stdio"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "transport": "stdio"
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "transport": "stdio"
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}"
      },
      "transport": "stdio"
    }
  }
}
```

## Available Tools

When using codemode as an MCP server, you get these tools:

### 1. `search_tools`
Search across all configured MCP servers for relevant tools.

```json
{
  "query": "create issue",
  "limit": 10
}
```

Returns ranked results with server, tool name, description, and relevance score.

### 2. `list_servers`
List all configured MCP servers.

```json
{
  "detailed": true
}
```

### 3. `list_tools`
List tools available on a specific server.

```json
{
  "server": "github",
  "detailed": true
}
```

### 4. `get_tool_schema`
Get the complete JSON schema for a tool.

```json
{
  "server": "github",
  "tool": "create_issue"
}
```

### 5. `execute_code` (Most Efficient!)
Execute Python code with access to all MCP servers via the `mcp` object.

```json
{
  "code": "files = await mcp.filesystem.list_directory(path='/var/log')\nlarge = [f for f in files if f['size'] > 1_000_000]\nreturn {'count': len(large), 'files': large[:5]}"
}
```

This is the most context-efficient approach - execute multi-step operations in a single call!

### 6. `call_tool`
Direct tool call (less efficient than execute_code for multi-step operations).

```json
{
  "server": "filesystem",
  "tool": "read_file",
  "arguments": {"path": "/etc/hosts"}
}
```

## Benefits of the Meta-MCP Pattern

### Context Efficiency
- **Traditional**: Each MCP server adds ~200 tokens per tool × 10 tools = 2,000+ tokens per server
- **With Codemode**: 6 tools total (~1,200 tokens) for access to unlimited servers/tools
- **Reduction**: 90%+ reduction even before execute_code optimization

### Progressive Disclosure
1. Start with just 6 codemode tools in context
2. Search or list to discover what you need
3. Execute code or call tools as needed
4. Only load schemas on demand

### Multi-Server Operations
Execute code that spans multiple servers in one call:

```python
# Search code, create issue, notify team - one call!
code = """
# Search filesystem
files = await mcp.filesystem.list_directory(path='/src')
large_files = [f for f in files if f['size'] > 1_000_000]

# Create GitHub issue
issue = await mcp.github.create_issue(
    repo='myorg/myrepo',
    title=f'Found {len(large_files)} large files',
    body='See analysis...'
)

# Notify on Slack
await mcp.slack.send_message(
    channel='#alerts',
    text=f'Created issue #{issue["number"]}'
)

return {'issue': issue['number'], 'files_found': len(large_files)}
"""
```

All in one tool call, no context bloat!

## Context Comparison

### Traditional Approach
```
Load 3 servers × 10 tools each × 200 tokens = 6,000 tokens
+ Tool call results
+ Multi-step round-trips
= 20,000+ tokens for complex operations
```

### Codemode as Library
```
Load tools on-demand
+ Execute code locally
= 500-1,000 tokens
```

### Codemode as MCP Server
```
Load 6 codemode tools = 1,200 tokens
+ execute_code with multi-server logic = minimal
= 1,500 tokens total (no matter how many underlying servers!)
```

## When to Use Each Mode

### Use as Library
- Direct Python scripting
- Application integration
- When you have a Python execution environment

### Use as MCP Server
- With Claude Desktop or similar MCP clients
- When you want to manage many MCP servers efficiently
- When you need the meta-MCP pattern for context efficiency
- When you want to share catalog configuration across tools

## Example Workflow

**User**: "Find large files in my project and create a GitHub issue about them"

**With Traditional MCP**:
- LLM sees 20+ tools from filesystem and github servers
- Makes multiple tool calls
- Context bloated with intermediate results

**With Codemode MCP**:
```json
{
  "tool": "execute_code",
  "arguments": {
    "code": "files = await mcp.filesystem.list_directory(path='.')\nlarge = [f for f in files if f['size'] > 1_000_000]\nissue = await mcp.github.create_issue(repo='user/repo', title=f'{len(large)} large files', body='Details...')\nreturn {'issue': issue['number'], 'count': len(large)}"
  }
}
```

Single tool call, minimal context, maximum efficiency!

## Installation

```bash
# Install mcp-codemode
pip install mcp-codemode-py

# Or with uv
uv pip install mcp-codemode-py
```

Then configure as shown above in your MCP client configuration.
