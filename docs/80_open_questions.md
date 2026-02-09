# 80. Open Questions / Verification Checklist

Generated: 2026-02-09

## Open questions

1) **Tooling surface and compatibility tools**
- Which tool names are guaranteed by the Copilot SDK in your environment vs provided via Puk “compatibility tools”? This affects playbook portability.
- Evidence: `src/puk/app.py:_build_compatibility_tools()`

2) **Git integration in run manifests**
- Specs mention optional git info; current `RunRecorder` manifest does not appear to record commit/dirty state.
- Evidence: `specs/SPEC-003-Run-as-unit-of-execution.md` vs `src/puk/run.py`.

3) **Playbook `functional_sources` parameter type mismatch**
- Playbook front-matter defines `functional_sources` as a `string` (comma-separated), while playbook instructions describe it as a list[path].
- Evidence: `playbooks/reverse-engineer-docs.md` front-matter vs body.

4) **Write-scope enforcement edge cases**
- How are multi-path operations handled (e.g., rename/move)? Current path extraction looks for keys like `path`, `paths`, `file`, etc.
- Evidence: `src/puk/app.py:_extract_paths()`

5) **Vendor directory scanning**
- Documentation/playbooks might need to exclude `vendor/` by default for most repositories to reduce noise.
- Evidence: `vendor/copilot-sdk/**`.

## Verification checklist (static)

- [ ] Confirm `puk` runs without workspace config and uses Copilot default provider.
- [ ] Confirm `.puk.toml` overrides work and precedence matches spec.
- [ ] Confirm playbook runs in plan mode deny all tool calls.
- [ ] Confirm playbook runs in apply mode deny writes outside `write_scope`.
- [ ] Confirm `puk runs list/show/tail` match recorded run directories.

## Verification checklist (runtime)

- [ ] Run `puk` and verify a new `.puk/runs/...` directory is created.
- [ ] Trigger a tool call and confirm `tool.call`/`tool.result` events are recorded.
- [ ] Run a playbook that writes under `docs/**` and confirm enforcement.
