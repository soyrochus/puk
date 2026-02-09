# 15. Functional Sources (Evidence Base)

Generated: 2026-02-09

## Functional sources provided

No explicit `functional_sources` were provided to this run (parameter was empty).

As a fallback evidence base, this section summarizes the repository’s own user-facing documentation.

## README.md (primary product description)

**Stated purpose**
- Puk is a *local coding assistant* built on top of the GitHub Copilot SDK, extended with **runs** and **playbooks**.

**Core capabilities (user-visible)**
- Interactive REPL (`puk`) and one-shot automated mode (`puk "..."`).
- Playbooks as repeatable automations (`puk run <playbook>`), with parameters and plan/apply.
- Persistent run records stored under `.puk/runs/...` with inspection tooling.

**Key usage flows (from README)**
- Install: `uv sync`
- Run REPL: `puk`
- One-shot prompt: `puk "..."`
- Run playbook: `puk run playbooks/reverse-engineer-docs.md`
- Inspect runs: `puk runs list|show|tail`

Evidence pointers:
- `README.md` (sections: Core features, Usage, Playbooks, Inspecting runs)

## Specs as functional/behavioral guidance

Even though not provided as `functional_sources`, the repository contains specs that describe intended behavior:

- **SPEC-003 Run as Unit of Execution**: run persistence model (manifest + NDJSON event log), append semantics, inspection commands.
  - Evidence: `specs/SPEC-003-Run-as-unit-of-execution.md`
- **SPEC-002 Implement BYO (LLM config)**: provider/model selection via global/workspace config and CLI overrides.
  - Evidence: `specs/SPEC-002-Implement-BYO.md`

## Glossary (inferred)

- **Run**: persisted record of a REPL session or one-shot execution, stored under `.puk/runs/...`.
- **Playbook**: Markdown file with YAML front-matter specifying parameters, allowed tools, write scope, and run mode.
- **Plan mode**: tools disabled; produces a plan artifact.
- **Apply mode**: tools enabled within allowlist + write scope.

## Non-functional requirements (inferred)

- Safety: write operations are constrained by playbook `write_scope` (path allowlist).
- Repeatability: playbooks are parameterized and validated before execution.
- Traceability: run recorder stores tool calls/results and artifacts.

Evidence pointers:
- `src/puk/app.py` (permission handler; tool allowlisting)
- `src/puk/playbooks.py` (parameter validation; write-scope matcher)
- `src/puk/run.py` (event log + artifacts)
