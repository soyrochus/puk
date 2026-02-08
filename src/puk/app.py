from __future__ import annotations

import asyncio
import logging
import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from copilot import CopilotClient
from copilot.generated.session_events import SessionEvent, SessionEventType
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout

from puk.config import BYOK_PROVIDERS, LLMSettings
from puk.ui import ConsoleRenderer

_ENV_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_LOG = logging.getLogger("puk")


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
    workspace: str = "."
    llm: LLMSettings = LLMSettings()


def _looks_like_env_var_name(value: str) -> bool:
    return bool(_ENV_NAME_PATTERN.match(value))


def _resolve_api_key(settings: LLMSettings) -> str:
    env_value = os.environ.get(settings.api_key)
    if env_value:
        return env_value
    # Backward-compatible fallback: allow direct key in config when value is not env-var-like.
    if not _looks_like_env_var_name(settings.api_key):
        return settings.api_key
    raise ValueError(
        f"Environment variable '{settings.api_key}' is not set for provider '{settings.provider}'."
    )


def _provider_config(settings: LLMSettings) -> dict | None:
    if settings.provider == "copilot":
        return None
    if settings.provider not in BYOK_PROVIDERS:
        raise ValueError(f"Unsupported provider '{settings.provider}'.")
    api_key = _resolve_api_key(settings)
    if settings.provider == "azure":
        parsed = urllib.parse.urlparse(settings.azure_endpoint)
        base_url = settings.azure_endpoint.rstrip("/")
        if parsed.scheme and parsed.netloc and "/openai/deployments/" in parsed.path:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        return {
            "type": "azure",
            "base_url": base_url,
            "api_key": api_key,
            "azure": {"api_version": settings.azure_api_version},
        }
    if settings.provider == "openai":
        return {"type": "openai", "base_url": "https://api.openai.com/v1", "api_key": api_key}
    if settings.provider == "anthropic":
        return {"type": "anthropic", "base_url": "https://api.anthropic.com", "api_key": api_key}
    raise ValueError(f"Unsupported provider '{settings.provider}'.")


class PukApp:
    def __init__(self, config: PukConfig):
        self.config = config
        self.client = CopilotClient()
        self.session = None
        self.renderer: Renderer = ConsoleRenderer()
        self._awaiting_response = False
        self._effective_model = config.llm.model

    def session_config(self) -> dict:
        config = {
            "streaming": True,
            "working_directory": str(Path(self.config.workspace).resolve()),
            "excluded_tools": [],  # keep internal SDK tools enabled
            "system_message": {"content": DEFAULT_SYSTEM_PROMPT},
            "on_permission_request": _auto_approve_permission,
            "temperature": self.config.llm.temperature,
            "max_output_tokens": self.config.llm.max_output_tokens,
        }
        if self._effective_model:
            config["model"] = self._effective_model
        provider = _provider_config(self.config.llm)
        if provider is not None:
            config["provider"] = provider
        return config

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
            # Errors are surfaced via send_and_wait exceptions; avoid duplicate prints here.
            pass
        elif event.type == SessionEventType.TOOL_USER_REQUESTED:
            # User confirmation requested for a tool - auto-approve handled by permission handler
            pass

    async def start(self) -> None:
        await self.client.start()
        self.session = await self.client.create_session(self.session_config())
        self.session.on(self._on_event)
        await self._log_backend_selected_model()

    async def ask(self, prompt: str) -> None:
        self._awaiting_response = True
        self.renderer.show_working()
        try:
            await self.session.send_and_wait({"prompt": prompt}, timeout=600)
        except Exception as exc:
            raise RuntimeError(self._user_facing_error(exc)) from None
        finally:
            self._mark_response_started()

    def _user_facing_error(self, exc: Exception) -> str:
        message = str(exc)
        if (
            self.config.llm.provider == "azure"
            and not self.config.llm.model
            and "No model available" in message
        ):
            return (
                "Azure returned 'No model available' for model=<auto>. "
                "No model is being passed by Puk for Azure; check Azure endpoint policy/config."
            )
        return message

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
                    try:
                        await self.ask(raw)
                    except RuntimeError as exc:
                        print(f"\n[error] {exc}")

    async def close(self) -> None:
        if self.session is not None:
            await self.session.destroy()
        await self.client.stop()

    async def _log_backend_selected_model(self) -> None:
        """Log backend-confirmed selected model from session.start, when available."""
        try:
            messages = await self.session.get_messages()
        except Exception:
            return
        for message in reversed(messages):
            if message.type == SessionEventType.SESSION_START:
                selected = getattr(message.data, "selected_model", None)
                if selected:
                    _LOG.info("LLM backend selected_model=%s", selected)
                return


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
