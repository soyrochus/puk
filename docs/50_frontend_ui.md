# 50. Frontend UI

Generated: 2026-02-09

## Summary

No web frontend (React/Angular/etc.) is present in this repository. The UI is a **terminal/console UI** implemented in Python.

Evidence pointers:
- No `package.json`, `src/app/**`, `*.tsx`, `*.jsx`, `angular.json` detected in the project root.
- `src/puk/ui.py` implements console rendering for the REPL.

## Terminal UI (REPL)

### Interaction model

- Shows a banner and usage hints.
- Accepts multiline input.
- Uses **Ctrl+J** to submit.
- Prints tool events/results and streamed assistant deltas.

Evidence pointers:
- `src/puk/ui.py` (`ConsoleRenderer`)
- `src/puk/app.py` (`PukApp.repl`, prompt-toolkit bindings)

### Local REPL commands (not sent to the model)

- `/runs` – list runs in workspace
- `/run <id|dir>` – show a run summary
- `/tail <id|dir>` – output events

Evidence pointers:
- `src/puk/app.py` (`PukApp.repl` local command parsing)

## UI flow diagram

```mermaid
flowchart TD
  START[Start puk] --> MODE{positional prompt?}
  MODE -- no --> REPL[Interactive REPL]
  MODE -- yes --> ONESHOT[One-shot ask()]

  REPL --> INPUT[User types multiline]
  INPUT --> SEND[Ctrl+J submit]
  SEND --> STREAM[Stream assistant deltas]
  STREAM --> REPL

  REPL -->|/runs,/run,/tail| LOCAL[Local inspection command]
  LOCAL --> REPL
```
