from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field

from .errors import PukError


class CoreConfig(BaseModel):
    profile: str = "default"
    ui: Literal["tui", "plain"] = "plain"
    repl: bool = True
    streaming: bool = True
    strict_config: bool = False
    telemetry: Literal["off", "local"] = "off"


class WorkspaceConfig(BaseModel):
    root: str = "."
    discover_root: bool = True
    allow_outside_root: bool = False
    follow_symlinks: bool = False
    max_file_bytes: int = 2_000_000
    ignore: list[str] = Field(
        default_factory=lambda: [
            ".git",
            ".puk",
            "node_modules",
            "dist",
            "build",
            "__pycache__",
        ]
    )
    allow_globs: list[str] = Field(
        default_factory=lambda: [
            "**/*.py",
            "**/*.md",
            "**/*.toml",
            "**/*.yml",
            "**/*.yaml",
            "**/*.json",
        ]
    )
    deny_globs: list[str] = Field(
        default_factory=lambda: [
            "**/.env",
            "**/*secret*",
            "**/*key*",
            "**/*.pem",
        ]
    )


class LlmConfig(BaseModel):
    provider: Literal["copilot", "openai", "azure", "anthropic"] = "copilot"
    model: str = "gpt-5"
    fallback_provider: str = ""
    fallback_model: str = ""
    api_key_env: str = ""
    azure_endpoint: str = ""
    azure_api_version: str = "2024-02-15-preview"
    max_output_tokens: int = 2048
    temperature: float = 0.2


class SessionConfig(BaseModel):
    infinite: bool = True
    compaction_threshold: float = 0.80
    system_prompt_file: str = ""
    response_timeout_seconds: int = 300


class SafetyConfig(BaseModel):
    confirm_mutations: bool = True
    confirm_commands: bool = True
    confirm_installs: bool = True
    confirm_mcp: bool = True
    redact_secrets: bool = True
    paranoid_reads: bool = False


class ToolsPolicyConfig(BaseModel):
    allow_delete: bool = False
    allow_overwrite: bool = True
    staging_mode: Literal["diff-first", "direct"] = "diff-first"
    max_write_files: int = 200


class TerminalPolicyConfig(BaseModel):
    shell: bool = False
    timeout_seconds: int = 300
    allowlist: list[str] = Field(
        default_factory=lambda: ["git", "python", "pytest", "ruff", "mypy", "make"]
    )
    denylist: list[str] = Field(
        default_factory=lambda: ["rm", "dd", "mkfs", "shutdown", "reboot", "curl", "wget"]
    )


class ToolsConfig(BaseModel):
    filesystem: bool = True
    terminal: bool = True
    python_exec: bool = True
    mcp: bool = False
    user_io: bool = True
    filesystem_policy: ToolsPolicyConfig = Field(default_factory=ToolsPolicyConfig)
    terminal_policy: TerminalPolicyConfig = Field(default_factory=TerminalPolicyConfig)


class PythonConfig(BaseModel):
    venv_mode: Literal["local", "global-cache"] = "local"
    local_venv_dir: str = ".puk/venv"
    global_cache_dir: str = "~/.puk/venvs"
    auto_create_venv: bool = True
    auto_install_requirements: bool = False
    requirements_files: list[str] = Field(
        default_factory=lambda: ["requirements.txt", "pyproject.toml"]
    )
    exec_timeout_seconds: int = 300


class MCPServerConfig(BaseModel):
    type: Literal["http", "sse", "local"]
    url: str = ""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    cwd: str = ""
    tools: list[str] = Field(default_factory=list)


class MCPConfig(BaseModel):
    enabled: bool = False
    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class PukConfig(BaseModel):
    core: CoreConfig = Field(default_factory=CoreConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    python: PythonConfig = Field(default_factory=PythonConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    model_config = {"extra": "ignore"}


@dataclass
class ConfigProvenance:
    values: dict[str, str]
    sources: dict[str, str]


@dataclass
class ConfigLoadResult:
    config: PukConfig
    provenance: ConfigProvenance
    root_base: Path
    root_path: Path


DEFAULT_CONFIG = PukConfig().model_dump()


def _load_toml(path: Path) -> dict[str, Any]:
    import tomllib

    data = tomllib.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def _discover_local_config(start_dir: Path) -> Path | None:
    current = start_dir
    while True:
        candidate_toml = current / ".puk.toml"
        if candidate_toml.is_file():
            return candidate_toml
        candidate_legacy = current / ".puk.config"
        if candidate_legacy.is_file():
            return candidate_legacy
        if current.parent == current:
            return None
        current = current.parent


def _merge_layer(target: dict[str, Any], layer: dict[str, Any], source: str, provenance: dict[str, str], prefix: str = "") -> None:
    for key, value in layer.items():
        path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            if not isinstance(target.get(key), dict):
                target[key] = {}
            _merge_layer(target[key], value, source, provenance, path)
        else:
            target[key] = value
            provenance[path] = source


def _find_unknown_keys(data: dict[str, Any], model: type[BaseModel], prefix: str = "") -> list[str]:
    unknown: list[str] = []
    fields = model.model_fields
    for key, value in data.items():
        if key not in fields:
            unknown.append(f"{prefix}{key}" if prefix else key)
            continue
        field = fields[key]
        annotation = field.annotation
        # If the field is a dict[str, Any], allow any nested keys
        if annotation == Dict[str, Any] or annotation == dict[str, Any]:
            continue
        if isinstance(value, dict) and hasattr(annotation, "model_fields"):
            unknown.extend(_find_unknown_keys(value, annotation, prefix=f"{prefix}{key}." if prefix else f"{key}."))
    return unknown


def load_config(
    *,
    cwd: Path,
    cli_root: str | None,
    cli_overrides: dict[str, Any] | None = None,
) -> ConfigLoadResult:
    cli_overrides = cli_overrides or {}
    home = Path.home()

    global_config_path = None
    global_primary = home / ".puk.toml"
    global_alt = home / ".config" / "puk" / "config.toml"
    if global_primary.is_file():
        global_config_path = global_primary
    elif global_alt.is_file():
        global_config_path = global_alt
    else:
        legacy_global = home / ".puk.config"
        if legacy_global.is_file():
            global_config_path = legacy_global

    global_config = _load_toml(global_config_path) if global_config_path else {}

    discover_root = global_config.get("workspace", {}).get("discover_root", True)

    local_config_path = None
    root_base = cwd
    if cli_root:
        root_base = Path(cli_root).expanduser().resolve()
        candidate = root_base / ".puk.toml"
        if candidate.is_file():
            local_config_path = candidate
        else:
            legacy = root_base / ".puk.config"
            if legacy.is_file():
                local_config_path = legacy
    else:
        if discover_root:
            local_config_path = _discover_local_config(cwd)
            if local_config_path:
                root_base = local_config_path.parent
        else:
            candidate = cwd / ".puk.toml"
            if candidate.is_file():
                local_config_path = candidate
            else:
                legacy = cwd / ".puk.config"
                if legacy.is_file():
                    local_config_path = legacy

    local_config = _load_toml(local_config_path) if local_config_path else {}

    merged: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    _merge_layer(merged, DEFAULT_CONFIG, "default", provenance)
    _merge_layer(merged, global_config, "global", provenance)
    _merge_layer(merged, local_config, "local", provenance)
    _merge_layer(merged, cli_overrides, "cli", provenance)

    strict_config = merged.get("core", {}).get("strict_config", False)
    if strict_config:
        unknown = _find_unknown_keys(merged, PukConfig)
        if unknown:
            raise PukError(f"Unknown config keys: {', '.join(unknown)}")

    config = PukConfig.model_validate(merged)

    if cli_root:
        root_path = Path(cli_root).expanduser()
        if not root_path.is_absolute():
            root_path = (cwd / root_path).resolve()
    else:
        root_setting = config.workspace.root or "."
        root_path = (root_base / root_setting).expanduser().resolve()

    config.workspace.root = str(root_path)

    sources = {
        "global": str(global_config_path) if global_config_path else "",
        "local": str(local_config_path) if local_config_path else "",
    }

    return ConfigLoadResult(
        config=config,
        provenance=ConfigProvenance(values=provenance, sources=sources),
        root_base=root_base,
        root_path=root_path,
    )


def config_to_toml(config: PukConfig) -> str:
    try:
        import tomli_w

        return tomli_w.dumps(config.model_dump())
    except Exception:
        # Fallback: simple repr
        return str(config.model_dump())


def build_cli_overrides(
    *,
    ui: str | None,
    confirm: bool,
    paranoid: bool,
    root: str | None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if ui:
        overrides.setdefault("core", {})["ui"] = ui
    if root:
        overrides.setdefault("workspace", {})["root"] = root
    if confirm:
        overrides.setdefault("safety", {})
        overrides["safety"]["confirm_mutations"] = False
        overrides["safety"]["confirm_commands"] = False
        overrides["safety"]["confirm_installs"] = False
    if paranoid:
        overrides.setdefault("safety", {})["paranoid_reads"] = True
    return overrides
