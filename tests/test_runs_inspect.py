from __future__ import annotations

import json
from pathlib import Path

from puk.run import RunRecorder
from puk import runs as run_inspect
from puk.config import LLMSettings


def _make_run(tmp_path: Path, title: str = "demo") -> Path:
    recorder = RunRecorder(tmp_path, "oneshot", LLMSettings(), None, [])
    recorder.start(title_slug=title)
    tid = recorder.next_turn_id()
    recorder.record_user_input("hi", tid)
    recorder.record_model_output("ok", tid)
    recorder.close(status="closed", reason="done")
    return recorder.paths.root


def test_discover_and_resolve(tmp_path: Path):
    run_dir = _make_run(tmp_path)
    runs = run_inspect.discover_runs(tmp_path)
    assert runs and runs[0].run_id
    resolved = run_inspect.resolve_run_ref(tmp_path, runs[0].run_id)
    assert resolved == run_dir
    resolved2 = run_inspect.resolve_run_ref(tmp_path, run_dir.name)
    assert resolved2 == run_dir


def test_format_show_contains_events(tmp_path: Path):
    run_dir = _make_run(tmp_path)
    out = run_inspect.format_run_show(run_dir, tail=5)
    assert "model.output" in out
    assert run_dir.name in out


def test_tail_events_reads(tmp_path: Path):
    run_dir = _make_run(tmp_path)
    events = list(run_inspect.tail_events(run_dir, follow=False))
    assert any(ev.get("type") == "model.output" for ev in events)
