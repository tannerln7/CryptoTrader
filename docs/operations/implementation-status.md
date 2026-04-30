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

Status: in-progress

Description: The repo is intentionally in a docs-first bootstrap state. Core implementation scaffolding such as `README.md`, `config/`, `src/`, `tests/`, and supporting project metadata has not yet been created.

Notes: The next implementation step is Phase 0 scaffolding. Remove temporary bootstrap notes from the guidebook and raw-recorder plan once the baseline scaffold exists.

Refs: `pre-git`; `AGENTS.md`; `docs/agent-guidebook.md`; `docs/phases/raw-recorder/raw-recorder.md`

### Agent research policy

Status: implemented

Description: The repo now requires Context7-first library and API research for code-related decisions and implementation whenever a dependency is encountered for the first time in a task.

Notes: Agents should resolve the library ID first, prefer exact official and version-specific matches, and then query docs with a focused task-specific question. Later encounters in the same task may reuse in-context guidance until scope or version assumptions change.

Refs: `pre-git`; `AGENTS.md`

## Raw Recorder Program

### Detailed raw-recorder phase plan set

Status: implemented

Description: The program-level raw-recorder plan now has a detailed execution sequence under `docs/phases/raw-recorder/phase0.md` through `phase8.md`.

Notes: The refined sequence separates runtime-contract scaffolding from storage implementation, splits Pyth capture from Aster market-stream capture, and isolates Aster depth/snapshot work because official depth-recovery rules require dedicated validation.

Refs: `pre-git`; `docs/phases/raw-recorder/raw-recorder.md`; `docs/phases/raw-recorder/phase0.md`

### R0 — Repository and documentation baseline

Status: in-progress

Description: Canonical documentation paths, planning references, and operations tracking scaffolds now exist. The repo still needs its initial config, source, test, and package scaffolding.

Notes: Future R0 work should preserve the canonical `docs/reference/`, `docs/operations/`, and `src/market_recorder/` structure.

Refs: `pre-git`; `docs/phases/raw-recorder/raw-recorder.md`

### R1 — Core raw recorder foundation

Status: planned

Description: Source-agnostic recorder foundations such as config loading, timestamp utilities, path generation, raw writing, CLI entrypoints, and validation tooling are planned but not yet implemented.

Notes: Keep this phase lightweight and reusable across providers.

Refs: `pre-git`; `docs/phases/raw-recorder/raw-recorder.md`

### R2 — Primary source capture

Status: planned

Description: Pyth Hermes and Aster live market streams are intended to be the first live raw capture targets once the shared recorder foundation exists.

Notes: Source integrations should remain config-driven and independent at ingest.

Refs: `pre-git`; `docs/phases/raw-recorder/raw-recorder.md`; `docs/reference/providers/pyth.md`; `docs/reference/providers/aster.md`

### R3 — Snapshot and L2 capture

Status: planned

Description: Aster REST depth snapshots and validated L2 stream capture are planned to support later book reconstruction and microstructure analysis.

Notes: Preserve reconstruction-relevant update IDs and raw payloads without rebuilding books in the ingest path.

Refs: `pre-git`; `docs/phases/raw-recorder/raw-recorder.md`; `docs/reference/providers/aster.md`

### R4 — Alert and event capture

Status: planned

Description: TradingView or similar alert events are planned as raw label streams that can later be joined with market data.

Notes: Keep alert payloads structured and preserve them as raw events.

Refs: `pre-git`; `docs/phases/raw-recorder/raw-recorder.md`; `docs/reference/providers/tradingview.md`

### R5 — Operational hardening

Status: planned

Description: Service management, health visibility, and data-quality checks are planned after the raw capture path is functional.

Notes: Favor lightweight observability and clear operator signals before adding heavier infrastructure.

Refs: `pre-git`; `docs/phases/raw-recorder/raw-recorder.md`

### R6 — Raw recorder freeze and handoff

Status: planned

Description: A stabilization and handoff phase is planned before normalization work begins.

Notes: This phase should confirm source behavior, storage growth, validation results, and known limitations.

Refs: `pre-git`; `docs/phases/raw-recorder/raw-recorder.md`