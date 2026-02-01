from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import click

from .agent import PukAgent
from .config import build_cli_overrides, load_config
from .errors import MissingInfoError, PukError, PolicyViolationError
from .reports import RunReport, write_report
from .repl import run_repl
from .staging import StagingManager
from .ui import NonInteractiveIO, PlainIO, TuiIO
from .workspace import Workspace


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("prompt", required=False)
@click.option("--root", type=click.Path(path_type=Path), help="Workspace root")
@click.option("--prompt-file", type=click.Path(path_type=Path), help="File containing initial prompt")
@click.option("--non-interactive", is_flag=True, help="Run without prompts")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed agent events")
@click.option("-C", "--confirm", is_flag=True, help="Skip confirmations for mutations")
@click.option("--paranoid", is_flag=True, help="Require confirmation for sensitive reads")
@click.option("--dry-run", is_flag=True, help="Plan and diff only; do not apply changes")
@click.option("--ui", type=click.Choice(["tui", "plain"], case_sensitive=False), help="UI mode")

def main(
    prompt: str | None,
    root: Path | None,
    prompt_file: Path | None,
    non_interactive: bool,
    verbose: bool,
    confirm: bool,
    paranoid: bool,
    dry_run: bool,
    ui: str | None,
) -> None:
    try:
        asyncio.run(
            async_main(
                prompt=prompt,
                root=root,
                prompt_file=prompt_file,
                non_interactive=non_interactive,
                verbose=verbose,
                confirm=confirm,
                paranoid=paranoid,
                dry_run=dry_run,
                ui=ui,
            )
        )
    except PukError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(exc.exit_code)


async def async_main(
    *,
    prompt: str | None,
    root: Path | None,
    prompt_file: Path | None,
    non_interactive: bool,
    verbose: bool,
    confirm: bool,
    paranoid: bool,
    dry_run: bool,
    ui: str | None,
) -> None:
    cwd = Path.cwd()
    cli_overrides = build_cli_overrides(
        ui=ui,
        confirm=confirm,
        paranoid=paranoid,
        root=str(root) if root else None,
    )
    cfg = load_config(cwd=cwd, cli_root=str(root) if root else None, cli_overrides=cli_overrides)

    root_path = Path(cfg.config.workspace.root)
    if not root_path.exists() or not root_path.is_dir():
        raise PolicyViolationError(f"Workspace root does not exist: {root_path}")

    if cfg.config.mcp.enabled and not cfg.config.tools.mcp:
        raise PukError("MCP enabled but tools.mcp is false")

    if cfg.config.llm.provider != "copilot":
        if not cfg.config.llm.api_key_env:
            raise PukError("api_key_env is required for BYOK providers", exit_code=5)
        if cfg.config.llm.api_key_env not in os.environ:
            raise PukError("API key env var not set", exit_code=5)
        if cfg.config.llm.provider == "azure" and not cfg.config.llm.azure_endpoint:
            raise PukError("azure_endpoint is required for Azure provider", exit_code=5)

    workspace = Workspace(
        root=root_path,
        allow_outside_root=cfg.config.workspace.allow_outside_root,
        follow_symlinks=cfg.config.workspace.follow_symlinks,
        allow_globs=cfg.config.workspace.allow_globs,
        deny_globs=cfg.config.workspace.deny_globs,
        ignore=cfg.config.workspace.ignore,
        max_file_bytes=cfg.config.workspace.max_file_bytes,
    )

    if non_interactive:
        io = NonInteractiveIO()
    else:
        if cfg.config.core.ui == "tui" and sys.stdout.isatty():
            io = TuiIO()
        else:
            io = PlainIO()

    io.update_context(
        {
            "root": str(root_path),
            "provider": cfg.config.llm.provider,
            "model": cfg.config.llm.model,
            "confirm": "off" if confirm else "guarded",
        }
    )

    if cfg.config.mcp.enabled and cfg.config.safety.confirm_mcp:
        if non_interactive:
            raise MissingInfoError("MCP confirmation required in non-interactive mode")
        confirmed = await io.confirm("Connect to configured MCP servers?", False)
        if not confirmed:
            raise PukError("MCP connection declined")

    run_id = time.strftime("%Y%m%d-%H%M%S")
    report = RunReport(run_id=run_id, start_time=time.time(), config_snapshot=cfg.config.model_dump())
    staging = StagingManager()

    tools: list = []

    initial_prompt = None
    if prompt_file:
        initial_prompt = prompt_file.read_text()
    if prompt:
        initial_prompt = f"{initial_prompt}\n{prompt}" if initial_prompt else prompt

    if non_interactive and not initial_prompt:
        raise PukError("Non-interactive mode requires a prompt", exit_code=2)

    agent = PukAgent(cfg.config, tools, io, report, verbose=verbose)

    try:
        await run_repl(
            agent=agent,
            io=io,
            cfg=cfg,
            staging=staging,
            report=report,
            initial_prompt=initial_prompt,
            non_interactive=non_interactive,
            dry_run=dry_run,
        )
    except PukError as exc:
        report.errors.append(str(exc))
        write_report(report, root_path)
        raise


if __name__ == "__main__":
    main()
