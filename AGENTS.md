# AGENTS.md — Project-Local Instructions

These rules apply to all agents working in this repository. They supplement global agent instructions. If there is a direct conflict, this file wins for this repo.

This repo supports a long-lived market-data and trading-research system: raw recording, normalization, feature generation, replay, backtesting, alerts, analysis, ML, and future integrations. The user will scope each phase in prompts. Implement the current task without breaking compatibility with later phases.

Repository docs under `docs/` are internal implementation, coordination, and reference documents for agents and maintainers. Optimize them for durable engineering guidance and current-state accuracy rather than public-facing project prose.

The repo's overall goals, structure, and governing rules should remain stable, but detailed plans, implementation notes, and operational guidance are expected to evolve as the project is implemented.

---

## 1) Canonical Repo Structure

Use this structure unless the user explicitly changes it. Do not create new top-level phase folders; add phase-specific work inside the existing layout.

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml
├── requirements.txt                  # optional if pyproject/lockfile is sufficient
├── .env.example                      # example only; never commit real secrets
├── .gitignore
├── config/
│   ├── config.example.yaml            # canonical runtime config example
│   └── sources.example.yaml           # optional source/provider examples
├── docs/
│   ├── agent-guidebook.md             # primary agent implementation reference
│   ├── reference/
│   │   ├── schemas.md
│   │   ├── data-layout.md
│   │   └── providers/
│   │       ├── pyth.md
│   │       ├── aster.md
│   │       └── tradingview.md
│   ├── operations/
│   │   ├── change-log.md              # durable commit-style change log
│   │   ├── implementation-status.md   # continuously maintained feature/status map
│   │   ├── deployment.md              # optional deployment notes
│   │   └── monitoring.md              # optional monitoring/health notes
│   ├── decisions/                     # durable ADR-style decisions
│   └── phases/                        # optional user-scoped phase plans
├── src/
│   └── market_recorder/
│       ├── config.py
│       ├── timeutil.py
│       ├── logging.py
│       ├── storage/                   # raw writers, paths, manifests
│       ├── sources/                   # provider adapters
│       ├── normalize/
│       ├── features/
│       ├── backtest/
│       ├── replay/
│       ├── alerts/
│       ├── ml/
│       └── cli.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/                           # utility entrypoints
├── ops/                               # systemd/docker/monitoring
├── notebooks/                         # exploratory only; no production logic
├── data/                              # ignored local mount/symlink only
└── implementor-errors.md              # create only if useful
```

Canonical names:

```text
AGENTS.md
README.md
config/config.example.yaml
docs/agent-guidebook.md
docs/reference/schemas.md
docs/reference/data-layout.md
docs/reference/providers/<provider>.md
docs/operations/change-log.md
docs/operations/implementation-status.md
src/market_recorder/
```

Use `snake_case` for Python modules and `kebab-case` for Markdown docs. Avoid duplicate docs for the same purpose. `docs/agent-guidebook.md` is the primary agent-facing implementation reference; do not keep parallel files like `project-reference-guide.md` or `docs/reference/market-data-recorder.md` unless they clearly redirect to it.

---

## 2) Canonical Docs and Maintenance

Agents must keep these documents consistent:

* `README.md` — human-facing overview, setup, quick start, normal operation.
* `docs/agent-guidebook.md` — primary implementation guide for agents: sources, APIs, streams, storage, schemas, rate limits, architecture definitions, caveats, and operational assumptions. Maintain it whenever project decisions or observed behavior drift from current definitions.
* `docs/reference/schemas.md` — focused schema reference for raw envelopes, normalized tables, feature tables, labels, replay data, and backtest results.
* `docs/reference/data-layout.md` — filesystem/data-lake layout.
* `docs/reference/providers/*.md` — provider-specific details.
* `config/config.example.yaml` — safe documented runtime config example.
* `docs/operations/change-log.md` — durable commit-style log of repo changes, short descriptions, and commit refs.
* `docs/operations/implementation-status.md` — continuously maintained feature/status map with major concepts, subgroups, current status, extension notes, and relevant commit refs.
* `docs/decisions/*.md` — durable decisions, migrations, and behavior changes when useful.
* `docs/phases/*.md` — optional user-scoped phase plans when a plan is complex enough to preserve.

If a task conflicts with docs, resolve the mismatch or report it clearly.

Treat intentional documentation drift as a required documentation update, not as a tolerated inconsistency. If a change would create substantial drift from the current docs and it is unclear whether that drift is intentional, stop and ask the user before continuing.

Agents must update relevant docs whenever:

* A new plan is created.
* A plan changes.
* Implementation behavior changes.
* Repo structure or code behavior differs from existing docs.
* API/source behavior is discovered to differ from current docs.
* Status, limitations, extension notes, or next steps change.

Before creating a new doc entry, check for an existing relevant entry and update it instead of duplicating it. Keep existing entries accurate, organized, and aligned with current repo status.

---

## 3) Core Invariants

These apply across all phases unless the user explicitly changes them.

### Preserve source truth

For external data and observed events:

* Preserve original provider payloads where practical.
* Add metadata rather than replacing source fields.
* Avoid lossy transformations in first-write paths.
* Do not discard unknown fields just because current code does not use them.
* Keep derived artifacts reproducible from stored source data.

### Keep layers separate

Maintain clear boundaries:

```text
raw/source data → normalized data → derived features → signals/labels/decisions → backtests/reports/actions
```

Do not collapse these layers into one opaque process unless explicitly scoped.

### Keep external sources independent

Do not blend or synthesize market prices during ingest unless explicitly requested. Store source streams separately and align them later by timestamp.

### Prefer reproducibility

Research/backtest outputs must be traceable to data sources, code version, config/parameters, symbols, date range, and execution assumptions.

### Use timestamp discipline

Use UTC everywhere. Preserve source event timestamps and record local receive timestamps for live ingest. Prefer storing source time, local receive time, monotonic time, source/provider name, and connection/run ID.

### No hidden live trading

No code may place trades, modify orders, manage positions, use private keys, or call live trading endpoints unless explicitly scoped and safety-confirmed by the user. Data, alerts, research, and execution must remain clearly separated.

---

## 4) Roles and Workflow

### Co-Engineer Agent

Plan with the user, decompose work, identify tradeoffs, and preserve repo-wide invariants. Do not invent facts, APIs, constraints, or requirements. If a real decision blocks progress, present 2–3 concrete options with tradeoffs. Use Context7 first when planning or evaluating a library, framework, SDK, or API surface for the first time in a task.

### Implementor Agent

Make scoped code/config/doc changes. Keep scope tight, follow repo rules, avoid unrelated cleanup, run checks, and report changed files plus validation. Use Context7 first before coding against a library, framework, SDK, or API surface that has not yet been researched in the current task.

### Reviewer Agent

Check whether the change satisfies the scoped task, preserves data/reproducibility, keeps layer boundaries clear, avoids trading/credential risk, remains future-compatible, and updates docs/tests/config appropriately.

### Standard workflow

1. Inspect repo state and relevant docs/configs.
2. Check existing docs for relevant entries before creating new ones.
3. Identify the smallest safe change.
4. Implement the scoped task.
5. Run appropriate validation.
6. Stage implementation changes into organized, separate commits by purpose.
7. Commit implementation changes once code/config edits for that scope are complete and validated.
8. Update all relevant docs for plan, design, implementation, status, behavior, and operational tracking changes.
9. Commit documentation updates separately from implementation commits.
10. Report summary, files changed, validation, docs updated, risks, and commit hashes.

For larger work, complete one chunk at a time. Retry a failing chunk at most 3 times unless the user says otherwise. If useful, document repeated failures in `implementor-errors.md`.

### Context7-First Library Research

When a task involves code-related decisions or implementation that depends on a library, framework, SDK, or documented API surface, agents must use Context7 as the default first documentation source the first time that dependency is encountered in the current task.

Rules:

* Query Context7 before making design decisions or writing code against that dependency.
* Later encounters in the same task may skip a repeat query if the needed guidance is still available in current memory/context.
* Re-query when version assumptions change, the task expands to a new API surface, or the earlier docs did not answer the current question.
* Determine the version from repo config, lockfiles, or existing code when possible. If the version is unknown, explicitly treat it as unspecified and prefer the most relevant current major-version docs.
* Fall back to web search, official docs, or direct provider documentation only when Context7 coverage is missing, insufficient, or failing.

How to query Context7 correctly:

1. Identify the exact library name and any relevant version, runtime, framework, or platform constraints.
2. Call `resolve-library-id` first using the library name and the full task-specific question. If the user already supplied a Context7 library ID in the form `/org/project` or `/org/project/version`, you may skip the resolve step.
3. Choose the best match by preferring an exact official package or project match, then a version-specific ID when the version is known.
4. Call `query-docs` with the selected library ID and a focused question about the actual code change, setup step, or API behavior you need.
5. Reuse the fetched guidance while it remains in working context, but issue a fresh query when later work depends on different APIs, changed versions, or unanswered details.

Query quality guidance:

* Prefer task-specific questions over short keywords.
* Include the actual goal, environment, and relevant API names in the query.
* Prefer official or primary packages over wrappers, forks, or community mirrors when multiple matches exist.
* Use version-specific IDs when available to reduce drift.

---

## 5) Architecture Rules

* Build for later phases without premature complexity.
* Keep modules focused and responsibilities clear.
* Keep provider-specific behavior inside source adapters or isolated modules.
* Use deterministic, documented data paths.
* Prefer configuration over hard-coded symbols, feed IDs, stream names, storage roots, retention settings, and job parameters.
* Do not introduce heavy infrastructure before the simpler layer works.
* Notebooks are exploratory only; production logic belongs in `src/`, `scripts/`, or `ops/`.

Good patterns:

```text
config-driven sources
append-only raw storage
reproducible jobs
clear ingest/normalize/feature/backtest interfaces
documented schemas and assumptions
```

Bad patterns:

```text
one-off hard-coded paths
mixing live ingest with analysis/backtest logic
silent data mutation
provider assumptions scattered across modules
data deletion without explicit retention policy
```

---

## 6) Data Handling Rules

### Raw/source data

Raw data should be append-only, timestamped, source-labeled, reconstructable, and separate from derived data. Do not implement destructive cleanup unless the task explicitly requests a retention policy.

### Normalized data

Normalized data must be reproducible from raw data, use documented schemas, preserve units/timestamp semantics, and include enough provenance to trace back to source records.

### Features

Feature code must avoid lookahead bias, document windowing/alignment rules, preserve parameter/config provenance, be deterministic for a given input/config, and keep labels/targets separate from features.

### Backtests/replay

Backtests must state assumptions, avoid future leakage, model fees/slippage/fill rules intentionally, record run metadata, produce repeatable outputs, and separate strategy logic from execution simulation.

### ML datasets

ML dataset creation must preserve temporal splits, avoid leakage, store feature/label definitions, record data/code versions, and make missing-data/class-imbalance handling explicit.

---

## 7) API and External Source Discipline

External APIs change. When adding or changing integrations:

* Prefer official docs and observed responses over assumptions.
* Respect rate limits and document them when relevant.
* Use retries/backoff for network integrations.
* Preserve raw responses when practical.
* Treat undocumented behavior as provisional.
* Keep endpoints, stream names, and source mappings configurable where feasible.
* Update the relevant provider/reference docs with URLs, endpoints/streams, limits, payload fields relied on, caveats, and validation performed.

---

## 8) Safety and Credentials

Never commit API keys, wallet/private keys, session tokens, real webhook secrets, or `.env` files with secrets. Use environment variables, ignored local config, or secret managers.

Do not log secrets. Be careful with authenticated account payloads if private streams are added later.

Any live-execution functionality must be isolated, explicitly enabled, and scoped by the user. Default behavior is data/research only.

Do not write docs or UI text implying guaranteed profit, guaranteed signal accuracy, or risk-free leverage. Backtests are historical simulations dependent on assumptions.

---

## 9) Testing and Validation

Validation must match the task. Use available tooling such as:

```text
python -m compileall ...
pytest
ruff
mypy
unit tests
integration smoke tests
sample data validation
```

If tooling is not configured, use lightweight checks appropriate to the change. Do not add a heavy toolchain without a clear reason.

Validation expectations:

* Source/recorder changes: verify connection, event writing, readable/decompressible outputs, valid sample records, required metadata, reconnect behavior, and reasonable rate-limit behavior.
* Normalization/feature changes: verify schema, counts, timestamp ordering/alignment, units, missing-data handling, and deterministic reruns.
* Backtest changes: verify no lookahead leakage, reproducible entry/exit logic, visible fee/slippage assumptions, edge cases, and run metadata.

Do not rely on “it runs.” Inspect representative outputs.

---

## 10) Documentation and Operational Tracking

When plans, design, implementation, behavior, status, or repo structure change, update the relevant docs in the same task.

Documentation rules:

* Check for existing entries before creating new entries.
* Update existing entries instead of duplicating them.
* Keep docs organized and consistent with current repo status.
* Reflect design, plan, and implementation changes in every relevant doc.
* If code behavior and docs disagree, either fix the docs, fix the code, or report the discrepancy clearly.

Update docs when changing public commands, config keys, storage layout, schemas, APIs/streams, rate-limit assumptions, source mappings, validation commands, backtest assumptions, implementation plans, feature status, extension notes, or runtime behavior.

Operational tracking docs are required for repo changes:

* `docs/operations/change-log.md` must receive a short durable entry describing the code and documentation changes plus the relevant code/doc commit refs once those commits exist.
* `docs/operations/implementation-status.md` must be updated when a change affects a feature, subsystem, status, known limitation, extension point, or planned next step.
* Commit completed implementation changes first.
* Then update the relevant docs other than `docs/operations/change-log.md`, including `docs/operations/implementation-status.md` when needed, and commit those documentation changes separately.
* Then update `docs/operations/change-log.md` with the relevant implementation/doc commit refs and commit the changelog change separately.
* A standalone changelog-only follow-up commit does not need its own changelog entry or self-reference. The same rule applies when only `docs/operations/change-log.md` changed and no earlier code/doc commits were created for that task.

Before final response, reconcile relevant docs:

```text
README.md
docs/agent-guidebook.md
docs/reference/*.md
docs/operations/change-log.md
docs/operations/implementation-status.md
docs/phases/*.md when phase plans changed
docs/decisions/*.md when durable decisions changed
config/config.example.yaml
AGENTS.md if repo-wide rules changed
```

Do not leave contradictory docs.

### `docs/operations/change-log.md`

Purpose: durable, concise, commit-style repo history for future agents.

Use newest-first entries:

```markdown
## YYYY-MM-DD

- `<commit>` — short summary. Optional second sentence for why it mattered.
```

For implementation work followed by documentation work, prefer entries that reference both when useful:

```markdown
## YYYY-MM-DD

- `<impl_commit>` / `<docs_commit>` — added raw Aster stream capture and documented source/status updates.
```

For docs-only work, reference the documentation commit:

```markdown
## YYYY-MM-DD

- `<docs_commit>` — updated repo workflow instructions for changelog sequencing.
```

If the only remaining commit for a task edits `docs/operations/change-log.md`, do not add a second self-referential entry for that changelog-only commit.

Keep entries short. This is not a full narrative and not a replacement for Git history.

### `docs/operations/implementation-status.md`

Purpose: continuously updated feature/status map for fast orientation.

Organize by major project concepts as root sections, then smaller subgroups. Each feature/subsystem entry should include:

```markdown
### Feature or subsystem name

Status: planned | in-progress | implemented | blocked | deprecated

Description: One or two sentences.

Notes: Future extension notes, caveats, known limitations, or integration assumptions.

Refs: commit refs, relevant docs, or issue/decision links.
```

Keep entries concise. This file should tell a future agent what exists, what is incomplete, what matters next, and where the relevant commits/docs are.

---

## 11) Commit Hygiene

If a task changes code, config, docs, tests, or migrations, it should end with commits unless the user explicitly says not to.

Commit sequence:

1. Stage implementation changes into organized, purpose-specific commits.
2. Commit implementation changes after code/config edits are complete and validated.
3. Update relevant docs other than `docs/operations/change-log.md`, including `docs/operations/implementation-status.md` when needed, with references to the implementation commit(s).
4. Commit the documentation updates separately.
5. Update `docs/operations/change-log.md` with the relevant implementation/doc commit refs.
6. Commit the changelog update separately.

For docs-only tasks, start at step 3 with the non-changelog docs, then commit the changelog update last. If a task only changes `docs/operations/change-log.md`, commit it directly without adding a self-referential changelog entry.

Use Conventional Commits:

```text
feat(recorder): add raw Aster stream capture
feat(storage): add hourly compressed writer
fix(pyth): reconnect after stream close
docs: update source reference guide
test(writer): cover hourly rotation
chore(deps): add zstandard dependency
```

Rules:

* Keep commits small and single-purpose.
* Separate implementation commits from documentation-only commits.
* Use imperative subject lines under 72 chars, no trailing period.
* Add a body for invariants, migrations, or tradeoffs.
* Do not mix formatting-only changes with functional changes.
* Do not commit unrelated cleanup.
* Aim for green commits.
* Do not rewrite shared history unless explicitly instructed.

---

## 12) Change Discipline

Before editing, understand the relevant module/docs, check existing patterns, identify the smallest safe change, and preserve unrelated workspace changes.

Do not reformat unrelated files, rename large structures casually, introduce global patterns without reason, revert unrelated user work, add broad abstractions for a single immediate use case, or hide behavior changes in refactors.

If observed behavior conflicts with docs, fix the code/docs mismatch or report it clearly.

---

## 13) Dependency Policy

Add dependencies cautiously. A new dependency needs a clear purpose, a reason current dependencies/stdlib are insufficient, updated requirements/lock files, updated setup docs, and validation.

Ask before adding heavy infrastructure or large frameworks unless the task explicitly calls for them, including:

```text
Kafka/Redpanda
ClickHouse/QuestDB/Timescale
Ray/Dask
PyTorch/TensorFlow
large exchange-framework libraries
large observability stacks
```

---

## 14) Operational Discipline

For long-running services:

* Use explicit service configuration.
* Log startup configuration safely.
* Expose or record health status where useful.
* Reconnect on transient failures.
* Fail loudly on invalid config.
* Avoid unbounded memory growth and unbounded queues.
* Flush/close files cleanly on shutdown.

For jobs/pipelines:

* Make inputs/outputs explicit.
* Make runs repeatable.
* Record run metadata.
* Avoid overwriting prior outputs unless configured.

---

## 15) Completion Report

Before reporting completion, confirm relevant docs plus `docs/operations/change-log.md` and `docs/operations/implementation-status.md` were updated and committed separately from implementation changes when implementation changes were made.

When finishing work, report:

```text
Summary
Files changed
Validation performed
Implementation commit(s)
Documentation commit(s)
Changelog commit(s)
Docs updated
Operational tracking docs updated
Assumptions or API behavior discovered
Known risks / follow-ups
```

For data/recorder/pipeline work, include sample evidence when practical: output path, record count, validation command, sources confirmed, and schemas checked.

---

## 16) Compatibility Checklist

Before finishing a phase-scoped task, verify:

* Source truth is preserved where applicable.
* Later phases can reproduce or audit outputs.
* Source, normalized, feature, and decision layers remain separate.
* Config is flexible enough for related future symbols/sources/timeframes.
* No hidden live-trading side effects were introduced.
* Timestamps, units, assumptions, and provenance are clear.
* Relevant docs, example configs, plans, and operational tracking docs are updated.
* Existing docs were checked before new entries were created.
* Docs remain organized and consistent with current repo status.
* Implementation, documentation, and changelog commits are separated where applicable.
* Outputs are deterministic/re-runnable where appropriate.
* The change fits canonical structure and naming conventions.

If not, fix it or call it out explicitly.
