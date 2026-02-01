from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolCallRecord:
    name: str
    params: dict[str, Any]
    result: Any
    timestamp: float


@dataclass
class DecisionRecord:
    prompt: str
    confirmed: bool
    timestamp: float


@dataclass
class RunReport:
    run_id: str
    start_time: float
    config_snapshot: dict[str, Any]
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    diffs: list[str] = field(default_factory=list)
    end_time: float | None = None

    def log_tool(self, name: str, params: dict[str, Any], result: Any) -> None:
        self.tool_calls.append(
            ToolCallRecord(name=name, params=params, result=result, timestamp=time.time())
        )

    def log_decision(self, prompt: str, confirmed: bool) -> None:
        self.decisions.append(DecisionRecord(prompt=prompt, confirmed=confirmed, timestamp=time.time()))

    def add_file(self, path: Path) -> None:
        self.files_touched.append(str(path))

    def add_command(self, command: str) -> None:
        self.commands_run.append(command)

    def add_diff(self, diff: str) -> None:
        if diff:
            self.diffs.append(diff)

    def finish(self) -> None:
        self.end_time = time.time()

    def to_json(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "config": self.config_snapshot,
            "tool_calls": [
                {
                    "name": call.name,
                    "params": call.params,
                    "result": call.result,
                    "timestamp": call.timestamp,
                }
                for call in self.tool_calls
            ],
            "decisions": [
                {
                    "prompt": decision.prompt,
                    "confirmed": decision.confirmed,
                    "timestamp": decision.timestamp,
                }
                for decision in self.decisions
            ],
            "files_touched": self.files_touched,
            "commands_run": self.commands_run,
            "warnings": self.warnings,
            "errors": self.errors,
            "diffs": self.diffs,
        }

    def to_markdown(self) -> str:
        lines = [f"# PUK Run Report {self.run_id}", ""]
        lines.append(f"Start: {time.ctime(self.start_time)}")
        if self.end_time:
            lines.append(f"End: {time.ctime(self.end_time)}")
        lines.append("")

        if self.warnings:
            lines.append("## Warnings")
            lines.extend([f"- {w}" for w in self.warnings])
            lines.append("")

        if self.errors:
            lines.append("## Errors")
            lines.extend([f"- {e}" for e in self.errors])
            lines.append("")

        if self.files_touched:
            lines.append("## Files Touched")
            lines.extend([f"- {f}" for f in self.files_touched])
            lines.append("")

        if self.commands_run:
            lines.append("## Commands Run")
            lines.extend([f"- {c}" for c in self.commands_run])
            lines.append("")

        if self.diffs:
            lines.append("## Diffs")
            for diff in self.diffs:
                lines.append("```diff")
                lines.append(diff)
                lines.append("```")
            lines.append("")

        return "\n".join(lines)


def create_run_dir(root: Path, run_id: str) -> Path:
    run_dir = root / ".puk" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_report(report: RunReport, root: Path) -> Path:
    run_dir = create_run_dir(root, report.run_id)
    report.finish()
    json_path = run_dir / "run.json"
    md_path = run_dir / "run.md"
    json_path.write_text(json.dumps(report.to_json(), indent=2))
    md_path.write_text(report.to_markdown())
    return run_dir
