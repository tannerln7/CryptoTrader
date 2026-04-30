# Agent Guidebook

This guidebook is the primary high-level implementation map for agents working on this market-data and trading-research repository.

Use it to understand the system architecture, major subsystems, and where detailed rules live. It should not duplicate the full contents of `AGENTS.md` or the focused reference files. When project decisions, implementation behavior, source behavior, or architecture drift, update this guidebook and the relevant detailed docs.

This guidebook and the other files under `docs/` are internal implementation, coordination, and reference documents for agents and maintainers. Favor durable engineering guidance, constraints, current-state notes, and implementation references over public-facing narrative.

For repo-wide agent rules, workflow, commit sequencing, documentation requirements, and safety constraints, see `AGENTS.md`.

> Temporary bootstrap note
> The repository is intentionally in a docs-first pre-scaffolding state. Missing baseline scaffold files and directories such as `README.md`, `config/`, `src/`, and `tests/` can be expected until Phase 0 scaffolding is completed.
> Remove this note once the baseline repo scaffold exists.

---

## 1) Project Goal

This repository supports a long-lived research system for BTC/ETH perpetual-market data and signal analysis.

Expected phases include:

```text
raw data recording
→ normalization
→ feature generation
→ replay/backtesting
→ alert analysis
→ visualization/reporting
→ ML datasets/models
→ future integrations
```

Each phase should be implemented so later phases can reuse the outputs without brittle glue, silent assumptions, or data loss.

---

## 2) Core Architecture

The project is organized around explicit data layers:

```text
external sources
  → raw/source data
  → normalized data
  → derived features
  → signals / labels / decisions
  → replay / backtests / reports / models
```

Keep these layers separate. Raw/source data should remain reconstructable. Derived artifacts should be reproducible from raw or versioned source datasets.

Detailed references:

```text
docs/reference/schemas.md       # raw envelopes and derived table schemas
docs/reference/data-layout.md   # filesystem/data-lake layout
```

---

## 3) Primary Source Layers

The current project focus is PancakeSwap Perpetuals / Aster-style BTC/ETH perpetual-market research.

| Layer       | Purpose                                                                       | Detailed reference                        |
| ----------- | ----------------------------------------------------------------------------- | ----------------------------------------- |
| Pyth        | Oracle/reference BTC/USD and ETH/USD price updates                            | `docs/reference/providers/pyth.md`        |
| Aster       | Perp market data: trades, L1, mark/index/funding, liquidations, L2, snapshots | `docs/reference/providers/aster.md`       |
| TradingView | Signal/alert labels from chart indicators                                     | `docs/reference/providers/tradingview.md` |

Keep these sources independent at ingest. Do not blend Pyth, Aster, TradingView, or any future source into a synthetic raw stream unless a task explicitly requires it.

Future sources such as Binance, OKX, Bybit, on-chain events, Bitquery, or private account/fill streams should be added as separate provider adapters with their own provider docs.

---

## 4) Repository Map

Canonical structure and naming live in `AGENTS.md`. Important paths:

```text
src/market_recorder/          # Python package
src/market_recorder/sources/  # provider adapters
src/market_recorder/storage/  # raw writers, paths, manifests
src/market_recorder/normalize/
src/market_recorder/features/
src/market_recorder/backtest/
src/market_recorder/replay/
src/market_recorder/alerts/
src/market_recorder/ml/

config/config.example.yaml

docs/agent-guidebook.md
docs/reference/schemas.md
docs/reference/data-layout.md
docs/reference/providers/*.md
docs/operations/change-log.md
docs/operations/implementation-status.md
```

Do not create one-off top-level folders for phase work. Add new functionality inside the existing structure.

---

## 5) Raw Recording Overview

Raw recording is the first data layer. Its job is intentionally narrow:

```text
connect
receive events
timestamp locally
wrap with metadata
write compressed raw records
rotate files
reconnect on failure
```

Raw recording should not calculate indicators, normalize away source fields, blend prices, run backtests, make trade decisions, or place orders.

Use these references for implementation details:

```text
docs/reference/schemas.md
docs/reference/data-layout.md
docs/reference/providers/pyth.md
docs/reference/providers/aster.md
docs/reference/providers/tradingview.md
```

---

## 6) Normalization Overview

Normalization converts raw source payloads into typed, queryable tables. Normalized tables are derived artifacts, not the source of truth.

Normalization should:

* Preserve provenance back to raw files or stable source records.
* Keep timestamp semantics explicit.
* Use documented schemas.
* Avoid silent unit ambiguity.
* Be deterministic for a given input set and config.

References:

```text
docs/reference/schemas.md
docs/reference/data-layout.md
```

---

## 7) Feature Generation Overview

Feature generation derives research-ready data from normalized or replay-ready inputs.

Examples:

```text
OHLCV bars
RVOL
spread and mid-price features
taker-flow features
funding context
Pyth-vs-Aster divergence
L2 depth/imbalance summaries
signal outcome labels
```

Feature code must avoid lookahead bias. Windowing, alignment, resampling, and label rules must be explicit and documented.

Feature outputs should include enough metadata to identify source dataset version, feature version, config/parameter hash, symbol/timeframe, and creation time.

---

## 8) Replay and Backtesting Overview

Replay and backtesting should use stored data, not live APIs.

Backtest and replay outputs should record enough metadata to reproduce the run:

```text
strategy version
code/git version
source dataset versions
feature versions
symbol/time range
fee model
slippage/fill model
funding assumptions
entry/exit assumptions
run config
```

Replay/backtest logic must avoid future leakage and keep strategy logic separate from execution simulation.

References:

```text
docs/reference/schemas.md
docs/reference/data-layout.md
```

---

## 9) Provider Adapter Guidelines

Each external source should have an isolated adapter under `src/market_recorder/sources/` or an equivalent source-specific module.

Provider adapters should:

* Keep endpoints, stream names, symbols, and feed IDs config-driven where practical.
* Preserve raw provider responses where appropriate.
* Implement reconnect/retry/backoff behavior for live streams.
* Respect documented rate limits.
* Record enough metadata to debug gaps and source failures.
* Keep provider-specific assumptions out of unrelated modules.

When a provider integration changes, update its provider reference file under `docs/reference/providers/` and update operational tracking docs as required by `AGENTS.md`.

---

## 10) Configuration Guidelines

Runtime behavior should be config-driven rather than hard-coded.

Typical config-owned values:

```text
storage root
enabled sources
symbols
Pyth feed IDs
Aster source symbols
stream names
snapshot intervals
compression settings
reconnect delays
webhook bind/port/path
```

The canonical example config is `config/config.example.yaml`. Keep it safe to commit and free of secrets.

Local configs containing real paths, secrets, private endpoints, or account identifiers should be ignored by Git.

---

## 11) Operational Tracking

`AGENTS.md` defines the exact rules for operational tracking and commit sequencing. In short, repo changes should be reflected in:

```text
docs/operations/change-log.md
docs/operations/implementation-status.md
```

Use `change-log.md` for durable commit-style history. Use `implementation-status.md` for a concise feature/status map showing what exists, what is incomplete, and what future agents need to know.

Implementation changes and documentation/status updates should be committed separately as described in `AGENTS.md`.

---

## 12) Documentation Update Map

Use this guidebook as the high-level project map. Put detailed rules in the appropriate focused docs.

| Change type                         | Update                                                                         |
| ----------------------------------- | ------------------------------------------------------------------------------ |
| Source/API/stream behavior          | `docs/reference/providers/<provider>.md`                                       |
| Raw or normalized schemas           | `docs/reference/schemas.md`                                                    |
| Data paths/layout                   | `docs/reference/data-layout.md`                                                |
| Config keys/defaults                | `config/config.example.yaml` and setup docs                                    |
| Major architecture decisions        | `docs/decisions/*.md`                                                          |
| Complex phase plans                 | `docs/phases/*.md`                                                             |
| Feature/status/change tracking      | `docs/operations/change-log.md` and `docs/operations/implementation-status.md` |
| High-level architecture/project map | `docs/agent-guidebook.md`                                                      |
| Agent workflow/rules                | `AGENTS.md`                                                                    |

Before creating a new doc entry, check for an existing relevant entry and update it instead of duplicating it.

---

## 13) Current Reference Map

Start here:

```text
AGENTS.md
  Repo-wide agent rules, workflow, safety, commit hygiene, docs maintenance, and compatibility constraints.

README.md
  User-facing setup and normal operation guide.

docs/agent-guidebook.md
  This file. High-level implementation map for agents.

docs/reference/schemas.md
  Raw envelopes, normalized tables, feature/replay/backtest schema conventions.

docs/reference/data-layout.md
  Runtime filesystem/data-lake layout and validation commands.

docs/reference/providers/pyth.md
  Pyth feed IDs, Hermes endpoint, rate limits, raw handling, normalization notes.

docs/reference/providers/aster.md
  Aster REST/WS endpoints, symbols, streams, depth snapshots, validation.

docs/reference/providers/tradingview.md
  TradingView JSON payload conventions, placeholders, webhook handling.

docs/operations/change-log.md
  Durable commit-style history of repo changes.

docs/operations/implementation-status.md
  Current feature/status map for future agents.
```

---

## 14) Agent Compatibility Checklist

Before finishing a task, verify:

* The change fits the user-scoped phase/task.
* Source truth is preserved where applicable.
* Layer boundaries remain clear.
* Outputs are reproducible or traceable to source/config/code.
* Timestamps, units, symbols, and source names are unambiguous.
* Config remains flexible for later symbols/sources/timeframes.
* No hidden live-trading behavior was introduced.
* Relevant docs and operational tracking files were updated according to `AGENTS.md`.
* Any observed drift from existing definitions was corrected or clearly reported.
