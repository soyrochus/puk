from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Literal

from copilot.tools import define_tool
from pydantic import BaseModel, Field

from ..errors import PolicyViolationError, ToolExecutionError
from ..staging import StagingManager
from ..workspace import Workspace
from ..reports import RunReport
from ..ui import UserIO


class ListDirectoryParams(BaseModel):
    path: str = Field(default=".", description="Directory to list")
    pattern: str = Field(default="*", description="Glob pattern to filter files")
    limit: int = Field(default=200, description="Maximum entries to return")


class ReadFileParams(BaseModel):
    path: str = Field(description="Path to the file to read")
    max_bytes: int = Field(default=0, description="Max bytes to read (0 for default)")
    redact_secrets: bool | None = Field(default=None, description="Whether to redact secrets")


class WriteFileParams(BaseModel):
    path: str = Field(description="Path to the file to write")
    content: str = Field(description="File contents")
    mode: Literal["create", "overwrite", "patch"] = Field(default="overwrite")


class DeletePathParams(BaseModel):
    path: str = Field(description="Path to delete")
    recursive: bool = Field(default=False, description="Delete directories recursively")


class MovePathParams(BaseModel):
    src: str = Field(description="Source path")
    dst: str = Field(description="Destination path")


class SearchTextParams(BaseModel):
    query: str = Field(description="Search query")
    globs: list[str] = Field(default_factory=list, description="Optional glob patterns")
    max_hits: int = Field(default=50, description="Maximum number of hits")


def _redact(text: str) -> str:
    patterns = [
        re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|private_key)\s*[:=]\s*[^\s]+"),
    ]
    redacted = text
    for pattern in patterns:
        redacted = pattern.sub(lambda m: m.group(0).split(":")[0] + ": [REDACTED]", redacted)
    return redacted


def _apply_unified_diff(original: str, diff_text: str) -> str:
    lines = original.splitlines(keepends=True)
    diff_lines = diff_text.splitlines(keepends=True)
    result: list[str] = []
    i = 0
    idx = 0
    while i < len(diff_lines):
        line = diff_lines[i]
        if line.startswith("@@"):
            # parse hunk header
            header = line
            i += 1
            try:
                _, ranges, _ = header.split("@@")
                old_range, new_range = ranges.strip().split(" ")
                old_start = int(old_range.split(",")[0].lstrip("-")) - 1
            except Exception as exc:
                raise ToolExecutionError("Invalid patch format") from exc
            # copy unchanged lines up to hunk
            while idx < old_start:
                result.append(lines[idx])
                idx += 1
            # apply hunk
            while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                hunk_line = diff_lines[i]
                if hunk_line.startswith("+"):
                    result.append(hunk_line[1:])
                elif hunk_line.startswith("-"):
                    idx += 1
                elif hunk_line.startswith(" "):
                    result.append(lines[idx])
                    idx += 1
                i += 1
        elif line.startswith("---") or line.startswith("+++"):
            i += 1
        else:
            i += 1
    # append remaining
    result.extend(lines[idx:])
    return "".join(result)


def create_filesystem_tools(
    workspace: Workspace,
    staging: StagingManager,
    io: UserIO,
    report: RunReport,
    *,
    confirm_mutations: bool,
    allow_delete: bool,
    allow_overwrite: bool,
    staging_mode: str,
    max_write_files: int,
    redact_secrets_default: bool,
    dry_run: bool = False,
    paranoid_reads: bool = False,
) -> list:
    write_count = {"count": 0}

    async def _confirm_and_apply(change, diff_text: str) -> bool:
        if diff_text:
            io.render_diff(diff_text)
            report.add_diff(diff_text)
        if confirm_mutations:
            confirmed = await io.confirm("Apply this change?", False)
            report.log_decision("apply change", confirmed)
            if not confirmed:
                return False
        if not dry_run:
            staging.apply_all()
        return True

    @define_tool(description="List files in a directory")
    async def list_directory(params: ListDirectoryParams) -> dict:
        path = workspace.resolve_path(params.path)
        if not path.exists():
            return {"error": f"Directory not found: {params.path}"}
        if not path.is_dir():
            return {"error": f"Not a directory: {params.path}"}
        files = []
        for entry in sorted(path.iterdir()):
            if workspace.should_ignore(entry):
                continue
            if not fnmatch.fnmatch(entry.name, params.pattern):
                continue
            files.append(
                {
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else None,
                }
            )
            if len(files) >= params.limit:
                break
        result = {"path": str(path), "files": files, "total": len(files)}
        report.log_tool("list_directory", params.model_dump(), result)
        return result

    @define_tool(description="Read the contents of a file")
    async def read_file(params: ReadFileParams) -> dict:
        path = workspace.resolve_path(params.path)
        workspace.ensure_allowed(path)
        if not path.exists():
            return {"error": f"File not found: {params.path}"}
        if not path.is_file():
            return {"error": f"Not a file: {params.path}"}
        if paranoid_reads:
            rel = path.relative_to(workspace.root).as_posix()
            if any(fnmatch.fnmatch(rel, pattern) for pattern in workspace.deny_globs):
                confirmed = await io.confirm(f"Read sensitive file {rel}?", False)
                report.log_decision(f"read sensitive {rel}", confirmed)
                if not confirmed:
                    return {"aborted": True}
        max_bytes = params.max_bytes or workspace.max_file_bytes
        if path.stat().st_size > max_bytes:
            return {"error": f"File too large ({path.stat().st_size} bytes)"}
        content = path.read_text(errors="ignore")
        redact = params.redact_secrets
        if redact is None:
            redact = redact_secrets_default
        if redact:
            content = _redact(content)
        result = {"path": str(path), "content": content, "size": len(content)}
        report.log_tool("read_file", params.model_dump(), {"path": str(path), "size": len(content)})
        return result

    @define_tool(description="Write contents to a file")
    async def write_file(params: WriteFileParams) -> dict:
        if write_count["count"] >= max_write_files:
            raise ToolExecutionError("Exceeded max_write_files limit")
        path = workspace.resolve_path(params.path)
        workspace.ensure_allowed(path)
        if params.mode == "create" and path.exists():
            return {"error": "File already exists"}
        if params.mode == "overwrite" and path.exists() and not allow_overwrite:
            return {"error": "Overwrite not allowed by policy"}
        new_content = params.content
        if params.mode == "patch":
            if not path.exists():
                return {"error": "Cannot patch missing file"}
            original = path.read_text(errors="ignore")
            new_content = _apply_unified_diff(original, params.content)
        change = staging.stage_write(path, new_content, reason="write_file")
        write_count["count"] += 1
        report.add_file(path)
        diff_text = staging.diff_for_change(change)
        if staging_mode == "direct":
            if confirm_mutations:
                confirmed = await io.confirm(f"Write file {path}?", False)
                report.log_decision(f"write file {path}", confirmed)
                if not confirmed:
                    return {"aborted": True}
            if not dry_run:
                staging.apply_all()
            if diff_text:
                report.add_diff(diff_text)
            result = {"written": True, "path": str(path)}
            report.log_tool("write_file", params.model_dump(), result)
            return result
        if not confirm_mutations:
            if not dry_run:
                staging.apply_all()
            if diff_text:
                report.add_diff(diff_text)
            result = {"written": True, "path": str(path)}
            report.log_tool("write_file", params.model_dump(), result)
            return result
        await _confirm_and_apply(change, diff_text)
        result = {"staged": True, "path": str(path)}
        report.log_tool("write_file", params.model_dump(), result)
        return result

    @define_tool(description="Delete a file or directory")
    async def delete_path(params: DeletePathParams) -> dict:
        if not allow_delete:
            return {"error": "Delete not allowed by policy"}
        path = workspace.resolve_path(params.path)
        workspace.ensure_allowed(path)
        if not path.exists():
            return {"error": "Path not found"}
        if path.is_dir() and not params.recursive:
            return {"error": "Refusing to delete directory without recursive=true"}
        change = staging.stage_delete(path, reason="delete_path")
        report.add_file(path)
        diff_text = staging.diff_for_change(change)
        if staging_mode == "direct":
            if confirm_mutations:
                confirmed = await io.confirm(f"Delete {path}?", False)
                report.log_decision(f"delete {path}", confirmed)
                if not confirmed:
                    return {"aborted": True}
            if not dry_run:
                staging.apply_all()
            report.add_diff(diff_text)
            result = {"deleted": True, "path": str(path)}
            report.log_tool("delete_path", params.model_dump(), result)
            return result
        if not confirm_mutations:
            if not dry_run:
                staging.apply_all()
            report.add_diff(diff_text)
            result = {"deleted": True, "path": str(path)}
            report.log_tool("delete_path", params.model_dump(), result)
            return result
        await _confirm_and_apply(change, diff_text)
        result = {"staged": True, "path": str(path)}
        report.log_tool("delete_path", params.model_dump(), result)
        return result

    @define_tool(description="Move or rename a path")
    async def move_path(params: MovePathParams) -> dict:
        src = workspace.resolve_path(params.src)
        dst = workspace.resolve_path(params.dst)
        workspace.ensure_allowed(src)
        workspace.ensure_allowed(dst)
        if not src.exists():
            return {"error": "Source not found"}
        change = staging.stage_move(src, dst, reason="move_path")
        report.add_file(src)
        report.add_file(dst)
        diff_text = staging.diff_for_change(change)
        if staging_mode == "direct":
            if confirm_mutations:
                confirmed = await io.confirm(f"Move {src} to {dst}?", False)
                report.log_decision(f"move {src} to {dst}", confirmed)
                if not confirmed:
                    return {"aborted": True}
            if not dry_run:
                staging.apply_all()
            report.add_diff(diff_text)
            result = {"moved": True, "src": str(src), "dst": str(dst)}
            report.log_tool("move_path", params.model_dump(), result)
            return result
        if not confirm_mutations:
            if not dry_run:
                staging.apply_all()
            report.add_diff(diff_text)
            result = {"moved": True, "src": str(src), "dst": str(dst)}
            report.log_tool("move_path", params.model_dump(), result)
            return result
        await _confirm_and_apply(change, diff_text)
        result = {"staged": True, "src": str(src), "dst": str(dst)}
        report.log_tool("move_path", params.model_dump(), result)
        return result

    @define_tool(description="Search for text within files")
    async def search_text(params: SearchTextParams) -> dict:
        root = workspace.root
        globs = params.globs or workspace.allow_globs
        hits: list[dict[str, str]] = []
        for path in root.rglob("*"):
            if path.is_dir():
                continue
            if workspace.should_ignore(path):
                continue
            rel = path.relative_to(root).as_posix()
            if not any(fnmatch.fnmatch(rel, pattern) for pattern in globs):
                continue
            if any(fnmatch.fnmatch(rel, pattern) for pattern in workspace.deny_globs):
                continue
            try:
                content = path.read_text(errors="ignore")
            except Exception:
                continue
            if params.query in content:
                for line_no, line in enumerate(content.splitlines(), start=1):
                    if params.query in line:
                        hits.append({"path": str(path), "line": str(line_no), "text": line.strip()})
                        if len(hits) >= params.max_hits:
                            break
            if len(hits) >= params.max_hits:
                break
        result = {"query": params.query, "hits": hits, "total": len(hits)}
        report.log_tool("search_text", params.model_dump(), {"total": len(hits)})
        return result

    return [
        list_directory,
        read_file,
        write_file,
        delete_path,
        move_path,
        search_text,
    ]
