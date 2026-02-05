# Puk

> “Puk, who can’t resist poking around and making things better.”

Puk is now a minimal proof-of-concept Copilot SDK app in the `puk` namespace.

![puk-small.png](./images/puk-small.png)

## What this first version includes

- Interactive REPL mode (`puk`)
- Two rendering modes:
  - `--mode plain`: simple text output
  - `--mode fancy`: rich unicode + colors
- Automated one-shot mode (`puk "your prompt"`) for non-interactive runs
- GitHub Copilot SDK session wiring with streaming enabled
- SDK internal tools left enabled (no tool exclusions)

## Install

```bash
uv sync
uv pip install -e .
```

## Usage

### Interactive REPL (fancy mode default)

```bash
puk
```

### Interactive REPL in plain mode

```bash
puk --mode plain
```

### Automated mode (one-shot prompt)

```bash
puk "Find all python files related with powerpoint in this directory tree"
```

### Workspace targeting

```bash
puk --workspace /path/to/project "Analyze this codebase"
```

## Acceptance-criteria scenario

Start the app in a repo/folder and ask:

```text
find all pyton files related with powerpoint in a directory tree
```

The agent will handle the request using Copilot SDK tools available in the session.

## Testing

```bash
uv run pytest
```

## License and Copyright

Copyright (c) 2026, Iwan van der Kleijn
