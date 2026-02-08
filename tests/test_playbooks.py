from __future__ import annotations

from pathlib import Path

import pytest

from puk.playbooks import (
    PlaybookValidationError,
    load_playbook,
    resolve_parameters,
)


def _write_playbook(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "playbook.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_playbook_requires_front_matter(tmp_path: Path):
    path = _write_playbook(tmp_path, "no front matter")
    with pytest.raises(PlaybookValidationError, match="missing YAML front-matter"):
        load_playbook(path)


def test_load_playbook_parses_and_validates(tmp_path: Path):
    content = """---
id: test-playbook
version: 1.2.3
description: A test playbook
parameters:
  target_dir:
    type: path
    required: true
  mode:
    type: enum
    enum_values: [fast, slow]
    default: fast
allowed_tools: [fs.read, fs.write]
write_scope: ["docs/**"]
run_mode: plan
---
Do something in {{target_dir}}.
"""
    path = _write_playbook(tmp_path, content)
    playbook = load_playbook(path)
    assert playbook.id == "test-playbook"
    assert playbook.parameters["mode"].default == "fast"


def test_resolve_parameters_enforces_required_and_types(tmp_path: Path):
    content = """---
id: test-playbook
version: 0.1.0
description: Required params
parameters:
  count:
    type: int
    required: true
  flag:
    type: bool
    default: false
  choice:
    type: enum
    enum_values: [alpha, beta]
allowed_tools: []
write_scope: ["out/**"]
run_mode: plan
---
Body.
"""
    playbook = load_playbook(_write_playbook(tmp_path, content))
    with pytest.raises(PlaybookValidationError, match="Missing required parameter 'count'"):
        resolve_parameters(playbook.parameters, {}, tmp_path)
    params = resolve_parameters(playbook.parameters, {"count": "2", "choice": "beta"}, tmp_path)
    assert params["count"] == 2
    assert params["flag"] is False
    assert params["choice"] == "beta"


def test_resolve_parameters_rejects_path_escape(tmp_path: Path):
    content = """---
id: test-playbook
version: 0.1.0
description: Path params
parameters:
  target:
    type: path
    required: true
allowed_tools: []
write_scope: ["out/**"]
run_mode: plan
---
Body.
"""
    playbook = load_playbook(_write_playbook(tmp_path, content))
    with pytest.raises(PlaybookValidationError, match="resolve within the workspace"):
        resolve_parameters(playbook.parameters, {"target": "../outside"}, tmp_path)
