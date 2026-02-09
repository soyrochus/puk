# 90. Appendix: Inventory & Stack Detection

Generated: 2026-02-09
Repo root: `/Users/ivanderk/src/puk`

## Repository summary

This repository is a **Python CLI application** named **`puk`**.

Evidence:
- `pyproject.toml` ([project] name/version/entrypoint)
- `src/puk/**.py` (application modules)
- `playbooks/reverse-engineer-docs.md` (playbook describing doc generation)
- `vendor/copilot-sdk/**` (vendored Copilot SDK materials)

## Detected stacks (best-effort)

| Area | Stack | Confidence | Evidence |
| --- | --- | ---: | --- |
| CLI app | Python 3.11+, Click/argparse-style CLI | High | `pyproject.toml`; `src/puk/__main__.py` |
| LLM runtime | GitHub Copilot SDK (primary) + BYOK providers | High | `src/puk/app.py`; `src/puk/config.py` |
| Playbooks | Markdown + YAML front-matter, plan/apply | High | `src/puk/playbooks.py`; `src/puk/playbook_runner.py`; `playbooks/reverse-engineer-docs.md` |
| Persistence | Local run storage under `.puk/runs` | High | `src/puk/run.py`; `src/puk/runs.py`; README |
| Frontend | None detected | High | no `package.json`, `src/app`, etc. |
| Backend HTTP API | None detected | High | no OpenAPI, routers/controllers in `src/puk/**` |
| Database | None detected | High | no migrations/ORM/schema files |

## Key top-level paths

| Path | Purpose |
| --- | --- |
| `src/puk/` | Main Python package |
| `playbooks/` | Playbook definitions (Markdown + YAML) |
| `specs/` | Design specs / ADR-like docs |
| `docs/` | Generated documentation output bundle (this set) |
| `vendor/copilot-sdk/` | Vendored Copilot SDK references/tests/docs |
| `images/` | README images |

## Key files (entrypoints / configuration)

| File | Notes |
| --- | --- |
| `pyproject.toml` | Project metadata + dependencies + script entrypoint `puk = puk.__main__:main` |
| `src/puk/__main__.py` | CLI: `puk`, plus `puk run ...` and `puk runs ...` subcommands |
| `src/puk/app.py` | Core app: session config, tool allowlisting, write-scope enforcement, REPL loop |
| `src/puk/config.py` | LLM config discovery/merge/validation (global + workspace + CLI flags) |
| `src/puk/playbook_runner.py` | Runs a playbook by converting it into a prompt; creates output dir |
| `src/puk/playbooks.py` | Playbook loader + parameter binding + write-scope path matching |
| `src/puk/run.py` | Run recorder: manifest + NDJSON event log + lock file |
| `src/puk/runs.py` | Discover/list/show/tail persisted runs |
| `example.puk.toml` | Example configuration (mentions ignore list; only `[llm]` is implemented per spec) |

## Notable features detected

- **Tool allowlisting**: playbooks can restrict available tools passed to the Copilot SDK session.
  - Evidence: `src/puk/app.py` `session_config()` sets `available_tools` and excludes `bash` unless allowed.
- **Write scope enforcement**: deny writes outside configured `write_scope`.
  - Evidence: `src/puk/app.py` `_permission_handler()` + `_assert_write_scope()`; `src/puk/playbooks.py:is_path_within_scope()`.
- **Plan/apply playbook execution**: in plan mode tools are disabled; in apply mode writes can occur within scope.
  - Evidence: `src/puk/playbook_runner.py` `_build_prompt()`; `src/puk/app.py` permission handler.
- **Run persistence**: `.puk/runs/<timestamp...>/run.json` + `events.ndjson` + `artifacts/`.
  - Evidence: `src/puk/run.py`; `src/puk/runs.py`.

## Skips / exclusions

Playbook exclusion globs would normally skip:
- `.git/`, `node_modules/`, `dist/`, `build/`, `target/`, `.venv/`, `venv/`, `__pycache__/`

Note: this repo contains a local `.venv/` and `.puk/runs/` that should generally be treated as generated artifacts; they are not part of the core source.
