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

### Basic Usage

```bash
# Start interactive REPL
puk

# Execute a single prompt
puk "Add docstrings to all functions in src/"

# Use with specific configuration
puk --config my-config.toml "Refactor the database module"
```

### Configuration

Puk looks for configuration in the following order:
1. `.puk.toml` in the current directory
2. `.puk.toml` in parent directories (if `discover_root = true`)
3. `~/.puk.toml` in your home directory

Example minimal configuration:

```toml
[workspace]
root = "."
allow_outside_root = false

[llm]
provider = "copilot"
model = "gpt-5"

[safety]
confirm_mutations = true
confirm_commands = true
```

See [example.puk.toml](./example.puk.toml) for a complete configuration reference.

### Common Commands

```bash
# Initialize configuration in current project
puk init

# Show current configuration
puk config

# Run with auto-confirmation (use with caution!)
puk --confirm "Update all imports to use absolute paths"

# Use plain UI mode
puk --ui plain

# Specify workspace root
puk --root /path/to/project "Add tests for utils module"
```

## Configuration Options

### Core Settings

- **ui**: Terminal UI mode (`tui` or `plain`)
- **repl**: Start REPL when no prompt provided
- **streaming**: Stream LLM responses in real-time
- **telemetry**: Control telemetry (`off` or `local`)

### Workspace Settings

- **root**: Project root directory
- **allow_outside_root**: Allow operations outside workspace
- **ignore**: Folders to exclude from operations
- **allow_globs/deny_globs**: File access controls

### Safety Settings

- **confirm_mutations**: Require confirmation for file changes
- **confirm_commands**: Require confirmation for shell commands
- **redact_secrets**: Automatically redact sensitive information
- **paranoid_reads**: Prompt before reading potentially sensitive files

### Tools

Puk uses the Copilot SDK's built-in tools for filesystem and terminal operations (`Read`, `Edit`, `bash`, etc.). Additionally, Puk provides:

- **python_exec**: Isolated Python execution in virtual environments
- **user_io**: User interaction tools (display, confirm, prompt, select)
- **mcp**: Model Context Protocol support

Use `builtin_excluded` to disable specific SDK tools (e.g., `["bash"]` to prevent shell access).

## Development

### Running Tests

```bash
# Install development dependencies
uv sync --dev

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=puk
```

### Code Quality

```bash
# Format code
uv run ruff format

# Lint
uv run ruff check

# Type checking
uv run mypy src/puk
```

## Architecture

Puk is built on:
- **GitHub Copilot SDK**: For LLM interactions and agent capabilities
- **Click**: Command-line interface framework
- **Rich**: Terminal UI and formatting
- **Pydantic**: Configuration validation and type safety

## Contributing

Contributions are welcome! Please see the [Principles of Participation](#principles-of-participation) section below.

## Documentation

- [Configuration Reference](./example.puk.toml)
- [Copilot SDK Tutorial](./Copilot-SDK-Tutorial.md)
- [Project Specifications](./specs/)


## Principles of Participation

Everyone is invited and welcome to contribute: open issues, propose pull requests, share ideas, or help improve documentation.  
Participation is open to all, regardless of background or viewpoint.  

This project follows the [FOSS Pluralism Manifesto](./FOSS_PLURALISM_MANIFESTO.md),  
which affirms respect for people, freedom to critique ideas, and space for diverse perspectives.  


## License and Copyright

Copyright (c) 2026, Iwan van der Kleijn

