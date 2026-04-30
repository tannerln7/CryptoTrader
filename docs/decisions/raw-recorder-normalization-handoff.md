# Raw Recorder Normalization Handoff

This document records what downstream normalization work can safely assume about the raw recorder as of 2026-04-30.

## Current State

Status: in-progress

The raw recorder architecture, contracts, and operator surfaces are now stable enough for normalization design and initial implementation.

A bounded stability run and representative multi-source raw validation have been completed. The longer 24-to-48 hour soak target from Phase 8 is still pending, so this handoff should be treated as architecture-stable but not yet fully closed operationally. Operator surfaces now include the service-first CLI control flow and a shipped systemd template that supervises the same foreground worker path.

## Bounded Stability Evidence

Recorded bounded soak run:

```text
run_id: recorder-20260430T152611Z-cf0ffa46
command: market-recorder run-service --duration-seconds 180 --health-interval-seconds 15
started: 2026-04-30T15:26:11.600507Z
finished: 2026-04-30T15:29:12.638365Z
health_manifest: data/manifests/runtime/health-recorder-20260430T152611Z-cf0ffa46.json
```

Observed component completion:

* `pyth` completed
* `aster.market` completed
* `aster.depth` completed

Observed output summary from that bounded soak:

* `pyth` latest output at `2026-04-30T15:29:11.930653Z`
* `aster.market` latest output at `2026-04-30T15:29:12.630652Z`
* `aster.depth` latest output at `2026-04-30T15:29:11.830653Z`

Route-quality evidence after the bounded soak:

```text
market-recorder report-data-quality --stale-after-seconds 600
Checked routes: 21
OK routes: 19
Missing routes: 0
Stale routes: 0
Invalid routes: 0
Optional-missing routes: BTCUSDT forceOrder, ETHUSDT forceOrder
```

Representative raw validation also succeeded for these files:

* `data/raw/pyth/sse/MULTI/price_stream/.../part-recorder-20260430T152611Z-cf0ffa46.jsonl.zst`
* `data/raw/aster/ws/BTCUSDT/bookTicker/.../part-recorder-20260430T152611Z-cf0ffa46.jsonl.zst`
* `data/raw/aster/rest/BTCUSDT/depth_snapshot_1000/.../part-recorder-20260430T152611Z-cf0ffa46.jsonl.zst`
* `data/raw/tradingview/webhook/ALL/alert/.../part-recorder-20260430T151136Z-5ae1698d.jsonl.zst`

## Normalization Can Assume

* Raw envelopes are stable at the current documented names: `raw.market_event.v1`, `raw.rest_snapshot.v1`, `raw.alert_event.v1`, `raw.recorder_error.v1`, and optional `raw.sse_line.v1`.
* Raw files follow the canonical layout under `raw/<source>/<transport>/<source_symbol>/<stream>/date=YYYY-MM-DD/hour=HH/part-<run_id>.jsonl.zst`.
* Filesystem path components are sanitized, while the raw envelope keeps the logical stream names. Example: `markPrice@1s` becomes `markPrice_1s` in the path, and `depth@100ms` becomes `depth_100ms`.
* Pyth is captured under `raw/pyth/sse/MULTI/price_stream/...`.
* Aster non-depth market streams are captured under `raw/aster/ws/<source_symbol>/<stream>/...`.
* Aster depth snapshots are captured under `raw/aster/rest/<source_symbol>/depth_snapshot_1000/...` with the current example config.
* Aster diff-depth and partial-depth streams preserve `U`, `u`, `pu`, bids, and asks in the raw payload.
* TradingView alerts, when enabled, are captured under `raw/tradingview/webhook/ALL/alert/...` and preserve both JSON and plain-text request bodies explicitly.
* `raw.recorder_error.v1` records are part of the raw layer and should be available to downstream quality and troubleshooting workflows.
* Runtime health manifests are written under `manifests/runtime/health-<run_id>.json` for unattended service runs.

## Normalization Must Not Assume

* Local order-book reconstruction has already happened in the ingest path. It has not.
* Every run contains event-driven streams such as `forceOrder` or TradingView alerts.
* TradingView is enabled by default in the example config. It is currently disabled by default.
* Every enabled route will appear in every bounded validation window.
* A 24-to-48 hour soak has already been completed. It has not.
* Provider payloads have already been normalized, unit-converted, or merged across sources.

## Immediate Guidance For Next Phase

* Build normalization readers against the current raw envelope fields and the sanitized filesystem layout.
* Treat `raw.recorder_error.v1` as diagnostics and quality metadata rather than as a market-data stream.
* For Aster depth normalization, use the preserved snapshots plus diff-depth payloads later; do not assume the ingest layer has already bridged snapshots to depth streams.
* Preserve provenance back to raw file path and record locator when building normalized tables.
* Keep source-specific normalization logic isolated rather than blending Pyth, Aster, and TradingView during ingest.

## Remaining Phase 8 Gap

The main remaining gap before calling the raw recorder fully closed is a longer soak run closer to the original 24-to-48 hour target.

That is now an evidence-gathering task, not an architecture task.
