# CryptoTrader

This repository is a long-lived market-data and trading-research workspace.

The repo now includes the Phase 0 scaffold and the Phase 1 runtime-contract foundation. Live market-data capture has not started yet.

## Current Status

- Phase 0 scaffold: implemented
- Phase 1 runtime contracts and recorder skeleton: implemented
- Live market-data capture: not implemented yet
- Next implementation phase: storage, rotation, and raw validation foundations

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

## Implemented Through Phase 1

The repo currently provides:

- the canonical scaffold and ownership layout from Phase 0
- typed runtime and source config loading from YAML examples
- UTC timestamp and run-id helpers
- raw envelope helper functions aligned with the schema docs
- an aiohttp-managed runtime skeleton with cleanup contexts and a shared client session
- focused unit coverage for config loading, envelope helpers, runtime lifecycle, CLI behavior, and time helpers

The repo still does not write raw files or connect to live providers.