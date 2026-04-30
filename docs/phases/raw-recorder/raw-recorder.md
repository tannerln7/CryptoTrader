# Raw Recorder Program Overview

This document is the high-level overview for the raw-recorder program.

Use it as the brief orientation map for what the raw recorder is meant to do, what it must not do, how the full effort is structured, and where to find the detailed phase references.

It is intentionally concise. Detailed phase execution guidance lives in the individual phase files in this directory.

---

## Purpose

The raw recorder is the first durable system layer for this repository.

Its job is to capture source market data and signal events accurately enough that future normalization, replay, backtesting, analysis, and ML work can depend on recorded source data instead of fragile live API access.

In short, the recorder should do this well:

```text
connect -> receive -> timestamp -> wrap -> write -> rotate -> reconnect -> validate
```

It should not calculate indicators, normalize away source fields, create synthetic blended prices, reconstruct full books in the ingest path, run backtests, or place trades.

---

## Source Coverage

The recorder program currently targets three source families:

* Pyth Hermes for BTC/USD and ETH/USD oracle and reference pricing.
* Aster futures APIs for BTCUSDT and ETHUSDT market data, depth snapshots, and order-book inputs.
* TradingView webhooks for alert and label events.

These sources must remain independent at ingest. Any alignment or synthesis happens later in derived layers.

---

## Core Rules

The full raw-recorder effort should preserve these high-level invariants:

* Preserve raw source truth whenever practical.
* Add metadata instead of replacing provider fields.
* Keep sources separate at ingest.
* Use UTC and record local receive timestamps.
* Prefer config-driven behavior over hard-coded symbols, endpoints, or stream names.
* Keep ingest lightweight and push expensive interpretation to later phases.
* Make each phase prove useful output through targeted validation, not just "it runs."
* Keep the recorder data and research focused; do not introduce live trading behavior unless explicitly re-scoped.

---

## Detailed Phase Set

The full implementation sequence is refined into the detailed phase files in this directory:

```text
phase0.md  # repository baseline and execution scaffold
phase1.md  # runtime contracts and recorder skeleton
phase2.md  # storage, rotation, and raw validation foundations
phase3.md  # Pyth reference stream capture
phase4.md  # Aster market stream capture
phase5.md  # Aster snapshots and depth capture
phase6.md  # TradingView alert and label capture
phase7.md  # operational hardening and unattended runtime
phase8.md  # stability run and normalization handoff
```

Use those files as the primary implementation reference for sequencing, scope, validation expectations, and completion criteria.

---

## How To Use This Overview

Use this file when you need to answer questions like:

* What is the raw recorder for?
* What sources does it cover?
* What does the full program include and exclude?
* Which detailed phase file should guide the next implementation step?

Use the phase files when you need:

* phase-specific objectives and boundaries
* expected end state for a phase
* validation expectations
* completion criteria and implementation caveats

---

## Supporting References

The detailed implementation and provider behavior assumptions live in these documents:

```text
docs/reference/schemas.md
docs/reference/data-layout.md
docs/reference/providers/pyth.md
docs/reference/providers/aster.md
docs/reference/providers/tradingview.md
docs/operations/change-log.md
docs/operations/implementation-status.md
```

If the implementation intentionally changes any durable assumption in those files, update them in the same task.

---

## Program Exit Condition

The raw-recorder effort is ready to hand off to normalization when:

* the required live sources are captured reliably,
* raw files follow the canonical layout and envelope shape,
* validation tooling can inspect representative outputs,
* operational status makes recorder failures visible,
* known source quirks and limitations are documented, and
* downstream work can depend on the raw layer without redesigning recorder architecture.