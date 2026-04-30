# Phase 4 — Aster Market Stream Capture

## Overview

This phase adds the primary Aster market streams that do not require order-book reconstruction logic: trades, book ticker, mark price, liquidations, and reference klines.

Depth streams and REST snapshots are intentionally deferred to the next phase because they impose additional sequencing and continuity requirements.

## Role In Sequence

This phase proves the recorder can handle the broader Aster market-data surface without yet taking on the added correctness burden of depth recovery.

## Objectives

* Record the primary non-depth Aster streams for BTCUSDT and ETHUSDT.
* Use a connection strategy that respects Aster stream limits and connection behavior.
* Preserve the exact raw payloads and combined-stream wrappers needed for later debugging.
* Keep source routing and stream naming config-driven.

## In Scope

* Combined or raw WebSocket market-stream capture for:
* `aggTrade`
* `bookTicker`
* `markPrice@1s`
* `forceOrder`
* `kline_1m`
* `kline_5m`
* `kline_15m`
* Stream-name construction and symbol mapping.
* Reconnect behavior and basic health counters.
* Live raw-output validation.

## Out Of Scope

* REST snapshots.
* Partial-depth streams.
* Diff-depth capture.
* Local order-book reconstruction.
* TradingView alert ingest.

## Definitive Ending Spot

At the end of this phase, the recorder can continuously capture the selected non-depth Aster market streams for BTCUSDT and ETHUSDT into canonical raw files with stable reconnect behavior.

## Required Validation

* Confirm all configured non-depth streams connect and emit records.
* Confirm stream names are lowercase and match the official stream naming rules.
* Confirm raw files are produced for each configured stream and symbol.
* Confirm reconnect behavior works after a forced disconnect.
* Confirm message handling remains stable under expected live event rates.

## Satisfactory Completion Criteria

* The recorder captures the main Aster market streams without conflating them with depth logic.
* The configuration model supports future stream additions without redesign.
* The implementation leaves enough traceability to debug stream-specific failures later.

## Notes

* Current official Aster docs confirm that combined streams are available at `/stream?streams=...`, wrap each event as `{"stream": ..., "data": ...}`, require lowercase stream names, and are limited to 200 streams per connection.
* Current official Aster docs also document 24-hour connection lifetime and server ping/pong behavior, so reconnect logic is part of baseline source capture.
* Keep the initial stream set below any avoidable complexity threshold rather than trying to capture every available feed at once.

## Docs To Keep In Sync

* `docs/reference/providers/aster.md`
* `config/config.example.yaml`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
