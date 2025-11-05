"""
Pytest configuration and fixtures.
"""

import pytest
import tempfile
from pathlib import Path
import json


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config(temp_dir):
    """Create a sample configuration file."""
    config_dir = temp_dir / ".codemode"
    config_dir.mkdir()

    config = {
        "mcpServers": {
            "test_server": {
                "command": "python",
                "args": ["-m", "test.mock_server"],
                "transport": "stdio"
            }
        }
    }

    config_file = config_dir / "config.json"
    with open(config_file, "w") as f:
        json.dump(config, f)

    return config_file


@pytest.fixture
def sample_config_with_env(temp_dir):
    """Create a config with environment variables."""
    config_dir = temp_dir / ".codemode"
    config_dir.mkdir()

    config = {
        "mcpServers": {
            "github": {
                "command": "mcp-server-github",
                "env": {
                    "GITHUB_TOKEN": "${GITHUB_TOKEN}",
                    "API_KEY": "${API_KEY}"
                },
                "transport": "stdio"
            }
        }
    }

    config_file = config_dir / "config.json"
    with open(config_file, "w") as f:
        json.dump(config, f)

    return config_file
