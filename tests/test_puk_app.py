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

    async def send_and_wait(self, payload):
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


@pytest.mark.asyncio
async def test_run_app_one_shot(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    await run_app(PukConfig(mode="plain", workspace="."), one_shot_prompt="hello")

    assert fake.started is True
    assert fake.stopped is True
    assert fake.session.prompts == ["hello"]
    assert fake.configs[0]["excluded_tools"] == []


def test_session_config_contains_workspace_and_system_message(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("puk.app.CopilotClient", lambda: fake)

    app = PukApp(PukConfig(mode="plain", workspace="."))
    cfg = app.session_config()

    assert cfg["streaming"] is True
    assert "system_message" in cfg
    assert "working_directory" in cfg
