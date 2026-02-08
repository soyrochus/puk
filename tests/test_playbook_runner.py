from __future__ import annotations

from pathlib import Path

import pytest

from puk.playbook_runner import _build_prompt, _prepare_output_directory
from puk.playbooks import PlaybookValidationError
from puk.playbooks import Playbook


def test_build_prompt_includes_runtime_validation_note() -> None:
    playbook = Playbook(
        id="demo",
        version="0.1.0",
        description="Demo playbook",
        parameters={},
        allowed_tools=["glob"],
        write_scope=["docs/**"],
        run_mode="apply",
        body="Body",
        path=Path("playbooks/demo.md"),
    )

    prompt = _build_prompt(playbook, parameters={}, mode="apply")

    assert "Parameter values have already been resolved and validated by the runner." in prompt
    assert "Do not perform separate permission/probe checks" in prompt
    assert "Do not use file-view tools on directory paths" in prompt


def test_prepare_output_directory_creates_missing_dir(tmp_path: Path) -> None:
    target = tmp_path / "docs"
    assert not target.exists()

    _prepare_output_directory({"output_dir": str(target)}, tmp_path)

    assert target.is_dir()


def test_prepare_output_directory_rejects_file_target(tmp_path: Path) -> None:
    target = tmp_path / "docs"
    target.write_text("not a directory", encoding="utf-8")

    with pytest.raises(PlaybookValidationError, match="not a directory"):
        _prepare_output_directory({"output_dir": str(target)}, tmp_path)
