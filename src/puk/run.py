from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ISO_FMT = "%Y-%m-%dT%H-%M-%SZ"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime(ISO_FMT)


def _safe_slug(text: str | None, max_len: int = 32) -> str:
    if not text:
        return ""
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text.lower())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:max_len]


@dataclass(frozen=True)
class RunPaths:
    root: Path
    manifest: Path
    events: Path
    artifacts_dir: Path
    lock: Path


class RunRecorder:
    def __init__(
        self,
        workspace: Path,
        mode: str,
        llm: Any,
        append_to_run: str | None,
        argv: list[str],
    ):
        self.workspace = workspace
        self.mode = mode
        self.llm = llm
        self.append_to_run = append_to_run
        self.argv = argv
        self.paths: RunPaths | None = None
        self.run_id: str | None = None
        self.seq = 0
        self.turn_id = 0
        self._lock_handle = None
        self._prior_status: str | None = None

    # ---------- public API ----------
    def start(self, title_slug: str | None = None) -> None:
        runs_root = self.workspace / ".puk" / "runs"
        runs_root.mkdir(parents=True, exist_ok=True)
        if self.append_to_run:
            self.paths, manifest = self._resolve_existing_run(runs_root, self.append_to_run)
            self.run_id = manifest.get("run_id")
            self._prior_status = manifest.get("status")
            self.seq = self._load_last_seq(self.paths.events)
            manifest["updated_at"] = _utcnow()
            manifest["status"] = "open"
            self._write_manifest(self.paths.manifest, manifest)
        else:
            self.run_id = str(uuid.uuid4())
            slug = _safe_slug(title_slug)
            dir_name = f"{_utcnow()}" + (f"-{slug}" if slug else "")
            run_root = runs_root / dir_name
            suffix = 1
            while run_root.exists():
                run_root = runs_root / f"{dir_name}-{suffix}"
                suffix += 1
            run_root.mkdir(parents=True, exist_ok=True)
            self.paths = RunPaths(
                root=run_root,
                manifest=run_root / "run.json",
                events=run_root / "events.ndjson",
                artifacts_dir=run_root / "artifacts",
                lock=run_root / "run.lock",
            )
            self.paths.artifacts_dir.mkdir(exist_ok=True)
            manifest = {
                "run_id": self.run_id,
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
                "title": title_slug or "",
                "status": "open",
                "workspace": str(self.workspace.resolve()),
                "mode": self.mode,
                "llm": {
                    "provider": self.llm.provider,
                    "model": self.llm.model,
                    "temperature": self.llm.temperature,
                    "max_output_tokens": self.llm.max_output_tokens,
                },
            }
            self._write_manifest(self.paths.manifest, manifest)
        self._acquire_lock()
        self._append_event(
            "session.start",
            {
                "mode": self.mode,
                "argv": self.argv,
                "workspace": str(self.workspace),
                "run_id": self.run_id,
                "append": bool(self.append_to_run),
            },
        )

    def close(self, status: str, reason: str) -> None:
        if not self.paths:
            return
        self._append_event("session.end", {"status": status, "reason": reason})
        self._append_event("status.change", {"status": status, "reason": reason})
        manifest = self._read_manifest(self.paths.manifest)
        manifest["status"] = status
        manifest["updated_at"] = _utcnow()
        self._write_manifest(self.paths.manifest, manifest)
        self._release_lock()

    def next_turn_id(self) -> int:
        self.turn_id += 1
        return self.turn_id

    def record_user_input(self, text: str, turn_id: int) -> None:
        self._append_event("input.user", {"text": text}, turn_id=turn_id)
        self._append_event("context.resolved", {"items": []}, turn_id=turn_id)

    def record_model_output(self, text: str, turn_id: int) -> None:
        self._append_event("model.output", {"text": text}, turn_id=turn_id)

    def record_tool_call(self, name: str, turn_id: int) -> None:
        self._append_event("tool.call", {"name": name}, turn_id=turn_id)

    def record_artifact(self, relative_path: str, turn_id: int, summary: str | None = None) -> None:
        self._append_event(
            "artifact.write",
            {"path": relative_path, "summary": summary or ""},
            turn_id=turn_id,
        )

    # ---------- internal helpers ----------
    def _acquire_lock(self) -> None:
        if not self.paths:
            return
        try:
            self._lock_handle = self.paths.lock.open("x")
            self._lock_handle.write(str(os.getpid()))
            self._lock_handle.flush()
        except FileExistsError as exc:
            raise RuntimeError(f"Run {self.paths.root} is already in use; concurrency is not allowed.") from exc

    def _release_lock(self) -> None:
        if self._lock_handle:
            self._lock_handle.close()
        if self.paths and self.paths.lock.exists():
            try:
                self.paths.lock.unlink()
            except OSError:
                pass

    def _resolve_existing_run(self, runs_root: Path, ref: str) -> tuple[RunPaths, dict[str, Any]]:
        candidate = Path(ref)
        if not candidate.is_absolute():
            candidate = (runs_root / ref).resolve()
        if candidate.exists():
            run_root = candidate
        else:
            run_root = self._find_run_by_id(runs_root, ref)
            if run_root is None:
                raise ValueError(f"Run reference '{ref}' does not exist under {runs_root}.")
        manifest = self._read_manifest(run_root / "run.json")
        paths = RunPaths(
            root=run_root,
            manifest=run_root / "run.json",
            events=run_root / "events.ndjson",
            artifacts_dir=run_root / "artifacts",
            lock=run_root / "run.lock",
        )
        return paths, manifest

    def _find_run_by_id(self, runs_root: Path, run_id: str) -> Path | None:
        if not runs_root.exists():
            return None
        for entry in runs_root.iterdir():
            manifest_path = entry / "run.json"
            if manifest_path.exists():
                manifest = self._read_manifest(manifest_path)
                if manifest.get("run_id") == run_id:
                    return entry
        return None

    def _load_last_seq(self, events_path: Path) -> int:
        if not events_path.exists():
            return 0
        last_seq = 0
        with events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    obj = json.loads(line)
                    last_seq = max(last_seq, int(obj.get("seq", 0)))
                except Exception:
                    raise ValueError("Existing event log is corrupted; cannot append.")
        return last_seq

    def _append_event(self, event_type: str, data: dict[str, Any], turn_id: int | None = None) -> None:
        if not self.paths:
            return
        self.seq += 1
        record = {
            "timestamp": _utcnow(),
            "seq": self.seq,
            "type": event_type,
            "run_id": self.run_id,
            "turn_id": turn_id,
            "data": data,
        }
        line = json.dumps(record, ensure_ascii=True)
        with self.paths.events.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _write_manifest(self, path: Path, manifest: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _read_manifest(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ValueError(f"Run manifest missing at {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Run manifest at {path} is invalid JSON.") from exc
