from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from copilot import CopilotClient
from copilot.generated.session_events import SessionEvent, SessionEventType
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout

from puk.ui import ConsoleRenderer


def _auto_approve_permission(request: dict, metadata: dict) -> dict:
    """Auto-approve all tool permission requests."""
    return {"kind": "approved"}


DEFAULT_SYSTEM_PROMPT = """You are Puk, a pragmatic local coding assistant.
Use SDK internal tools whenever useful to inspect files and run searches.
When users ask for codebase discovery tasks, use filesystem/search tools before answering.
"""


class Renderer(Protocol):
    def show_banner(self) -> None: ...

    def show_tool_event(self, tool_name: str) -> None: ...

    def show_working(self) -> None: ...

    def hide_working(self) -> None: ...

    def write_delta(self, chunk: str) -> None: ...

    def end_message(self) -> None: ...


@dataclass
class PukConfig:
    model: str = "gpt-5"
    workspace: str = "."


class PukApp:
    def __init__(self, config: PukConfig):
        self.config = config
        self.client = CopilotClient()
        self.session = None
        self.renderer: Renderer = ConsoleRenderer()
        self._awaiting_response = False

    def session_config(self) -> dict:
        return {
            "model": self.config.model,
            "streaming": True,
            "working_directory": str(Path(self.config.workspace).resolve()),
            "excluded_tools": [],  # keep internal SDK tools enabled
            "system_message": {"content": DEFAULT_SYSTEM_PROMPT},
            "on_permission_request": _auto_approve_permission,
        }

    def _on_event(self, event: SessionEvent) -> None:
        # Debug: uncomment to see all events
        # print(f"[DEBUG] {event.type}")
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            self._mark_response_started()
            chunk = event.data.delta_content
            if chunk:
                self.renderer.write_delta(chunk)
        elif event.type == SessionEventType.ASSISTANT_TURN_END:
            self._mark_response_started()
            self.renderer.end_message()
        elif event.type == SessionEventType.TOOL_EXECUTION_START:
            self._mark_response_started()
            name = event.data.tool_name or "unknown"
            self.renderer.show_tool_event(name)
        elif event.type == SessionEventType.SESSION_ERROR:
            self._mark_response_started()
            msg = event.data.message if event.data.message else "Unknown error"
            print(f"\n[error] {msg}")
        elif event.type == SessionEventType.TOOL_USER_REQUESTED:
            # User confirmation requested for a tool - auto-approve handled by permission handler
            pass

    async def start(self) -> None:
        await self.client.start()
        self.session = await self.client.create_session(self.session_config())
        self.session.on(self._on_event)

    async def ask(self, prompt: str) -> None:
        self._awaiting_response = True
        self.renderer.show_working()
        try:
            await self.session.send_and_wait({"prompt": prompt}, timeout=600)
        finally:
            self._mark_response_started()

    def _mark_response_started(self) -> None:
        if not self._awaiting_response:
            return
        self._awaiting_response = False
        self.renderer.hide_working()

    async def repl(self) -> None:
        self.renderer.show_banner()
        bindings = KeyBindings()

        def _submit(event) -> None:
            event.app.current_buffer.validate_and_handle()

        @bindings.add("c-j")
        def _(event) -> None:
            _submit(event)

        session = PromptSession("puk> ", multiline=True, key_bindings=bindings)
        with patch_stdout():
            while True:
                raw = await session.prompt_async()
                stripped = raw.strip()
                if stripped in {"/exit", "/quit", "quit", "exit"}:
                    return
                if stripped:
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
