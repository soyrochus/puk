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
    assert any(ev["type"] == "input.user" for ev in events)


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


def test_stale_lock_is_recovered(tmp_path):
    recorder1 = RunRecorder(tmp_path, "oneshot", LLMSettings(), None, [])
    recorder1.start()
    paths = recorder1.paths
    assert paths is not None
    recorder1._release_lock()

    paths.lock.write_text("999999", encoding="utf-8")
    recorder2 = RunRecorder(tmp_path, "oneshot", LLMSettings(), recorder1.run_id, [])
    recorder2.paths = paths
    recorder2._acquire_lock()
    assert recorder2._lock_handle is not None
    recorder2._release_lock()


def test_unique_run_dir_created_when_exists(tmp_path, monkeypatch):
    # force same timestamp
    monkeypatch.setattr("puk.run._utcnow", lambda: "2026-02-08T18-09-01Z")
    recorder1 = RunRecorder(tmp_path, "oneshot", LLMSettings(), None, [])
    recorder1.start(title_slug="demo")
    recorder2 = RunRecorder(tmp_path, "oneshot", LLMSettings(), None, [])
    recorder2.start(title_slug="demo")
    assert recorder1.paths.root != recorder2.paths.root


def test_tool_call_and_result_events_include_metadata(tmp_path):
    recorder = RunRecorder(
        workspace=tmp_path,
        mode="oneshot",
        llm=LLMSettings(),
        append_to_run=None,
        argv=["puk"],
    )
    recorder.start(title_slug="demo")
    turn_id = recorder.next_turn_id()
    recorder.record_tool_call(
        name="view",
        turn_id=turn_id,
        tool_call_id="call_123",
        arguments='{"path":"README.md"}',
    )
    recorder.record_tool_result(
        name="view",
        turn_id=turn_id,
        tool_call_id="call_123",
        success=True,
        result="ok",
    )
    recorder.close(status="closed", reason="completed")

    events = _read_events(recorder.paths.events)
    tool_call = next(ev for ev in events if ev["type"] == "tool.call")
    tool_result = next(ev for ev in events if ev["type"] == "tool.result")

    assert tool_call["turn_id"] == turn_id
    assert tool_call["data"]["name"] == "view"
    assert tool_call["data"]["tool_call_id"] == "call_123"
    assert tool_call["data"]["arguments"] == '{"path":"README.md"}'
    assert tool_result["turn_id"] == turn_id
    assert tool_result["data"]["name"] == "view"
    assert tool_result["data"]["tool_call_id"] == "call_123"
    assert tool_result["data"]["success"] is True
    assert tool_result["data"]["result"] == "ok"
