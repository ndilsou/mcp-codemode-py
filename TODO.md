# TODO

## Immediate (for v0.2)

- [ ] **Integrate official MCP SDK** - Replace mock runtime.py with actual MCP client
  - Use `mcp` package for stdio/SSE transport
  - Load MCP configuration from standard locations
  - Connect to actual MCP servers

- [ ] **Configuration management**
  - Read from `~/.mcp/config.json` or similar
  - Support environment variables
  - Allow programmatic configuration

- [ ] **Testing**
  - Unit tests for core functionality
  - Integration tests with mock MCP server
  - Test stub generation
  - Test search functionality

## Future Enhancements

- [ ] **Advanced search** (optional)
  - Add embeddings-based search as opt-in
  - Keep text-based as default (lightweight)

- [ ] **Streaming support**
  - Handle streaming tool responses
  - Progress updates for long-running operations

- [ ] **Better error handling**
  - More informative error messages
  - Retry logic for transient failures
  - Graceful degradation

- [ ] **Performance optimizations**
  - Parallel tool calls
  - Connection pooling
  - Better caching strategies

- [ ] **Documentation**
  - API reference
  - More examples
  - Integration guides

- [ ] **Sandboxing** (optional)
  - Approach 4: Code execution sandbox
  - RestrictedPython integration
  - For autonomous agent use cases

## Nice to Have

- [ ] Generate typed client classes (like Approach 1)
- [ ] Support for custom transports
- [ ] Metrics and observability
- [ ] Interactive CLI (REPL mode)
- [ ] VS Code extension for stub exploration
