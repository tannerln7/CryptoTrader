# Phase 3 — Pyth Reference Stream Capture

## Overview

This phase adds the first live external source by recording Pyth Hermes BTC/USD and ETH/USD price updates as raw reference data.

Pyth is intentionally isolated first because its transport and payload model are narrower than Aster market streams and it is a clean way to validate the recorder's live ingest path.

## Role In Sequence

This is the first live-capture phase. It should prove that the recorder can maintain a long-lived external stream, preserve raw payloads, and reconnect safely without yet taking on the broader Aster surface.

## Objectives

* Record BTC/USD and ETH/USD updates from the Hermes streaming endpoint.
* Preserve Hermes payloads faithfully inside the raw envelope.
* Handle normal long-lived-stream disconnect behavior.
* Keep Pyth isolated from all other sources at ingest.

## In Scope

* Pyth feed ID configuration.
* SSE/streaming HTTP connection management.
* Local receive timestamps and connection identifiers.
* Reconnect behavior and error capture.
* Raw output validation for live Pyth files.

## Out Of Scope

* Price decoding into normalized tables.
* Historical benchmark backfill.
* Aster or TradingView capture.
* Cross-source joins.

## Definitive Ending Spot

At the end of this phase, the recorder can continuously capture live Pyth BTC/USD and ETH/USD updates into canonical raw files and recover from expected stream closures.

## Required Validation

* Confirm the Hermes stream opens and emits updates for the configured feeds.
* Confirm raw files are written under the expected Pyth path layout.
* Confirm sample records preserve the source payload and required envelope fields.
* Confirm reconnect behavior after an intentional disconnect or stream close.
* Confirm no source-specific normalization or synthesis is happening in the ingest path.

## Satisfactory Completion Criteria

* Live Pyth capture works without redesigning the storage or lifecycle foundations.
* The phase produces usable raw files for later normalization work.
* Normal reconnect behavior is treated as expected rather than exceptional.

## Notes

* Current Pyth docs confirm that `/v2/updates/price/stream` is the SSE endpoint for live price updates.
* Current Pyth docs also state the streaming connection closes automatically after 24 hours, so reconnection is a required baseline behavior rather than an optional hardening feature.
* Prefer using a maintained streaming HTTP client directly and reusing application-managed sessions rather than depending on an outdated SSE helper by default.

## Docs To Keep In Sync

* `docs/reference/providers/pyth.md`
* `config/config.example.yaml`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
