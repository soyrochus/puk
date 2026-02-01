from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import venv
from pathlib import Path
from typing import Literal

from copilot.tools import define_tool
from pydantic import BaseModel, Field

from ..errors import ToolExecutionError
from ..reports import RunReport
from ..ui import UserIO
from ..workspace import Workspace


class PythonGenerateParams(BaseModel):
    spec: str = Field(description="Specification for the code to generate")
    files: list[str] = Field(default_factory=list, description="Target files")
    constraints: str = Field(default="", description="Constraints for generation")


class PythonExecParams(BaseModel):
    entrypoint: str = Field(description="Python file or module to execute")
    args: list[str] = Field(default_factory=list, description="Arguments to pass")
    venv_policy: Literal["local", "global-cache", "default"] = Field(default="default")
    cwd: str = Field(default=".", description="Working directory")


def _venv_path(root: Path, mode: str, local_dir: str, global_dir: str) -> Path:
    if mode == "local":
        return root / local_dir
    hash_id = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    return Path(global_dir).expanduser() / hash_id


def create_python_tools(
    workspace: Workspace,
    io: UserIO,
    report: RunReport,
    *,
    venv_mode: str,
    local_venv_dir: str,
    global_cache_dir: str,
    auto_create_venv: bool,
    auto_install_requirements: bool,
    exec_timeout_seconds: int,
    confirm_installs: bool,
) -> list:
    @define_tool(description="Generate Python code based on a specification")
    async def python_generate(params: PythonGenerateParams) -> dict:
        result = {
            "message": "python_generate is a placeholder in this build",
            "spec": params.spec,
            "files": params.files,
            "constraints": params.constraints,
            "proposed_code_bundle": {},
        }
        report.log_tool("python_generate", params.model_dump(), {"files": params.files})
        return result

    @define_tool(description="Execute Python code in an isolated virtual environment")
    async def python_exec(params: PythonExecParams) -> dict:
        mode = venv_mode if params.venv_policy == "default" else params.venv_policy
        venv_dir = _venv_path(workspace.root, mode, local_venv_dir, global_cache_dir)
        if not venv_dir.exists():
            if not auto_create_venv:
                return {"error": "Virtual environment not found"}
            if confirm_installs:
                confirmed = await io.confirm(f"Create virtual environment at {venv_dir}?", False)
                report.log_decision(f"create venv {venv_dir}", confirmed)
                if not confirmed:
                    return {"aborted": True}
            venv_dir.parent.mkdir(parents=True, exist_ok=True)
            venv.EnvBuilder(with_pip=True).create(venv_dir)
        python_bin = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
        if not python_bin.exists():
            return {"error": "Python executable not found in venv"}

        cwd = workspace.resolve_path(params.cwd)
        entry = params.entrypoint
        entry_path = Path(entry)
        if not entry_path.is_absolute():
            candidate = cwd / entry_path
            if candidate.exists():
                entry = str(candidate)
        cmd = [str(python_bin), entry, *params.args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=exec_timeout_seconds)
        except asyncio.TimeoutError:
            raise ToolExecutionError("Python execution timed out")
        result = {
            "exit_code": proc.returncode,
            "stdout": stdout.decode(errors="ignore"),
            "stderr": stderr.decode(errors="ignore"),
        }
        report.add_command(" ".join(cmd))
        report.log_tool("python_exec", params.model_dump(), {"exit_code": proc.returncode})
        return result

    return [python_generate, python_exec]
