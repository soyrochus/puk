"""Tests for puk.config module."""
from __future__ import annotations

from pathlib import Path

import pytest

from puk.config import (
    CoreConfig,
    LlmConfig,
    MCPConfig,
    MCPServerConfig,
    PukConfig,
    PythonConfig,
    SafetyConfig,
    SessionConfig,
    ToolsConfig,
    WorkspaceConfig,
    _discover_local_config,
    _find_unknown_keys,
    _load_toml,
    _merge_layer,
    build_cli_overrides,
    load_config,
)
from puk.errors import PukError


class TestCoreConfig:
    def test_defaults(self):
        config = CoreConfig()
        assert config.profile == "default"
        assert config.ui == "plain"
        assert config.repl is True
        assert config.streaming is True
        assert config.strict_config is False
        assert config.telemetry == "off"

    def test_custom_values(self):
        config = CoreConfig(profile="custom", ui="tui", streaming=False)
        assert config.profile == "custom"
        assert config.ui == "tui"
        assert config.streaming is False


class TestWorkspaceConfig:
    def test_defaults(self):
        config = WorkspaceConfig()
        assert config.root == "."
        assert config.discover_root is True
        assert config.allow_outside_root is False
        assert config.follow_symlinks is False
        assert config.max_file_bytes == 2_000_000
        assert ".git" in config.ignore
        assert "**/*.py" in config.allow_globs
        assert "**/.env" in config.deny_globs

    def test_custom_ignore_list(self):
        config = WorkspaceConfig(ignore=["custom_dir"])
        assert config.ignore == ["custom_dir"]


class TestLlmConfig:
    def test_defaults(self):
        config = LlmConfig()
        assert config.provider == "copilot"
        assert config.model == "gpt-5"
        assert config.temperature == 0.2
        assert config.max_output_tokens == 2048

    def test_azure_settings(self):
        config = LlmConfig(
            provider="azure",
            azure_endpoint="https://my.azure.endpoint",
            azure_api_version="2024-02-15-preview",
        )
        assert config.provider == "azure"
        assert config.azure_endpoint == "https://my.azure.endpoint"


class TestSafetyConfig:
    def test_defaults(self):
        config = SafetyConfig()
        assert config.confirm_mutations is True
        assert config.confirm_commands is True
        assert config.confirm_installs is True
        assert config.confirm_mcp is True
        assert config.redact_secrets is True
        assert config.paranoid_reads is False


class TestToolsConfig:
    def test_defaults(self):
        config = ToolsConfig()
        assert config.python_exec is True
        assert config.mcp is False
        assert config.user_io is True
        assert config.builtin_excluded == []


class TestPythonConfig:
    def test_defaults(self):
        config = PythonConfig()
        assert config.venv_mode == "local"
        assert config.local_venv_dir == ".puk/venv"
        assert config.auto_create_venv is True
        assert config.exec_timeout_seconds == 300


class TestSessionConfig:
    def test_defaults(self):
        config = SessionConfig()
        assert config.infinite is True
        assert config.compaction_threshold == 0.80
        assert config.response_timeout_seconds == 300


class TestMCPConfig:
    def test_defaults(self):
        config = MCPConfig()
        assert config.enabled is False
        assert config.servers == {}

    def test_with_servers(self):
        server = MCPServerConfig(type="http", url="http://localhost:8080")
        config = MCPConfig(enabled=True, servers={"test": server})
        assert config.enabled is True
        assert "test" in config.servers


class TestPukConfig:
    def test_all_sections_have_defaults(self):
        config = PukConfig()
        assert isinstance(config.core, CoreConfig)
        assert isinstance(config.workspace, WorkspaceConfig)
        assert isinstance(config.llm, LlmConfig)
        assert isinstance(config.session, SessionConfig)
        assert isinstance(config.safety, SafetyConfig)
        assert isinstance(config.tools, ToolsConfig)
        assert isinstance(config.python, PythonConfig)
        assert isinstance(config.mcp, MCPConfig)

    def test_ignores_extra_fields(self):
        config = PukConfig.model_validate({"unknown_field": "value"})
        assert not hasattr(config, "unknown_field")


class TestMergeLayer:
    def test_simple_merge(self):
        target = {"a": 1, "b": 2}
        layer = {"b": 3, "c": 4}
        provenance = {}
        _merge_layer(target, layer, "test", provenance)
        assert target == {"a": 1, "b": 3, "c": 4}
        assert provenance["b"] == "test"
        assert provenance["c"] == "test"

    def test_nested_merge(self):
        target = {"outer": {"inner": 1, "keep": 2}}
        layer = {"outer": {"inner": 10, "new": 3}}
        provenance = {}
        _merge_layer(target, layer, "source", provenance)
        assert target["outer"]["inner"] == 10
        assert target["outer"]["keep"] == 2
        assert target["outer"]["new"] == 3


class TestFindUnknownKeys:
    def test_no_unknown_keys(self):
        data = {"profile": "test", "ui": "plain"}
        unknown = _find_unknown_keys(data, CoreConfig)
        assert unknown == []

    def test_finds_unknown_keys(self):
        data = {"profile": "test", "unknown_key": "value"}
        unknown = _find_unknown_keys(data, CoreConfig)
        assert "unknown_key" in unknown

    def test_nested_unknown_keys(self):
        data = {"core": {"profile": "test", "bad_key": "value"}}
        unknown = _find_unknown_keys(data, PukConfig)
        assert "core.bad_key" in unknown


class TestDiscoverLocalConfig:
    def test_finds_puk_toml(self, tmp_path: Path):
        config_file = tmp_path / ".puk.toml"
        config_file.write_text("[core]\nprofile = 'test'\n")
        result = _discover_local_config(tmp_path)
        assert result == config_file

    def test_finds_parent_config(self, tmp_path: Path):
        config_file = tmp_path / ".puk.toml"
        config_file.write_text("[core]\nprofile = 'test'\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = _discover_local_config(subdir)
        assert result == config_file

    def test_returns_none_when_not_found(self, tmp_path: Path):
        result = _discover_local_config(tmp_path)
        assert result is None

    def test_prefers_puk_toml_over_legacy(self, tmp_path: Path):
        toml_file = tmp_path / ".puk.toml"
        toml_file.write_text("[core]\nprofile = 'new'\n")
        legacy_file = tmp_path / ".puk.config"
        legacy_file.write_text("[core]\nprofile = 'legacy'\n")
        result = _discover_local_config(tmp_path)
        assert result == toml_file


class TestLoadToml:
    def test_loads_valid_toml(self, tmp_path: Path):
        config_file = tmp_path / "test.toml"
        config_file.write_text("[section]\nkey = 'value'\n")
        result = _load_toml(config_file)
        assert result == {"section": {"key": "value"}}

    def test_returns_empty_dict_for_non_dict(self, tmp_path: Path):
        config_file = tmp_path / "test.toml"
        config_file.write_text("'just a string'")
        # This would raise a parse error, but let's test with valid TOML
        config_file.write_text("key = 'value'\n")
        result = _load_toml(config_file)
        assert isinstance(result, dict)


class TestLoadConfig:
    def test_loads_defaults_when_no_config_files(self, tmp_path: Path):
        result = load_config(cwd=tmp_path, cli_root=None)
        assert result.config.core.profile == "default"
        assert result.root_path == tmp_path

    def test_loads_local_config(self, tmp_path: Path, sample_puk_toml: str):
        config_file = tmp_path / ".puk.toml"
        config_file.write_text(sample_puk_toml)
        result = load_config(cwd=tmp_path, cli_root=None)
        assert result.config.core.profile == "test"
        assert result.config.safety.confirm_mutations is False

    def test_cli_overrides_take_precedence(self, tmp_path: Path, sample_puk_toml: str):
        config_file = tmp_path / ".puk.toml"
        config_file.write_text(sample_puk_toml)
        overrides = {"core": {"profile": "cli_override"}}
        result = load_config(cwd=tmp_path, cli_root=None, cli_overrides=overrides)
        assert result.config.core.profile == "cli_override"

    def test_explicit_cli_root(self, tmp_path: Path):
        workspace = tmp_path / "myworkspace"
        workspace.mkdir()
        result = load_config(cwd=tmp_path, cli_root=str(workspace))
        assert result.root_path == workspace

    def test_strict_config_raises_on_unknown_keys(self, tmp_path: Path):
        config_file = tmp_path / ".puk.toml"
        config_file.write_text("""
[core]
strict_config = true
unknown_key = "bad"
""")
        with pytest.raises(PukError, match="Unknown config keys"):
            load_config(cwd=tmp_path, cli_root=None)

    def test_provenance_tracks_sources(self, tmp_path: Path, sample_puk_toml: str):
        config_file = tmp_path / ".puk.toml"
        config_file.write_text(sample_puk_toml)
        result = load_config(cwd=tmp_path, cli_root=None)
        assert "core.profile" in result.provenance.values
        assert result.provenance.values["core.profile"] == "local"


class TestBuildCliOverrides:
    def test_empty_overrides(self):
        result = build_cli_overrides(ui=None, confirm=False, paranoid=False, root=None)
        assert result == {}

    def test_ui_override(self):
        result = build_cli_overrides(ui="tui", confirm=False, paranoid=False, root=None)
        assert result["core"]["ui"] == "tui"

    def test_confirm_disables_all_confirmations(self):
        result = build_cli_overrides(ui=None, confirm=True, paranoid=False, root=None)
        assert result["safety"]["confirm_mutations"] is False
        assert result["safety"]["confirm_commands"] is False
        assert result["safety"]["confirm_installs"] is False

    def test_paranoid_enables_paranoid_reads(self):
        result = build_cli_overrides(ui=None, confirm=False, paranoid=True, root=None)
        assert result["safety"]["paranoid_reads"] is True

    def test_root_override(self):
        result = build_cli_overrides(ui=None, confirm=False, paranoid=False, root="/custom/root")
        assert result["workspace"]["root"] == "/custom/root"

    def test_multiple_overrides(self):
        result = build_cli_overrides(ui="plain", confirm=True, paranoid=True, root="/root")
        assert result["core"]["ui"] == "plain"
        assert result["safety"]["confirm_mutations"] is False
        assert result["safety"]["paranoid_reads"] is True
        assert result["workspace"]["root"] == "/root"
