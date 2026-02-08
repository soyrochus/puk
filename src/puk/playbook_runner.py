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
    _prepare_output_directory(parameters, workspace)
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
    except BaseException as exc:
        reason = "interrupted by user" if isinstance(exc, KeyboardInterrupt) else str(exc)
        await app.close(status="failed", reason=reason)
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
        "Runtime note: Parameter values have already been resolved and validated by the runner.\n"
        "Do not perform separate permission/probe checks; proceed directly with the playbook steps.\n"
        "Use directory-oriented tools for directories and file-oriented tools for files.\n"
        "Do not use file-view tools on directory paths (for example repo_root or output_dir).\n"
        "For repository enumeration, use glob/list-directory style tools.\n"
        f"{mode_block}\n"
        "Playbook instructions:\n"
        f"{rendered_body}\n"
    )


def _prepare_output_directory(parameters: dict[str, Any], workspace: Path) -> None:
    raw_output_dir = parameters.get("output_dir")
    if not raw_output_dir:
        return
    output_dir = Path(str(raw_output_dir))
    if not output_dir.is_absolute():
        output_dir = (workspace / output_dir).resolve()
    if output_dir.exists() and not output_dir.is_dir():
        raise PlaybookValidationError(
            f"output_dir '{output_dir}' exists but is not a directory."
        )
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise PlaybookValidationError(
            f"Unable to create output_dir '{output_dir}': {exc}"
        ) from exc


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
