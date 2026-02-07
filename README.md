# Puk

> “Puk, who can’t resist poking around and making things better.”

Puk is now a minimal proof-of-concept Copilot SDK app in the `puk` namespace.

![puk-small.png](./images/puk-small.png)

## What this first version includes

- Interactive REPL mode (`puk`)
- Multiline REPL input with explicit send
- Automated one-shot mode (`puk "your prompt"`) for non-interactive runs
- GitHub Copilot SDK session wiring with streaming enabled
- SDK internal tools left enabled (no tool exclusions)

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

## Principles of Participation

Everyone is invited and welcome to contribute: open issues, propose pull requests, share ideas, or help improve documentation.  
Participation is open to all, regardless of background or viewpoint.  

This project follows the [FOSS Pluralism Manifesto](./FOSS_PLURALISM_MANIFESTO.md),  
which affirms respect for people, freedom to critique ideas, and space for diverse perspectives.  


## License and Copyright

Copyright (c) 2026, Iwan van der Kleijn

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.