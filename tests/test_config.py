"""
Tests for configuration management.
"""

import pytest
import os
from pathlib import Path

from mcp_codemode.config import ConfigManager, Config, ServerConfig


def test_config_model():
    """Test configuration model validation."""
    config = Config(
        mcpServers={
            "filesystem": ServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                transport="stdio"
            )
        }
    )

    assert "filesystem" in config.mcpServers
    assert config.mcpServers["filesystem"].command == "npx"
    assert config.mcpServers["filesystem"].transport == "stdio"


def test_config_load(sample_config):
    """Test loading configuration from file."""
    manager = ConfigManager(sample_config)
    config = manager.load()

    assert "test_server" in config.mcpServers
    assert config.mcpServers["test_server"].command == "python"


def test_config_env_expansion(sample_config_with_env, monkeypatch):
    """Test environment variable expansion."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_123")
    monkeypatch.setenv("API_KEY", "api_key_456")

    manager = ConfigManager(sample_config_with_env)
    config = manager.load()

    assert config.mcpServers["github"].env["GITHUB_TOKEN"] == "test_token_123"
    assert config.mcpServers["github"].env["API_KEY"] == "api_key_456"


def test_config_env_expansion_missing(sample_config_with_env):
    """Test that missing env vars are left as-is."""
    manager = ConfigManager(sample_config_with_env)
    config = manager.load()

    # Should keep original if env var not set
    assert "${GITHUB_TOKEN}" in config.mcpServers["github"].env.get("GITHUB_TOKEN", "")


def test_config_not_found():
    """Test behavior when config file doesn't exist."""
    manager = ConfigManager("/nonexistent/path/config.json")
    config = manager.load()

    # Should return empty config
    assert len(config.mcpServers) == 0


def test_config_search_hierarchy(temp_dir):
    """Test config file search in parent directories."""
    # Save current directory
    original_cwd = Path.cwd()

    try:
        # Create config in parent directory
        parent_config_dir = temp_dir / ".codemode"
        parent_config_dir.mkdir()

        config_file = parent_config_dir / "config.json"
        config_file.write_text('{"mcpServers": {"test": {"command": "echo"}}}')

        # Search from subdirectory
        sub_dir = temp_dir / "subdir" / "nested"
        sub_dir.mkdir(parents=True)

        os.chdir(sub_dir)

        manager = ConfigManager()
        resolved_path = manager._resolve_config_path(None)

        # Should find parent config
        assert resolved_path == config_file
    finally:
        # Restore original directory
        os.chdir(original_cwd)


def test_create_default_config(temp_dir):
    """Test creating default configuration."""
    # Create config at explicit path
    config_path = temp_dir / ".codemode" / "config.json"

    manager = ConfigManager()
    created_path = manager.create_default_config(config_path)

    assert created_path == config_path
    assert config_path.exists()

    # Load and verify
    manager2 = ConfigManager(config_path)
    config = manager2.load()

    assert "filesystem" in config.mcpServers
