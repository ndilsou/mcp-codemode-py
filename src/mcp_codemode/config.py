"""
Configuration management for MCP Code Mode.

Reads configuration from .codemode/config.json
"""

import json
import os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: Literal["stdio", "sse"] = "stdio"
    url: str | None = None  # For SSE transport


class Config(BaseModel):
    """Main configuration for MCP Code Mode."""

    mcpServers: dict[str, ServerConfig] = Field(default_factory=dict)
    stubDir: str = ".codemode/stubs"
    cacheEnabled: bool = True


class ConfigManager:
    """Manages configuration loading and environment variable expansion."""

    def __init__(self, config_path: Path | str | None = None):
        self.config_path = self._resolve_config_path(config_path)
        self._config: Config | None = None

    def _resolve_config_path(self, config_path: Path | str | None) -> Path:
        """
        Resolve the configuration file path.

        Search order:
        1. Explicit path if provided
        2. .codemode/config.json in current directory
        3. .codemode/config.json in parent directories (walk up)
        4. ~/.codemode/config.json (user home)
        """
        if config_path:
            return Path(config_path)

        # Search in current directory and parents
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            candidate = parent / ".codemode" / "config.json"
            if candidate.exists():
                return candidate

        # Fall back to home directory
        home_config = Path.home() / ".codemode" / "config.json"
        return home_config

    def load(self) -> Config:
        """
        Load configuration from file.

        Returns:
            Config object with expanded environment variables

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config is invalid JSON
            ValidationError: If config doesn't match schema
        """
        if not self.config_path.exists():
            # Return empty config if no file found
            return Config()

        with open(self.config_path) as f:
            data = json.load(f)

        # Expand environment variables
        data = self._expand_env_vars(data)

        # Validate and parse
        self._config = Config(**data)
        return self._config

    def _expand_env_vars(self, data: dict) -> dict:
        """
        Recursively expand environment variables in config.

        Supports ${VAR_NAME} syntax.
        """
        if isinstance(data, dict):
            return {k: self._expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._expand_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Expand ${VAR_NAME} patterns
            import re

            def replace_env_var(match):
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))

            return re.sub(r'\$\{([^}]+)\}', replace_env_var, data)
        else:
            return data

    def get(self) -> Config:
        """Get loaded config, loading if not already loaded."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def create_default_config(self, path: Path | None = None) -> Path:
        """
        Create a default configuration file.

        Args:
            path: Path to create config at (default: .codemode/config.json)

        Returns:
            Path to created config file
        """
        if path is None:
            path = Path.cwd() / ".codemode" / "config.json"

        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Default configuration
        default_config = {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        str(Path.cwd())
                    ],
                    "transport": "stdio"
                }
            }
        }

        with open(path, "w") as f:
            json.dump(default_config, f, indent=2)

        return path


# Global config manager instance
_config_manager: ConfigManager | None = None


def get_config_manager(config_path: Path | str | None = None) -> ConfigManager:
    """Get or create the global config manager."""
    global _config_manager
    if _config_manager is None or config_path is not None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


def load_config(config_path: Path | str | None = None) -> Config:
    """Convenience function to load configuration."""
    manager = get_config_manager(config_path)
    return manager.load()
