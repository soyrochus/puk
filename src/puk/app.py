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
from copilot.tools import define_tool
from copilot.types import Tool
from copilot.generated.session_events import SessionEvent, SessionEventType
from pydantic import BaseModel, Field
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

_TOOL_ALIASES: dict[str, str] = {
    "read": "read_file",
    "read_file": "read_file",
    "fs.read": "read_file",
    "view": "view",
    "edit": "edit",
    "edit_file": "edit",
    "fs.write": "write_file",
    "write_file": "write_file",
    "create_file": "create_file",
    "create_directory": "create_directory",
    "mkdir": "create_directory",
    "list directory": "list_directory",
    "list_directory": "list_directory",
    "ls": "list_directory",
    "glob_search": "glob",
    "grep_search": "grep",
}


class _PathParams(BaseModel):
    path: str = Field(description="Path relative to workspace or absolute path within workspace")


class _CreateFileParams(BaseModel):
    path: str = Field(description="File path to create")
    content: str = Field(default="", description="Initial file content")


class _WriteFileParams(BaseModel):
    path: str = Field(description="File path to write")
    content: str = Field(description="Content to write")
    append: bool = Field(default=False, description="Append instead of overwrite")


class _ReadFileParams(BaseModel):
    path: str = Field(description="File path to read")
    start_line: int | None = Field(default=None, ge=1, description="1-based inclusive start line")
    end_line: int | None = Field(default=None, ge=1, description="1-based inclusive end line")


class _ListDirectoryParams(BaseModel):
    path: str = Field(default=".", description="Directory path to list")
    recursive: bool = Field(default=False, description="Recursively list contents")
    max_entries: int = Field(default=200, ge=1, le=5000, description="Maximum entries to return")


def _auto_approve_permission(request: dict, metadata: dict) -> dict:
    """Auto-approve all tool permission requests."""
    return {"kind": "approved"}


def _deny_permission(reason: str) -> dict:
    return {"kind": "denied-interactively-by-user", "reason": reason}


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


def _normalize_tool_name(name: str) -> str:
    normalized = " ".join(name.strip().split())
    lowered = normalized.lower()
    return _TOOL_ALIASES.get(lowered, lowered.replace(" ", "_"))


def _tool_requires_existing_target(tool_name: str) -> bool:
    lowered = _normalize_tool_name(tool_name)
    return lowered in {"edit"}


def _truncate(text: str, limit: int = 240) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _summarize_json(value: object, limit: int = 240) -> str:
    try:
        return _truncate(json.dumps(value, ensure_ascii=True, sort_keys=True), limit=limit)
    except Exception:
        return _truncate(str(value), limit=limit)


def _coerce_turn_id(raw: object) -> int | None:
    if raw is None:
        return None
    try:
        text = str(raw).strip()
        if not text:
            return None
        return int(text)
    except Exception:
        return None


def _extract_error_message(raw_error: object) -> str:
    if raw_error is None:
        return ""
    if isinstance(raw_error, str):
        return raw_error
    message = getattr(raw_error, "message", None)
    if message:
        return str(message)
    return str(raw_error)


def _summarize_tool_result_data(data: object) -> tuple[bool | None, str | None]:
    success = getattr(data, "success", None)
    error = _extract_error_message(getattr(data, "error", None))
    result_obj = getattr(data, "result", None)
    result_text = ""
    if result_obj is not None:
        detailed = getattr(result_obj, "detailed_content", None)
        content = getattr(result_obj, "content", None)
        if detailed:
            result_text = str(detailed)
        elif content:
            result_text = str(content)
        else:
            result_text = str(result_obj)
    if error:
        summary = f"error: {error}"
    elif result_text:
        summary = result_text
    else:
        summary = None
    return success, (_truncate(summary, 400) if summary else None)


DEFAULT_SYSTEM_PROMPT = """You are Puk, a pragmatic local coding assistant.
Use SDK internal tools whenever useful to inspect files and run searches.
When users ask for codebase discovery tasks, use filesystem/search tools before answering.
"""


class Renderer(Protocol):
    def show_banner(self) -> None: ...

    def show_tool_event(self, tool_name: str) -> None: ...

    def show_tool_result(self, tool_name: str, success: bool | None, summary: str | None) -> None: ...

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
        self._last_tool_name: str | None = None
        self._identical_tool_streak = 0
        self._tool_name_by_call_id: dict[str, str] = {}
        self._last_tool_failure_signature: str | None = None
        self._identical_tool_failure_streak = 0
        self._max_identical_tool_calls = self._read_positive_int_env(
            "PUK_MAX_IDENTICAL_TOOL_CALLS", default=120
        )
        self._max_identical_tool_failures = self._read_positive_int_env(
            "PUK_MAX_IDENTICAL_TOOL_FAILURES", default=8
        )

    def session_config(self) -> dict:
        normalized_tools: list[str] | None = None
        excluded_tools = []
        if self.config.allowed_tools is not None:
            normalized_tools = self._normalize_allowed_tools(self.config.allowed_tools)
            allowed_lower = {name.strip().lower() for name in normalized_tools}
            # Prevent shell fallback when a playbook does not allow bash.
            if "bash" not in allowed_lower:
                excluded_tools.append("bash")
        config = {
            "streaming": True,
            "working_directory": str(Path(self.config.workspace).resolve()),
            "excluded_tools": excluded_tools,
            "system_message": {"content": DEFAULT_SYSTEM_PROMPT},
            "on_permission_request": self._permission_handler(),
            "temperature": self.config.llm.temperature,
            "max_output_tokens": self.config.llm.max_output_tokens,
        }
        if normalized_tools is not None:
            # Prefer SDK-native allowlisting so unavailable tools are hidden from the model.
            config["available_tools"] = normalized_tools
            compatibility_tools = self._build_compatibility_tools(normalized_tools)
            if compatibility_tools:
                config["tools"] = compatibility_tools
        if self._effective_model:
            config["model"] = self._effective_model
        provider = _provider_config(self.config.llm)
        if provider is not None:
            config["provider"] = provider
        return config

    def _permission_handler(self):
        if self.config.execution_mode == "plan" or self.config.write_scope is not None:
            write_scope = self.config.write_scope or []
            workspace = Path(self.config.workspace)

            def _handler(request: dict, metadata: dict) -> dict:
                tool_name = _normalize_tool_name(_extract_tool_name(request, metadata))
                if self.config.execution_mode == "plan":
                    return _deny_permission("Tool execution is disabled in plan mode.")
                if self.config.write_scope is not None and _tool_may_write(tool_name):
                    paths = _extract_paths(request, metadata)
                    if not paths:
                        return _deny_permission("Write scope enforcement requires a target path.")
                    for path in paths:
                        if not is_path_within_scope(path, workspace, write_scope):
                            return _deny_permission(
                                f"Path '{path}' is outside the allowed write scope."
                            )
                        if _tool_requires_existing_target(tool_name):
                            resolved = Path(path)
                            if not resolved.is_absolute():
                                resolved = (workspace / resolved).resolve()
                            if not resolved.exists():
                                return _deny_permission(
                                    f"Target path '{path}' does not exist for tool '{tool_name}'. "
                                    "Use create_file/write_file/create_directory first."
                                )
                return {"kind": "approved"}

            return _handler
        return _auto_approve_permission

    def _on_event(self, event: SessionEvent) -> None:
        # Debug: uncomment to see all events
        # print(f"[DEBUG] {event.type}")
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            self._mark_response_started()
            self._reset_tool_loop_state()
            chunk = event.data.delta_content
            if chunk:
                self.renderer.write_delta(chunk)
                if (self.run_recorder or self._capture_output) and self._active_turn_id is not None:
                    self._output_buffer.append(chunk)
        elif event.type == SessionEventType.ASSISTANT_REASONING_DELTA:
            self._mark_response_started()
            self._reset_tool_loop_state()
        elif event.type == SessionEventType.ASSISTANT_TURN_END:
            self._mark_response_started()
            self._reset_tool_loop_state()
            self._tool_name_by_call_id = {}
            self._reset_tool_failure_state()
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
            tool_call_id = event.data.tool_call_id
            if tool_call_id:
                self._tool_name_by_call_id[tool_call_id] = name
            arguments = (
                _summarize_json(event.data.arguments)
                if getattr(event.data, "arguments", None) is not None
                else None
            )
            self.renderer.show_tool_event(name)
            turn_id = self._resolve_turn_id(event.data.turn_id)
            if self.run_recorder:
                self.run_recorder.record_tool_call(
                    name=name,
                    turn_id=turn_id,
                    tool_call_id=tool_call_id,
                    arguments=arguments,
                )
            self._record_tool_streak(name)
            if self._max_identical_tool_calls and self._identical_tool_streak > self._max_identical_tool_calls:
                raise RuntimeError(
                    f"Tool loop guard triggered after {self._identical_tool_streak} consecutive '{name}' calls."
                )
        elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
            success, result = _summarize_tool_result_data(event.data)
            turn_id = self._resolve_turn_id(event.data.turn_id)
            tool_call_id = event.data.tool_call_id
            name = event.data.tool_name or self._tool_name_by_call_id.get(tool_call_id) or "unknown"
            if tool_call_id:
                self._tool_name_by_call_id.pop(tool_call_id, None)
            self.renderer.show_tool_result(name, success, result)
            self._record_tool_failure(name, success, result)
            if self.run_recorder:
                self.run_recorder.record_tool_result(
                    name=name,
                    turn_id=turn_id,
                    tool_call_id=tool_call_id,
                    success=success,
                    result=result,
                )
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
        self._tool_name_by_call_id = {}
        self._reset_tool_loop_state()
        self._reset_tool_failure_state()
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

    def _resolve_turn_id(self, event_turn_id: object) -> int | None:
        if self._active_turn_id is not None:
            return self._active_turn_id
        parsed = _coerce_turn_id(event_turn_id)
        if parsed is not None:
            return parsed
        if self.run_recorder and self.run_recorder.turn_id > 0:
            return self.run_recorder.turn_id
        return None

    def _record_tool_streak(self, tool_name: str) -> None:
        if tool_name == self._last_tool_name:
            self._identical_tool_streak += 1
        else:
            self._last_tool_name = tool_name
            self._identical_tool_streak = 1

    def _reset_tool_loop_state(self) -> None:
        self._last_tool_name = None
        self._identical_tool_streak = 0

    def _record_tool_failure(self, tool_name: str, success: bool | None, result: str | None) -> None:
        if success is not False:
            self._reset_tool_failure_state()
            return
        snippet = " ".join((result or "").split())
        if len(snippet) > 180:
            snippet = snippet[:177] + "..."
        signature = f"{tool_name}:{snippet}"
        if signature == self._last_tool_failure_signature:
            self._identical_tool_failure_streak += 1
        else:
            self._last_tool_failure_signature = signature
            self._identical_tool_failure_streak = 1
        if (
            self._max_identical_tool_failures
            and self._identical_tool_failure_streak > self._max_identical_tool_failures
        ):
            raise RuntimeError(
                "Tool failure loop guard triggered after "
                f"{self._identical_tool_failure_streak} identical failures from '{tool_name}'. "
                "This often indicates the model is using an edit tool on a file that does not exist."
            )

    def _reset_tool_failure_state(self) -> None:
        self._last_tool_failure_signature = None
        self._identical_tool_failure_streak = 0

    def _read_positive_int_env(self, name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError:
            _LOG.warning("Ignoring invalid %s=%r (expected integer).", name, raw)
            return default
        return max(0, value)

    def _normalize_allowed_tools(self, allowed_tools: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for name in allowed_tools:
            canonical = _normalize_tool_name(name)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            normalized.append(canonical)
        return normalized

    def _build_compatibility_tools(self, allowed_tools: list[str]) -> list[Tool]:
        allowed = set(allowed_tools)
        tools: list[Tool] = []

        def _create_directory(params: _PathParams, _invocation):
            target = self._resolve_workspace_path(params.path)
            self._assert_write_scope(target)
            target.mkdir(parents=True, exist_ok=True)
            return f"created directory: {target}"

        def _create_file(params: _CreateFileParams, _invocation):
            target = self._resolve_workspace_path(params.path)
            self._assert_write_scope(target)
            if target.exists():
                raise FileExistsError(f"Path already exists: {target}")
            if not target.parent.exists():
                raise FileNotFoundError(f"Parent directory does not exist: {target.parent}")
            target.write_text(params.content, encoding="utf-8")
            return f"created file: {target}"

        def _write_file(params: _WriteFileParams, _invocation):
            target = self._resolve_workspace_path(params.path)
            self._assert_write_scope(target)
            if not target.parent.exists():
                raise FileNotFoundError(f"Parent directory does not exist: {target.parent}")
            mode = "a" if params.append else "w"
            with target.open(mode, encoding="utf-8") as handle:
                handle.write(params.content)
            return f"wrote file: {target}"

        def _read_file(params: _ReadFileParams, _invocation):
            target = self._resolve_workspace_path(params.path)
            if not target.exists():
                raise FileNotFoundError(f"Path does not exist: {target}")
            if target.is_dir():
                raise IsADirectoryError(f"Path is a directory: {target}")
            text = target.read_text(encoding="utf-8")
            if params.start_line is None and params.end_line is None:
                return text
            lines = text.splitlines()
            start_idx = (params.start_line - 1) if params.start_line is not None else 0
            end_idx = params.end_line if params.end_line is not None else len(lines)
            return "\n".join(lines[start_idx:end_idx])

        def _list_directory(params: _ListDirectoryParams, _invocation):
            target = self._resolve_workspace_path(params.path)
            if not target.exists():
                raise FileNotFoundError(f"Path does not exist: {target}")
            if not target.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {target}")
            entries = (
                sorted(target.rglob("*")) if params.recursive else sorted(target.iterdir())
            )[: params.max_entries]
            workspace = Path(self.config.workspace).resolve()
            lines = []
            for entry in entries:
                rel = entry.relative_to(workspace)
                suffix = "/" if entry.is_dir() else ""
                lines.append(f"{rel.as_posix()}{suffix}")
            return "\n".join(lines)

        if "create_directory" in allowed:
            tools.append(
                define_tool(
                    name="create_directory",
                    description="Create a directory path inside the workspace.",
                    handler=_create_directory,
                    params_type=_PathParams,
                )
            )
        if "create_file" in allowed:
            tools.append(
                define_tool(
                    name="create_file",
                    description="Create a new file with optional initial content.",
                    handler=_create_file,
                    params_type=_CreateFileParams,
                )
            )
        if "write_file" in allowed:
            tools.append(
                define_tool(
                    name="write_file",
                    description="Write or append file content. Creates the file if missing.",
                    handler=_write_file,
                    params_type=_WriteFileParams,
                )
            )
        if "read_file" in allowed:
            tools.append(
                define_tool(
                    name="read_file",
                    description="Read a file from the workspace, optionally by line range.",
                    handler=_read_file,
                    params_type=_ReadFileParams,
                )
            )
        if "list_directory" in allowed:
            tools.append(
                define_tool(
                    name="list_directory",
                    description="List directory contents from the workspace.",
                    handler=_list_directory,
                    params_type=_ListDirectoryParams,
                )
            )
        return tools

    def _resolve_workspace_path(self, raw_path: str) -> Path:
        workspace = Path(self.config.workspace).resolve()
        path = Path(raw_path)
        if not path.is_absolute():
            path = (workspace / path).resolve()
        else:
            path = path.resolve()
        if not path.is_relative_to(workspace):
            raise PermissionError(f"Path '{raw_path}' is outside the workspace.")
        return path

    def _assert_write_scope(self, path: Path) -> None:
        if self.config.write_scope is None:
            return
        workspace = Path(self.config.workspace).resolve()
        if not is_path_within_scope(str(path), workspace, self.config.write_scope):
            raise PermissionError(f"Path '{path}' is outside the allowed write scope.")

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
                tools = getattr(message.data, "tools", None)
                if tools:
                    _LOG.debug("LLM backend tools=%s", ",".join(tools))
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
    except BaseException as exc:
        reason = "interrupted by user" if isinstance(exc, KeyboardInterrupt) else str(exc)
        await app.close(status="failed", reason=reason)
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
