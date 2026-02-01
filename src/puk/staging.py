from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from .errors import ToolExecutionError


ChangeKind = Literal["write", "delete", "move"]


@dataclass
class StagedChange:
    kind: ChangeKind
    path: Path | None = None
    content: str | None = None
    src: Path | None = None
    dst: Path | None = None
    reason: str = ""


class StagingManager:
    def __init__(self) -> None:
        self._changes: list[StagedChange] = []

    @property
    def changes(self) -> list[StagedChange]:
        return list(self._changes)

    def has_changes(self) -> bool:
        return bool(self._changes)

    def stage_write(self, path: Path, content: str, reason: str = "") -> StagedChange:
        change = StagedChange(kind="write", path=path, content=content, reason=reason)
        self._changes.append(change)
        return change

    def stage_delete(self, path: Path, reason: str = "") -> StagedChange:
        change = StagedChange(kind="delete", path=path, reason=reason)
        self._changes.append(change)
        return change

    def stage_move(self, src: Path, dst: Path, reason: str = "") -> StagedChange:
        change = StagedChange(kind="move", src=src, dst=dst, reason=reason)
        self._changes.append(change)
        return change

    def revert_all(self) -> None:
        self._changes.clear()

    def diff_for_change(self, change: StagedChange) -> str:
        if change.kind == "write" and change.path:
            old_text = ""
            if change.path.exists():
                old_text = change.path.read_text(errors="ignore")
            new_text = change.content or ""
            return "".join(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=str(change.path),
                    tofile=str(change.path),
                )
            )
        if change.kind == "delete" and change.path:
            if not change.path.exists():
                return f"{change.path} already deleted\n"
            old_text = change.path.read_text(errors="ignore")
            return "".join(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    [],
                    fromfile=str(change.path),
                    tofile=str(change.path),
                )
            )
        if change.kind == "move" and change.src and change.dst:
            return f"move {change.src} -> {change.dst}\n"
        return ""

    def combined_diff(self) -> str:
        return "\n".join(self.diff_for_change(change) for change in self._changes)

    def apply_all(self) -> list[StagedChange]:
        applied: list[StagedChange] = []
        remaining: list[StagedChange] = []
        for change in self._changes:
            try:
                if change.kind == "write" and change.path:
                    change.path.parent.mkdir(parents=True, exist_ok=True)
                    change.path.write_text(change.content or "")
                elif change.kind == "delete" and change.path:
                    if change.path.is_dir():
                        for child in sorted(change.path.rglob("*"), reverse=True):
                            if child.is_file():
                                child.unlink()
                            else:
                                child.rmdir()
                        change.path.rmdir()
                    elif change.path.exists():
                        change.path.unlink()
                elif change.kind == "move" and change.src and change.dst:
                    change.dst.parent.mkdir(parents=True, exist_ok=True)
                    change.src.rename(change.dst)
                applied.append(change)
            except Exception as exc:
                remaining.append(change)
                raise ToolExecutionError(f"Failed to apply change {change}: {exc}") from exc
        self._changes = remaining
        return applied
