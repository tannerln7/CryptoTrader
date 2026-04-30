# Deployment Notes

This file records confirmed deployment and runtime operation guidance for repository services and jobs.

Use it for durable operator-facing implementation notes such as service units, runtime prerequisites, startup procedures, environment expectations, filesystem assumptions, and deployment-specific caveats. Keep speculation and unconfirmed ideas out of this file.

## How To Maintain

* Add sections only when a runnable service, job, or deployment target exists.
* Separate confirmed procedures from future ideas or open questions.
* Update this file when entrypoints, ports, environment requirements, service definitions, or operator steps change.
* Link to `docs/operations/monitoring.md` for health checks and to `docs/operations/implementation-status.md` for current readiness.

## Current State

The repo now has a runnable unattended service entrypoint through `market-recorder run-service`.

## Section Template

```md
## Deployment target or service name

Status: planned | in-progress | implemented | blocked | deprecated

Purpose: Short description of what is being deployed.

Prerequisites: Environment, filesystems, secrets, or tools required.

Procedure: Step-by-step deployment or startup instructions.

Validation: How to confirm the deployment is healthy.

Notes: Caveats, rollback notes, or operational assumptions.

Refs: Relevant docs, scripts, configs, or commit refs.
```

## Recorder service

Status: implemented

Purpose: Run the enabled live recorder components together with a shared runtime, periodic health-manifest updates, and predictable shutdown behavior.

Prerequisites: Repo-local `.venv`; installed package and dependencies; a writable data root; network access for the enabled market-data sources; local webhook exposure only if `tradingview.enabled` is true.

Procedure: Activate `.venv`, verify `market-recorder validate-config`, then start the service with `market-recorder run-service --health-interval-seconds 10`. Add `--duration-seconds <n>` for bounded smoke or soak runs.

Validation: Confirm the service prints a `Health manifest:` path on exit for bounded runs. During an active run, inspect `data/manifests/runtime/health-<run_id>.json` and confirm the expected components are `running` or `completed`. Follow with `market-recorder report-data-quality --stale-after-seconds 600`.

Notes: The default example config currently enables Pyth and Aster, and leaves TradingView disabled. If TradingView is enabled, deploy it behind a reverse proxy or tunnel that exposes an accepted public port instead of assuming direct public binding from a development workstation.

Refs: `20b70dd`; `docs/operations/monitoring.md`; `docs/phases/raw-recorder/phase7.md`