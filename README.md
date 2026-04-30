# CryptoTrader

CryptoTrader is a Python workspace for durable market-data capture and trading research.

The current system focuses on collecting raw market and alert data in a reproducible way so later normalization, analysis, feature generation, replay, backtesting, and ML workflows can build on a stable source-of-truth layer.

## What This Repository Does

- Captures live market data from Pyth and Aster.
- Captures TradingView webhook alerts as raw events.
- Controls a repo-scoped background recorder service with start, stop, restart, status, and health commands.
- Stores append-only compressed raw records in a canonical filesystem layout.
- Writes runtime health manifests for unattended recorder runs.
- Validates raw files and reports missing, stale, or invalid data routes.
- Keeps provider payloads intact so downstream jobs can normalize or derive data later without losing source fidelity.

## Current Scope

This repository is currently centered on the raw recording layer and the operator surfaces around it.

Implemented provider-facing components:

- Pyth Hermes SSE capture for reference price updates.
- Aster non-depth WebSocket market capture.
- Aster depth WebSocket capture plus periodic REST order-book snapshots.
- TradingView-compatible webhook ingestion for alert events.
- A repo-scoped background recorder service control surface with lock, state, log, and health-manifest output.
- Route-aware raw data quality reporting.

The raw layer is intentionally narrow. It connects to sources, timestamps and wraps events, writes compressed records, rotates files, and surfaces service plus runtime health. It does not normalize source payloads, generate features, backtest strategies, or place trades.

## How It Works

The recorder is config-driven and organized around explicit data boundaries:

```text
external sources
	-> raw/source capture
	-> normalized datasets
	-> derived features
	-> replay / backtests / reports / models
```

Today, the implemented path is the raw/source capture layer.

At runtime, the system:

1. Loads typed runtime and provider configuration from YAML.
2. Uses the `market-recorder` CLI as the operator control surface for background service lifecycle or one-shot dev/debug commands.
3. Starts a shared aiohttp runtime for HTTP, SSE, and WebSocket workloads.
4. Connects to enabled sources or binds the TradingView webhook receiver.
5. Wraps incoming payloads in canonical raw envelopes with timestamps and run metadata.
6. Writes `.jsonl.zst` files using hourly rotation under the configured data root.
7. Persists repo-scoped service state under `data/service/`, emits runtime health manifests under the effective data root, and supports post-run quality validation.

## Storage Model

Raw records are written under a canonical route-based layout:

```text
data/raw/<source>/<transport>/<source_symbol>/<stream>/date=YYYY-MM-DD/hour=HH/part-<run_id>.jsonl.zst
```

Examples:

- `data/raw/pyth/sse/MULTI/price_stream/...`
- `data/raw/aster/ws/BTCUSDT/bookTicker/...`
- `data/raw/aster/rest/BTCUSDT/depth_snapshot_1000/...`
- `data/raw/tradingview/webhook/ALL/alert/...`

Runtime health manifests are written under:

```text
data/manifests/runtime/health-<run_id>.json
```

Service-control files are written under:

```text
data/service/recorder-service.json
data/service/recorder-service.lock
data/service/recorder-service.log
```

The raw envelope and storage contracts are documented in:

- `docs/reference/schemas.md`
- `docs/reference/data-layout.md`

## Repository Layout

```text
config/                 Example runtime and source configuration
docs/                   Architecture, provider, and operations documentation
ops/                    Deployment and operational assets
scripts/                Utility entrypoints
src/market_recorder/    Recorder package and provider adapters
tests/                  Unit and integration coverage
```

Key package areas:

- `src/market_recorder/config.py` for config loading and validation.
- `src/market_recorder/runtime.py` for the shared runtime and lifecycle management.
- `src/market_recorder/storage/` for path generation, writing, and validation.
- `src/market_recorder/sources/` for provider adapters.
- `src/market_recorder/alerts/` for alert ingestion.
- `src/market_recorder/service.py` for unattended service orchestration.
- `src/market_recorder/service_control.py` for repo-scoped service state, locking, and foreground worker control.
- `src/market_recorder/quality.py` for route-level health and quality checks.
- `src/market_recorder/cli.py` for the `market-recorder` command.
- `ops/systemd/` for the systemd service template and instance env example.

## Getting Started

Create and activate the repo-local virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies. For day-to-day operation, install the package only:

```bash
python -m pip install --upgrade pip
python -m pip install .
```

For development, install the package in editable mode with the test and lint extras (this is what `requirements.txt` resolves to):

```bash
python -m pip install -r requirements.txt
```

Run baseline checks:

```bash
python -m compileall src tests
pytest
ruff check .
```

Validate the example configuration:

```bash
market-recorder validate-config
```

## Configuration

The repo ships with safe example configuration files:

- `config/config.example.yaml`
- `config/sources.example.yaml`
- `.env.example`

The runtime config controls storage and runtime behavior. The sources config controls which providers are enabled and how their symbols, streams, snapshot cadence, and webhook settings are defined.

Keep secrets and private endpoints out of committed config.

## Common Workflows

### Background service control

Show the current recorder-service state:

```bash
market-recorder
```

Start the configured recorder service in the background:

```bash
market-recorder start
```

Inspect service status and summarized health:

```bash
market-recorder status
market-recorder health
```

Restart or stop the background service:

```bash
market-recorder restart
market-recorder stop
```

### Systemd deployment

The repo ships a systemd template and env-file example under `ops/systemd/`:

```text
ops/systemd/market-recorder@.service
ops/systemd/market-recorder.env.example
```

For a systemd-managed instance, copy the env example to `/etc/market-recorder/<instance>.env`, install or link the unit, then enable the instance:

```bash
sudo mkdir -p /etc/market-recorder
sudo cp ops/systemd/market-recorder.env.example /etc/market-recorder/main.env
sudo cp ops/systemd/market-recorder@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now market-recorder@main.service
```

Use systemd for lifecycle operations when the unit owns the worker:

```bash
sudo systemctl status market-recorder@main.service
sudo systemctl restart market-recorder@main.service
sudo systemctl stop market-recorder@main.service
journalctl -u market-recorder@main.service -f
```

The systemd unit runs the foreground `service-worker` path directly, so `market-recorder status` and `market-recorder health` still report recorder-level state for that repo checkout. Do not mix `market-recorder start` or `stop` with a systemd-managed instance; use `systemctl` for lifecycle and the CLI for app-level inspection.

### Uninstall and disable

For a CLI-managed background recorder, stop the worker and remove the repo-scoped control files:

```bash
market-recorder stop
rm -rf data/service
```

The `data/service/` directory only holds the lock, state JSON, and capture log for the controller; raw output and health manifests live under the configured data root and are not removed by this step.

For a systemd-managed instance, disable the unit and remove the installed assets:

```bash
sudo systemctl disable --now market-recorder@<instance>.service
sudo rm /etc/systemd/system/market-recorder@.service
sudo rm /etc/market-recorder/<instance>.env
sudo rmdir /etc/market-recorder 2>/dev/null || true
sudo systemctl daemon-reload
```

The systemd unit's `StateDirectory=market-recorder/<instance>` is not removed automatically. Delete `/var/lib/market-recorder/<instance>` only after confirming the captured raw data and health manifests are no longer needed.

To uninstall the package itself, remove the virtual environment (`rm -rf .venv`) or run `python -m pip uninstall market-recorder` from the active environment.

### Runtime bootstrap and foreground dev/debug

Start the recorder runtime and exit after startup checks:

```bash
market-recorder run
```

### Sample write and validation

Write a sample compressed raw file:

```bash
market-recorder write-sample
```

Validate an existing raw file:

```bash
market-recorder validate-raw path/to/file.jsonl.zst
```

### Capture a single source

Capture a bounded Pyth sample:

```bash
market-recorder capture-pyth --event-limit 2 --duration-seconds 20
```

Capture bounded Aster market streams:

```bash
market-recorder capture-aster --event-limit 8 --duration-seconds 30
```

Capture bounded Aster depth streams and REST snapshots:

```bash
market-recorder capture-aster-depth --event-limit 12 --duration-seconds 30
```

### Serve TradingView alerts locally

Run the TradingView-compatible webhook receiver for local testing:

```bash
market-recorder serve-tradingview \
	--bind-host 127.0.0.1 \
	--bind-port 18080 \
	--path /webhook/test \
	--request-limit 2 \
	--duration-seconds 20
```

Run the recorder worker in the foreground for local debugging or bounded smoke runs:

```bash
market-recorder run-service --duration-seconds 20 --health-interval-seconds 2
```

The public `start` command wraps the same worker path, but runs it in the background and records repo-scoped service state.

Run a route-aware quality report after capture:

```bash
market-recorder report-data-quality --stale-after-seconds 600
```

For bounded validation runs, stop the worker before treating `validate-raw` or `report-data-quality` as authoritative. The current writer keeps the active hour file open during capture, so in-progress files may appear empty or partially written until shutdown finalizes them.

## Validation And Development

Useful local commands:

```bash
pytest tests/unit -q
ruff check .
market-recorder status
market-recorder health
market-recorder validate-config
market-recorder report-data-quality --stale-after-seconds 600
```

Development conventions:

- Use the repo-local `.venv` as the Python interpreter.
- Treat `pyproject.toml` as the main project metadata source of truth.
- Keep `data/` local and untracked.
- Preserve provider source payloads in raw capture paths.
- Keep raw capture, normalization, features, and backtests as separate layers.
- Update the relevant docs when behavior, contracts, or operational assumptions change.

## Documentation

Start here depending on what you need:

- `docs/agent-guidebook.md` for the implementation map.
- `docs/reference/schemas.md` for raw envelope contracts.
- `docs/reference/data-layout.md` for filesystem layout.
- `docs/reference/providers/pyth.md` for Pyth integration details.
- `docs/reference/providers/aster.md` for Aster integration details.
- `docs/reference/providers/tradingview.md` for TradingView alert ingestion details.
- `docs/operations/deployment.md` for deployment notes.
- `docs/operations/monitoring.md` for health and monitoring guidance.
- `ops/systemd/` for the shipped systemd unit template and env example.
- `docs/decisions/raw-recorder-normalization-handoff.md` for the current raw-recorder handoff state.

## Status

The raw recorder is operational for bounded live capture, service-first background operation, and direct systemd supervision through the shipped unit template. The current control surface supports `start`, `stop`, `restart`, `status`, and `health`, while keeping `run-service` and the source-specific commands available for development and debugging. The next major layer is downstream normalization built on the existing raw contracts, storage layout, and provider-specific capture paths.