# 10. Overview

Generated: 2026-02-09

## What this system is

**Puk** is a local CLI coding assistant built on the **GitHub Copilot SDK**. It provides:
- an interactive **REPL** for iterative conversations,
- a **one-shot** mode for single prompts,
- **playbooks** (repeatable automation flows with parameters and plan/apply), and
- persisted **run records** capturing provenance (inputs, tool calls, outputs, artifacts).

Evidence pointers:
- `README.md`
- `pyproject.toml`
- `src/puk/__main__.py`

## How to install / run (from repo docs)

- Install dependencies:
  - `uv sync`
- Start REPL:
  - `puk`
- Run a one-shot prompt:
  - `puk "Find all python files related with powerpoint in this directory tree"`
- Run a playbook:
  - `puk run playbooks/reverse-engineer-docs.md`

Evidence pointers:
- `README.md` (Install, Usage)

## High-level runtime processes

Puk has two main runtime modes:

1) **Interactive REPL**
- Creates a Copilot SDK session and streams assistant output.
- Provides local slash commands (`/runs`, `/run <id>`, `/tail <id>`) that are *not* sent to the model.

2) **Playbook runner**
- Loads a playbook (Markdown + YAML front-matter), resolves typed parameters, and builds a single prompt containing:
  - metadata (id/version/description)
  - resolved parameters
  - allowed tools + write scope
  - instructions body
- Runs it in plan or apply mode.

Evidence pointers:
- `src/puk/app.py` (`PukApp.repl`, `PukApp.ask`)
- `src/puk/playbook_runner.py` (`run_playbook_sync`, `_build_prompt`)
- `src/puk/playbooks.py` (`load_playbook`, `resolve_parameters`)

## Key concepts

- **Tool allowlisting**: playbooks can restrict which tools are visible/usable by the model.
  - Evidence: `src/puk/app.py:session_config()`
- **Write scoping**: write/edit/create operations are denied outside `write_scope`.
  - Evidence: `src/puk/app.py:_permission_handler()` + `src/puk/playbooks.py:is_path_within_scope()`
- **Run persistence**: run manifests + NDJSON event logs + artifacts per run.
  - Evidence: `src/puk/run.py` and `src/puk/runs.py`

## Project layout (where things live)

- `src/puk/` – main application modules
- `playbooks/` – playbook definitions
- `specs/` – design specs that describe intended behavior
- `.puk/runs/` – generated run history (created at runtime; not core source)

Evidence pointers:
- `src/puk/__main__.py`
- `src/puk/run.py`
