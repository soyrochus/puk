from __future__ import annotations

import asyncio
from pathlib import Path

from .agent import PukAgent
from .config import ConfigLoadResult
from .reports import RunReport, write_report
from .staging import StagingManager
from .ui import UserIO


HELP_TEXT = """Available commands:
/help       Show this help
/config     Show effective config and provenance
/model      Show or change model/provider
/tools      List enabled tools
/root       Show or change workspace root
/plan       Ask for a plan without executing tools
/run        Execute last plan or apply pending actions
/diff       Show pending changes
/apply      Apply staged changes
/revert     Discard pending changes
/logs       Show last run report path
/exit       Exit the session
"""


def _format_config(cfg: ConfigLoadResult) -> str:
    data = cfg.config.model_dump()
    lines = ["Effective config:"]
    lines.append(str(data))
    lines.append("\nProvenance:")
    for key, source in sorted(cfg.provenance.values.items()):
        lines.append(f"- {key}: {source}")
    if cfg.provenance.sources.get("global"):
        lines.append(f"Global config: {cfg.provenance.sources['global']}")
    if cfg.provenance.sources.get("local"):
        lines.append(f"Local config: {cfg.provenance.sources['local']}")
    return "\n".join(lines)


def _format_tools(cfg: ConfigLoadResult) -> str:
    tools = cfg.config.tools
    lines = [
        f"filesystem={tools.filesystem}",
        f"terminal={tools.terminal}",
        f"python_exec={tools.python_exec}",
        f"mcp={tools.mcp}",
        f"user_io={tools.user_io}",
        f"filesystem_policy.staging_mode={tools.filesystem_policy.staging_mode}",
    ]
    return "\n".join(lines)


async def run_repl(
    *,
    agent: PukAgent,
    io: UserIO,
    cfg: ConfigLoadResult,
    staging: StagingManager,
    report: RunReport,
    initial_prompt: str | None,
    non_interactive: bool,
    dry_run: bool = False,
) -> None:
    last_plan: str | None = None
    last_prompt: str | None = None

    await agent.start()

    if initial_prompt:
        await agent.send(initial_prompt)
        last_prompt = initial_prompt
        if non_interactive:
            run_dir = write_report(report, Path(cfg.config.workspace.root))
            await io.display(f"Run report: {run_dir}")
            await agent.close()
            return

    await io.display("PUK REPL started. Type /help for commands.")

    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        prompt = line.rstrip()
        if prompt.endswith("\\"):
            lines = [prompt[:-1]]
            while True:
                continuation = input("... ")
                if continuation.endswith("\\"):
                    lines.append(continuation[:-1])
                else:
                    lines.append(continuation)
                    break
            prompt = "\n".join(lines).strip()
        if prompt.startswith("/"):
            cmd, *args = prompt.split(" ")
            if cmd == "/help":
                await io.display(HELP_TEXT)
            elif cmd == "/config":
                await io.display(_format_config(cfg))
            elif cmd == "/model":
                if args:
                    if len(args) == 1:
                        cfg.config.llm.model = args[0]
                    elif len(args) >= 2:
                        cfg.config.llm.provider = args[0]
                        cfg.config.llm.model = args[1]
                    await io.display("Model updated; restart session to apply.")
                else:
                    await io.display(
                        f"provider={cfg.config.llm.provider}, model={cfg.config.llm.model}"
                    )
            elif cmd == "/tools":
                await io.display(_format_tools(cfg))
            elif cmd == "/root":
                if args:
                    new_root = Path(args[0]).expanduser().resolve()
                    if cfg.config.safety.confirm_mutations:
                        confirmed = await io.confirm(
                            f"Change root to {new_root}?", False
                        )
                        report.log_decision("change root", confirmed)
                        if not confirmed:
                            continue
                    cfg.config.workspace.root = str(new_root)
                    await io.display("Root updated; restart session to apply.")
                else:
                    await io.display(f"root={cfg.config.workspace.root}")
            elif cmd == "/plan":
                plan_prompt = " ".join(args) if args else (last_prompt or "")
                if not plan_prompt:
                    await io.display("Provide a prompt to plan.")
                    continue
                last_plan = await agent.plan(plan_prompt)
                await io.display(last_plan)
            elif cmd == "/run":
                if staging.has_changes():
                    if dry_run:
                        await io.display("Dry run enabled; staged changes not applied.")
                        continue
                    if cfg.config.safety.confirm_mutations:
                        confirmed = await io.confirm("Apply staged changes?", False)
                        report.log_decision("apply staged", confirmed)
                        if not confirmed:
                            continue
                    staging.apply_all()
                    await io.display("Staged changes applied.")
                elif last_plan:
                    await agent.send(f"Execute this plan:\n{last_plan}")
                else:
                    await io.display("No plan or staged actions to run.")
            elif cmd == "/diff":
                diff = staging.combined_diff()
                io.render_diff(diff)
            elif cmd == "/apply":
                if dry_run:
                    await io.display("Dry run enabled; staged changes not applied.")
                    continue
                if cfg.config.safety.confirm_mutations:
                    confirmed = await io.confirm("Apply staged changes?", False)
                    report.log_decision("apply staged", confirmed)
                    if not confirmed:
                        continue
                staging.apply_all()
                await io.display("Staged changes applied.")
            elif cmd == "/revert":
                staging.revert_all()
                await io.display("Staged changes cleared.")
            elif cmd == "/logs":
                run_dir = write_report(report, Path(cfg.config.workspace.root))
                await io.display(f"Run report: {run_dir}")
            elif cmd == "/exit":
                break
            else:
                await io.display("Unknown command. Type /help for list.")
            continue

        last_prompt = prompt
        await agent.send(prompt)

    run_dir = write_report(report, Path(cfg.config.workspace.root))
    await io.display(f"Run report: {run_dir}")
    await agent.close()
