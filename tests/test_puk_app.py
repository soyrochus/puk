from __future__ import annotations

import pytest

from puk.app import PukApp, PukConfig, run_app


class FakeSession:
    def __init__(self):
        self.handlers = []
        self.prompts = []
        self.destroyed = False

    def on(self, handler):
        self.handlers.append(handler)

    async def send_and_wait(self, payload, timeout=None):
        self.prompts.append(payload["prompt"])

    async def destroy(self):
        self.destroyed = True


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

    await run_app(PukConfig(workspace="."), one_shot_prompt="hello")

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
