from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from puk.config import LLMSettings, log_resolved_llm_config, resolve_llm_config, validate_llm_settings


def _write_llm_config(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_resolve_llm_config_merge_precedence(monkeypatch, tmp_path: Path) -> None:
    global_path = tmp_path / "global.toml"
    _write_llm_config(
        global_path,
        """
        [llm]
        provider = "openai"
        model = "gpt-5-mini"
        max_output_tokens = 1024
        """,
    )
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    _write_llm_config(
        workspace_path / ".puk.toml",
        """
        [llm]
        model = "gpt-5-large"
        temperature = 0.7
        """,
    )

    monkeypatch.setattr("puk.config.get_global_config_path", lambda: global_path)

    resolved = resolve_llm_config(
        workspace=workspace_path,
        parameters={"model": "gpt-5-override", "max_output_tokens": 512},
    )

    assert resolved.settings.provider == "openai"
    assert resolved.settings.model == "gpt-5-override"
    assert resolved.settings.temperature == 0.7
    assert resolved.settings.max_output_tokens == 512
    assert resolved.sources["provider"] == "global"
    assert resolved.sources["model"] == "parameter"
    assert resolved.sources["temperature"] == "workspace"
    assert resolved.sources["max_output_tokens"] == "parameter"


def test_resolve_llm_config_invalid_workspace_config(monkeypatch, tmp_path: Path) -> None:
    global_path = tmp_path / "global.toml"
    global_path.write_text("", encoding="utf-8")
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    _write_llm_config(workspace_path / ".puk.toml", 'llm = "bad"')

    monkeypatch.setattr("puk.config.get_global_config_path", lambda: global_path)

    with pytest.raises(ValueError, match="Invalid \\[llm\\] section"):
        resolve_llm_config(workspace=workspace_path, parameters={})


def test_resolve_llm_config_uses_legacy_workspace_filename(monkeypatch, tmp_path: Path) -> None:
    global_path = tmp_path / "global.toml"
    global_path.write_text("", encoding="utf-8")
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    _write_llm_config(
        workspace_path / ".puk.config",
        """
        [llm]
        provider = "azure"
        azure_endpoint = "https://example.openai.azure.com"
        """,
    )

    monkeypatch.setattr("puk.config.get_global_config_path", lambda: global_path)

    resolved = resolve_llm_config(workspace=workspace_path, parameters={})

    assert resolved.settings.provider == "azure"
    assert resolved.settings.azure_endpoint == "https://example.openai.azure.com"


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (LLMSettings(provider="unknown"), "Invalid LLM provider"),
        (
            LLMSettings(provider="openai", model=""),
            "Providers 'openai' and 'anthropic' require an explicit non-empty model",
        ),
        (LLMSettings(temperature=3.0), "LLM temperature must be between"),
        (LLMSettings(max_output_tokens=0), "LLM max_output_tokens must be a positive integer"),
        (LLMSettings(provider="azure", model="gpt-5", azure_endpoint=""), "Azure provider requires a non-empty"),
        (LLMSettings(provider="openai", model="gpt-5", api_key=""), "BYOK providers require a non-empty"),
    ],
)
def test_validate_llm_settings_invalid(settings: LLMSettings, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_llm_settings(settings)


def test_validate_llm_settings_allows_empty_model_for_copilot() -> None:
    validate_llm_settings(LLMSettings(provider="copilot", model=""))


def test_validate_llm_settings_allows_empty_model_for_azure() -> None:
    validate_llm_settings(
        LLMSettings(
            provider="azure",
            model="",
            api_key="AZURE_OPENAI_API_KEY",
            azure_endpoint="https://example.openai.azure.com",
        )
    )


def test_resolve_llm_config_uses_provider_default_api_key_for_azure(monkeypatch, tmp_path: Path) -> None:
    global_path = tmp_path / "global.toml"
    global_path.write_text("", encoding="utf-8")
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    _write_llm_config(
        workspace_path / ".puk.toml",
        """
        [llm]
        provider = "azure"
        azure_endpoint = "https://example.openai.azure.com"
        """,
    )

    monkeypatch.setattr("puk.config.get_global_config_path", lambda: global_path)
    resolved = resolve_llm_config(workspace=workspace_path, parameters={})

    assert resolved.settings.api_key == "AZURE_OPENAI_API_KEY"
    assert resolved.sources["api_key"] == "default"


def test_log_resolved_llm_config_redacts_literal_api_key(monkeypatch, tmp_path: Path, caplog) -> None:
    global_path = tmp_path / "global.toml"
    global_path.write_text("", encoding="utf-8")
    monkeypatch.setattr("puk.config.get_global_config_path", lambda: global_path)

    resolved = resolve_llm_config(
        workspace=tmp_path,
        parameters={
            "provider": "azure",
            "azure_endpoint": "https://example.openai.azure.com",
            "api_key": "not-an-env-var-name-secret-value",
        },
    )

    with caplog.at_level("INFO", logger="puk"):
        log_resolved_llm_config(resolved)

    assert "not-an-env-var-name-secret-value" not in caplog.text
    assert "LLM config api_key=<redacted>" in caplog.text
