# 70. Ops & Runtime

Generated: 2026-02-09

## Build / install / test

From README and pyproject:

- Install:
  - `uv sync`
- Run:
  - `puk` (REPL)
  - `puk "..."` (one-shot)
- Test:
  - `uv run pytest`

Evidence pointers:
- `README.md` (Install, Testing)
- `pyproject.toml` (`[project]`, optional dev dependencies, pytest config)

## Configuration model

### LLM settings

LLM settings are resolved with precedence:
1. Defaults
2. Global config: OS-specific `puk.toml`
3. Workspace config: `<workspace>/.puk.toml` (fallback legacy `.puk.config`)
4. CLI parameters (`--provider`, `--model`, `--temperature`, `--max-output-tokens`)

Validation rules include provider allowlist and model requirement for OpenAI/Anthropic.

Evidence pointers:
- `src/puk/config.py` (`resolve_llm_config`, `validate_llm_settings`, `get_global_config_path`)
- `src/puk/__main__.py` (CLI flags)

### Safety controls

- `allowed_tools`: playbook-specified allowlist passed to Copilot session as `available_tools`.
- `write_scope`: path allowlist enforced at permission request time.
- Environment variables:
  - `PUK_LOG_LEVEL` (log verbosity)
  - `PUK_MAX_IDENTICAL_TOOL_CALLS` (loop guard)
  - `PUK_MAX_IDENTICAL_TOOL_FAILURES` (failure loop guard)

Evidence pointers:
- `src/puk/app.py` (`session_config`, permission handler, env reads)

## Persistence / runtime state

- Runs stored under `.puk/runs/<timestamp...>/`.
- A lock file (`run.lock`) prevents concurrent append.

Evidence pointers:
- `src/puk/run.py`

## CI / containers / deployment

No first-party Docker/Kubernetes manifests or CI workflows were found for this project root.
(Note: `vendor/copilot-sdk/.github/workflows/**` exists but appears vendor-related.)

Evidence pointers:
- `vendor/copilot-sdk/.github/workflows/**`
