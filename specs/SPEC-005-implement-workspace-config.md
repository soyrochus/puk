# SPEC-005 - Implement Workspace Config

## 1. Purpose

Implement support for the `[workspace]` section from `example.puk.toml` using the same override model already used for `[llm]`.

This enables workspace behavior to be configured via:
- global config
- project/workspace config (`.puk.toml`)
- runtime parameters (highest precedence)

## 2. Scope

In scope:
- Parse and validate `[workspace]` keys from config files.
- Resolve effective workspace settings with precedence: `default -> global -> workspace -> parameter`.
- Wire resolved workspace settings into runtime path/sandbox behavior.
- Add parameter-layer overrides for workspace settings.
- Add logs showing effective workspace settings + source per key.

Out of scope:
- New non-workspace config sections (`[core]`, `[session]`, `[safety]`, `[tools]`, `[python]`, `[mcp]`).
- New policy engines beyond the listed workspace controls.

## 3. Config Files and Locations

Use the same discovery points as LLM config:

1. Global:
- Linux: `~/.config/puk/puk.toml`
- macOS: `~/Library/Application Support/puk/puk.toml`
- Windows: `%APPDATA%\puk\puk.toml`
2. Workspace:
- `<workspace>/.puk.toml`
- fallback: `<workspace>/.puk.config`

## 4. Override Precedence

Effective `[workspace]` config is merged key-by-key in this exact order:

1. Defaults
2. Global config
3. Workspace config
4. Parameters

This is identical to the current `[llm]` override mechanism.

## 5. `[workspace]` Schema (To Implement)

Implement support for:

```toml
[workspace]
root = "."
discover_root = true
allow_outside_root = false
follow_symlinks = false
max_file_bytes = 2000000
ignore = [".git", ".puk", "node_modules", "dist", "build", "__pycache__"]
allow_globs = ["**/*.py", "**/*.md", "**/*.toml", "**/*.yml", "**/*.yaml", "**/*.json"]
deny_globs = ["**/.env", "**/*secret*", "**/*key*", "**/*.pem"]
```

## 6. Defaults

Default values should match `example.puk.toml`:
- `root = "."`
- `discover_root = true`
- `allow_outside_root = false`
- `follow_symlinks = false`
- `max_file_bytes = 2000000`
- `ignore = [".git", ".puk", "node_modules", "dist", "build", "__pycache__"]`
- `allow_globs = ["**/*.py", "**/*.md", "**/*.toml", "**/*.yml", "**/*.yaml", "**/*.json"]`
- `deny_globs = ["**/.env", "**/*secret*", "**/*key*", "**/*.pem"]`

## 7. Validation Rules

- `root` must be a non-empty path string.
- `discover_root`, `allow_outside_root`, `follow_symlinks` must be boolean.
- `max_file_bytes` must be a positive integer.
- `ignore`, `allow_globs`, `deny_globs` must be lists of non-empty strings.
- If `allow_outside_root=false`, resolved root must remain within invocation workspace boundary.
- If `follow_symlinks=false`, symlink-based escapes outside effective root must be denied.

Validation must fail fast with clear, actionable messages.

## 8. Resolution Semantics

Define terms:
- **Invocation workspace**: CLI `--workspace` value (current behavior).
- **Effective root**: the root used to constrain filesystem operations and path validations.

Resolution flow:
1. Start from invocation workspace.
2. If `discover_root=true`, search upward for `.puk.toml` or `.puk.config`; if found, use that directory as base root.
3. Resolve `workspace.root` relative to that base root (or invocation workspace if no discovery hit).
4. Canonicalize to absolute path.
5. Enforce `allow_outside_root` and `follow_symlinks` policies.

## 9. Runtime Behavior

Effective workspace settings must be enforced in:
- tool path resolution and permission checks
- playbook path parameter validation (`type=path`)
- write scope checks
- file-read operations (`max_file_bytes`, allow/deny globs, ignore list)

Policy rules:
- `deny_globs` always wins over `allow_globs`.
- `ignore` directories are excluded from scans/search/list operations by default.
- Reads larger than `max_file_bytes` are rejected with explicit reason.

## 10. Parameters Layer

Add runtime parameter overrides for workspace settings (same concept as `[llm]` parameters).

Minimum overrides to support:
- `workspace_root`
- `workspace_discover_root`
- `workspace_allow_outside_root`
- `workspace_follow_symlinks`
- `workspace_max_file_bytes`
- `workspace_ignore`
- `workspace_allow_globs`
- `workspace_deny_globs`

CLI/API wiring should map these to the parameter layer used by config resolution.

## 11. Observability

Log effective workspace settings and source per key (`default`, `global`, `workspace`, `parameter`), similar to `[llm]` logging.

Sensitive path patterns do not require redaction, but logs should remain concise.

## 12. Acceptance Criteria

1. Puk loads and validates `[workspace]` from global/workspace config files.
2. Precedence is exactly `default -> global -> workspace -> parameter`.
3. Parameter overrides win per key over file/default values.
4. Runtime enforces `allow_outside_root` and `follow_symlinks`.
5. Runtime enforces `max_file_bytes`, `ignore`, `allow_globs`, and `deny_globs`.
6. Path-type playbook parameters validate against effective root boundary.
7. Effective workspace config and provenance are logged.

## 13. Test Plan

Unit tests:
- Merge precedence per workspace key across all 4 layers.
- Validation failures for bad types/values.
- Root resolution behavior with/without `discover_root`.
- `deny_globs` precedence over `allow_globs`.

Integration tests:
- Reads outside effective root are blocked when `allow_outside_root=false`.
- Symlink escape attempts blocked when `follow_symlinks=false`.
- Large file read blocked by `max_file_bytes`.
- Ignore directories excluded from scan/list/search behavior.
- Parameter overrides change runtime behavior without editing config files.
