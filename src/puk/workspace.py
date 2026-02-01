from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import PolicyViolationError, PukError


@dataclass
class Workspace:
    root: Path
    allow_outside_root: bool
    follow_symlinks: bool
    allow_globs: list[str]
    deny_globs: list[str]
    ignore: list[str]
    max_file_bytes: int

    def resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.expanduser().resolve()
        if not self.allow_outside_root:
            if not self._is_within_root(resolved):
                raise PolicyViolationError(
                    f"Path escapes workspace root: {resolved} (root: {self.root})"
                )
        return resolved

    def _is_within_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.root)
            return True
        except ValueError:
            return False

    def ensure_allowed(self, path: Path) -> None:
        rel = path
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            rel = path
        rel_posix = rel.as_posix()
        for pattern in self.deny_globs:
            if fnmatch.fnmatch(rel_posix, pattern):
                raise PolicyViolationError(f"Path denied by pattern: {pattern}")
        if self.allow_globs:
            allowed = any(fnmatch.fnmatch(rel_posix, pattern) for pattern in self.allow_globs)
            if not allowed:
                raise PolicyViolationError("Path not allowed by workspace allow_globs")

    def should_ignore(self, path: Path) -> bool:
        rel = path
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            rel = path
        rel_posix = rel.as_posix()
        for pattern in self.ignore:
            if fnmatch.fnmatch(rel_posix, pattern) or rel_posix.startswith(pattern.rstrip("/") + "/"):
                return True
        return False
