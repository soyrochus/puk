from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from copilot import CopilotClient
from copilot.generated.session_events import SessionEventType
from rich.console import Console

from puk.ui import FancyRenderer, PlainRenderer


DEFAULT_SYSTEM_PROMPT = """You are Puk, a pragmatic local coding assistant.
Use SDK internal tools whenever useful to inspect files and run searches.
When users ask for codebase discovery tasks, use filesystem/search tools before answering.
"""


class Renderer(Protocol):
    def show_banner(self) -> None: ...

    def show_tool_event(self, tool_name: str) -> None: ...

    def write_delta(self, chunk: str) -> None: ...

    def end_message(self) -> None: ...


@dataclass
class PukConfig:
    mode: str = "fancy"
    model: str = "gpt-5"
    workspace: str = "."


class PukApp:
    def __init__(self, config: PukConfig):
        self.config = config
        self.client = CopilotClient()
        self.session = None
        self.renderer: Renderer = PlainRenderer() if config.mode == "plain" else FancyRenderer(console=Console())

    def session_config(self) -> dict:
        return {
            "model": self.config.model,
            "streaming": True,
            "working_directory": str(Path(self.config.workspace).resolve()),
            "excluded_tools": [],  # keep internal SDK tools enabled
            "system_message": {"content": DEFAULT_SYSTEM_PROMPT},
        }

    def _on_event(self, event) -> None:
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            chunk = getattr(event, "delta", None) or getattr(event, "delta_content", "")
            if chunk:
                self.renderer.write_delta(chunk)
        elif event.type == SessionEventType.ASSISTANT_TURN_END:
            self.renderer.end_message()
        elif event.type == SessionEventType.TOOL_INVOCATION_START:
            name = getattr(event, "tool_name", "unknown")
            self.renderer.show_tool_event(name)

    async def start(self) -> None:
        await self.client.start()
        self.session = await self.client.create_session(self.session_config())
        self.session.on(self._on_event)

    async def ask(self, prompt: str) -> None:
        await self.session.send_and_wait({"prompt": prompt})

    async def repl(self) -> None:
        self.renderer.show_banner()
        while True:
            raw = input("puk> ").strip()
            if raw in {"/exit", "/quit", "quit", "exit"}:
                return
            if raw:
                await self.ask(raw)

    async def close(self) -> None:
        if self.session is not None:
            await self.session.destroy()
        await self.client.stop()


async def run_app(config: PukConfig, one_shot_prompt: str | None = None) -> None:
    app = PukApp(config)
    try:
        await app.start()
        if one_shot_prompt:
            await app.ask(one_shot_prompt)
            return
        await app.repl()
    finally:
        await app.close()


def run_sync(config: PukConfig, one_shot_prompt: str | None = None) -> None:
    asyncio.run(run_app(config, one_shot_prompt=one_shot_prompt))
