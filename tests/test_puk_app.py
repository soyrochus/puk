from __future__ import annotations

import pytest

from pathlib import Path

from puk.app import PukApp, PukConfig, run_app
from puk.config import LLMSettings
from puk.run import RunRecorder


class FakeSession:
    def __init__(self):
        self.handlers = []
        self.prompts = []
        self.destroyed = False

    def on(self, handler):
        self.handlers.append(handler)

    async def send_and_wait(self, payload, timeout=None):
        self.prompts.append(payload["prompt"])

    async def get_messages(self):
        return []

    async def destroy(self):
        self.destroyed = True


class ErrorSession(FakeSession):
    def __init__(self, message: str):
        super().__init__()
        self.message = message

    async def send_and_wait(self, payload, timeout=None):
        raise Exception(self.message)


class FakeClient:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.configs = []
        self.session = FakeSession()

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def create_session(self, config):
        self.configs.append(config)
        return self.session


class SpyRenderer:
    def __init__(self):
        self.calls = []

    def show_banner(self):
        pass

    def show_tool_event(self, tool_name):
        pass

    def show_working(self):
        self.calls.append("show_working")

    def hide_working(self):
        self.calls.append("hide_working")

    def write_delta(self, chunk):
        pass

    def end_message(self):
        pass


@pytest.mark.asyncio
async def test_run_app_one_shot(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)
    recorder = RunRecorder(Path("."), "oneshot", LLMSettings(), None, [])

    await run_app(PukConfig(workspace="."), one_shot_prompt="hello", recorder=recorder)

    await run_app(PukConfig(workspace="."), one_shot_prompt="hello", recorder=recorder)

    assert fake.started is True
    assert fake.stopped is True
    assert fake.session.prompts == ["hello"]
    assert fake.configs[0]["excluded_tools"] == []


def test_session_config_contains_workspace_and_system_message(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    app = PukApp(PukConfig(workspace="."))
    cfg = app.session_config()

    assert cfg["streaming"] is True
    assert "system_message" in cfg
    assert "working_directory" in cfg


def test_session_config_omits_model_for_copilot_auto(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    app = PukApp(PukConfig(workspace=".", llm=LLMSettings(provider="copilot", model="")))
    cfg = app.session_config()

    assert "model" not in cfg


def test_session_config_includes_azure_provider(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-azure-key")
    app = PukApp(
        PukConfig(
            workspace=".",
            llm=LLMSettings(
                provider="azure",
                model="gpt-5",
                api_key="AZURE_OPENAI_API_KEY",
                azure_endpoint="https://example.openai.azure.com",
                azure_api_version="2024-02-15-preview",
            ),
        )
    )

    cfg = app.session_config()

    assert cfg["model"] == "gpt-5"
    assert cfg["provider"] == {
        "type": "azure",
        "base_url": "https://example.openai.azure.com",
        "api_key": "test-azure-key",
        "azure": {"api_version": "2024-02-15-preview"},
    }


def test_session_config_fails_for_missing_byok_env_var(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)
    monkeypatch.delenv("MISSING_AZURE_KEY", raising=False)
    app = PukApp(
        PukConfig(
            workspace=".",
            llm=LLMSettings(
                provider="azure",
                model="gpt-5",
                api_key="MISSING_AZURE_KEY",
                azure_endpoint="https://example.openai.azure.com",
            ),
        )
    )

    with pytest.raises(ValueError, match="Environment variable 'MISSING_AZURE_KEY' is not set"):
        app.session_config()


@pytest.mark.asyncio
async def test_ask_shows_and_hides_working_indicator(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)
    app = PukApp(PukConfig(workspace="."))
    app.session = fake.session
    renderer = SpyRenderer()
    app.renderer = renderer

    await app.ask("hello")

    assert renderer.calls == ["show_working", "hide_working"]


@pytest.mark.asyncio
async def test_ask_azure_auto_model_error_has_clear_guidance(monkeypatch):
    fake = FakeClient()
    fake.session = ErrorSession(
        "Session error: Execution failed: Error: No model available. Check policy enablement under GitHub Settings > Copilot"
    )
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)
    app = PukApp(
        PukConfig(
            workspace=".",
            llm=LLMSettings(
                provider="azure",
                model="",
                api_key="AZURE_OPENAI_API_KEY",
                azure_endpoint="https://example.openai.azure.com",
            ),
        )
    )
    app.session = fake.session

    with pytest.raises(RuntimeError, match="No model is being passed by Puk for Azure"):
        await app.ask("hello")


def test_session_config_allows_azure_without_explicit_model(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-azure-key")

    app = PukApp(
        PukConfig(
            workspace=".",
            llm=LLMSettings(
                provider="azure",
                model="",
                api_key="AZURE_OPENAI_API_KEY",
                azure_endpoint="https://example.openai.azure.com",
            ),
        )
    )

    cfg = app.session_config()
    assert "model" not in cfg
