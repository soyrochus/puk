# Puk

> “Puk, who can’t resist poking around and making things better.”

Puk is a local coding assistant built on top of the GitHub Copilot SDK. It treats every session as a first-class **run**—prompts, tool calls, and artifacts are logged under `.puk/runs/…` so you can inspect and append later. You can stay on Copilot defaults or supply your own API keys for BYO providers.

![puk-small.png](./images/puk-small.png)

## Core features

- Interactive REPL (`puk`) and automated one-shot (`puk "do X"`).
- Persistent runs: manifest + event log + artifacts in `.puk/runs/…`.
- Append to an existing run for long-lived sessions.
- Run inspection from CLI (`puk runs …`) and REPL (`/runs`, `/run <id>`, `/tail <id>`).
- Copilot SDK by default; BYO providers/config via flags or config files.

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
