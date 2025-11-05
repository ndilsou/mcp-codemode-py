# Design Reflection: MCP Code Mode for Python

## Core Insight from Articles

Both Anthropic and Cloudflare discovered the same thing: **LLMs are dramatically better at writing code than making tool calls**.

### Why?
- LLMs trained on millions of real-world code examples
- Only trained on synthetic tool-calling examples
- Code feels natural; tool calling feels artificial

### Impact
- **98.7% token reduction** (150K → 2K tokens)
- Multi-step operations without round-trips
- Local data processing/filtering
- Leverage LLM's core strength

## Four Approaches Explored

### 1. Generated Modules ✨ (Most Pythonic)
```python
from mcp_codemode.servers.filesystem import read_file
result = await read_file(path="/etc/hosts")
```

**Feel:** Natural, explicit, exactly like using any Python library

**Pros:** Best IDE support, type checking, familiar patterns
**Cons:** Generation overhead, filesystem footprint

### 2. Proxy Objects 🪄 (Most Flexible)
```python
from mcp_codemode import mcp
result = await mcp.filesystem.read_file(path="/etc/hosts")
```

**Feel:** Magic, but convenient; minimal boilerplate

**Pros:** Lazy loading, zero generation, simple
**Cons:** No static types, less IDE support, "magic"

### 3. Pydantic Hybrid 🎯 (My Favorite)
```python
from mcp_codemode import mcp
result = await mcp.filesystem.read_file(path="/etc/hosts")
# + Pydantic validation
# + .pyi stubs for IDE
```

**Feel:** Best of both worlds—convenient AND safe

**Pros:** Type-safe, validated, IDE support, lazy loading
**Cons:** Slightly more complex

### 4. Cloudflare Style 🔒 (Most Context-Efficient)
```python
# LLM sees ONE tool: "execute_python"
# LLM writes code that runs in sandbox
code = """
files = await mcp.filesystem.list_directory(path="/var/log")
large = [f for f in files if f['size'] > 1MB]
return large[:5]
"""
```

**Feel:** Pure Cloudflare model—radical context reduction

**Pros:** Minimal LLM context, multi-step in one go
**Cons:** Sandboxing complexity, debugging harder

## My Recommendation

**Hybrid approach combining #3 and #4:**

### For Claude Code (my use case):
Use **Approach 3 (Pydantic Hybrid)** because:
1. I (Claude) already run in a controlled environment
2. I write code directly in files you can see
3. We want type safety and validation
4. IDE support helps developers understand MCP tools

### For Agent Frameworks (like Anthropic/Cloudflare):
Use **Approach 4 (Code Execution)** because:
1. Agent needs to make decisions autonomously
2. Single tool = minimal context
3. Sandbox provides security
4. Multi-step operations without LLM round-trips

## Implementation Taste

What feels "right" to me as a Pythonic API:

```python
# Simple import
from mcp_codemode import mcp

# Optional: explicit connection (for auth, config)
await mcp.connect("filesystem", config={...})

# Natural usage with validation
result = await mcp.filesystem.read_file(path="/etc/hosts")

# Multi-step - processed locally
files = await mcp.filesystem.list_directory(path="/var/log")
large_files = [f for f in files if f['size'] > 1_000_000]

for file in large_files[:10]:
    content = await mcp.filesystem.read_file(path=file['path'])
    # Analyze without context overhead

# Only return what matters
return {"count": len(large_files), "sample": large_files[:3]}
```

### Key Design Principles

1. **Lazy Everything**
   - Only load schemas when tools are called
   - Cache aggressively
   - Progressive disclosure

2. **Type Safety**
   - Pydantic models from JSON Schema
   - Runtime validation
   - Generate .pyi stubs for IDE

3. **Zero Boilerplate**
   - One import: `from mcp_codemode import mcp`
   - No configuration unless needed
   - Works immediately

4. **Pythonic**
   - Async/await throughout
   - Context managers for connections
   - Type hints everywhere (3.13+)

5. **Debuggable**
   - Clear error messages
   - Schema validation errors show what's wrong
   - Logs show actual MCP calls

## Technical Stack

- **Python 3.13+** (latest type hint features)
- **Pydantic v2** (validation + JSON Schema)
- **uv** (fast package management)
- **httpx** (async MCP communication)
- **RestrictedPython** (optional sandbox for Approach 4)

## Next Steps

1. **Converge on design** with user feedback
2. **Build core runtime** (MCP client, connection management)
3. **Implement chosen approach** (likely #3)
4. **Add stub generation** (.pyi files)
5. **Testing & examples**
6. **Production polish**

## Open Questions for Discussion

1. **Which approach feels best to you?** #3 is my favorite, but I'd love your input
2. **Sandbox support?** Should we support Approach 4 for agent frameworks?
3. **Connection management?** Explicit connect() or automatic?
4. **Error handling?** Raise exceptions or return Result types?
5. **Streaming?** Should tools support streaming responses?
6. **Caching?** How aggressive should schema caching be?

## Context Efficiency Example

Traditional approach:
```
LLM: [sees 50 tool definitions = 10K tokens]
LLM: Use list_directory
Tool: [returns 500 files = 5K tokens]
LLM: [processes, sees all data]
LLM: Use read_file on file X
Tool: [returns content = 10K tokens]
LLM: [processes]
LLM: Use create_issue
Total: ~25K+ tokens
```

Code Mode approach:
```
LLM: [sees 1-3 tool definitions or writes code directly]
Code:
  files = await list_directory()
  large = [f for f in files if f['size'] > 1MB]
  content = await read_file(large[0])
  # analyze locally
  await create_issue(...)
Result: "Created issue #123" = 20 tokens
Total: ~500 tokens
```

**50x reduction** in context usage!
