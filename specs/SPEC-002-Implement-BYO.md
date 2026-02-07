# SPEC-002 - Implement BYO (LLM Config Only)

## 1. Purpose

Implement Epic 8 (BYOK and execution portability) in a minimal first increment by adding configurable LLM provider/model selection through `puk.toml` or `.puk.toml`

This spec is intentionally limited to the `[llm]` section from `example.puk.toml`.

## 2. Scope

In scope:

- Config file discovery and merge for LLM settings only.
- Runtime resolution of effective LLM settings from defaults, global config, workspace config, and parameters.
- Validation rules for `[llm]` values.
- Wiring resolved LLM settings into session/runtime creation.

Out of scope:

- Any config section except `[llm]`.
- Cost routing policies, per-playbook model routing, and advanced policy engines.
- Changes to run/playbook semantics beyond model/provider selection.

## 3. Epic 8 Mapping

From `backlog-puk.md`:

- Epic 8.1 Backend abstraction: implemented by selecting provider/model from config and parameters.
- Epic 8.2 Cost and policy routing: deferred (not in this spec).

## 4. Config Files and Locations

PUK reads `puk.toml` from:

1. Global user config directory (OS-dependent):
- Linux: `~/.config/puk/puk.toml`
- macOS: `~/Library/Application Support/puk/puk.toml`
- Windows: `%APPDATA%\\puk\\puk.toml`
2. Workspace directory:
- `<workspace>/.puk.toml`  (hidden file on Linux and MacOS)

The workspace directory is the effective working root for the current invocation.

## 5. Override Precedence

Effective config must be merged in this exact order:

1. Defaults
2. Global dir config
3. Workspace dir config
4. Parameters

Where later layers override earlier layers key-by-key.

`Parameters` means runtime overrides (CLI flags and/or explicit runtime arguments).

## 6. `[llm]` Schema (Only Section To Implement)

Based on `example.puk.toml`, implement support for:

```toml
[llm]
provider = "copilot"          # "copilot" | "openai" | "azure" | "anthropic"
model = "gpt-5"
fallback_provider = ""
fallback_model = ""
api_key_env = "OPENAI_API_KEY"
azure_endpoint = ""
azure_api_version = "2024-02-15-preview"
max_output_tokens = 2048
temperature = 0.2
```

## 7. Validation Rules

- `provider` must be one of: `copilot`, `openai`, `azure`, `anthropic`.
- `model` must be a non-empty string.
- `fallback_provider` must be empty or one of supported providers.
- If `fallback_provider` is set, `fallback_model` must be non-empty.
- `temperature` must be numeric and in `[0.0, 2.0]`.
- `max_output_tokens` must be a positive integer.
- For `azure` provider, `azure_endpoint` must be non-empty.
- For non-azure providers, `azure_*` keys may exist but are ignored.
- `api_key_env` must be non-empty for BYOK providers (`openai`, `azure`, `anthropic`).

Validation failures must be fail-fast with clear actionable messages.

## 8. Runtime Behavior

- If provider is `copilot`, continue using Copilot SDK path.
- If provider is BYOK (`openai`, `azure`, `anthropic`), route through the corresponding backend abstraction layer.
- If primary provider initialization fails and fallback is configured, attempt fallback once.
- If both fail, return a user-readable error indicating tried providers/models.

## 9. Parameters Layer

Parameters layer must be able to override `[llm]` keys, at minimum:

- `provider`
- `model`
- `temperature`
- `max_output_tokens`

If a parameter override is provided, it always wins over workspace/global/default values.

## 10. Observability

Expose effective resolved LLM config (with provenance) via debug/log output:

- Final provider/model selected.
- Whether fallback is configured.
- Config source for each effective key: `default`, `global`, `workspace`, or `parameter`.

Never print API key values; only print env var names (for example `OPENAI_API_KEY`).

## 11. Acceptance Criteria

1. PUK loads `[llm]` from global and workspace `puk.toml` files.
2. Effective config precedence is exactly: `default -> global -> workspace -> parameters`.
3. Only `[llm]` is implemented from `example.puk.toml`; other sections are ignored by this spec.
4. Invalid `[llm]` values fail fast with clear error messages.
5. BYOK provider selection works through runtime abstraction with optional fallback behavior.
6. Existing Copilot default path remains functional when no BYOK overrides are supplied.

## 12. Test Plan

- Unit tests:
  - Merge precedence per key across all 4 layers.
  - Validation for provider, model, temperature, max tokens.
  - Azure-specific required endpoint behavior.
  - Fallback preconditions and fallback attempt path.
- Integration tests:
  - No config present -> defaults used.
  - Global only -> global values used.
  - Global + workspace -> workspace wins.
  - Parameter overrides -> parameters win over all file values.
  - Invalid workspace config -> startup fails with explicit message.

