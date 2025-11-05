"""
Approach 4: Cloudflare-Style Code Execution

Philosophy:
- Instead of exposing many tools to LLM, expose ONE tool: "execute_python"
- LLM writes Python code that uses MCP tools
- Code runs in isolated sandbox
- Results returned via stdout/return value

This is the pure Cloudflare model adapted for Python:
- Cloudflare: TypeScript code runs in V8 isolate
- Us: Python code runs in subprocess/RestrictedPython

Key insight from Cloudflare:
"Instead of being presented with all the tools of all the connected MCP servers,
our agent is presented with just one tool, which simply executes some TypeScript code."

Pros:
- Minimal LLM context (only one tool definition!)
- Multi-step operations in single execution
- No tool-calling overhead
- LLM writes natural Python code

Cons:
- Requires secure Python sandboxing (harder than JS isolates)
- Debugging sandboxed code is trickier
- Less control over individual tool calls
"""

from typing import Any
import asyncio
import sys
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr


# === The Single Tool for the LLM ===

EXECUTE_PYTHON_TOOL = {
    "name": "execute_python",
    "description": """
Execute Python code with access to MCP servers via the `mcp` object.

Available servers and tools can be accessed via:
- mcp.filesystem.read_file(path="...")
- mcp.github.create_issue(repo="...", title="...", body="...")
- mcp.slack.send_message(channel="...", text="...")

The code should use `print()` to output results that will be returned to the LLM.
You can also `return` a value from the code.

Example:
```python
# Multi-step operation
files = await mcp.filesystem.list_directory(path="/var/log")
large_files = [f for f in files['entries'] if f['size'] > 1_000_000]

# Process locally
for file in large_files[:5]:
    content = await mcp.filesystem.read_file(path=file['path'])
    # Analyze content...

print(f"Found {len(large_files)} large files")
return large_files[:5]
```
""".strip(),
    "inputSchema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute"
            }
        },
        "required": ["code"]
    }
}


# === Sandbox Implementation ===

class PythonSandbox:
    """Secure Python code execution sandbox."""

    def __init__(self, mcp_instance):
        self.mcp = mcp_instance

    async def execute(self, code: str) -> dict[str, Any]:
        """
        Execute Python code in a sandbox with MCP access.

        Returns:
            Dict with 'stdout', 'stderr', 'return_value', 'success'
        """
        # Capture stdout/stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        # Build safe globals
        safe_globals = {
            "__builtins__": self._get_safe_builtins(),
            "mcp": self.mcp,
            "print": print,  # Will be captured
            # Add other safe built-ins as needed
        }

        result = {
            "stdout": "",
            "stderr": "",
            "return_value": None,
            "success": False
        }

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Compile code
                compiled = compile(code, "<sandbox>", "exec")

                # Execute in controlled namespace
                exec_locals = {}
                exec(compiled, safe_globals, exec_locals)

                # If code defined an async main function or returned coroutine
                if "main" in exec_locals and asyncio.iscoroutinefunction(exec_locals["main"]):
                    return_value = await exec_locals["main"]()
                elif exec_locals and asyncio.iscoroutine(list(exec_locals.values())[-1]):
                    return_value = await list(exec_locals.values())[-1]
                else:
                    return_value = exec_locals.get("result")

                result["return_value"] = return_value
                result["success"] = True

        except Exception as e:
            result["stderr"] += f"Error: {type(e).__name__}: {e}\n"
            result["success"] = False

        result["stdout"] = stdout_capture.getvalue()
        result["stderr"] += stderr_capture.getvalue()

        return result

    def _get_safe_builtins(self) -> dict:
        """Return a restricted set of builtins."""
        # This is a simple example - production would use RestrictedPython
        safe = {}
        safe_names = [
            "abs", "all", "any", "bool", "dict", "enumerate", "filter",
            "float", "int", "len", "list", "map", "max", "min", "range",
            "sorted", "str", "sum", "tuple", "zip", "isinstance", "type"
        ]
        for name in safe_names:
            safe[name] = __builtins__[name]
        return safe


# === Better Sandbox with RestrictedPython ===

class RestrictedPythonSandbox:
    """
    More secure sandbox using RestrictedPython.

    RestrictedPython compiles Python code with restrictions:
    - No imports
    - No file access
    - No dangerous builtins
    - Can restrict attribute access
    """

    def __init__(self, mcp_instance):
        self.mcp = mcp_instance

    async def execute(self, code: str) -> dict[str, Any]:
        """Execute code with RestrictedPython."""
        try:
            from RestrictedPython import compile_restricted, safe_globals
            from RestrictedPython.Eval import default_guarded_getitem
            from RestrictedPython.Guards import guarded_iter_unpack_sequence

            stdout_capture = StringIO()
            result = {
                "stdout": "",
                "stderr": "",
                "return_value": None,
                "success": False
            }

            # Compile with restrictions
            byte_code = compile_restricted(
                code,
                filename="<sandbox>",
                mode="exec"
            )

            if byte_code.errors:
                result["stderr"] = "\n".join(byte_code.errors)
                return result

            # Build restricted globals
            restricted_globals = {
                **safe_globals,
                "__builtins__": self._get_safe_builtins(),
                "_getitem_": default_guarded_getitem,
                "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
                "mcp": self.mcp,
                "_print_": lambda *args, **kwargs: print(*args, **kwargs, file=stdout_capture),
            }

            with redirect_stdout(stdout_capture):
                exec_locals = {}
                exec(byte_code.code, restricted_globals, exec_locals)

                # Handle async main
                if "main" in exec_locals and asyncio.iscoroutinefunction(exec_locals["main"]):
                    return_value = await exec_locals["main"]()
                else:
                    return_value = exec_locals.get("result")

                result["return_value"] = return_value
                result["stdout"] = stdout_capture.getvalue()
                result["success"] = True

        except Exception as e:
            result["stderr"] = f"Error: {type(e).__name__}: {e}"
            result["success"] = False

        return result

    def _get_safe_builtins(self) -> dict:
        """Restricted builtins for sandbox."""
        return {
            "abs": abs, "all": all, "any": any, "bool": bool,
            "dict": dict, "enumerate": enumerate, "filter": filter,
            "float": float, "int": int, "len": len, "list": list,
            "map": map, "max": max, "min": min, "range": range,
            "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
            "zip": zip, "print": print,
        }


# === How this integrates with Claude Code ===

async def claude_code_integration():
    """
    With this approach, Claude Code would:

    1. See only ONE tool: execute_python
    2. Write Python code to accomplish tasks
    3. Code runs in sandbox with MCP access
    4. Results returned in one shot
    """

    # Claude sees this tool definition
    tool_definition = EXECUTE_PYTHON_TOOL

    # Claude writes code like this:
    code = """
# Fetch documentation and create GitHub issue
docs = await mcp.filesystem.read_file(path="/docs/API.md")

# Search for specific section
lines = docs['content'].split('\\n')
auth_section = [l for l in lines if 'authentication' in l.lower()]

# Create issue with findings
issue = await mcp.github.create_issue(
    repo="myorg/myrepo",
    title="Update authentication docs",
    body=f"Found {len(auth_section)} references to auth. Need update."
)

print(f"Created issue #{issue['number']}")
return issue
"""

    # Execute in sandbox
    from mcp_codemode import mcp
    sandbox = PythonSandbox(mcp)
    result = await sandbox.execute(code)

    # Return to Claude
    return {
        "output": result["stdout"],
        "result": result["return_value"],
        "error": result["stderr"] if not result["success"] else None
    }


# === Context Comparison ===

CONTEXT_COMPARISON = """
Traditional Tool Calling:
- LLM sees: 50 tool definitions × ~200 tokens = 10,000 tokens
- For multi-step: each tool result goes through LLM
- Example: List files (500 tokens) → LLM → Read file (5000 tokens) → LLM → Create issue (300 tokens)
- Total: ~16,000 tokens

Code Mode:
- LLM sees: 1 tool definition = ~300 tokens
- Multi-step happens in sandbox
- Example: List → filter → read → create in single execution
- Results only: "Created issue #123" = ~20 tokens
- Total: ~320 tokens

98% reduction! Just like Anthropic's article showed.
"""


if __name__ == "__main__":
    print(__doc__)
    print("\n" + CONTEXT_COMPARISON)
