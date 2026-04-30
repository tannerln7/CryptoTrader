# Implementation Status

This file is the repository's current feature and subsystem map for agents and maintainers.

Use it to show what exists, what is planned, what is in progress, what is blocked, and what future work should treat as the current intended state. This file is not a changelog; it should describe the latest status of the repo rather than narrating every edit.

## How To Maintain

* Organize entries by major project concept or subsystem.
* Keep each entry concise and update it in place rather than appending contradictory notes.
* Use the status labels `planned`, `in-progress`, `implemented`, `blocked`, or `deprecated`.
* Each entry should include `Status`, `Description`, `Notes`, and `Refs`.
* Use commit refs once Git history exists. Before Git is initialized, use a temporary marker such as `pre-git`.
* Reflect intentional implementation or planning drift here when it changes the current expected state of the repo.

## Entry Template

```md
### Feature or subsystem name

Status: planned | in-progress | implemented | blocked | deprecated

Description: One or two sentences.

Notes: Future extension notes, caveats, known limitations, or integration assumptions.

Refs: commit refs, relevant docs, or issue/decision links.
```

## Repository Bootstrap

### Repository scaffold

Status: implemented

Description: The baseline scaffold now exists, including `README.md`, `pyproject.toml`, example config, a `src/market_recorder` package skeleton, a repo-local `.venv` interpreter convention, and unit smoke coverage.

Notes: Treat `pyproject.toml` as the source of truth for package metadata and tool configuration. Future work should extend the scaffold without changing canonical top-level layout unless the user explicitly re-scopes the repo.

Refs: `4a88c06`; `AGENTS.md`; `docs/phases/raw-recorder/phase0.md`

### Agent research policy

Status: implemented

Description: The repo now requires Context7-first library and API research for code-related decisions and implementation whenever a dependency is encountered for the first time in a task.

Notes: Agents should resolve the library ID first, prefer exact official and version-specific matches, and then query docs with a focused task-specific question. Later encounters in the same task may reuse in-context guidance until scope or version assumptions change.

Refs: `4a88c06`; `AGENTS.md`

## Raw Recorder Program

### Detailed raw-recorder phase plan set

Status: implemented

Description: The program-level raw-recorder plan now has a detailed execution sequence under `docs/phases/raw-recorder/phase0.md` through `phase8.md`.

Notes: The refined sequence separates runtime-contract scaffolding from storage implementation, splits Pyth capture from Aster market-stream capture, and isolates Aster depth/snapshot work because official depth-recovery rules require dedicated validation.

Refs: `4a88c06`; `docs/phases/raw-recorder/raw-recorder.md`; `docs/phases/raw-recorder/phase0.md`

### Phase 0 — Repository baseline and execution scaffold

Status: implemented

Description: The canonical repo scaffold, local interpreter convention, example config files, package placeholders, minimal CLI, and smoke-test baseline now exist.

Notes: Phase 1 should build on these placeholders rather than relocating modules or reintroducing ambiguity around config, package layout, or interpreter selection.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase0.md`

### Phase 1 — Runtime contracts and recorder skeleton

Status: planned

Description: Source-agnostic recorder foundations such as config loading, timestamp utilities, path generation, runtime contracts, and recorder orchestration are planned but not yet implemented.

Notes: Keep this phase lightweight and reusable across providers.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase1.md`

### Phase 2 — Storage, rotation, and raw validation foundations

Status: planned

Description: Raw file writing, rotation, compression, manifest handling, and validation tooling are planned before live source capture begins.

Notes: Preserve append-only raw storage semantics and keep validation representative and deterministic.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase2.md`

### Phase 3 — Pyth reference stream capture

Status: planned

Description: Pyth Hermes reference-price capture is planned as the first live raw stream integration.

Notes: Preserve source payloads, provider timing metadata, and feed-level config without blending reference prices into exchange streams.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase3.md`; `docs/reference/providers/pyth.md`

### Phase 4 — Aster market stream capture

Status: planned

Description: Aster trade, ticker, mark-price, liquidation, and baseline market stream capture is planned after the recorder core and storage layers exist.

Notes: Source integrations should remain config-driven, connection-aware, and independent at ingest.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase4.md`; `docs/reference/providers/aster.md`

### Phase 5 — Aster snapshots and depth capture

Status: planned

Description: Aster REST depth snapshots and validated L2 stream capture are planned to support later book reconstruction and microstructure analysis.

Notes: Preserve reconstruction-relevant update IDs and raw payloads without rebuilding books in the ingest path.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase5.md`; `docs/reference/providers/aster.md`

### Phase 6 — TradingView alert and label capture

Status: planned

Description: TradingView or similar alert events are planned as raw label streams that can later be joined with market data.

Notes: Keep alert payloads structured, authenticated where appropriate, and preserved as raw events.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase6.md`; `docs/reference/providers/tradingview.md`

### Phase 7 — Operational hardening and unattended runtime

Status: planned

Description: Service management, health visibility, reconnect resilience, and data-quality checks are planned after the raw capture path is functional.

Notes: Favor lightweight observability and clear operator signals before adding heavier infrastructure.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase7.md`

### Phase 8 — Stability run and normalization handoff

Status: planned

Description: A stabilization and handoff phase is planned before normalization work begins.

Notes: This phase should confirm source behavior, storage growth, validation results, and known limitations.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase8.md`