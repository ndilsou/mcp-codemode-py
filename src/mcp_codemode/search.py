"""
Text-based search for MCP tools.

Implements simple, lightweight text matching for tool discovery.
No embeddings, no heavy dependencies - just string matching with scoring.
"""

from typing import Any
from .models import SearchResult
from .runtime import get_runtime


def simple_text_match(query: str, text: str) -> float:
    """
    Calculate a simple relevance score between query and text.

    Uses multiple heuristics:
    - Exact match: 1.0
    - Word match: 0.8 per word
    - Substring match: 0.5
    - Token overlap: 0.3 per token

    Args:
        query: Search query
        text: Text to match against

    Returns:
        Relevance score between 0.0 and 1.0
    """
    query_lower = query.lower()
    text_lower = text.lower()

    # Exact match
    if query_lower == text_lower:
        return 1.0

    # Substring match
    if query_lower in text_lower:
        return 0.8

    # Word-level matching
    query_words = set(query_lower.split())
    text_words = set(text_lower.split())

    if query_words and text_words:
        overlap = len(query_words & text_words)
        if overlap > 0:
            # Partial credit based on overlap
            return 0.5 + (0.3 * overlap / len(query_words))

    # Token-level matching (for partial words)
    query_tokens = set(query_lower.replace("_", " ").split())
    text_tokens = set(text_lower.replace("_", " ").split())

    if query_tokens and text_tokens:
        overlap = len(query_tokens & text_tokens)
        if overlap > 0:
            return 0.3 * overlap / len(query_tokens)

    return 0.0


def simple_search(
    query: str,
    tools: list[dict],
    server_name: str
) -> list[SearchResult]:
    """
    Search tools using simple text matching.

    Args:
        query: Search query
        tools: List of tool info dicts
        server_name: Name of the server these tools belong to

    Returns:
        List of SearchResult objects, sorted by score
    """
    results = []

    for tool in tools:
        tool_name = tool.get("name", "")
        description = tool.get("description", "")

        # Match against both name and description
        name_score = simple_text_match(query, tool_name)
        desc_score = simple_text_match(query, description)

        # Combine scores (name weighted higher)
        combined_score = max(name_score * 1.0, desc_score * 0.7)

        if combined_score > 0:
            results.append(SearchResult(
                server=server_name,
                tool=tool_name,
                description=description,
                score=combined_score
            ))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)

    return results


async def search_all_servers(
    query: str,
    *,
    server_filter: str | None = None,
    limit: int = 10
) -> list[SearchResult]:
    """
    Search across all MCP servers for tools matching a query.

    Args:
        query: Search query
        server_filter: Optional server name to limit search
        limit: Maximum results to return

    Returns:
        List of SearchResult objects, sorted by relevance
    """
    runtime = await get_runtime()
    all_results = []

    # Get list of servers to search
    if server_filter:
        servers = [server_filter]
    else:
        servers = await runtime.list_servers()

    # Search each server
    for server_name in servers:
        try:
            tools = await runtime.list_server_tools_detailed(server_name)
            tool_dicts = [t.model_dump() for t in tools]

            results = simple_search(query, tool_dicts, server_name)
            all_results.extend(results)
        except Exception as e:
            # Skip servers that fail
            # TODO: Log warning
            pass

    # Sort all results by score
    all_results.sort(key=lambda r: r.score, reverse=True)

    # Return top N
    return all_results[:limit]


async def search_servers(query: str) -> list[str]:
    """
    Search for servers by name or capability.

    Args:
        query: Search query

    Returns:
        List of matching server names, sorted by relevance
    """
    runtime = await get_runtime()
    servers = await runtime.list_servers_detailed()

    results = []
    for server in servers:
        # Match against server name and description
        name_score = simple_text_match(query, server.name)
        desc_score = simple_text_match(query, server.description)

        combined_score = max(name_score * 1.0, desc_score * 0.8)

        if combined_score > 0:
            results.append((server.name, combined_score))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)

    return [name for name, _ in results]
