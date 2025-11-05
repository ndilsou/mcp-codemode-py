"""
Tests for search functionality.
"""

import pytest
from mcp_codemode.search import simple_text_match, simple_search
from mcp_codemode.models import SearchResult


def test_exact_match():
    """Test exact text matching."""
    score = simple_text_match("read_file", "read_file")
    assert score == 1.0


def test_substring_match():
    """Test substring matching."""
    score = simple_text_match("read", "read_file")
    assert score == 0.8


def test_word_match():
    """Test word-level matching."""
    score = simple_text_match("file", "read file from disk")
    assert score > 0.5


def test_no_match():
    """Test no match."""
    score = simple_text_match("xyz", "abc def")
    assert score == 0.0


def test_simple_search():
    """Test searching tools."""
    tools = [
        {"name": "read_file", "description": "Read contents of a file"},
        {"name": "write_file", "description": "Write content to a file"},
        {"name": "list_directory", "description": "List files in a directory"},
    ]

    results = simple_search("read", tools, "filesystem")

    assert len(results) > 0
    assert results[0].tool == "read_file"
    assert results[0].server == "filesystem"
    assert results[0].score > 0


def test_simple_search_by_description():
    """Test searching by description."""
    tools = [
        {"name": "create_issue", "description": "Create a new GitHub issue"},
        {"name": "list_repos", "description": "List repositories"},
    ]

    results = simple_search("issue", tools, "github")

    assert len(results) > 0
    assert results[0].tool == "create_issue"


def test_simple_search_ordering():
    """Test that results are ordered by score."""
    tools = [
        {"name": "other_thing", "description": "Something else"},
        {"name": "read_file", "description": "Read a file"},
        {"name": "file_reader", "description": "Reads files"},
    ]

    results = simple_search("read file", tools, "test")

    assert len(results) >= 2
    # First result should have higher score
    assert results[0].score >= results[1].score
