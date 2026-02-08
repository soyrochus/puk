from __future__ import annotations

import json
from pathlib import Path

import pytest

from puk.config import LLMSettings
from puk.run import RunRecorder


def _read_events(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_create_run_and_events(tmp_path):
    recorder = RunRecorder(
        workspace=tmp_path,
        mode="oneshot",
        llm=LLMSettings(),
        append_to_run=None,
        argv=["puk"],
    )
    recorder.start(title_slug="demo")
    turn_id = recorder.next_turn_id()
    recorder.record_user_input("hi", turn_id=turn_id)
    recorder.record_model_output("ok", turn_id=turn_id)
    recorder.close(status="closed", reason="completed")

    manifest = json.loads((recorder.paths.manifest).read_text())
    assert manifest["status"] == "closed"
    events = _read_events(recorder.paths.events)
    assert events[0]["type"] == "session.start"
    assert events[-1]["type"] == "status.change"
    assert events[2]["type"] == "input.user"


def test_append_requires_existing_run(tmp_path):
    recorder = RunRecorder(
        workspace=tmp_path,
        mode="repl",
        llm=LLMSettings(),
        append_to_run="missing",
        argv=[],
    )
    with pytest.raises(ValueError):
        recorder.start()


def test_concurrency_lock(tmp_path):
    recorder1 = RunRecorder(tmp_path, "oneshot", LLMSettings(), None, [])
    recorder1.start()

    recorder2 = RunRecorder(tmp_path, "oneshot", LLMSettings(), recorder1.run_id, [])
    recorder2.paths = recorder1.paths  # simulate same run resolution
    with pytest.raises(RuntimeError):
        recorder2._acquire_lock()

