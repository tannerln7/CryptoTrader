# Monitoring Notes

This file records confirmed monitoring, health, and data-quality guidance for repository services and jobs.

Use it to document what operators should watch, how health is assessed, what failure signals matter, and what lightweight checks are available. Keep it aligned with the actual runtime behavior of the repo.

## How To Maintain

* Add monitoring sections only after a service, job, or validation process exists.
* Prefer concrete checks, thresholds, and failure signals over aspirational tooling lists.
* Update this file when logs, health signals, validation scripts, or operational expectations change.
* Keep ongoing feature readiness in `docs/operations/implementation-status.md`; use this file for runtime observability and operator checks.

## Current State

The repo now has a service-owned Unix control socket, a runtime health manifest, journald-backed systemd supervision assets, and a route-aware raw data quality report.

## Section Template

```md
## Service, job, or data process name

Status: planned | in-progress | implemented | blocked | deprecated

Signals: Logs, metrics, manifests, files, or timestamps that indicate health.

Checks: Commands, scripts, or inspection steps used to confirm the system is healthy.

Failure Indicators: Conditions that should be treated as warnings or incidents.

Response Notes: Initial operator actions or escalation guidance.

Refs: Relevant docs, scripts, configs, or commit refs.
```

## Recorder service

Status: implemented

Signals: `/run/market-recorder/<instance>/control.sock`; `market-recorder status`; `market-recorder health`; `data/manifests/runtime/health-<run_id>.json`; newest raw file timestamps under the expected source routes; `market-recorder report-data-quality` exit status and per-route summaries; `journalctl -u market-recorder@<instance>.service`.

Checks: Confirm `market-recorder status` reports `running` for the expected PID, config path, and control socket. Confirm `market-recorder health` shows the expected enabled components. For advanced troubleshooting, confirm `systemctl status market-recorder@<instance>.service` is `active (running)` and inspect `journalctl -u market-recorder@<instance>.service` for startup or shutdown failures. For bounded runs, expect runtime component statuses to reach `completed` after shutdown. For active runs, expect `running`. Treat `market-recorder report-data-quality --stale-after-seconds 600` and `validate-raw` as post-stop checks for sealed data only, because those commands skip or refuse active `.jsonl.zst.open` files by default.

Failure Indicators: `market-recorder status` returns `failed`; `market-recorder status` says the unit is active but the control socket is unavailable; `systemctl status` shows restart loops or failed state; journald shows repeated startup or configuration failures; finalized raw files are invalid after graceful shutdown; required routes are missing or stale; the health manifest is missing or stale for an active run; component statuses are `failed`; repeated recorder-error raw files appear for the same route; or no new raw files arrive for a source that normally emits continuously.

Response Notes: Re-run `market-recorder validate-config`, inspect `journalctl -u market-recorder@<instance>.service` when the CLI reports socket or startup failures, check network reachability to the affected provider, inspect the newest `raw.recorder_error.v1` files for that source, and use `market-recorder restart` as the normal operator recovery path. Treat `forceOrder` and idle TradingView alert routes as optional unless the workload specifically expects them.

Log Surface Notes: The installed service writes its stdout and stderr to journald. The recorder is intentionally quiet during steady-state ingestion and only writes startup messages, exception tracebacks, and shutdown notices there, so a short or quiet journal during a healthy run is expected; rely on `market-recorder status`, `market-recorder health`, and `report-data-quality` for ongoing signal. Use `journalctl -u market-recorder@<instance>.service` instead of looking for a repo-scoped service log file.

Refs: `e8c159b`; `20b70dd`; `docs/operations/deployment.md`; `docs/phases/raw-recorder/phase7.md`; `src/market_recorder/service_control.py`; `ops/systemd/market-recorder@.service`