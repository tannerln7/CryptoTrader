# CryptoTrader

This repository is a long-lived market-data and trading-research workspace.

The repo now includes the Phase 0 scaffold, the Phase 1 runtime-contract foundation, the Phase 2 storage and validation foundation, the Phase 3 live Pyth capture path, and the Phase 4 Aster non-depth market capture path.

## Current Status

- Phase 0 scaffold: implemented
- Phase 1 runtime contracts and recorder skeleton: implemented
- Phase 2 storage, rotation, and raw validation foundations: implemented
- Phase 3 Pyth reference stream capture: implemented
- Phase 4 Aster non-depth market stream capture: implemented
- Aster depth/snapshot capture and TradingView capture: not implemented yet
- Next implementation phase: Aster snapshots and depth capture

## Repo Defaults

- Python interpreter: in-repo `.venv`
- Package layout: `src/market_recorder`
- Project metadata source of truth: `pyproject.toml`
- Convenience install file: `requirements.txt`
- Default local data root for examples: `./data`

## Quick Start

Create the repo-local virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install the scaffold package and dev tools:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the baseline checks:

```bash
python -m compileall src tests
pytest
ruff check .
```

Validate the example config files:

```bash
market-recorder validate-config
```

Run the current runtime bootstrap check:

```bash
market-recorder run
```

Write a sample raw `.jsonl.zst` file under the configured data root:

```bash
market-recorder write-sample
```

Validate a raw file without loading it all into memory:

```bash
market-recorder validate-raw path/to/file.jsonl.zst
```

Capture a bounded live Pyth sample:

```bash
market-recorder capture-pyth --event-limit 2 --duration-seconds 20
```

Capture a bounded live Aster sample:

```bash
market-recorder capture-aster --event-limit 8 --duration-seconds 30
```

## Canonical Layout

Important paths:

```text
config/
src/market_recorder/
tests/
scripts/
ops/
notebooks/
docs/
```

Detailed structure and rules live in `AGENTS.md`.

## Config Files

- Runtime example config: `config/config.example.yaml`
- Source/provider example config: `config/sources.example.yaml`
- Environment example file: `.env.example`

These files are safe examples only. Do not commit real secrets or private endpoints.

## Working Conventions

- Keep the `.venv` inside the repo and use it as the interpreter.
- Treat `pyproject.toml` as the dependency and tooling source of truth.
- Use `requirements.txt` only as a convenience wrapper for local development installs.
- Keep `data/` local and untracked except for committed placeholders.
- Update the relevant docs when behavior, structure, or assumptions change.

## Implemented Through Phase 4

The repo currently provides:

- the canonical scaffold and ownership layout from Phase 0
- typed runtime and source config loading from YAML examples
- UTC timestamp and run-id helpers
- raw envelope helper functions aligned with the schema docs
- an aiohttp-managed runtime skeleton with cleanup contexts and a shared client session
- canonical raw path generation aligned with the data-layout reference
- a streaming Zstandard JSONL writer with hourly rotation
- a streaming raw-file validator and sample-write CLI path
- a live Pyth Hermes SSE capture command that writes raw reference events to canonical storage
- a live Aster combined-stream capture command for non-depth market streams
- focused unit coverage for config loading, envelope helpers, runtime lifecycle, CLI behavior, time helpers, storage pathing, writer rotation, and raw validation

The repo can now generate and validate sample raw files locally, capture bounded live Pyth events, and capture bounded live Aster non-depth events. Aster depth/snapshot work and TradingView integration are still pending.