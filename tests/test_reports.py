"""Tests for puk.reports module."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from puk.reports import (
    DecisionRecord,
    RunReport,
    ToolCallRecord,
    create_run_dir,
    write_report,
)


class TestToolCallRecord:
    def test_creation(self):
        record = ToolCallRecord(
            name="test_tool",
            params={"key": "value"},
            result={"status": "ok"},
            timestamp=1234567890.0,
        )
        assert record.name == "test_tool"
        assert record.params == {"key": "value"}
        assert record.result == {"status": "ok"}
        assert record.timestamp == 1234567890.0


class TestDecisionRecord:
    def test_creation(self):
        record = DecisionRecord(
            prompt="Do you want to proceed?",
            confirmed=True,
            timestamp=1234567890.0,
        )
        assert record.prompt == "Do you want to proceed?"
        assert record.confirmed is True
        assert record.timestamp == 1234567890.0


class TestRunReport:
    @pytest.fixture
    def report(self) -> RunReport:
        return RunReport(
            run_id="test-run-123",
            start_time=1234567890.0,
            config_snapshot={"key": "value"},
        )

    def test_initial_state(self, report: RunReport):
        assert report.run_id == "test-run-123"
        assert report.start_time == 1234567890.0
        assert report.config_snapshot == {"key": "value"}
        assert report.tool_calls == []
        assert report.decisions == []
        assert report.files_touched == []
        assert report.commands_run == []
        assert report.warnings == []
        assert report.errors == []
        assert report.diffs == []
        assert report.end_time is None

    def test_log_tool(self, report: RunReport):
        report.log_tool("my_tool", {"arg": 1}, {"result": "ok"})
        assert len(report.tool_calls) == 1
        assert report.tool_calls[0].name == "my_tool"
        assert report.tool_calls[0].params == {"arg": 1}
        assert report.tool_calls[0].result == {"result": "ok"}
        assert report.tool_calls[0].timestamp > 0

    def test_log_decision(self, report: RunReport):
        report.log_decision("Confirm?", True)
        assert len(report.decisions) == 1
        assert report.decisions[0].prompt == "Confirm?"
        assert report.decisions[0].confirmed is True
        assert report.decisions[0].timestamp > 0

    def test_add_file(self, report: RunReport):
        report.add_file(Path("/tmp/test.py"))
        assert "/tmp/test.py" in report.files_touched

    def test_add_command(self, report: RunReport):
        report.add_command("python script.py")
        assert "python script.py" in report.commands_run

    def test_add_diff(self, report: RunReport):
        report.add_diff("--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new")
        assert len(report.diffs) == 1

    def test_add_diff_skips_empty(self, report: RunReport):
        report.add_diff("")
        assert len(report.diffs) == 0

    def test_finish(self, report: RunReport):
        assert report.end_time is None
        report.finish()
        assert report.end_time is not None
        assert report.end_time >= report.start_time


class TestRunReportToJson:
    def test_basic_json_output(self):
        report = RunReport(
            run_id="json-test",
            start_time=1000.0,
            config_snapshot={"setting": "value"},
        )
        report.finish()
        data = report.to_json()

        assert data["run_id"] == "json-test"
        assert data["start_time"] == 1000.0
        assert data["end_time"] is not None
        assert data["config"] == {"setting": "value"}
        assert data["tool_calls"] == []
        assert data["decisions"] == []
        assert data["files_touched"] == []
        assert data["commands_run"] == []
        assert data["warnings"] == []
        assert data["errors"] == []
        assert data["diffs"] == []

    def test_json_with_tool_calls(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        report.log_tool("tool1", {"a": 1}, {"b": 2})
        data = report.to_json()

        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["name"] == "tool1"
        assert data["tool_calls"][0]["params"] == {"a": 1}
        assert data["tool_calls"][0]["result"] == {"b": 2}
        assert "timestamp" in data["tool_calls"][0]

    def test_json_with_decisions(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        report.log_decision("Proceed?", False)
        data = report.to_json()

        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["prompt"] == "Proceed?"
        assert data["decisions"][0]["confirmed"] is False

    def test_json_is_serializable(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={"nested": {"key": "value"}},
        )
        report.log_tool("tool", {"list": [1, 2, 3]}, None)
        report.log_decision("Test?", True)
        report.add_file(Path("/path/to/file"))
        report.add_command("echo hello")
        report.warnings.append("warning!")
        report.errors.append("error!")
        report.add_diff("diff content")
        report.finish()

        # Should not raise
        json_str = json.dumps(report.to_json())
        assert isinstance(json_str, str)


class TestRunReportToMarkdown:
    def test_basic_markdown(self):
        report = RunReport(
            run_id="md-test",
            start_time=1000.0,
            config_snapshot={},
        )
        report.finish()
        md = report.to_markdown()

        assert "# PUK Run Report md-test" in md
        assert "Start:" in md
        assert "End:" in md

    def test_markdown_without_end_time(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        md = report.to_markdown()
        assert "Start:" in md

    def test_markdown_with_warnings(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        report.warnings.append("This is a warning")
        md = report.to_markdown()

        assert "## Warnings" in md
        assert "This is a warning" in md

    def test_markdown_with_errors(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        report.errors.append("This is an error")
        md = report.to_markdown()

        assert "## Errors" in md
        assert "This is an error" in md

    def test_markdown_with_files(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        report.add_file(Path("/path/to/file.py"))
        md = report.to_markdown()

        assert "## Files Touched" in md
        assert "/path/to/file.py" in md

    def test_markdown_with_commands(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        report.add_command("python main.py")
        md = report.to_markdown()

        assert "## Commands Run" in md
        assert "python main.py" in md

    def test_markdown_with_diffs(self):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        report.add_diff("-old\n+new")
        md = report.to_markdown()

        assert "## Diffs" in md
        assert "```diff" in md
        assert "-old" in md
        assert "+new" in md


class TestCreateRunDir:
    def test_creates_directory_structure(self, tmp_path: Path):
        run_dir = create_run_dir(tmp_path, "my-run-id")
        assert run_dir == tmp_path / ".puk" / "runs" / "my-run-id"
        assert run_dir.exists()
        assert run_dir.is_dir()

    def test_creates_parent_dirs(self, tmp_path: Path):
        # .puk and runs don't exist yet
        run_dir = create_run_dir(tmp_path, "test")
        assert (tmp_path / ".puk").exists()
        assert (tmp_path / ".puk" / "runs").exists()

    def test_idempotent(self, tmp_path: Path):
        run_dir1 = create_run_dir(tmp_path, "same-id")
        run_dir2 = create_run_dir(tmp_path, "same-id")
        assert run_dir1 == run_dir2


class TestWriteReport:
    def test_writes_json_and_markdown(self, tmp_path: Path):
        report = RunReport(
            run_id="write-test",
            start_time=1000.0,
            config_snapshot={"test": True},
        )
        report.log_tool("tool", {}, {})

        run_dir = write_report(report, tmp_path)

        json_path = run_dir / "run.json"
        md_path = run_dir / "run.md"

        assert json_path.exists()
        assert md_path.exists()

        # Verify JSON content
        json_content = json.loads(json_path.read_text())
        assert json_content["run_id"] == "write-test"
        assert json_content["config"]["test"] is True

        # Verify markdown content
        md_content = md_path.read_text()
        assert "write-test" in md_content

    def test_sets_end_time(self, tmp_path: Path):
        report = RunReport(
            run_id="test",
            start_time=1000.0,
            config_snapshot={},
        )
        assert report.end_time is None

        write_report(report, tmp_path)
        assert report.end_time is not None

    def test_returns_run_dir_path(self, tmp_path: Path):
        report = RunReport(
            run_id="path-test",
            start_time=1000.0,
            config_snapshot={},
        )
        run_dir = write_report(report, tmp_path)
        assert run_dir == tmp_path / ".puk" / "runs" / "path-test"
