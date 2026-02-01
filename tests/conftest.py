"""Common fixtures for puk tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_puk_toml() -> str:
    """Return sample .puk.toml content."""
    return """
[core]
profile = "test"
ui = "plain"

[workspace]
root = "."
max_file_bytes = 1000000

[llm]
provider = "copilot"
model = "gpt-4"

[safety]
confirm_mutations = false
"""


@pytest.fixture
def sample_global_config() -> str:
    """Return sample global config content."""
    return """
[core]
ui = "tui"
streaming = true

[workspace]
ignore = [".git", "node_modules", "__pycache__"]
"""
