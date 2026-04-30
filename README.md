# CryptoTrader

This repository is a long-lived market-data and trading-research workspace.

Phase 0 establishes the canonical scaffold only. No live recorder behavior is implemented yet.

## Current Status

- Phase 0 scaffold: in progress in the working tree
- Live market-data capture: not implemented yet
- Next implementation phase after scaffold: runtime contracts and recorder skeleton

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

## Phase 0 Scope

Phase 0 is intentionally structural:

- create the canonical repo scaffold
- make ownership explicit
- add minimal package placeholders
- add safe example config
- add baseline validation hooks

It should reduce ambiguity, not add runtime complexity.