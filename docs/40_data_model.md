# 40. Data Model

Generated: 2026-02-09

## Summary

No database schema, ORM models, or migration system was detected in the core application code.

Puk persists run history to the **filesystem** under `.puk/runs/**` using:
- a JSON manifest file (`run.json`)
- an append-only NDJSON event log (`events.ndjson`)
- an artifacts directory (`artifacts/`)

Evidence pointers:
- `src/puk/run.py` (`RunPaths`, `RunRecorder`, manifest/event log writes)
- `src/puk/runs.py` (discovery + reading manifests/events)

## Persisted file formats (conceptual schema)

### Run directory layout

```
.puk/runs/<run_dir>/
  run.json
  events.ndjson
  artifacts/
  run.lock
```

Evidence pointers:
- `src/puk/run.py` (`RunPaths` fields; `RunRecorder.start()`)

### `run.json` (manifest) fields (best-effort)

From `RunRecorder.start()`:
- `run_id`
- `created_at`, `updated_at`
- `title`
- `status`
- `workspace`
- `mode`
- `llm`: provider/model/temperature/max_output_tokens

Evidence pointers:
- `src/puk/run.py` (manifest dict in `RunRecorder.start()`)

### `events.ndjson` (event record) fields (best-effort)

From `_append_event()`:
- `timestamp`
- `seq`
- `type`
- `run_id`
- `turn_id`
- `data` (event-specific payload)

Evidence pointers:
- `src/puk/run.py:_append_event()`

## ER-ish diagram (filesystem persistence)

```mermaid
erDiagram
  RUN_DIR ||--|| RUN_JSON : contains
  RUN_DIR ||--|| EVENTS_NDJSON : contains
  RUN_DIR ||--o{ ARTIFACT_FILE : contains

  RUN_JSON {
    string run_id
    string created_at
    string updated_at
    string status
    string workspace
    string mode
  }

  EVENTS_NDJSON {
    string timestamp
    int seq
    string type
    string run_id
    int turn_id
    json data
  }

  ARTIFACT_FILE {
    string path
    bytes content
  }
```

## Notes / limitations

- This section is derived purely from static code reading; it does not inspect runtime-created `.puk/` contents.
- If future versions add additional persisted indices or caches, they should be documented alongside `run.json` and `events.ndjson`.
