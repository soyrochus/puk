# Puk

> “Puk, who can’t resist poking around and making things better.”

Puk is a local coding assistant built on top of the GitHub Copilot SDK, extended with first-class runs and playbooks. It goes beyond a plain chat shell by adding persistent execution logs, plan/apply automation, scoped writes, and run inspection tooling.

![puk-small.png](./images/puk-small.png)

## Core features

- Copilot SDK runtime by default, with optional BYO providers via config or CLI overrides.
- Playbooks as repeatable automation units (`puk run ...`) with parameters, `plan/apply`, and tool/write scoping.
- Interactive REPL (`puk`) and automated one-shot execution (`puk "..."`).
- Persistent run records in `.puk/runs/...` (inputs, tool calls, outputs, artifacts), with append support.
- Run inspection from CLI (`puk runs ...`) and REPL shortcuts (`/runs`, `/run <id>`, `/tail <id>`).

## Install

```bash
uv sync
```

## Usage

### Interactive REPL

```bash
puk
```

Press Enter to add a new line, and use Ctrl+J to send your message.

### Automated mode (one-shot prompt)

```bash
puk "Find all python files related with powerpoint in this directory tree"
```

### Workspace targeting

```bash
puk --workspace /path/to/project "Analyze this codebase"
```

### Playbooks

Playbooks are repeatable automation flows defined as Markdown files with YAML front-matter
(`id`, `parameters`, `allowed_tools`, `write_scope`, `run_mode`).

Run a playbook:

```bash
puk run playbooks/reverse-engineer-docs.md
```

Run in plan mode (no file writes):

```bash
puk run playbooks/reverse-engineer-docs.md --mode plan
```

Apply mode with parameters:

```bash
puk run playbooks/reverse-engineer-docs.md \
  --mode apply \
  --param repo_root=src/puk \
  --param functional_sources=README.md,specs
```

Common notes:
- Parameter values for `path` types must resolve within `--workspace`.
- `reverse-engineer-docs.md` writes within `docs/**` by default.
- Runs are recorded under `.puk/runs/...` and can be inspected with `puk runs ...`.

Expected outputs for `playbooks/reverse-engineer-docs.md`:
- `docs/00_index.md`
- `docs/README.md`
- `docs/10_overview.md`
- `docs/15_functional_sources.md`
- `docs/20_architecture.md`
- `docs/30_backend_api.md`
- `docs/40_data_model.md`
- `docs/50_frontend_ui.md`
- `docs/60_user_flows.md`
- `docs/70_ops_and_runtime.md`
- `docs/80_open_questions.md`
- `docs/90_appendix_inventory.md`

### Inspecting runs

```bash
puk runs list
puk runs show <run_id-or-dir>
puk runs tail <run_id-or-dir> --follow
```

In the REPL you can type `/runs`, `/run <ref>`, or `/tail <ref>` without sending them to the model.

## Command-line options

| Option | Description |
| --- | --- |
| `prompt` (positional) | If provided, run one-shot; otherwise start REPL. |
| `-a, --append-to-run RUN_REF` | Append events to an existing run (by `run_id` or directory under `.puk/runs`). |
| `--workspace PATH` | Working directory for tools and run storage (defaults to `.`). |
| `--provider`, `--model`, `--temperature`, `--max-output-tokens` | Override LLM settings (can also come from config). |

Playbook command:

- `puk run <playbook_path> [--param key=value ...] [--mode plan|apply] [--workspace DIR] [-a RUN_REF]`

Run inspection subcommands:

- `puk runs list [--workspace DIR] [--json]`
- `puk runs show <run_ref> [--workspace DIR] [--tail N] [--json]`
- `puk runs tail <run_ref> [--workspace DIR] [--follow] [--limit N]`

## Quick check

Start the app in a repo/folder and ask something simple:

```text
find all python files
```

Then view the recorded run:

```bash
puk runs list
puk runs show <the-listed-run-id>
```

## Testing

```bash
uv run pytest
```

## Principles of Participation

Everyone is invited and welcome to contribute: open issues, propose pull requests, share ideas, or help improve documentation.  
Participation is open to all, regardless of background or viewpoint.  

This project follows the [FOSS Pluralism Manifesto](./FOSS_PLURALISM_MANIFESTO.md),  
which affirms respect for people, freedom to critique ideas, and space for diverse perspectives.  


## License and Copyright

Copyright (c) 2026, Iwan van der Kleijn

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
