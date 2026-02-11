from __future__ import annotations

import logging
import os
import platform
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import tomllib

SUPPORTED_PROVIDERS = {"copilot", "openai", "azure", "anthropic"}
BYOK_PROVIDERS = {"openai", "azure", "anthropic"}
MODEL_REQUIRED_PROVIDERS = {"openai", "anthropic"}
_ENV_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_PROVIDER_DEFAULT_API_KEY = {
    "openai": "OPENAI_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


@dataclass(frozen=True)
class LLMSettings:
    provider: str = "copilot"
    model: str = ""
    api_key: str = "OPENAI_API_KEY"
    azure_endpoint: str = ""
    azure_api_version: str = "2024-02-15-preview"
    max_output_tokens: int = 2048
    temperature: float = 0.2


@dataclass(frozen=True)
class ResolvedLLMConfig:
    settings: LLMSettings
    sources: dict[str, str]


@dataclass(frozen=True)
class WorkspaceSettings:
    root: str = "."
    discover_root: bool = True
    allow_outside_root: bool = False
    follow_symlinks: bool = False
    max_file_bytes: int = 2_000_000
    ignore: list[str] = field(
        default_factory=lambda: [
            ".git",
            ".puk",
            "node_modules",
            "dist",
            "build",
            "__pycache__",
        ]
    )
    allow_globs: list[str] = field(
        default_factory=lambda: [
            "**/*.py",
            "**/*.md",
            "**/*.toml",
            "**/*.yml",
            "**/*.yaml",
            "**/*.json",
        ]
    )
    deny_globs: list[str] = field(
        default_factory=lambda: [
            "**/.env",
            "**/*secret*",
            "**/*key*",
            "**/*.pem",
        ]
    )


@dataclass(frozen=True)
class ResolvedWorkspaceConfig:
    settings: WorkspaceSettings
    sources: dict[str, str]


LLM_KEYS = [
    "provider",
    "model",
    "api_key",
    "azure_endpoint",
    "azure_api_version",
    "max_output_tokens",
    "temperature",
]

WORKSPACE_KEYS = [
    "root",
    "discover_root",
    "allow_outside_root",
    "follow_symlinks",
    "max_file_bytes",
    "ignore",
    "allow_globs",
    "deny_globs",
]

WORKSPACE_PARAM_MAP = {
    "workspace_root": "root",
    "workspace_discover_root": "discover_root",
    "workspace_allow_outside_root": "allow_outside_root",
    "workspace_follow_symlinks": "follow_symlinks",
    "workspace_max_file_bytes": "max_file_bytes",
    "workspace_ignore": "ignore",
    "workspace_allow_globs": "allow_globs",
    "workspace_deny_globs": "deny_globs",
}


def _default_llm_values() -> dict[str, Any]:
    return {key: getattr(LLMSettings(), key) for key in LLM_KEYS}


def _normalize_llm_layer(layer: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in layer.items() if key in LLM_KEYS}


def _default_workspace_values() -> dict[str, Any]:
    return {key: getattr(WorkspaceSettings(), key) for key in WORKSPACE_KEYS}


def _normalize_workspace_layer(layer: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in layer.items() if key in WORKSPACE_KEYS}


def get_global_config_path() -> Path | None:
    system = platform.system().lower()
    if system == "windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return Path(appdata) / "puk" / "puk.toml"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "puk" / "puk.toml"
    return Path.home() / ".config" / "puk" / "puk.toml"


def load_llm_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    content = path.read_bytes()
    data = tomllib.loads(content.decode("utf-8"))
    llm_section = data.get("llm", {})
    if not isinstance(llm_section, dict):
        raise ValueError(f"Invalid [llm] section in {path}; expected a table.")
    return _normalize_llm_layer(llm_section)


def load_workspace_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    content = path.read_bytes()
    data = tomllib.loads(content.decode("utf-8"))
    workspace_section = data.get("workspace", {})
    if not isinstance(workspace_section, dict):
        raise ValueError(f"Invalid [workspace] section in {path}; expected a table.")
    return _normalize_workspace_layer(workspace_section)


def resolve_llm_config(workspace: Path, parameters: dict[str, Any]) -> ResolvedLLMConfig:
    defaults = _default_llm_values()
    sources = {key: "default" for key in defaults}

    global_path = get_global_config_path()
    if global_path:
        global_layer = load_llm_config_file(global_path)
        for key, value in global_layer.items():
            defaults[key] = value
            sources[key] = "global"

    workspace_path = workspace / ".puk.toml"
    workspace_layer = load_llm_config_file(workspace_path)
    if not workspace_layer:
        # Backward-compatible fallback for legacy workspace filename.
        workspace_layer = load_llm_config_file(workspace / ".puk.config")
    for key, value in workspace_layer.items():
        defaults[key] = value
        sources[key] = "workspace"

    param_layer = {k: v for k, v in parameters.items() if v is not None}
    for key, value in param_layer.items():
        if key not in LLM_KEYS:
            continue
        defaults[key] = value
        sources[key] = "parameter"

    provider = defaults.get("provider")
    provider_default_key = _PROVIDER_DEFAULT_API_KEY.get(provider)
    if (
        provider_default_key
        and sources.get("api_key") == "default"
        and defaults.get("api_key") == LLMSettings().api_key
    ):
        defaults["api_key"] = provider_default_key

    settings = LLMSettings(**defaults)
    validate_llm_settings(settings)
    return ResolvedLLMConfig(settings=settings, sources=sources)


def resolve_workspace_config(
    workspace: Path,
    parameters: dict[str, Any],
) -> ResolvedWorkspaceConfig:
    defaults = _default_workspace_values()
    sources = {key: "default" for key in defaults}

    global_path = get_global_config_path()
    if global_path:
        global_layer = load_workspace_config_file(global_path)
        for key, value in global_layer.items():
            defaults[key] = value
            sources[key] = "global"

    param_layer = {
        WORKSPACE_PARAM_MAP[key]: value
        for key, value in parameters.items()
        if key in WORKSPACE_PARAM_MAP and value is not None
    }
    discover_root_hint = param_layer.get("discover_root", defaults["discover_root"])

    workspace_layer: dict[str, Any] = {}
    workspace_path = workspace / ".puk.toml"
    legacy_path = workspace / ".puk.config"
    if discover_root_hint:
        discovered = _find_workspace_config_file(workspace)
        if discovered is not None:
            workspace_layer = load_workspace_config_file(discovered)
    else:
        if workspace_path.exists():
            workspace_layer = load_workspace_config_file(workspace_path)
        elif legacy_path.exists():
            workspace_layer = load_workspace_config_file(legacy_path)

    for key, value in workspace_layer.items():
        defaults[key] = value
        sources[key] = "workspace"

    for key, value in param_layer.items():
        defaults[key] = value
        sources[key] = "parameter"

    settings = WorkspaceSettings(**defaults)
    validate_workspace_settings(settings)

    base_root = workspace
    if settings.discover_root:
        discovered = _find_workspace_config_file(workspace)
        if discovered is not None:
            base_root = discovered.parent

    root_value = settings.root
    resolved_root = (base_root / root_value).resolve()
    invocation_root = workspace.resolve()
    if not settings.allow_outside_root and not _is_relative_to(resolved_root, invocation_root):
        raise ValueError(
            "Workspace root must remain within the invocation workspace when allow_outside_root is false. "
            f"Resolved root '{resolved_root}' is outside '{invocation_root}'."
        )

    settings = replace(settings, root=str(resolved_root))
    return ResolvedWorkspaceConfig(settings=settings, sources=sources)


def validate_llm_settings(settings: LLMSettings) -> None:
    if settings.provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Invalid LLM provider '{settings.provider}'. Supported providers: {sorted(SUPPORTED_PROVIDERS)}."
        )
    if settings.provider in MODEL_REQUIRED_PROVIDERS and not settings.model:
        raise ValueError(
            "Providers 'openai' and 'anthropic' require an explicit non-empty model value."
        )
    if not isinstance(settings.temperature, (int, float)):
        raise ValueError("LLM temperature must be numeric.")
    temperature = float(settings.temperature)
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("LLM temperature must be between 0.0 and 2.0.")
    if not isinstance(settings.max_output_tokens, int) or settings.max_output_tokens <= 0:
        raise ValueError("LLM max_output_tokens must be a positive integer.")
    if settings.provider == "azure" and not settings.azure_endpoint:
        raise ValueError("Azure provider requires a non-empty azure_endpoint.")
    if settings.provider in BYOK_PROVIDERS and not settings.api_key:
        raise ValueError("BYOK providers require a non-empty api_key value.")


def validate_workspace_settings(settings: WorkspaceSettings) -> None:
    if not isinstance(settings.root, str) or not settings.root.strip():
        raise ValueError("Workspace root must be a non-empty path string.")
    for name in ("discover_root", "allow_outside_root", "follow_symlinks"):
        value = getattr(settings, name)
        if not isinstance(value, bool):
            raise ValueError(f"Workspace {name} must be a boolean.")
    if not isinstance(settings.max_file_bytes, int) or settings.max_file_bytes <= 0:
        raise ValueError("Workspace max_file_bytes must be a positive integer.")
    for field in ("ignore", "allow_globs", "deny_globs"):
        value = getattr(settings, field)
        if not isinstance(value, list):
            raise ValueError(f"Workspace {field} must be a list of non-empty strings.")
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Workspace {field} must be a list of non-empty strings.")


def log_resolved_llm_config(resolved: ResolvedLLMConfig) -> None:
    logger = logging.getLogger("puk")
    settings = resolved.settings
    logger.info(
        "LLM config resolved: provider=%s model=%s",
        settings.provider,
        settings.model or "<auto>",
    )
    for key in LLM_KEYS:
        value = getattr(settings, key)
        if key == "api_key" and isinstance(value, str) and not _ENV_NAME_PATTERN.match(value):
            value = "<redacted>"
        logger.info("LLM config %s=%s (source=%s)", key, value, resolved.sources.get(key, "default"))


def log_resolved_workspace_config(resolved: ResolvedWorkspaceConfig) -> None:
    logger = logging.getLogger("puk")
    settings = resolved.settings
    logger.info("Workspace config resolved: root=%s", settings.root)
    for key in WORKSPACE_KEYS:
        value = getattr(settings, key)
        logger.info(
            "Workspace config %s=%s (source=%s)",
            key,
            value,
            resolved.sources.get(key, "default"),
        )


def _find_workspace_config_file(start: Path) -> Path | None:
    current = start.resolve()
    candidates = [current, *current.parents]
    for directory in candidates:
        primary = directory / ".puk.toml"
        if primary.exists():
            return primary
        legacy = directory / ".puk.config"
        if legacy.exists():
            return legacy
    return None


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False
