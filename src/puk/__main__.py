from __future__ import annotations

import argparse
import sys

from puk.app import PukConfig, run_sync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="puk", description="Minimal Copilot SDK REPL")
    parser.add_argument("prompt", nargs="?", help="Optional one-shot prompt for automated mode")
    parser.add_argument("--model", default="gpt-5", help="Model to use with Copilot SDK")
    parser.add_argument("--workspace", default=".", help="Root directory for agent tools")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = PukConfig(model=args.model, workspace=args.workspace)
    try:
        run_sync(config, one_shot_prompt=args.prompt)
    except KeyboardInterrupt:
        print("\nPuk has been interrupted by the user. Back to the burrow.", file=sys.stderr)
        raise SystemExit(130) from None
    except FileNotFoundError as exc:
        if exc.filename == "copilot":
            raise SystemExit("The `copilot` CLI binary was not found. Install GitHub Copilot CLI first.") from exc
        raise


if __name__ == "__main__":
    main()
