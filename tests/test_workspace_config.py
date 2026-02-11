from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from puk.config import resolve_workspace_config


def _write_workspace_config(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_resolve_workspace_config_merge_precedence(monkeypatch, tmp_path: Path) -> None:
    global_path = tmp_path / "global.toml"
    _write_workspace_config(
        global_path,
        """
        [workspace]
        root = "global-root"
        max_file_bytes = 1024
        allow_outside_root = true
        """,
    )
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    _write_workspace_config(
        workspace_path / ".puk.toml",
        """
        [workspace]
        root = "workspace-root"
        max_file_bytes = 2048
        """,
    )

    monkeypatch.setattr("puk.config.get_global_config_path", lambda: global_path)

    resolved = resolve_workspace_config(
        workspace=workspace_path,
        parameters={
            "workspace_root": "param-root",
            "workspace_max_file_bytes": 512,
            "workspace_allow_outside_root": False,
            "workspace_discover_root": False,
        },
    )

    expected_root = (workspace_path / "param-root").resolve()
    assert resolved.settings.root == str(expected_root)
    assert resolved.settings.max_file_bytes == 512
    assert resolved.settings.allow_outside_root is False
    assert resolved.sources["root"] == "parameter"
    assert resolved.sources["max_file_bytes"] == "parameter"
    assert resolved.sources["allow_outside_root"] == "parameter"


def test_resolve_workspace_config_rejects_invalid_values(monkeypatch, tmp_path: Path) -> None:
    global_path = tmp_path / "global.toml"
    _write_workspace_config(
        global_path,
        """
        [workspace]
        max_file_bytes = -5
        """,
    )
    monkeypatch.setattr("puk.config.get_global_config_path", lambda: global_path)

    with pytest.raises(ValueError, match="Workspace max_file_bytes must be a positive integer"):
        resolve_workspace_config(workspace=tmp_path, parameters={})


def test_resolve_workspace_config_discovers_root(monkeypatch, tmp_path: Path) -> None:
    global_path = tmp_path / "global.toml"
    global_path.write_text("", encoding="utf-8")
    root = tmp_path / "repo"
    root.mkdir()
    subdir = root / "subdir"
    subdir.mkdir()
    _write_workspace_config(
        root / ".puk.toml",
        """
        [workspace]
        root = "."
        allow_outside_root = true
        """,
    )

    monkeypatch.setattr("puk.config.get_global_config_path", lambda: global_path)

    resolved = resolve_workspace_config(
        workspace=subdir,
        parameters={"workspace_discover_root": True},
    )

    assert resolved.settings.root == str(root.resolve())
