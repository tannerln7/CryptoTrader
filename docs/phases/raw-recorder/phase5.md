# Phase 5 — Aster Snapshots and Depth Capture

## Overview

This phase adds the Aster snapshot and depth feeds needed for later order-book reconstruction and microstructure analysis.

It is deliberately isolated because the official depth-recovery rules introduce stronger correctness requirements than the other Aster streams.

## Role In Sequence

This phase extends Aster capture from “market stream recording” to “reconstruction-capable raw capture.” It should only begin once the non-depth Aster path is stable.

## Objectives

* Capture REST depth snapshots for BTCUSDT and ETHUSDT on a configured cadence.
* Capture and validate partial-depth and diff-depth streams.
* Preserve the update identifiers and ordering context needed for later reconstruction.
* Record enough metadata to diagnose gaps and restart conditions.

## In Scope

* REST depth snapshots.
* Partial-depth streams such as `depth20@100ms` or the confirmed working equivalent.
* Diff-depth streams such as `depth@100ms` or the confirmed working equivalent.
* Continuity and sequence validation sufficient to support later reconstruction.
* Provider-doc updates when observed behavior differs from prior assumptions.

## Out Of Scope

* Live order-book reconstruction.
* L2-derived features.
* Retention policies.
* Strategy logic.

## Definitive Ending Spot

At the end of this phase, the recorder captures Aster snapshots and depth updates in a way that makes later book reconstruction possible without forcing reconstruction into the ingest path.

## Required Validation

* Confirm snapshot capture writes raw REST snapshot files under canonical paths.
* Confirm partial-depth and diff-depth stream names work in practice and are documented.
* Confirm raw records preserve `lastUpdateId`, `U`, `u`, `pu`, and bid/ask payload fields where provided.
* Confirm continuity checks can detect when depth recovery would need to restart from a fresh snapshot.
* Confirm sample snapshot and depth files decompress and validate.

## Satisfactory Completion Criteria

* The raw dataset contains the information needed for later local order-book reconstruction.
* Depth capture is operationally separate from reconstruction logic.
* Provider assumptions are updated to match observed current behavior.

## Notes

* Current official Aster docs document explicit order-book recovery rules: buffer depth events, fetch a snapshot, ensure the bridging event satisfies `U <= lastUpdateId <= u`, and restart when `pu` continuity fails.
* The latest official Aster docs currently show market-data and depth examples under `/fapi/v1/...`; this should be rechecked against live behavior and the provider reference during implementation.
* Treat depth stream naming as something to confirm with current docs and live capture rather than assuming older endpoint variants are still correct.

## Docs To Keep In Sync

* `docs/reference/providers/aster.md`
* `docs/reference/data-layout.md`
* `config/config.example.yaml`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
