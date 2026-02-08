# SPEC-004 - Playbooks

## 1. Purpose

Introduce Playbooks as first-class, repeatable execution units that externalize intent, parameters, and allowed capabilities. This moves Puk beyond ad-hoc chat toward deterministic, auditable automation with plan/apply semantics.

## 2. Scope

In scope:
- Playbook file format and loader (Markdown with machine-readable front-matter).
- Parameter schema, validation, and binding into execution context.
- CLI entrypoint for running playbooks with parameters.
- Plan / Apply execution modes with confirmation gate.
- Integration with existing run persistence (SPEC-003) for logging plan and apply events.

Out of scope:
- Remote playbook registries or catalogs.
- UI for plan review beyond CLI text output.
- Tool/plugin installation; assume tools already available in the session.

## 3. Playbook Format

- File type: Markdown (`.md`) with YAML front-matter at the top.
- Required front-matter fields:
  - `id` (string, unique within workspace)
  - `version` (semver string)
  - `description` (short human summary)
  - `parameters` (map of typed parameter definitions; see §4)
  - `allowed_tools` (list of tool names/ids permitted during execution)
  - `write_scope` (paths or globs the playbook may modify)
  - `run_mode` (default execution mode: `plan` or `apply`)
- Body: freeform Markdown instructions to the agent; may embed parameter placeholders (e.g., `{{target_dir}}`) that are substituted before prompting.
- Example (illustrative only):
  ```yaml
  ---
  id: reverse-engineer-docs
  version: 0.1.0
  description: Generate docs from code inspection
  parameters:
    target_dir:
      type: string
      required: true
      description: Folder to write docs into
  allowed_tools: [fs.read, fs.write, search]
  write_scope: ["docs/**", "README.md"]
  run_mode: plan
  ---
  ```
  *(Body contains the human-readable playbook steps.)*

## 4. Parameters

- Each parameter definition supports:
  - `type`: `string` | `int` | `float` | `bool` | `enum` | `path`
  - `required`: bool (default false)
  - `default`: value (type-compatible)
  - `description`: human text
  - `enum_values`: required when `type=enum`
- Validation rules:
  - Required params must be supplied or have defaults.
  - Type conversion must succeed; otherwise fail fast before model invocation.
  - Path parameters must resolve within workspace; reject traversal outside workspace.
  - Unknown parameters supplied at CLI cause an error.
- Binding:
  - A resolved parameter map is injected into the prompt template (string replace `{{name}}`).
  - The bound map is also attached to the session context so tools can reference typed values.

## 5. CLI Contract

- Command: `puk run <playbook_path> [--param key=value ...] [--mode plan|apply] [--append-to-run RUN_REF] [--workspace DIR]`
- Behavior:
  - Loads and validates playbook front-matter and parameters.
  - Determines effective mode: CLI `--mode` overrides playbook `run_mode` default.
  - Creates or appends to a run (SPEC-003), logging playbook id/version, parameters, and mode.
  - In `plan` mode: render structured plan output (see §6) and mark run status `open|planned`.
  - In `apply` mode: requires a plan; executes steps; status `closed|failed` accordingly.
  - If `--mode apply` is given without a prior plan, proceed but log that apply is unreviewed.

## 6. Plan / Apply Semantics

- `plan`:
  - Agent produces a structured plan object (list of steps with descriptions, intended tools, and targeted files).
  - Plan is printed to CLI and written to run artifacts (e.g., `plan.json`).
  - No file writes or tool calls with side effects are executed in plan mode.
- `apply`:
  - Executes with the allowed tools and write_scope constraints.
  - Associates executed actions with plan steps when available.
  - Persists artifacts/diffs under the run’s `artifacts/` and logs `artifact.write` events.
  - If `apply` follows a recorded plan, reference the plan artifact id in events.

## 7. Loader & Validation Flow

1) Locate playbook file (must exist and have front-matter).
2) Parse YAML front-matter; validate required fields and parameter schema.
3) Apply CLI `--param` overrides; validate required/typed values.
4) Render prompt body with parameter substitutions.
5) Enforce allowed_tools/write_scope constraints in session configuration.
6) Hand off to execution (plan or apply) with resolved context.

## 8. Constraints & Guardrails

- No execution if validation fails; emit actionable errors.
- Tool calls must be constrained to `allowed_tools`; disallow others at session config level.
- File writes must be limited to `write_scope`; reject attempts outside allowed paths.
- Playbook body is treated as user intent; avoid mutating it at runtime.
- Maintain compatibility with existing Copilot SDK defaults; BYO provider config still applies.

## 9. Observability

- Runs log `context.resolved` with playbook id/version and parameter map.
- Plan artifact stored as `artifacts/plan.json` (or `.md` if text) and referenced from events.
- Apply events link to the plan artifact when present.
- CLI outputs clear status: `planned`, `applied`, or `failed`.

## 10. Acceptance Criteria

1) `puk run <playbook> --param …` loads, validates, and executes in plan or apply mode without using ad-hoc prompts.
2) Invalid or missing parameters fail before model/tool invocation with clear messaging.
3) `allowed_tools` and `write_scope` are enforced during apply; disallowed actions are blocked.
4) Plan mode produces a structured plan artifact and does not write files.
5) Apply mode writes within scope, logs artifacts, and links to the originating plan when available.
6) All playbook executions are recorded in run manifests and events (SPEC-003) with playbook metadata and parameters.
7) CLI help documents `puk run` and `--param/--mode` usage.

## 11. Test Plan

Unit tests:
- Front-matter parsing with required fields present/missing.
- Parameter validation: required, type conversion, enum values, path sandboxing.
- Allowed tools/write_scope enforcement configuration.
- Plan artifact serialization shape.

Integration tests:
- `puk run <pb> --mode plan` produces plan artifact, no file writes.
- `puk run <pb> --mode apply --param …` executes and writes only within `write_scope`.
- CLI `--param` override precedence over defaults.
- Apply after a recorded plan references the plan artifact in events.
- Unknown parameter or missing required parameter → fails fast.
- Disallowed tool invocation is blocked and logged as error.
