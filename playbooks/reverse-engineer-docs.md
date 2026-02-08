---
id: reveng_docs_multistack_v0
name: "Reverse-engineer Project Documentation (Python/Node/Java + React/Angular)"
version: "0.1"
status: "draft"
owner: "Puk"
tags: ["reverse-engineering", "documentation", "multistack", "copilot-sdk"]
description: >
  Generate technical and inferred functional documentation by scanning a repository’s source tree.
  Uses only default Copilot SDK tools (filesystem + git if available). Produces docs incrementally
  in parts to prevent context overflow. Final step assembles a coherent documentation bundle in /docs.
---

# Playbook: Reverse-engineer Project Documentation (Incremental, Context-safe)

## 0. Purpose and outputs

This playbook generates a concrete documentation bundle for an existing codebase by scanning the repository
and synthesizing technical documentation (architecture, APIs, data model hints, UI flows) and inferred
functional documentation (from user-provided functional sources and repo artefacts).

Outputs are written incrementally as separate files under `docs/` to avoid context overflow (“context rot”).
The final step assembles an index and an integrated “main” document that references the parts.

Primary outputs:
- `docs/00_index.md` (navigation + build metadata)
- `docs/10_overview.md` (high-level system summary)
- `docs/20_architecture.md` (components, layers, runtime view)
- `docs/30_backend_api.md` (API inventory, endpoints, contracts where visible)
- `docs/40_data_model.md` (schema hints, ORM models, migrations; no DB introspection)
- `docs/50_frontend_ui.md` (routes/pages/components/forms; React/Angular)
- `docs/60_user_flows.md` (inferred flows with evidence pointers)
- `docs/70_ops_and_runtime.md` (build/run/deploy, env, configs)
- `docs/80_open_questions.md` (unknowns + where to look)
- `docs/90_appendix_inventory.md` (file inventory, detected stacks, key references)
- `docs/README.md` (assembled entry-point summary linking sections)

Non-goals:
- Perfect completeness. This is static reverse engineering, not runtime tracing.
- No custom tools, no parsers beyond what the agent can do by reading files with default tools.
- No network calls.

## 1. Parameters and validation

### 1.1 Required parameters
- `repo_root` (path): root directory to scan.
- `output_dir` (path, default: `docs`): directory to write documentation parts.
- `functional_sources` (list[path]): paths (files or dirs) that contain functional guidance:
  README files, product docs, ADRs, specs, user stories, etc. These are treated as evidence
  for inferred functional docs.

### 1.2 Optional parameters
- `include_globs` (list[string], default: `["**/*"]`)
- `exclude_globs` (list[string], default: `["**/.git/**", "**/node_modules/**", "**/dist/**", "**/build/**", "**/target/**", "**/.venv/**", "**/venv/**", "**/__pycache__/**"]`)
- `max_file_size_kb` (int, default: `512`) – skip huge files and record skips in inventory.
- `max_files_per_chunk` (int, default: `200`) – chunk size for incremental scanning.
- `max_read_files_per_section` (int, default: `80`) – hard guardrail to avoid context blow-up per section.
- `diagram_format` (enum, default: `mermaid`): `mermaid | text` (mermaid diagrams embedded in markdown).
- `frontend_focus` (enum, default: `auto`): `auto | react | angular | none`
- `backend_focus` (enum, default: `auto`): `auto | python | node | java | mixed`

### 1.3 Validation rules (fail fast)
- `repo_root` exists.
- `output_dir` is within repo (do not allow `..` escapes).
- `functional_sources` exist; if empty, proceed but generate weaker functional docs and flag it.
- Ensure `output_dir` is writeable (or create it).

## 2. Default tool surface (ONLY)
Allowed tools are restricted to what the Copilot SDK provides by default:
- Filesystem read/list/write in the workspace.
- Git metadata if available via built-in tooling (HEAD, status), otherwise file timestamps.
No custom parsers, no MCP, no external commands.

Guardrail: do not attempt to “run” code, start servers, or install dependencies.

## 3. Context safety strategy (anti-overflow)

This playbook is executed in stages. Each stage produces a file in `output_dir`, then **drops context**
and proceeds to the next stage using only:
- the section file(s) already written
- a small inventory summary
- and a targeted list of files for the next section

Hard rules:
- Never attempt to read the entire repo contents into the model context.
- Use file inventories and targeted sampling.
- Each section must cite “evidence pointers”: file paths and line ranges where possible
  (approximate references are acceptable if the tool can’t capture line ranges reliably).

## 4. Execution flow

### Step A — Inventory and stack detection (writes 90_appendix_inventory.md)
1. Enumerate repository tree with include/exclude globs.
2. Identify stack signals by file patterns:
   - Python: `pyproject.toml`, `requirements.txt`, `setup.cfg`, `*.py`
   - Node: `package.json`, `tsconfig.json`, `*.js`, `*.ts`
   - Java: `pom.xml`, `build.gradle`, `src/main/java/**`
   - React: `package.json` deps, `src/App.*`, `react-router`, `*.jsx`/`*.tsx`
   - Angular: `angular.json`, `src/app/**`, `*.component.*`, `*.module.*`
   - DB hints: migration folders, `schema.sql`, ORM models
   - API hints: `openapi.*`, `swagger.*`, controller/routes folders
3. Record:
   - detected stacks + confidence
   - key files
   - skipped files (too large / excluded)
4. Write inventory appendix.

### Step B — Functional evidence capture (writes docs/15_functional_sources.md)
1. Read and summarize only the files/directories listed in `functional_sources`.
2. Extract:
   - stated purpose
   - user roles
   - workflows / use cases
   - domain terms / glossary
   - non-functional requirements (security, performance)
3. Write `docs/15_functional_sources.md` as “evidence base”.
This file is the anchor for later inferred functional documentation.

### Step C — Technical overview (writes docs/10_overview.md and docs/20_architecture.md)
Input: inventory + small targeted reads of:
- build files (pom/gradle, package.json, pyproject/requirements)
- main entrypoints (server main, app module, index.ts, Spring Boot Application class)
- config files (application.yml, .env.example, config modules)

1. Produce `10_overview.md`:
   - what the system is
   - main runtime processes
   - how to build/run (from evidence)
   - where key things live in the tree

2. Produce `20_architecture.md`:
   - component decomposition (backend services, front-end apps, shared libs)
   - layer view (presentation/domain/data; or controllers/services/repos; inferred)
   - key dependencies and boundaries
   - include at least one Mermaid diagram:
     - Component diagram (high-level)
     - Optional: deployment sketch if Docker/K8s files exist

### Step D — Backend API documentation (writes docs/30_backend_api.md)
Input: targeted reads of API-signaling files:
- OpenAPI/Swagger specs if present (prefer these)
- routing/controller files:
  - Python: FastAPI/Flask/Django views, `urls.py`, `routers`
  - Node: Express/NestJS controllers/routes
  - Java: Spring `@RestController` classes

Deliver:
- API inventory table (service/module → endpoints)
- request/response structures where visible in code/specs
- auth hints (middleware, filters, JWT, OAuth config)
- error handling conventions
- Mermaid sequence diagram for one “representative” request flow (best effort)

Constraint:
- If API surface is large, document by grouping (e.g., by controller/router module) and limit per chunk.
- Always include file pointers.

### Step E — Data model documentation (writes docs/40_data_model.md)
Input: targeted reads of:
- migration scripts (Flyway/Liquibase, Alembic, Prisma, Sequelize, TypeORM migrations)
- ORM/entity definitions (SQLAlchemy models, Django models, JPA entities)
- schema files (`schema.sql`)

Deliver:
- conceptual entities list and relations (best effort)
- table/schema hints if migrations exist
- how persistence is wired (repositories/DAOs)
- Mermaid ER-ish diagram (approximate) based only on static evidence

Guardrail:
- No DB introspection. Everything is derived from files.

### Step F — Front-end UI and forms (writes docs/50_frontend_ui.md)
Input: targeted reads of:
- route definitions (React Router, Angular routing module)
- page/container components
- form components and validators
- API client modules

Deliver:
- UI structure:
  - routes/pages
  - main components
  - forms (field names, validation hints, submission endpoints)
- state management hints (Redux, Zustand, NgRx, services)
- Mermaid diagram:
  - route map or UI flow map

If no frontend detected, write a short “not present” section with evidence.

### Step G — Inferred user flows (writes docs/60_user_flows.md)
Inputs:
- `15_functional_sources.md` evidence base
- API and UI docs generated in prior steps
- selected code hints (auth flow, onboarding, checkout-like flows)

Deliver:
- user flows described as:
  - Flow name
  - Preconditions
  - Steps (UI + backend interactions)
  - Evidence pointers to docs sections and code paths
- At least one Mermaid flow diagram.

Guardrail:
- Every inferred claim must cite evidence pointers (functional source, route file, controller, etc.).
- If evidence is weak, mark as “hypothesis” and move to open questions.

### Step H — Ops and runtime (writes docs/70_ops_and_runtime.md)
Input: targeted reads of:
- Dockerfile(s), docker-compose, Helm, K8s manifests
- CI pipelines (.github/workflows, Jenkinsfile, GitLab CI)
- environment config samples

Deliver:
- how to build/run/test
- runtime configuration model
- deployment topology (if defined)
- logging/monitoring hints

### Step I — Open questions and verification checklist (writes docs/80_open_questions.md)
Deliver:
- unknowns that require humans or runtime checks
- suggested verification steps (manual and static)
- gaps due to excluded files or missing functional sources

### Step J — Assemble final docs (writes docs/00_index.md and docs/README.md)
1. Create `00_index.md` with links to all parts, plus metadata:
   - repo id (path), commit sha if available, generation timestamp
   - detected stacks
2. Create `README.md` as the top-level entry point:
   - short narrative summary
   - recommended reading order
   - link to index and key sections

Hard rule:
- Assembly is purely from already generated parts. No new repo scanning here.

## 5. Quality constraints (“real and concrete”)

Every technical section must include at least:
- evidence pointers (paths)
- an inventory (tables) for APIs/routes/entities (even if partial)
- at least one diagram in Mermaid if enabled

“Concrete” means:
- identify actual modules/classes/files, not generic descriptions
- document actual endpoints/routes seen
- show actual config keys where present
- show actual UI route paths where present

## 6. Failure modes and safe degradation

- If repository is huge: fall back to sampling by directories and prioritize:
  - build files + entrypoints + API specs + routing/controllers + migrations + routing/ui.
- If code is minified/bundled: skip and record.
- If functional sources are missing: produce weaker functional flows and flag clearly.

## 7. Deliverables summary (files written)

- `docs/00_index.md`
- `docs/README.md`
- `docs/10_overview.md`
- `docs/15_functional_sources.md`
- `docs/20_architecture.md`
- `docs/30_backend_api.md`
- `docs/40_data_model.md`
- `docs/50_frontend_ui.md`
- `docs/60_user_flows.md`
- `docs/70_ops_and_runtime.md`
- `docs/80_open_questions.md`
- `docs/90_appendix_inventory.md`
