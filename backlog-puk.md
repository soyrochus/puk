# Backlog Puk

## Baseline (already assumed)

### Puk v0 — Agent Shell Parity

**Goal:** Working Copilot SDK integration with a basic REPL.

Capabilities:

* CLI shell with conversational loop.
* Access to Copilot SDK agent runtime.
* Basic tool invocation (filesystem, git).
* Session-local context only.
* No persistence beyond chat history.
* No abstraction above “chat”.

At this point, **Puk duplicates Copilot CLI**. This is intentional: it gives you a stable, known baseline and validates SDK integration.

Everything below exists to *escape* this parity trap.

---

## Epic 1 — From Chat to Execution Units


### 1.1 Introduce “Runs” as a first-class concept (CLI-aligned)

A `Run` is the persisted record of one coherent execution session. In Puk, that means:

* Default mode (no positional `prompt`) starts an interactive REPL session and the run contains the full REPL interaction until exit.
* Automated mode (positional `prompt` provided) executes a single-shot and the run contains that one execution.

Both modes must support appending to an existing run with a new parameter.

#### CLI contract (this increment)

Current CLI (as given):

* `prompt` is an optional positional argument. If present, run in automated (single-shot) mode; if absent, run REPL.

Add:

* `-a, --append-to-run RUN_REF`
  If provided, write all events from this invocation into the referenced run instead of creating a new one.

Resulting behavior:

* `puk`
  Starts REPL. Creates a new run under `.puk/runs/…` and appends all REPL turns/events until exit.

* `puk --append-to-run <run_ref>`
  Starts REPL. Appends all REPL turns/events to an existing run.

* `puk "do X"`
  Automated single-shot. Creates a new run and records the whole execution as one segment.

* `puk "do X" --append-to-run <run_ref>`
  Automated single-shot. Appends this execution segment to an existing run.

Constraints:

* `RUN_REF` must accept at least:

  * `run_id`, or
  * a path to a run directory under `.puk/runs/...`
* If `RUN_REF` does not exist: fail fast with a clear error (no implicit creation, because “append” must be explicit).

#### Run storage rule

* Runs are stored in `.puk/runs/<run_dir>/`.
* `<run_dir>` is timestamp-based and can include an optional title slug.
* Each run has a stable `run_id` stored in its manifest and used by `--append-to-run`.

#### What a run contains (session-level, not “one turn”)

A run is an append-only timeline. It must capture the *connection* between the interaction and the produced solution by storing a provenance chain, not just raw chat.

Minimum persisted structure:

* `run.json` (manifest)

  * `run_id`
  * `created_at`, `updated_at`
  * optional `title`
  * `status` (`open` | `closed` | `failed`)
  * workspace fingerprint (workspace path; optionally git info if present)
  * model/provider/temperature/max-output-tokens as resolved at runtime (so later you can explain output variance)

* `events.ndjson` (append-only event log)
  Every REPL turn and every single-shot execution is recorded as a sequence of events. Required event types:

  * `session.start` (mode = repl|oneshot, argv/params snapshot)
  * `input.user` (the user text; for oneshot this is the positional prompt)
  * `context.resolved` (with provenance pointers: file paths, retrieved chunks, prior run refs)
  * `model.output` (assistant response; tool plan if applicable)
  * `tool.call` / `tool.result` (timestamped, ordered)
  * `artifact.write` (what was created/changed, and where)
  * `status.change` (planned/applied/failed; open/closed)
  * `session.end`

* `artifacts/` directory

  * diffs/patches, generated files, reports, logs
  * artifacts are referenced from `artifact.write` events (the log is the authoritative connection between “conversation” and “solution”)

Status semantics

* New run starts as `open`.
* REPL exit sets `closed` (or `failed` if exiting due to an error).
* One-shot runs typically go `open → closed` within the same invocation.
* When appending, the run becomes `open` for the duration of the append and returns to `closed` after completion (or stays `open` only if you want “long-lived runs”; choose one and enforce it consistently).

#### Increment (what is delivered)

* Implement `Run` persistence under `.puk/runs/…`.
* Implement `--append-to-run` across both modes (default REPL and positional-prompt one-shot).
* Persist the minimal manifest + append-only event log + artifact storage.
* Ensure that for any output artifact, you can trace back in the run log:
  prompt/turn → resolved context → tool calls → artifact write.


---

## Epic 2 — Playbooks (Core Differentiator)

### 2.1 Playbook format and loader

**Why:** This is where Puk stops being “chat”.

Increment:

* Define playbook as:

  * Markdown + machine-readable front-matter.
  * Fields: id, version, parameters, allowed tools, write scope.
* CLI support:

  ```
  puk run playbooks/update_tests.md --param target_dir=specs
  ```

Outcome:

* Intent is externalized.
* Execution is no longer ad-hoc.

### 2.2 Parameter verification and binding

**Why:** Without this, playbooks are just fancy prompts.

Increment:

* Typed parameters with defaults.
* Fail-fast validation before agent execution.
* Parameter binding injected into prompt and tool context.

Outcome:

* Playbooks are repeatable.
* Errors move from “model hallucination” to deterministic validation.

### 2.3 Execution plan phase

**Why:** Enterprises need “what will you do?” before “do it”.

Increment:

* `run_mode = plan | apply`.
* Agent produces a structured plan in plan mode.
* Apply mode requires plan acceptance.

Outcome:

* You now have **plan/apply semantics**.
* This is a conceptual break from Copilot CLI.

---

## Epic 3 — Script Generation as an Asset

### 3.1 Script extraction and classification

**Why:** Scripts are where value compounds.

Increment:

* When agent outputs runnable logic (bash, Python, Node, git sequences):

  * Detect and extract as a script artifact.
  * Attach metadata: playbook, params, repo fingerprint.

Outcome:

* Scripts stop being text blobs in chat logs.
* They become reusable objects.

### 3.2 Script cache

**Why:** “Generate once, reuse many times.”

Increment:

* Local script cache keyed by:

  * intent (embedding + playbook id)
  * parameters (canonicalized)
  * repo signature (language, framework, manifests)
* Retrieval before generation:

  * reuse
  * adapt
  * regenerate only if needed.

Outcome:

* Token spend drops.
* Output stability increases.
* This is *reuse economics*, not prompt engineering.

---

## Epic 4 — Scripts as Plugins (Lightweight Tools)

### 4.1 Plugin manifest and registry

**Why:** MCP is too heavy for most local automation.

Increment:

* Plugin = executable + manifest:

  * name, inputs, outputs
  * declared capabilities
* Auto-discovery:

  * project-level and user-level plugin dirs.

Outcome:

* Tools can be added in minutes.
* No server, no protocol boilerplate.

### 4.2 Capability gating and scope enforcement

**Why:** Safety and governance.

Increment:

* Capabilities enforced at runtime:

  * filesystem read/write
  * command execution
  * network
* Playbooks explicitly allow plugins.
* Write boundaries enforced (e.g. `specs/` only).

Outcome:

* You have a *controlled execution surface*.
* This is where Puk becomes enterprise-viable.

---

## Epic 5 — Memory Beyond the Session

### 5.1 Session memory

**Why:** Continuity of work.

Increment:

* Store run outcomes, decisions, failures.
* Resume runs.
* Reference prior runs explicitly.

Outcome:

* Work spans days and repos, not just one shell session.

### 5.2 Long-term curated memory

**Why:** Organizations repeat themselves.

Increment:

* Memory entries with:

  * content
  * provenance
  * scope (user / org / client)
  * validity rules.
* Not raw chat — structured knowledge.

Outcome:

* “How we do things” becomes executable context.
* This is orthogonal to Copilot’s repo-scoped memory.

---

## Epic 6 — RAG as a Controlled Plane

### 6.1 Retrieval sources

**Why:** Context must be deliberate.

Increment:

* Indexed sources:

  * playbooks
  * script cache
  * docs packs
  * graph-backed code models (later)
* Playbooks declare allowed sources.

Outcome:

* No accidental data leakage.
* Deterministic context assembly.

### 6.2 Retrieval policy

**Why:** RAG without policy is liability.

Increment:

* Playbook-level controls:

  * recency bias
  * mandatory references
  * redaction rules
  * token budgets.

Outcome:

* RAG becomes predictable and auditable.

---

## Epic 7 — Graph-Backed Structural Memory (Advanced)

### 7.1 Graph ingestion playbooks

**Why:** LLMs cannot hold large systems in context.

Increment:

* Playbooks that:

  * parse code
  * populate graph (Neo4j / Postgres AGE).
* Graph becomes memory substrate.

Outcome:

* Agents reason *over structure*, not text dumps.

### 7.2 Graph-driven downstream playbooks

**Why:** Compound value.

Increment:

* Playbooks that query graph:

  * generate docs
  * detect coupling
  * identify refactor candidates.

Outcome:

* Puk becomes a **system cognition tool**, not just a generator.

---

## Epic 8 — BYOK and Execution Portability

### 8.1 Backend abstraction

**Why:** Avoid lock-in.

Increment:

* Model backend is configurable.
* Copilot models, OpenAI, Anthropic via the same run semantics.

Outcome:

* Same playbooks, different inference engines.

### 8.2 Cost and policy routing

**Why:** Economics matter.

Increment:

* Per-playbook model selection.
* Cheap models for analysis, premium for codegen.

Outcome:

* Puk becomes cost-aware, not just capable.

---

## End State (What Puk Is)

At the end of this backlog, **Puk is no longer a CLI**.

It is:

* a **playbook runner**
* a **script and automation asset manager**
* a **memory and retrieval plane**
* a **controlled execution environment**
* portable across model providers
* layered *above* Copilot, not beside it

Copilot CLI remains the best interactive shell.

Puk becomes the place where:

> “We solved this once — now we do it safely, repeatedly, and cheaper.”

That distinction is the business case.
