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

Status: implemented

Description: The repo now has typed runtime and source config loading, UTC and run-id helpers, raw-envelope helpers, logging setup, a CLI bootstrap path, and an aiohttp cleanup-context runtime container with a shared client session.

Notes: The current runtime skeleton intentionally stops before source transport and raw-file writing. Phase 2 should reuse the validated config and lifecycle surfaces instead of redefining them.

Refs: `242d9aa`; `docs/phases/raw-recorder/phase1.md`; `src/market_recorder/runtime.py`; `src/market_recorder/contracts.py`

### Phase 2 — Storage, rotation, and raw validation foundations

Status: implemented

Description: The repo now has canonical raw-path generation, a streaming Zstandard JSONL writer with hourly rotation, raw-file validation utilities, and CLI sample-write and validate-raw commands for local proof of output.

Notes: The storage layer currently targets append-only `part-<run_id>.jsonl.zst` files and validates records in a streaming fashion. Phase 3 should plug live Pyth events into this existing path instead of redesigning storage.

Refs: `3bc71a4`; `docs/phases/raw-recorder/phase2.md`; `src/market_recorder/storage/writer.py`; `src/market_recorder/storage/validate.py`

### Phase 3 — Pyth reference stream capture

Status: implemented

Description: The repo now has a live Pyth Hermes SSE adapter, bounded CLI capture command, reconnect-aware looping, and validated raw reference-event output under the canonical Pyth storage path.

Notes: The current implementation writes multi-feed raw envelopes under `raw/pyth/sse/MULTI/price_stream/...` and keeps Pyth isolated from all other source ingest paths.

Refs: `e0dce93`; `docs/phases/raw-recorder/phase3.md`; `docs/reference/providers/pyth.md`; `src/market_recorder/sources/pyth.py`

### Phase 4 — Aster market stream capture

Status: implemented

Description: The repo now has an Aster non-depth combined-stream adapter, bounded CLI capture command, config-driven stream-target construction, and validated raw output for live Aster market events.

Notes: Live validation confirmed that the symbol portion of stream names must be lowercase while suffixes like `aggTrade`, `bookTicker`, and `markPrice@1s` retain their documented case. `forceOrder` remains activity-dependent, so bounded live validation cannot guarantee an emitted liquidation event on every run.

Refs: `5874f41`; `docs/phases/raw-recorder/phase4.md`; `docs/reference/providers/aster.md`; `src/market_recorder/sources/aster.py`

### Phase 5 — Aster snapshots and depth capture

Status: implemented

Description: The repo now has periodic Aster REST depth snapshots, bounded partial-depth and diff-depth capture, and validated raw output for live Aster L2 inputs.

Notes: The current implementation preserves `lastUpdateId`, `U`, `u`, `pu`, bids, and asks in raw payloads, records REST snapshots on the configured cadence, and emits restart-required recorder errors when diff-depth `pu` continuity breaks. It intentionally stops short of local order-book reconstruction.

Refs: `2e0fe9f`; `docs/phases/raw-recorder/phase5.md`; `docs/reference/providers/aster.md`; `src/market_recorder/sources/aster_depth.py`

### Phase 6 — TradingView alert and label capture

Status: implemented

Description: The repo now has an aiohttp-based TradingView webhook receiver, a CLI command to serve it locally, and validated raw alert output for both JSON and plain-text webhook bodies.

Notes: The current implementation preserves valid JSON payloads as structured objects, preserves non-JSON payloads as plain text, writes canonical raw alert events quickly, and keeps the request path intentionally lightweight. Phase 7 should build on this runtime surface rather than moving alert capture into a separate stack.

Refs: `2eaf53a`; `docs/phases/raw-recorder/phase6.md`; `docs/reference/providers/tradingview.md`; `src/market_recorder/alerts/tradingview.py`

### Phase 7 — Operational hardening and unattended runtime

Status: planned

Description: Service management, health visibility, reconnect resilience, and data-quality checks are planned after the raw capture path is functional.

Notes: Favor lightweight observability and clear operator signals before adding heavier infrastructure. This is now the next implementation phase after the TradingView webhook receiver.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase7.md`

### Phase 8 — Stability run and normalization handoff

Status: planned

Description: A stabilization and handoff phase is planned before normalization work begins.

Notes: This phase should confirm source behavior, storage growth, validation results, and known limitations.

Refs: `4a88c06`; `docs/phases/raw-recorder/phase8.md`