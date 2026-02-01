from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from copilot import CopilotClient
from copilot.generated.session_events import SessionEventType

from .config import PukConfig
from .reports import RunReport
from .ui import UserIO


@dataclass
class AgentContext:
    root: str
    provider: str
    model: str
    tools_enabled: list[str]
    confirm_mode: str


def build_system_prompt(config: PukConfig, root: str, tool_names: list[str] | None = None) -> str:
    safety = config.safety
    tools_policy = config.tools
    staging_mode = tools_policy.filesystem_policy.staging_mode
    prompt = f"""You are the PUK agent.

Workspace root: {root}
Scoping rules: stay within the workspace root unless policy explicitly allows otherwise.

Confirmation rules:
- confirm_mutations={safety.confirm_mutations}
- confirm_commands={safety.confirm_commands}
- confirm_installs={safety.confirm_installs}
- confirm_mcp={safety.confirm_mcp}

Staging policy: {staging_mode}

Tool usage etiquette:
- Use tools for any filesystem, command, or environment action.
- Ask for clarification using user I/O tools if required information is missing.
- Do not claim actions were performed without tool evidence.
"""
    if config.session.system_prompt_file:
        path = (Path(root) / config.session.system_prompt_file).expanduser()
        if path.exists() and path.is_file():
            extra = path.read_text(errors="ignore")
            prompt = f"{prompt}\\n{extra}"
    if tool_names:
        prompt = (
            prompt
            + "\nAvailable tools (use only these): "
            + ", ".join(sorted(tool_names))
            + "\n"
        )
    return prompt


class PukAgent:
    def __init__(
        self,
        config: PukConfig,
        tools: list,
        io: UserIO,
        report: RunReport,
        *,
        verbose: bool = False,
    ) -> None:
        self.config = config
        self.tools = tools
        self.io = io
        self.report = report
        self.verbose = verbose
        self.client = CopilotClient()
        self.session = None

    async def start(self) -> None:
        await self.client.start()
        tool_names = [tool.name for tool in self.tools]
        if not tool_names:
            tool_names = None
        session_config: dict[str, Any] = {
            "model": self.config.llm.model,
            "streaming": self.config.core.streaming,
            "tools": self.tools,
            "system_message": {
                "mode": "append",
                "content": build_system_prompt(
                    self.config, self.config.workspace.root, tool_names=tool_names
                ),
            },
            "infinite_sessions": {
                "enabled": self.config.session.infinite,
                "background_compaction_threshold": self.config.session.compaction_threshold,
            },
        }
        if self.config.tools.builtin_excluded:
            session_config["excluded_tools"] = self.config.tools.builtin_excluded
        if self.config.mcp.enabled and self.config.tools.mcp:
            session_config["mcp_servers"] = {
                name: server.model_dump() for name, server in self.config.mcp.servers.items()
            }
        self.session = await self.client.create_session(session_config)

        def handle_event(event):
            if self.verbose:
                asyncio.create_task(self._log_event(event))
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                delta = getattr(event.data, "delta_content", None) or ""
                if delta:
                    self.io.assistant_delta(delta)
            elif event.type in (
                SessionEventType.SESSION_IDLE,
                SessionEventType.ASSISTANT_TURN_END,
            ):
                self.io.assistant_complete()
            elif event.type == SessionEventType.TOOL_EXECUTION_START:
                tool_name = (
                    getattr(event.data, "tool_name", None)
                    or getattr(event.data, "mcp_tool_name", None)
                    or "tool"
                )
                self.io.tool_invocation(tool_name)
            elif event.type == SessionEventType.SESSION_ERROR:
                message = (
                    getattr(event.data, "message", None)
                    or getattr(event.data, "error", None)
                    or "Session error"
                )
                asyncio.create_task(self.io.display(str(message), "error"))

        self.session.on(handle_event)

    async def send(self, prompt: str) -> None:
        if not self.session:
            raise RuntimeError("Session not started")
        try:
            await self.session.send_and_wait(
                {"prompt": prompt},
                timeout=self.config.session.response_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await self.io.display(
                "Timed out waiting for session idle; the agent may still be working. "
                "Consider retrying or increasing session.response_timeout_seconds.",
                "warning",
            )
        except Exception as exc:
            await self.io.display(f"Session error: {exc}", "error")

    async def plan(self, prompt: str) -> str:
        system_prompt = "Provide a step-by-step plan only. Do not call tools."
        session = await self.client.create_session(
            {
                "model": self.config.llm.model,
                "streaming": False,
                "tools": [],
                "systemMessage": {"content": system_prompt},
            }
        )
        response = await session.send_and_wait({"prompt": prompt})
        await session.close()
        if isinstance(response, dict):
            return response.get("message", "") or str(response)
        return str(response)

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
        await self.client.stop()

    async def _log_event(self, event) -> None:
        data = event.data
        summary_parts: list[str] = [f"type={event.type.value}"]
        content = getattr(data, "content", None)
        delta = getattr(data, "delta_content", None)
        tool_name = getattr(data, "tool_name", None) or getattr(data, "mcp_tool_name", None)
        message = getattr(data, "message", None)
        if content:
            summary_parts.append(f"content={content[:200]!r}")
        if delta:
            summary_parts.append(f"delta={delta[:200]!r}")
        if tool_name:
            summary_parts.append(f"tool={tool_name}")
        if message:
            summary_parts.append(f"message={message!r}")
        await self.io.display("event: " + " ".join(summary_parts), level="info")
