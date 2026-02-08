from __future__ import annotations

import asyncio
import logging
import os
import re
import urllib.parse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from copilot import CopilotClient
from copilot.generated.session_events import SessionEvent, SessionEventType
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout

from puk.config import BYOK_PROVIDERS, LLMSettings
from puk.playbooks import is_path_within_scope
from puk.run import RunRecorder
from puk import runs as run_inspect
from puk.ui import ConsoleRenderer

_ENV_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_LOG = logging.getLogger("puk")


def _auto_approve_permission(request: dict, metadata: dict) -> dict:
    """Auto-approve all tool permission requests."""
    return {"kind": "approved"}


def _deny_permission(reason: str) -> dict:
    return {"kind": "denied", "reason": reason}


def _extract_tool_name(request: dict, metadata: dict) -> str:
    return (
        request.get("tool_name")
        or request.get("name")
        or metadata.get("tool_name")
        or metadata.get("name")
        or "unknown"
    )


def _extract_paths(request: dict, metadata: dict) -> list[str]:
    candidates = []
    for source in (request, metadata):
        for key in ("path", "paths", "file", "files", "target", "targets", "destination", "dest"):
            if key not in source:
                continue
            value = source[key]
            if isinstance(value, (list, tuple)):
                candidates.extend([str(item) for item in value])
            else:
                candidates.append(str(value))
    return [path for path in candidates if path]


def _tool_may_write(tool_name: str) -> bool:
    lowered = tool_name.lower()
    return any(token in lowered for token in ("write", "append", "edit", "create", "mkdir", "rm", "delete"))


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
    allowed_tools: list[str] | None = None
    write_scope: list[str] | None = None
    execution_mode: str | None = None


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
    def __init__(self, config: PukConfig, run_recorder: RunRecorder | None = None):
        self.config = config
        self.client = CopilotClient()
        self.session = None
        self.renderer: Renderer = ConsoleRenderer()
        self._awaiting_response = False
        self._effective_model = config.llm.model
        self.run_recorder = run_recorder
        self._active_turn_id: int | None = None
        self._output_buffer: list[str] = []
        self._capture_output = False
        self._last_output: str | None = None

    def session_config(self) -> dict:
        config = {
            "streaming": True,
            "working_directory": str(Path(self.config.workspace).resolve()),
            "excluded_tools": [],  # keep internal SDK tools enabled
            "system_message": {"content": DEFAULT_SYSTEM_PROMPT},
            "on_permission_request": self._permission_handler(),
            "temperature": self.config.llm.temperature,
            "max_output_tokens": self.config.llm.max_output_tokens,
        }
        if self._effective_model:
            config["model"] = self._effective_model
        provider = _provider_config(self.config.llm)
        if provider is not None:
            config["provider"] = provider
        return config

    def _permission_handler(self):
        if (
            self.config.execution_mode == "plan"
            or self.config.allowed_tools is not None
            or self.config.write_scope is not None
        ):
            allowed = set(self.config.allowed_tools or [])
            write_scope = self.config.write_scope or []
            workspace = Path(self.config.workspace)

            def _handler(request: dict, metadata: dict) -> dict:
                tool_name = _extract_tool_name(request, metadata)
                if self.config.execution_mode == "plan":
                    return _deny_permission("Tool execution is disabled in plan mode.")
                if self.config.allowed_tools is not None and tool_name not in allowed:
                    return _deny_permission(f"Tool '{tool_name}' is not allowed for this playbook.")
                if self.config.write_scope is not None and _tool_may_write(tool_name):
                    paths = _extract_paths(request, metadata)
                    if not paths:
                        return _deny_permission("Write scope enforcement requires a target path.")
                    for path in paths:
                        if not is_path_within_scope(path, workspace, write_scope):
                            return _deny_permission(
                                f"Path '{path}' is outside the allowed write scope."
                            )
                return {"kind": "approved"}

            return _handler
        return _auto_approve_permission

    def _on_event(self, event: SessionEvent) -> None:
        # Debug: uncomment to see all events
        # print(f"[DEBUG] {event.type}")
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            self._mark_response_started()
            chunk = event.data.delta_content
            if chunk:
                self.renderer.write_delta(chunk)
                if (self.run_recorder or self._capture_output) and self._active_turn_id is not None:
                    self._output_buffer.append(chunk)
        elif event.type == SessionEventType.ASSISTANT_TURN_END:
            self._mark_response_started()
            self.renderer.end_message()
            if self.run_recorder and self._active_turn_id is not None:
                text = "".join(self._output_buffer)
                self.run_recorder.record_model_output(text, turn_id=self._active_turn_id)
            if self._capture_output and self._active_turn_id is not None:
                self._last_output = "".join(self._output_buffer)
            self._output_buffer = []
            self._active_turn_id = None
            self._capture_output = False
        elif event.type == SessionEventType.TOOL_EXECUTION_START:
            self._mark_response_started()
            name = event.data.tool_name or "unknown"
            self.renderer.show_tool_event(name)
            if self.run_recorder:
                self.run_recorder.record_tool_call(name=name, turn_id=self._active_turn_id)
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
        if self.run_recorder:
            self.run_recorder.start(title_slug=self._title_slug())

    def _title_slug(self) -> str | None:
        # Use model or workspace name as a light slug when none is obvious.
        return Path(self.config.workspace).name

    async def ask(
        self,
        prompt: str,
        capture: bool = False,
        context_items: list[dict] | None = None,
    ) -> str | None:
        self._awaiting_response = True
        turn_id = self.run_recorder.next_turn_id() if self.run_recorder else None
        self._active_turn_id = turn_id
        self._output_buffer = []
        self._capture_output = capture
        self._last_output = None
        if self.run_recorder:
            self.run_recorder.record_user_input(prompt, turn_id=turn_id, context_items=context_items)
        self.renderer.show_working()
        try:
            await self.session.send_and_wait({"prompt": prompt}, timeout=600)
        except Exception as exc:
            if self.run_recorder:
                self.run_recorder.close(status="failed", reason=str(exc))
            raise RuntimeError(self._user_facing_error(exc)) from None
        finally:
            self._mark_response_started()
        return self._last_output

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
                # Local commands (not sent to model)
                if stripped.startswith("/runs"):
                    self._cmd_list_runs()
                    continue
                if stripped.startswith("/run "):
                    self._cmd_show_run(stripped.split(" ", 1)[1])
                    continue
                if stripped.startswith("/tail "):
                    self._cmd_tail_run(stripped.split(" ", 1)[1])
                    continue
                if stripped:
                    try:
                        await self.ask(raw)
                    except RuntimeError as exc:
                        print(f"\n[error] {exc}")

    async def close(self, status: str = "closed", reason: str = "completed") -> None:
        if self.session is not None:
            await self.session.destroy()
        await self.client.stop()
        if self.run_recorder:
            self.run_recorder.close(status=status, reason=reason)

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

    # ----- local inspection commands -----
    def _cmd_list_runs(self) -> None:
        runs = run_inspect.discover_runs(Path(self.config.workspace))
        print(run_inspect.format_runs_table(runs))

    def _cmd_show_run(self, ref: str) -> None:
        try:
            run_dir = run_inspect.resolve_run_ref(Path(self.config.workspace), ref)
            print(run_inspect.format_run_show(run_dir, tail=20))
        except Exception as exc:
            print(f"[runs] {exc}")

    def _cmd_tail_run(self, ref: str) -> None:
        try:
            run_dir = run_inspect.resolve_run_ref(Path(self.config.workspace), ref)
            for ev in run_inspect.tail_events(run_dir, follow=False):
                print(json.dumps(ev))
        except Exception as exc:
            print(f"[runs] {exc}")


async def run_app(config: PukConfig, one_shot_prompt: str | None = None, recorder: RunRecorder | None = None) -> None:
    app = PukApp(config, run_recorder=recorder)
    try:
        await app.start()
        if one_shot_prompt:
            await app.ask(one_shot_prompt)
            await app.close(status="closed", reason="completed")
            return
        await app.repl()
        await app.close(status="closed", reason="completed")
    except Exception as exc:
        await app.close(status="failed", reason=str(exc))
        raise


def run_sync(
    config: PukConfig,
    one_shot_prompt: str | None = None,
    append_to_run: str | None = None,
    argv: list[str] | None = None,
) -> None:
    recorder = RunRecorder(
        workspace=Path(config.workspace),
        mode="oneshot" if one_shot_prompt else "repl",
        llm=config.llm,
        append_to_run=append_to_run,
        argv=argv or [],
    )
    asyncio.run(run_app(config, one_shot_prompt=one_shot_prompt, recorder=recorder))
