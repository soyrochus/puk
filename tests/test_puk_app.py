from __future__ import annotations

from types import SimpleNamespace
import pytest

from pathlib import Path

from puk.app import PukApp, PukConfig, run_app
from puk.config import LLMSettings
from puk.run import RunRecorder
from copilot.generated.session_events import SessionEventType


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


class RecorderSpy:
    def __init__(self, turn_id: int = 1):
        self.turn_id = turn_id
        self.tool_calls = []
        self.tool_results = []

    def record_tool_call(self, **kwargs):
        self.tool_calls.append(kwargs)

    def record_tool_result(self, **kwargs):
        self.tool_results.append(kwargs)


@pytest.mark.asyncio
async def test_run_app_one_shot(monkeypatch):
    fake1 = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake1)
    recorder1 = RunRecorder(Path("."), "oneshot", LLMSettings(), None, [])
    await run_app(PukConfig(workspace="."), one_shot_prompt="hello", recorder=recorder1)
    assert fake1.started is True
    assert fake1.stopped is True
    assert fake1.session.prompts == ["hello"]

    fake2 = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake2)
    recorder2 = RunRecorder(Path("."), "oneshot", LLMSettings(), None, [])
    await run_app(PukConfig(workspace="."), one_shot_prompt="hello", recorder=recorder2)
    assert fake2.session.prompts == ["hello"]
    assert fake1.configs[0]["excluded_tools"] == []


def test_session_config_contains_workspace_and_system_message(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    app = PukApp(PukConfig(workspace="."))
    cfg = app.session_config()

    assert cfg["streaming"] is True
    assert "system_message" in cfg
    assert "working_directory" in cfg


def test_session_config_excludes_bash_when_playbook_disallows_it(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    app = PukApp(PukConfig(workspace=".", allowed_tools=["glob", "view"]))
    cfg = app.session_config()

    assert "bash" in cfg["excluded_tools"]
    assert cfg["available_tools"] == ["glob", "view"]


def test_session_config_keeps_bash_available_when_playbook_allows_it(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    app = PukApp(PukConfig(workspace=".", allowed_tools=["glob", "bash"]))
    cfg = app.session_config()

    assert "bash" not in cfg["excluded_tools"]
    assert cfg["available_tools"] == ["glob", "bash"]


def test_permission_handler_does_not_block_read_requests_for_allowed_tools_mode(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    app = PukApp(PukConfig(workspace=".", allowed_tools=["glob"]))
    handler = app._permission_handler()

    result = handler({"kind": "read", "path": "README.md"}, {})
    assert result["kind"] == "approved"


def test_permission_handler_denies_plan_mode_with_valid_kind(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    app = PukApp(PukConfig(workspace=".", execution_mode="plan"))
    handler = app._permission_handler()

    result = handler({"kind": "read", "path": "README.md"}, {})
    assert result["kind"] == "denied-interactively-by-user"


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


def test_on_event_records_tool_call_and_result():
    app = PukApp(PukConfig(workspace="."))
    app.renderer = SpyRenderer()
    recorder = RecorderSpy(turn_id=7)
    app.run_recorder = recorder
    app._active_turn_id = 7

    start_event = SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_START,
        data=SimpleNamespace(
            tool_name="view",
            tool_call_id="call_1",
            arguments={"path": "README.md"},
            turn_id="7",
        ),
    )
    complete_event = SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_COMPLETE,
        data=SimpleNamespace(
            tool_name="view",
            tool_call_id="call_1",
            turn_id="7",
            success=True,
            error=None,
            result=SimpleNamespace(content="ok", detailed_content=None),
        ),
    )

    app._on_event(start_event)
    app._on_event(complete_event)

    assert len(recorder.tool_calls) == 1
    assert recorder.tool_calls[0]["name"] == "view"
    assert recorder.tool_calls[0]["tool_call_id"] == "call_1"
    assert '"path": "README.md"' in recorder.tool_calls[0]["arguments"]
    assert len(recorder.tool_results) == 1
    assert recorder.tool_results[0]["name"] == "view"
    assert recorder.tool_results[0]["tool_call_id"] == "call_1"
    assert recorder.tool_results[0]["success"] is True
    assert recorder.tool_results[0]["result"] == "ok"


def test_tool_loop_guard_raises_on_repeated_identical_calls(monkeypatch):
    monkeypatch.setenv("PUK_MAX_IDENTICAL_TOOL_CALLS", "2")
    app = PukApp(PukConfig(workspace="."))
    app.renderer = SpyRenderer()
    app.run_recorder = RecorderSpy(turn_id=1)
    app._active_turn_id = 1

    event = SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_START,
        data=SimpleNamespace(
            tool_name="view",
            tool_call_id="call_1",
            arguments={"path": "README.md"},
            turn_id="1",
        ),
    )

    app._on_event(event)
    app._on_event(event)
    with pytest.raises(RuntimeError, match="Tool loop guard triggered"):
        app._on_event(event)
