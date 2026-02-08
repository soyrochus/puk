from __future__ import annotations

import logging
import os
import platform
import re
from dataclasses import dataclass
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


LLM_KEYS = [
    "provider",
    "model",
    "api_key",
    "azure_endpoint",
    "azure_api_version",
    "max_output_tokens",
    "temperature",
]


def _default_llm_values() -> dict[str, Any]:
    return {key: getattr(LLMSettings(), key) for key in LLM_KEYS}


def _normalize_llm_layer(layer: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in layer.items() if key in LLM_KEYS}


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
