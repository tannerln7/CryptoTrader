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

Description: The repo now has canonical per-stream raw-path generation, a streaming Zstandard JSONL writer with active/sealed segment lifecycle, route-resolved age and size rotation, and sealed-file validation utilities.

Notes: Writers now own active `.jsonl.zst.open` files and atomically seal them into `.jsonl.zst` files on time or size rotation and on clean close. Active segments are chmodded `0600` while open, and sealed segments are chmodded `0640` so operator-group read access never implies write access to raw data. The route layout stays `raw/<source>/<transport>/<source_symbol>/<stream>/date=YYYY-MM-DD/hour=HH/...`; only the segment filename, lifecycle, and final permission model changed. `segment_start_utc` is the bucket start used for partitioning and active naming, `segment_end_utc` is the actual seal time used in sealed naming, and record-content timing remains available via `first_record_ts_recv_utc` and `last_record_ts_recv_utc` in writer seal metadata. The parsed `manual_rotation` config is reserved for a future service-owned checkpoint flow and is not yet exposed as an operator command.

Refs: `e8c159b`; `3bc71a4`; `0c3d0e6`; `docs/phases/raw-recorder/phase2.md`; `docs/reference/data-layout.md`; `config/config.example.yaml`; `src/market_recorder/storage/writer.py`; `src/market_recorder/storage/validate.py`

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

Status: implemented

Description: The repo now has an unattended service runner, a runtime health-manifest writer, and a route-aware raw data quality report for the enabled sources.

Notes: The current implementation keeps hardening lightweight: `run-service` supervises the enabled components, writes `manifests/runtime/health-<run_id>.json`, and `report-data-quality` validates the newest sealed raw file per expected route while treating `forceOrder` and TradingView alerts as optional event-driven paths. Active `.open` segments are now reported separately as `incomplete-active` or `stale-active` candidates and are not treated as valid sealed data by default.

Refs: `20b70dd`; `0c3d0e6`; `docs/phases/raw-recorder/phase7.md`; `docs/operations/deployment.md`; `docs/operations/monitoring.md`; `src/market_recorder/service.py`; `src/market_recorder/quality.py`

### Checkout-mode developer wrappers

Status: implemented

Description: The repo now ships explicit checkout-mode helper scripts that force source-first development commands to run against the current checkout instead of an installed wheel.

Notes: `scripts/dev/env.sh` exports `MARKET_RECORDER_LAYOUT=checkout`, pins `MARKET_RECORDER_REPO_ROOT` to the checkout root, unsets the installed app-root override, and prepends `src/` to `PYTHONPATH`. `scripts/dev/market-recorder` wraps the repo-local `.venv` interpreter with that environment so `validate-config` and other CLI commands work from any working directory.

Refs: `7b56d9f`; `scripts/dev/env.sh`; `scripts/dev/market-recorder`; `scripts/README.md`

### Recorder service control surface

Status: implemented

Description: The `market-recorder` CLI now defaults to service status and controls an installed systemd unit through a service-owned Unix socket with `start`, `stop`, `restart`, `status`, and `health` commands.

Notes: Fresh installs now default to the `production` instance and place the installer-managed app under `/opt/CryptoTrader`, the operator launcher under `/usr/local/bin/market-recorder`, and live instance config under `/etc/CryptoTrader/<instance>.yaml`, `/etc/CryptoTrader/<instance>.sources.yaml`, and `/etc/CryptoTrader/<instance>.env`. Re-running the installer preserves existing instance files and writes updated defaults to adjacent `.new` files when templates change. The running service owns `/run/market-recorder/<instance>/control.sock`, answers only `ping`, `status`, `health`, and `stop`, and marks systemd readiness through direct `NOTIFY_SOCKET` writes only after the socket and health surface are ready. `run-service` remains the development and debugging foreground path, while checkout-mode CLI usage is explicit through `scripts/dev`.

Refs: `7b56d9f`; `0c7b256`; `e8c159b`; `docs/operations/deployment.md`; `docs/operations/monitoring.md`; `README.md`; `src/market_recorder/cli.py`; `src/market_recorder/service_control.py`; `ops/systemd/market-recorder@.service`

### Install and service verification

Status: implemented

Description: A focused install and service-control verification on 2026-04-30 covered fresh-machine install paths, `validate-config`, `write-sample`, `validate-raw` rejection of active `.jsonl.zst.open` segments, `systemd-analyze verify` of the shipped unit template, and a 3-minute bounded live `start`/`status`/`health`/`stop` cycle against a `/tmp` data root.

Notes: The live cycle finished with all enabled components reporting `running` throughout, all active segments sealed on graceful stop (`KillSignal=SIGTERM` semantics), and `report-data-quality --stale-after-seconds 600` reporting 19 OK routes with only the activity-driven `forceOrder` routes optional-missing. A follow-up config-loader fix now makes non-editable `python -m pip install .` installs resolve `market-recorder validate-config`, repo-relative sources configs, and explicit repo-local config paths against the runtime repo root instead of the installed package location under `.venv`. The current installed layout now centers the operator workflow on `/opt/CryptoTrader`, `/etc/CryptoTrader`, `/usr/local/bin/market-recorder`, and fresh installs only, with checkout-mode validation handled separately through `scripts/dev`.

Refs: `7b56d9f`; `2dda61c`; `e8c159b`; `docs/operations/deployment.md`; `docs/operations/monitoring.md`; `README.md`; `src/market_recorder/config.py`; `tests/unit/test_config.py`; `src/market_recorder/service_control.py`; `tests/unit/test_service_control.py`

### Phase 8 — Stability run and normalization handoff

Status: in-progress

Description: Bounded stability evidence, stale-note cleanup, and a normalization handoff note are now in place before downstream normalization work begins.

Notes: A 180-second bounded soak run on 2026-04-30 completed with `pyth`, `aster.market`, and `aster.depth` all reporting `completed`, and the follow-up route-quality report showed 19 OK routes, 0 missing routes, 0 stale routes, and 0 invalid routes, with only the activity-driven `forceOrder` routes marked optional-missing. The remaining gap is the longer 24-to-48 hour soak target documented in the normalization handoff note.

Refs: `13b3a6c`; `docs/phases/raw-recorder/phase8.md`; `docs/decisions/raw-recorder-normalization-handoff.md`