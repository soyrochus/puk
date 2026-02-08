from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from puk.app import PukApp, PukConfig
from puk.config import LLMSettings
from puk.playbooks import Playbook, PlaybookValidationError, extract_plan_from_text, render_body
from puk.run import RunRecorder


def run_playbook_sync(
    workspace: Path,
    playbook: Playbook,
    mode: str,
    parameters: dict[str, Any],
    llm: LLMSettings,
    append_to_run: str | None,
    argv: list[str],
) -> None:
    recorder = RunRecorder(
        workspace=workspace,
        mode=mode,
        llm=llm,
        append_to_run=append_to_run,
        argv=argv,
    )
    config = PukConfig(
        workspace=str(workspace),
        llm=llm,
        allowed_tools=playbook.allowed_tools,
        write_scope=playbook.write_scope,
        execution_mode=mode,
    )
    app = PukApp(config, run_recorder=recorder)
    prompt = _build_prompt(playbook, parameters, mode)
    import asyncio

    asyncio.run(_run_playbook(app, recorder, playbook, parameters, mode, prompt))


async def _run_playbook(
    app: PukApp,
    recorder: RunRecorder,
    playbook: Playbook,
    parameters: dict[str, Any],
    mode: str,
    prompt: str,
) -> None:
    context_items = [
        {
            "type": "playbook",
            "id": playbook.id,
            "version": playbook.version,
            "parameters": parameters,
            "mode": mode,
        }
    ]
    try:
        await app.start()
        recorder.record_event(
            "playbook.start",
            {"id": playbook.id, "version": playbook.version, "mode": mode, "parameters": parameters},
        )
        output = await app.ask(prompt, capture=True, context_items=context_items) or ""
        if mode == "plan":
            _persist_plan(recorder, output)
            await app.close(status="planned", reason="planned")
            return
        plan_ref = _find_plan_artifact(recorder.paths)
        recorder.record_event(
            "playbook.apply",
            {"plan_artifact": plan_ref, "unreviewed": plan_ref is None},
        )
        await app.close(status="closed", reason="completed")
    except Exception as exc:
        await app.close(status="failed", reason=str(exc))
        raise


def _build_prompt(playbook: Playbook, parameters: dict[str, Any], mode: str) -> str:
    param_lines = "\n".join(f"- {key}: {value}" for key, value in parameters.items()) or "- (none)"
    rendered_body = render_body(playbook.body, parameters)
    if mode == "plan":
        mode_block = (
            "Execution mode: PLAN\n"
            "Do not call tools or modify files. Produce a JSON plan with this structure:\n"
            '{"steps":[{"description":"...", "tools":["tool.name"], "files":["path/relative/to/workspace"]}]}\n'
        )
    else:
        mode_block = (
            "Execution mode: APPLY\n"
            "Use only the allowed tools and stay within the write scope.\n"
        )
    return (
        f"Playbook: {playbook.id} (v{playbook.version})\n"
        f"Description: {playbook.description}\n"
        f"Parameters:\n{param_lines}\n"
        f"Allowed tools: {', '.join(playbook.allowed_tools)}\n"
        f"Write scope: {', '.join(playbook.write_scope)}\n"
        f"{mode_block}\n"
        "Playbook instructions:\n"
        f"{rendered_body}\n"
    )


def _persist_plan(recorder: RunRecorder, output: str) -> None:
    if recorder.paths is None:
        raise PlaybookValidationError("Run recorder is not initialized.")
    artifacts_dir = recorder.paths.artifacts_dir
    try:
        plan = extract_plan_from_text(output)
        plan_path = artifacts_dir / "plan.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        recorder.record_artifact("artifacts/plan.json", turn_id=recorder.turn_id, summary="plan")
        recorder.record_event("playbook.plan", {"artifact": "artifacts/plan.json"})
    except PlaybookValidationError as exc:
        plan_path = artifacts_dir / "plan.md"
        plan_path.write_text(output, encoding="utf-8")
        recorder.record_artifact("artifacts/plan.md", turn_id=recorder.turn_id, summary="plan")
        recorder.record_event("playbook.plan", {"artifact": "artifacts/plan.md", "error": str(exc)})
        raise


def _find_plan_artifact(paths) -> str | None:
    if paths is None:
        return None
    for name in ("plan.json", "plan.md"):
        candidate = paths.artifacts_dir / name
        if candidate.exists():
            return f"artifacts/{name}"
    return None
