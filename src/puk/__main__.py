from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from puk.app import PukConfig, run_sync
from puk.config import (
    log_resolved_llm_config,
    log_resolved_workspace_config,
    resolve_llm_config,
    resolve_workspace_config,
)
from puk.playbook_runner import run_playbook_sync
from puk.playbooks import (
    PlaybookValidationError,
    load_playbook,
    parse_param_assignments,
    resolve_parameters,
)


def _add_llm_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default=None, help="LLM provider to use")
    parser.add_argument("--model", default=None, help="Model to use with the provider")
    parser.add_argument("--temperature", default=None, type=float, help="LLM temperature override")
    parser.add_argument(
        "--max-output-tokens",
        default=None,
        type=int,
        help="Maximum output tokens override",
    )


def _add_workspace_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-root", default=None, help="Workspace root override")
    parser.add_argument(
        "--workspace-discover-root",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Enable workspace root discovery",
    )
    parser.add_argument(
        "--workspace-allow-outside-root",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Allow paths outside the resolved workspace root",
    )
    parser.add_argument(
        "--workspace-follow-symlinks",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Allow symlink traversal outside the resolved workspace root",
    )
    parser.add_argument(
        "--workspace-max-file-bytes",
        default=None,
        type=int,
        help="Maximum file size allowed for reads",
    )
    parser.add_argument(
        "--workspace-ignore",
        action="append",
        default=None,
        help="Ignored directory names (comma-separated or repeatable)",
    )
    parser.add_argument(
        "--workspace-allow-globs",
        action="append",
        default=None,
        help="Allowed file globs (comma-separated or repeatable)",
    )
    parser.add_argument(
        "--workspace-deny-globs",
        action="append",
        default=None,
        help="Denied file globs (comma-separated or repeatable)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="puk",
        description="Minimal Copilot SDK REPL",
        epilog="Additional commands: `puk run <playbook>` and `puk runs list|show|tail`.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("prompt", nargs="?", help="Optional one-shot prompt for automated mode")
    parser.add_argument(
        "-a",
        "--append-to-run",
        dest="append_to_run",
        default=None,
        help="Append events to existing run id or path under .puk/runs",
    )
    _add_llm_args(parser)
    _add_workspace_args(parser)
    parser.add_argument("--workspace", default=".", help="Root directory for agent tools")
    return parser


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="puk run", description="Run a playbook")
    parser.add_argument("playbook_path", help="Path to the playbook markdown file")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="Playbook parameter assignment (key=value). Repeatable.",
    )
    parser.add_argument("--mode", choices=["plan", "apply"], default=None, help="Execution mode")
    parser.add_argument(
        "-a",
        "--append-to-run",
        dest="append_to_run",
        default=None,
        help="Append events to existing run id or path under .puk/runs",
    )
    parser.add_argument("--workspace", default=".", help="Root directory for agent tools")
    _add_llm_args(parser)
    _add_workspace_args(parser)
    return parser


def build_runs_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="puk runs", description="Inspect recorded runs")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List runs")
    list_parser.add_argument("--workspace", default=".", help="Workspace to scan for runs")
    list_parser.add_argument("--json", action="store_true", help="Emit raw JSON list")

    show_parser = sub.add_parser("show", help="Show run manifest and recent events")
    show_parser.add_argument("run_ref", help="Run id or directory name")
    show_parser.add_argument("--workspace", default=".", help="Workspace to scan for runs")
    show_parser.add_argument("--tail", type=int, default=20, help="Number of events to display")
    show_parser.add_argument("--json", action="store_true", help="Emit raw events JSON")

    tail_parser = sub.add_parser("tail", help="Stream run events")
    tail_parser.add_argument("run_ref", help="Run id or directory name")
    tail_parser.add_argument("--workspace", default=".", help="Workspace to scan for runs")
    tail_parser.add_argument("--follow", action="store_true", help="Follow for new events")
    tail_parser.add_argument("--limit", type=int, default=None, help="Maximum events to show")

    return parser


def main() -> None:
    # Dispatch between main run mode and runs subcommands
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        run_parser = build_run_parser()
        args = run_parser.parse_args(sys.argv[2:])
        logging.basicConfig(level=os.environ.get("PUK_LOG_LEVEL", "INFO"))
        workspace = Path(getattr(args, "workspace", "."))
        try:
            workspace_params = _workspace_param_overrides(args)
            resolved_workspace = resolve_workspace_config(
                workspace=workspace,
                parameters=workspace_params,
            )
            log_resolved_workspace_config(resolved_workspace)
            resolved = resolve_llm_config(
                workspace=workspace,
                parameters={
                    "provider": args.provider,
                    "model": args.model,
                    "temperature": args.temperature,
                    "max_output_tokens": args.max_output_tokens,
                },
            )
            log_resolved_llm_config(resolved)
            playbook = load_playbook(Path(args.playbook_path))
            raw_params = parse_param_assignments(args.param)
            effective_workspace = Path(resolved_workspace.settings.root)
            parameters = resolve_parameters(
                playbook.parameters,
                raw_params,
                effective_workspace,
                allow_outside_root=resolved_workspace.settings.allow_outside_root,
                follow_symlinks=resolved_workspace.settings.follow_symlinks,
            )
            mode = args.mode or playbook.run_mode
            run_playbook_sync(
                workspace=effective_workspace,
                playbook=playbook,
                mode=mode,
                parameters=parameters,
                llm=resolved.settings,
                append_to_run=args.append_to_run,
                workspace_settings=resolved_workspace.settings,
                argv=sys.argv[1:],
            )
        except (ValueError, PlaybookValidationError) as exc:
            raise SystemExit(str(exc)) from None
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from None
        except FileNotFoundError as exc:
            if exc.filename == "copilot":
                raise SystemExit(
                    "The `copilot` CLI binary was not found. Install GitHub Copilot CLI first."
                ) from exc
            raise
        except KeyboardInterrupt:
            print("\nPuk run was interrupted by the user.", file=sys.stderr)
            raise SystemExit(130) from None
        return
    if len(sys.argv) > 1 and sys.argv[1] == "runs":
        runs_parser = build_runs_parser()
        args = runs_parser.parse_args(sys.argv[2:])
        logging.basicConfig(level=os.environ.get("PUK_LOG_LEVEL", "INFO"))
        from puk import runs as run_inspect

        workspace = Path(getattr(args, "workspace", "."))
        if args.command == "list":
            discovered = run_inspect.discover_runs(workspace)
            if args.json:
                print(json.dumps([ri.__dict__ | {"dir": str(ri.dir)} for ri in discovered], indent=2))
            else:
                print(run_inspect.format_runs_table(discovered))
            return
        if args.command == "show":
            run_dir = run_inspect.resolve_run_ref(workspace, args.run_ref)
            if args.json:
                manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
                events = run_inspect.load_events(run_dir)
                print(json.dumps({"manifest": manifest, "events": events[-args.tail :]}, indent=2))
            else:
                print(run_inspect.format_run_show(run_dir, tail=args.tail))
            return
        if args.command == "tail":
            run_dir = run_inspect.resolve_run_ref(workspace, args.run_ref)
            count = 0
            for ev in run_inspect.tail_events(run_dir, follow=args.follow):
                print(json.dumps(ev))
                count += 1
                if args.limit and count >= args.limit:
                    break
            return

    args = build_parser().parse_args()
    logging.basicConfig(level=os.environ.get("PUK_LOG_LEVEL", "INFO"))

    try:
        workspace_params = _workspace_param_overrides(args)
        resolved_workspace = resolve_workspace_config(
            workspace=Path(args.workspace),
            parameters=workspace_params,
        )
        log_resolved_workspace_config(resolved_workspace)
        resolved = resolve_llm_config(
            workspace=Path(args.workspace),
            parameters={
                "provider": args.provider,
                "model": args.model,
                "temperature": args.temperature,
                "max_output_tokens": args.max_output_tokens,
            },
        )
        log_resolved_llm_config(resolved)
        config = PukConfig(
            workspace=resolved_workspace.settings.root,
            llm=resolved.settings,
            workspace_settings=resolved_workspace.settings,
        )
        run_sync(config, one_shot_prompt=args.prompt, append_to_run=args.append_to_run, argv=sys.argv[1:])
    except KeyboardInterrupt:
        print("\nPuk has been interrupted by the user. Back to the burrow.", file=sys.stderr)
        raise SystemExit(130) from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
    except FileNotFoundError as exc:
        if exc.filename == "copilot":
            raise SystemExit("The `copilot` CLI binary was not found. Install GitHub Copilot CLI first.") from exc
        raise


if __name__ == "__main__":
    main()


def _workspace_param_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "workspace_root": args.workspace_root,
        "workspace_discover_root": args.workspace_discover_root,
        "workspace_allow_outside_root": args.workspace_allow_outside_root,
        "workspace_follow_symlinks": args.workspace_follow_symlinks,
        "workspace_max_file_bytes": args.workspace_max_file_bytes,
        "workspace_ignore": _split_list_args(args.workspace_ignore),
        "workspace_allow_globs": _split_list_args(args.workspace_allow_globs),
        "workspace_deny_globs": _split_list_args(args.workspace_deny_globs),
    }


def _split_list_args(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    items: list[str] = []
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if item:
                items.append(item)
    return items or None
