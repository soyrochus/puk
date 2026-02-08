from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    dir: Path
    created_at: str
    updated_at: str
    status: str
    mode: str
    title: str
    workspace: str


def _runs_root(workspace: Path) -> Path:
    return workspace / ".puk" / "runs"


def _load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("title", "")
    return data


def discover_runs(workspace: Path) -> list[RunInfo]:
    root = _runs_root(workspace)
    if not root.exists():
        return []
    runs: list[RunInfo] = []
    for entry in root.iterdir():
        manifest_path = entry / "run.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = _load_manifest(manifest_path)
        except Exception:
            continue
        runs.append(
            RunInfo(
                run_id=manifest.get("run_id", ""),
                dir=entry,
                created_at=manifest.get("created_at", ""),
                updated_at=manifest.get("updated_at", ""),
                status=manifest.get("status", ""),
                mode=manifest.get("mode", ""),
                title=manifest.get("title", ""),
                workspace=manifest.get("workspace", ""),
            )
        )
    runs.sort(key=lambda r: r.updated_at, reverse=True)
    return runs


def _find_run_by_id(workspace: Path, run_id: str) -> Path | None:
    for info in discover_runs(workspace):
        if info.run_id == run_id:
            return info.dir
    return None


def resolve_run_ref(workspace: Path, ref: str) -> Path:
    root = _runs_root(workspace)
    candidate = Path(ref)
    if not candidate.is_absolute():
        candidate = (root / ref).resolve()
    if (candidate / "run.json").exists():
        return candidate
    found = _find_run_by_id(workspace, ref)
    if found:
        return found
    raise ValueError(f"Run reference '{ref}' does not exist under {root}")


def load_events(run_dir: Path) -> list[dict]:
    events_path = run_dir / "events.ndjson"
    if not events_path.exists():
        return []
    events: list[dict] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events


def tail_events(run_dir: Path, follow: bool = False, poll_interval: float = 0.5) -> Iterator[dict]:
    events_path = run_dir / "events.ndjson"
    if not events_path.exists():
        return iter(())
    with events_path.open("r", encoding="utf-8") as handle:
        while True:
            pos = handle.tell()
            line = handle.readline()
            if line:
                try:
                    yield json.loads(line)
                except Exception:
                    pass
                continue
            if not follow:
                break
            time.sleep(poll_interval)
            handle.seek(pos)


def _shorten(text: str, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def format_runs_table(runs: Iterable[RunInfo]) -> str:
    rows = [
        ["run_id", "status", "mode", "updated_at", "title", "dir"],
    ]
    for r in runs:
        rows.append([r.run_id, r.status, r.mode, r.updated_at, _shorten(r.title, 30), str(r.dir.name)])
    col_sizes = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for idx, row in enumerate(rows):
        line = "  ".join(val.ljust(col_sizes[i]) for i, val in enumerate(row))
        lines.append(line)
        if idx == 0:
            lines.append("-" * len(line))
    return "\n".join(lines)


def format_run_show(run_dir: Path, tail: int | None = 20) -> str:
    manifest = _load_manifest(run_dir / "run.json")
    events = load_events(run_dir)
    if tail is not None:
        events = events[-tail:]
    lines = [
        f"run: {run_dir.name}",
        f"run_id: {manifest.get('run_id','')}",
        f"status: {manifest.get('status','')}   mode: {manifest.get('mode','')}   workspace: {manifest.get('workspace','')}",
        f"created: {manifest.get('created_at','')}   updated: {manifest.get('updated_at','')}",
        f"title: {manifest.get('title','')}",
        "",
        "events:",
    ]
    for ev in events:
        data = ev.get("data", {})
        summary = ""
        if ev.get("type") == "model.output":
            summary = _shorten(str(data.get("text", "")))
        elif ev.get("type") == "input.user":
            summary = _shorten(str(data.get("text", "")))
        elif ev.get("type") == "artifact.write":
            summary = f"{data.get('path','')}"
        elif ev.get("type") == "tool.call":
            summary = data.get("name", "")
        line = f"{ev.get('seq')} [{ev.get('timestamp')}] {ev.get('type')} (turn {ev.get('turn_id')}): {summary}"
        lines.append(line)
    return "\n".join(lines)
