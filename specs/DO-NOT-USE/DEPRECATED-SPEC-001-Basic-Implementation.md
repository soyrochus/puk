# PUK — Local Copilot-Style Code Generation Agent (Python)

## 1. Purpose and positioning

Puk is a local, agentic code generation and automation tool that provides a Copilot-like experience outside of the IDE. It runs as a command-line application with an interactive REPL and optional rich terminal UI, and uses the GitHub Copilot SDK to plan and execute multi-step tasks through explicit tools. Puk operates within a defined workspace by default, asks for confirmation before mutating actions, and supports both interactive and non-interactive execution modes. It can generate and modify Python code, execute commands, and run isolated Python environments, while keeping the human in control through clear policies, diffs, and audit logs.

It connects to the GitHub Copilot agentic runtime via the Copilot SDK (through Copilot CLI in server mode) and can also operate using BYOK providers (OpenAI/Azure/Anthropic) when configured. 

PUK supports agentic workflows: multi-step reasoning, tool invocation, safe local code changes, command execution, and optional MCP integrations. It defaults to safe interaction and confirmation gates for mutating actions.

## 1.1 Absolute requirements

Puk MUST be implemented, basded on, The GitHub Copilot SDK. Details, documentation and examples on how to implement this can be found in the {root}/Copilot-SDK-Tutorial.md file

## 2. Core principles

1. Local-first: executes on a local machine, operating on local folders and repos.
2. Workspace-scoped: operates inside a declared root by default; escaping requires explicit opt-in.
3. Human-in-control by default: confirmation is required for mutating or risky actions unless explicitly disabled.
4. Repeatable: supports batch/non-interactive runs with deterministic logs and artifacts.
5. Tool-driven agency: the model can only act through exposed tools; tool availability is policy-controlled. 

## 3. User experience modes

PUK supports three user interaction modes. All share the same underlying agent core.

### 3.1 Rich TUI (default)

A terminal UI with:

* Left: conversation / streaming output
* Right: context panel (workspace root, active config, model/provider, tool policy, last actions)
* Bottom: prompt input + command palette (e.g., `/plan`, `/diff`, `/tools`, `/config`)
* Optional panes: file tree preview, diagnostics, “pending actions” queue

Implementation suggestion: `textual` or `rich` (TUI framework is an implementation detail, but the UX is specified above).

### 3.2 Simple prompt environment

Plain terminal mode:

* Streaming responses
* Minimal prompts for confirmations
* Text-only rendering of tables and diffs

### 3.3 REPL (always available; default entry)

When invoked without a one-shot prompt, PUK starts an interactive REPL:

* multiline input support
* slash commands (see Section 7)
* persistent session context for the duration of the run

## 4. Invocation patterns

### 4.1 Default (interactive)

* Starts REPL (TUI by default if terminal supports it)
* Maintains a Copilot SDK session with streaming enabled 

Example:

* `puk`
* `puk --root .`

### 4.2 Prompt from CLI (still interactive by default)

* `puk "create a FastAPI endpoint for /health"`
* PUK executes the prompt, then continues interactively unless forced otherwise.

### 4.3 Prompt from file

* `puk --prompt-file ./task.txt`
* Executes file content as the initial prompt, then continues interactively unless forced otherwise.

### 4.4 Non-interactive batch mode

This is the mode you were reaching for: **non-interactive**.

* `puk --non-interactive --prompt-file ./task.txt`
* Behavior:

  * no follow-up questions
  * if required information is missing, fail with an actionable error and exit non-zero
  * writes outputs to specified locations
  * emits a structured run report

### 4.5 Confirm modes and semantics

PUK has an explicit confirmation policy:

* Default: **guarded**

  * asks permission before mutating/risky actions
  * asks for missing information

* `-C` / `--confirm` (force mutating actions without permission prompts)

  * In interactive mode:

    * still asks for missing information (clarifications)
    * does **not** ask permission for writes/deletes/command execution
  * In non-interactive mode:

    * executes permitted operations without asking anything
    * missing information still fails fast

* Optional stricter mode: `--paranoid`

  * requires confirmation even for some reads that may leak secrets (e.g., `.env`, key stores)

## 5. Configuration model

### 5.1 Config files and precedence

PUK loads configuration from:

1. Global config (user-level): `~/.puk.config` (or `~/.config/puk/config.toml`)
2. Local config: `<root>/.puk.config`
3. CLI arguments / environment overrides

Precedence: CLI > Local > Global.

### 5.2 Config format

Recommended: TOML or YAML. Must support:

* provider/model selection
* tool policy
* workspace constraints
* MCP configuration
* Python execution policy

### 5.3 Minimal required keys

Provider and model (Copilot subscription default or BYOK):

* `provider = "copilot" | "openai" | "azure" | "anthropic"`
* `model = "..."`
* `streaming = true/false`
* `infinite_sessions.enabled = true/false` + compaction threshold 

Workspace policy:

* `workspace.root = "/path"` (if not set, CLI/root resolution rules apply)
* `workspace.allow_outside_root = false` (default)
* `workspace.follow_symlinks = false` (default)

Confirm policy:

* `safety.confirm_mutations = true` (default)
* `safety.confirm_commands = true` (default)
* `safety.confirm_deletes = true` (default)
* `safety.redact_secrets = true` (default)

Tools:

* `tools.python_exec = true/false`
* `tools.user_io = true/false`
* `tools.mcp = true/false`
* `tools.builtin_excluded = [...]` (optional list of SDK tools to disable)

## 6. Workspace scoping rules

PUK operates within a workspace root determined by:

1. CLI `--root` if provided
2. Local `.puk.config` discovery in current working directory or ancestor chain
3. Current working directory

Enforcement:

* All filesystem operations must canonicalize paths and deny escapes from root unless `allow_outside_root=true`.
* Symlink strategy:

  * default: do not follow symlinks that lead outside root
  * optionally allow with explicit policy

This is implemented in the tool layer. The model never receives a raw “open any path” capability.

## 7. REPL commands (interactive control surface)

Required commands:

* `/help` show commands
* `/config` show effective config and provenance (global/local/cli)
* `/model` show current provider/model; optionally switch if allowed
* `/tools` list enabled tools and policies
* `/root` show/change root (change requires confirmation unless `--confirm`)
* `/plan` ask the agent for a step plan without executing
* `/run` execute the last plan (or execute queued actions)
* `/diff` show pending changes (git diff-like)
* `/apply` apply staged changes (write files)
* `/revert` discard pending changes
* `/logs` show last run report
* `/exit`

The command set is intentionally small; most interaction happens through normal prompts.

## 8. Agent runtime architecture

### 8.1 Components

1. CLI/TUI front-end
2. Config loader + policy engine
3. Workspace manager (root, path guards, symlink policy)
4. Copilot SDK session manager:

   * starts Copilot client
   * creates sessions
   * registers tools
   * handles streaming events 
5. Tool registry:

   * SDK built-in tools (filesystem, terminal) - provided by Copilot SDK
   * python execution tools - PUK-provided isolated venv execution
   * user I/O tools (confirm/prompt/select) - PUK-provided
6. Action queue + change staging
7. Run report generator (JSON + human-readable)

### 8.2 Session lifecycle

* Start client
* Create session with:

  * model/provider
  * tools
  * optional MCP servers 
  * system message (policy and interaction rules)
* Stream events to UI
* Close session on exit

## 9. Tools: required baseline set

PUK must provide tools with explicit schemas (Pydantic models suggested). 

### 9.1 User I/O tools (mandatory)

* `display_message(level, message)`
* `confirm_action(question, default)`
* `prompt_user(question, default)`
* `select_option(question, options, default_index)`

These are used by the agent to request clarifications and confirmations. 

### 9.2 Filesystem and terminal tools (SDK built-in)

PUK delegates filesystem and terminal operations to the Copilot SDK's built-in tools:

* `Read` - read file contents
* `Edit` - modify files
* `List directory` - list directory contents
* `bash` - execute shell commands
* `grep` - search within files
* `glob` - find files by pattern

These tools are provided by the SDK and respect its built-in safety mechanisms. PUK can optionally disable specific built-in tools via the `tools.builtin_excluded` configuration.

### 9.4 Python generation and execution tools (recommended)

Two distinct tools:

1. `python_generate(spec, files, constraints) -> proposed_code_bundle`
2. `python_exec(entrypoint, args, venv_policy, cwd) -> stdout/stderr/result`

Venv policy:

* Always run inside a virtual environment.
* Two supported strategies:

  * local: `<root>/.puk/venv`
  * global cache: `~/.puk/venvs/<hash>`
* Dependency installation rules:

  * only from explicit requirements (no silent pip installs unless confirmed or `--confirm`)
  * log every install action

Execution constraints:

* default timeout
* capture outputs
* write artifacts to `.puk/runs/<run_id>/`

## 10. MCP support (optional, first-class)

PUK can connect to MCP servers, configured in `.puk.config` and attached to sessions via `mcpServers` settings. 

Requirements:

* Namespacing preserved (`github/*`, `postgres/*`, etc.) 
* Per-server tool allowlist (no wildcard unless explicitly configured)
* MCP usage is auditable in run reports

## 11. Safety model

PUK is not “safe by nature”. Safety is achieved by capability control and confirmations.

### 11.1 Capability control (primary)

* Only register tools allowed by policy.
* Enforce root scoping in every tool.
* Deny unknown tools by construction.

### 11.2 Confirmation gates (secondary)

Default behavior:

* Ask confirmation before:

  * writing/modifying files
  * deleting/moving paths
  * running commands
  * installing packages
  * connecting to new MCP endpoints
* `--confirm` disables permission prompts for mutating actions but still allows clarification prompts (interactive only).

### 11.3 Staging and diff-first workflow (recommended default)

* Writes go to a staging area first (or git patch plan).
* Show diff.
* Apply only after confirmation (unless `--confirm`).

### 11.4 Audit and reporting

Every run produces:

* `run.json` (structured): config snapshot, tool calls, decisions, files touched, commands run, timings
* `run.md` (human): summary, warnings, diffs, next steps

## 12. Output expectations (what PUK produces)

PUK’s primary outputs are:

* code changes in the workspace (staged then applied)
* generated files (modules, tests, scripts)
* run reports and diffs
* optional generated patches (for PR application later)

PUK should support a “dry run” mode:

* `--dry-run` produces plan + diffs but does not apply changes.

## 13. Non-functional requirements

* OS: Linux/macOS first; Windows optional
* Python: 3.11+
* Robust streaming handling in TUI and plain mode 
* Timeouts and interrupt handling (Ctrl+C)
* Deterministic exit codes:

  * 0 success
  * 2 missing info in non-interactive mode
  * 3 policy violation (attempted out-of-root action)
  * 4 tool execution failure
  * 5 provider/auth failure

## 14. System prompt contract (policy injection)

PUK must inject a system message that states:

* current root and scoping rules
* confirmation rules
* staging/diff policy
* tool usage etiquette (ask for clarification; don’t guess in batch mode)
* do not claim actions performed without tool evidence

This aligns with the SDK’s recommended approach: instruct the AI how to use I/O tools and when to confirm. 

---

## 15. `.puk.config` schema

PUK supports three configuration layers with this precedence:

1. Global config (user-level)
2. Local config (`<root>/.puk.config`)
3. CLI arguments / env overrides

Effective config is the merged result with “last writer wins” semantics at the field level (CLI overrides local overrides global).

### 15.1 Format and parsing

* File name: `.puk.config`
* Recommended format: **TOML**
* Alternative accepted format (optional): YAML, if enabled at build time
* Unknown keys:

  * default: warning + ignore (for forward compatibility)
  * optional strict mode: fail on unknown keys (`core.strict_config=true`)

### 15.2 Schema overview (TOML)

#### 15.2.1 Core

```toml
[core]
profile = "default"              # optional; allows named profile selection later
ui = "tui"                       # "tui" | "plain"
repl = true                      # start REPL when no prompt is provided
streaming = true                 # stream assistant tokens/events
strict_config = false            # if true, unknown keys cause error
telemetry = "off"                # "off" | "local" (local logs only; no remote)
```

#### 15.2.2 Workspace scope

```toml
[workspace]
root = "."                       # resolved to absolute path at runtime
discover_root = true             # if true, search upward for .puk.config
allow_outside_root = false       # free mode (dangerous) requires explicit true
follow_symlinks = false          # if false, deny symlink escapes from root
max_file_bytes = 2000000         # default read limit per file (2MB)
ignore = [".git", ".puk", "node_modules", "dist", "build", "__pycache__"]
allow_globs = ["**/*.py", "**/*.md", "**/*.toml", "**/*.yml", "**/*.yaml", "**/*.json"]
deny_globs = ["**/.env", "**/*secret*", "**/*key*", "**/*.pem"]  # can be overridden
```

Validation rules:

* `root` must exist and be a directory (unless `workspace.create_root=true` is added later).
* If `allow_outside_root=false`, *all* tool paths must be canonicalized and verified to remain under `root`.
* If `follow_symlinks=false`, canonicalization must treat symlinks conservatively and deny escapes.

#### 15.2.3 Provider and model (Copilot subscription or BYOK)

The SDK supports: default Copilot subscription via Copilot CLI, and BYOK providers (OpenAI/Azure/Anthropic) with per-session model selection. 

```toml
[llm]
provider = "copilot"             # "copilot" | "openai" | "azure" | "anthropic"
model = "gpt-5"                  # provider-specific model string
fallback_provider = ""           # optional, same enum as provider
fallback_model = ""              # optional
api_key_env = ""                 # e.g. "OPENAI_API_KEY" (required for BYOK)
azure_endpoint = ""              # required if provider="azure"
azure_api_version = "2024-02-15-preview"
max_output_tokens = 2048         # upper bound; enforce in session config where possible
temperature = 0.2                # optional; only if SDK/provider supports it
```

Validation rules:

* If `provider="copilot"`, BYOK fields are ignored.
* If `provider!="copilot"`, `api_key_env` must be set and present in environment at runtime.
* If `provider="azure"`, `azure_endpoint` must be set.
* If `fallback_provider` is set, it must include required fields too.

#### 15.2.4 Session behavior

The tutorial describes sessions, streaming, and optional “infiniteSessions” compaction. 

```toml
[session]
infinite = true
compaction_threshold = 0.80
system_prompt_file = ""          # optional path to a template, relative to root
```

Validation rules:

* `compaction_threshold` must be in (0.0, 1.0).

#### 15.2.5 Safety and confirmations

```toml
[safety]
confirm_mutations = true         # writes, deletes, moves, renames, patch apply
confirm_commands = true          # command execution
confirm_installs = true          # pip installs / venv changes
confirm_mcp = true               # connecting to MCP servers
redact_secrets = true            # redact likely secrets from displayed output/logs
paranoid_reads = false           # if true, requires confirm before reading sensitive globs
```

CLI override semantics:

* `--confirm` forces:

  * `confirm_mutations=false`
  * `confirm_commands=false`
  * `confirm_installs=false`
  * but still allows clarification questions in interactive mode

#### 15.2.6 Tools policy

PUK provides custom tools for Python execution and user I/O. Filesystem and terminal operations use the SDK's built-in tools.

```toml
[tools]
python_exec = true               # PUK's isolated venv Python execution
user_io = true                   # PUK's user interaction tools
mcp = false                      # MCP tool passthrough
builtin_excluded = []            # SDK tools to disable, e.g. ["bash"]
```

Notes:

* `builtin_excluded` allows disabling specific SDK built-in tools (e.g., `["bash"]` to prevent shell access).
* Filesystem and terminal operations are handled by SDK built-in tools (`Read`, `Edit`, `bash`, etc.).

#### 15.2.7 Python execution (venv isolation)

```toml
[python]
venv_mode = "local"              # "local" | "global-cache"
local_venv_dir = ".puk/venv"
global_cache_dir = "~/.puk/venvs"
auto_create_venv = true
auto_install_requirements = false  # if true, allowed to pip install without explicit request (still confirm unless --confirm)
requirements_files = ["requirements.txt", "pyproject.toml"]
exec_timeout_seconds = 300
```

Validation rules:

* In `venv_mode="local"`, `local_venv_dir` is relative to root.
* In `venv_mode="global-cache"`, cache key must incorporate root path (or repo hash) plus dependency fingerprint.

#### 15.2.8 MCP servers (optional)

The tutorial specifies `mcpServers` with types `http`, `sse`, `local`, and per-server tool allowlists. 

```toml
[mcp]
enabled = false

[mcp.servers.github]
type = "http"
url = "https://api.githubcopilot.com/mcp/"
tools = ["*"]                    # or explicit list
```

Local MCP example:

```toml
[mcp.servers.postgres]
type = "local"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-postgres"]
cwd = "."
tools = ["query", "list_tables"]
```

Validation rules:

* If `mcp.enabled=true`, then `tools.mcp=true` must also be true.
* For `type="local"`, `command` is required.
* Tool allowlists default to empty (deny-all) unless specified.

### 15.3 Complete example `.puk.config` (practical default)

```toml
[core]
ui = "tui"
repl = true
streaming = true

[workspace]
root = "."
discover_root = true
allow_outside_root = false
follow_symlinks = false
ignore = [".git", ".puk", "node_modules", "dist", "build", "__pycache__"]

[llm]
provider = "copilot"
model = "gpt-5"

[session]
infinite = true
compaction_threshold = 0.80

[safety]
confirm_mutations = true
confirm_commands = true
confirm_installs = true
confirm_mcp = true
redact_secrets = true
paranoid_reads = false

[tools]
python_exec = true
user_io = true
mcp = false
# builtin_excluded = ["bash"]  # optionally disable SDK tools

[python]
venv_mode = "local"
local_venv_dir = ".puk/venv"
auto_create_venv = true
auto_install_requirements = false
requirements_files = ["requirements.txt", "pyproject.toml"]
exec_timeout_seconds = 300
```

### 15.4 Required implementation behaviors tied to schema

* PUK must be able to print the "effective config" and show provenance (global/local/cli) via `/config`.
* Any attempt to act outside root while `workspace.allow_outside_root=false` must fail with a policy violation exit code.
* Mutating actions use SDK built-in tools which have their own confirmation mechanisms.
* In `--non-interactive` mode:

  * missing information is an immediate error (exit code "missing info")
  * confirmations cannot be prompted; behavior depends on `--confirm` and config.

