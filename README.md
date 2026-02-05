# Puk

> “Puk, who can’t resist poking around and making things better.”

## Puk is a local, agentic code generation and automation tool

Puk is a local, agentic code generation and automation tool that provides a Copilot-like experience outside of the IDE. It runs as a command-line application with an interactive REPL and optional rich terminal UI, and uses the GitHub Copilot SDK to plan and execute multi-step tasks through explicit tools. Puk operates within a defined workspace by default, asks for confirmation before mutating actions, and supports both interactive and non-interactive execution modes. It can generate and modify Python code, execute commands, and run isolated Python environments, while keeping the human in control through clear policies, diffs, and audit logs.

![puk-small.png](./images/puk-small.png)

NOTE: Currently this application is a thin shell over the Copilot SDK and very much alpha software and the Copilot SDK itself is still in early beta. So use at your own risk!

## Features

- **Agentic Code Generation**: Multi-step task planning and execution using GitHub Copilot SDK
- **Interactive REPL**: Command-line interface with optional rich terminal UI
- **Workspace Safety**: Operates within defined boundaries with confirmation prompts for mutations
- **Tool System**: SDK-provided filesystem and terminal tools, plus isolated Python execution and MCP protocol support
- **Flexible Configuration**: TOML-based configuration with project and global settings
- **Audit Logging**: Track all actions and changes for transparency
- **Diff-first Approach**: Review changes before they're applied to your codebase

## Installation

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Install from source

```bash
# Clone the repository
git clone https://github.com/soyrochus/puk.git
cd puk

# Install with uv
uv sync

# Or install in development modes
uv pip install -e .
```

## Quick Start

TODO

## Principles of Participation

Everyone is invited and welcome to contribute: open issues, propose pull requests, share ideas, or help improve documentation.  
Participation is open to all, regardless of background or viewpoint.  

This project follows the [FOSS Pluralism Manifesto](./FOSS_PLURALISM_MANIFESTO.md),  
which affirms respect for people, freedom to critique ideas, and space for diverse perspectives.  


## License and Copyright

Copyright (c) 2026, Iwan van der Kleijn

