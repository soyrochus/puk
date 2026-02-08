from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from puk.app import PukConfig, run_sync
from puk.config import log_resolved_llm_config, resolve_llm_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="puk", description="Minimal Copilot SDK REPL")
    parser.add_argument("prompt", nargs="?", help="Optional one-shot prompt for automated mode")
    parser.add_argument("--provider", default=None, help="LLM provider to use")
    parser.add_argument("--model", default=None, help="Model to use with the provider")
    parser.add_argument("--temperature", default=None, type=float, help="LLM temperature override")
    parser.add_argument(
        "--max-output-tokens",
        default=None,
        type=int,
        help="Maximum output tokens override",
    )
    parser.add_argument("--workspace", default=".", help="Root directory for agent tools")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=os.environ.get("PUK_LOG_LEVEL", "INFO"))
    try:
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
        config = PukConfig(workspace=args.workspace, llm=resolved.settings)
        run_sync(config, one_shot_prompt=args.prompt)
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
