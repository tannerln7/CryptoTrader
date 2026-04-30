# Monitoring Notes

This file records confirmed monitoring, health, and data-quality guidance for repository services and jobs.

Use it to document what operators should watch, how health is assessed, what failure signals matter, and what lightweight checks are available. Keep it aligned with the actual runtime behavior of the repo.

## How To Maintain

* Add monitoring sections only after a service, job, or validation process exists.
* Prefer concrete checks, thresholds, and failure signals over aspirational tooling lists.
* Update this file when logs, health signals, validation scripts, or operational expectations change.
* Keep ongoing feature readiness in `docs/operations/implementation-status.md`; use this file for runtime observability and operator checks.

## Current State

The repo now has a runtime health manifest and a route-aware raw data quality report.

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

Signals: `data/manifests/runtime/health-<run_id>.json`; stdout logs from `market-recorder run-service`; newest raw file timestamps under the expected source routes; `market-recorder report-data-quality` exit status and per-route summaries.

Checks: Confirm the health manifest exists and its `component_statuses` show the enabled components. For bounded runs, expect `completed`. For active runs, expect `running`. Run `market-recorder report-data-quality --stale-after-seconds 600` to validate the newest file on each expected route.

Failure Indicators: Missing required routes; stale routes; invalid raw files; a missing or stale health manifest; component statuses marked `failed`; repeated recorder-error raw files for the same route; no new raw files for a source that normally emits continuously.

Response Notes: Re-run `market-recorder validate-config`, check network reachability to the affected provider, inspect the newest `raw.recorder_error.v1` files for that source, and restart the bounded service run. Treat `forceOrder` and idle TradingView alert routes as optional unless the workload specifically expects them.

Refs: `20b70dd`; `docs/operations/deployment.md`; `docs/phases/raw-recorder/phase7.md`