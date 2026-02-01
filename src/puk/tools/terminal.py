from __future__ import annotations

import asyncio
import os
import shlex
from pathlib import Path

from copilot.tools import define_tool
from pydantic import BaseModel, Field

from ..errors import PolicyViolationError, ToolExecutionError
from ..workspace import Workspace
from ..reports import RunReport
from ..ui import UserIO


class RunCommandParams(BaseModel):
    cmd: str = Field(description="Command to run")
    cwd: str = Field(default=".", description="Working directory")
    timeout: int = Field(default=0, description="Timeout in seconds")
    env_allowlist: list[str] = Field(default_factory=list, description="Environment variables to pass through")
    shell: bool = Field(default=False, description="Run command via shell")


def create_terminal_tool(
    workspace: Workspace,
    io: UserIO,
    report: RunReport,
    *,
    confirm_commands: bool,
    allowlist: list[str],
    denylist: list[str],
    default_timeout: int,
    shell_default: bool,
) -> list:
    @define_tool(description="Run a command in the terminal")
    async def run_command(params: RunCommandParams) -> dict:
        cwd = workspace.resolve_path(params.cwd)
        if not cwd.exists() or not cwd.is_dir():
            return {"error": f"Invalid cwd: {params.cwd}"}
        cmd_text = params.cmd
        if not cmd_text.strip():
            return {"error": "Empty command"}

        first_token = shlex.split(cmd_text)[0]
        if first_token in denylist:
            raise PolicyViolationError(f"Command denied by policy: {first_token}")
        if allowlist and first_token not in allowlist:
            raise PolicyViolationError(f"Command not in allowlist: {first_token}")

        if confirm_commands:
            confirmed = await io.confirm(f"Run command: {cmd_text}?", False)
            report.log_decision(f"run command: {cmd_text}", confirmed)
            if not confirmed:
                return {"aborted": True}

        timeout = params.timeout or default_timeout
        if params.shell and not shell_default:
            raise PolicyViolationError("Shell execution disabled by policy")
        shell = params.shell if params.shell is not None else shell_default
        env = None
        if params.env_allowlist:
            env = {k: v for k, v in dict(**os.environ).items() if k in params.env_allowlist}

        try:
            if shell:
                proc = await asyncio.create_subprocess_shell(
                    cmd_text,
                    cwd=str(cwd),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env or None,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *shlex.split(cmd_text),
                    cwd=str(cwd),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env or None,
                )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                raise ToolExecutionError("Command timed out")
            result = {
                "exit_code": proc.returncode,
                "stdout": stdout.decode(errors="ignore"),
                "stderr": stderr.decode(errors="ignore"),
            }
            report.add_command(cmd_text)
            report.log_tool("run_command", params.model_dump(), {"exit_code": proc.returncode})
            return result
        except Exception as exc:
            raise ToolExecutionError(f"Command failed: {exc}") from exc

    return [run_command]
