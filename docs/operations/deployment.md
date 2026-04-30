# Deployment Notes

This file records confirmed deployment and runtime operation guidance for repository services and jobs.

Use it for durable operator-facing implementation notes such as service units, runtime prerequisites, startup procedures, environment expectations, filesystem assumptions, and deployment-specific caveats. Keep speculation and unconfirmed ideas out of this file.

## How To Maintain

* Add sections only when a runnable service, job, or deployment target exists.
* Separate confirmed procedures from future ideas or open questions.
* Update this file when entrypoints, ports, environment requirements, service definitions, or operator steps change.
* Link to `docs/operations/monitoring.md` for health checks and to `docs/operations/implementation-status.md` for current readiness.

## Current State

The repo now has a service-first operator surface through `market-recorder start`, `status`, `health`, `restart`, and `stop`, plus a shipped systemd template that supervises the same foreground worker path directly.

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

Purpose: Run the enabled live recorder components behind a repo-scoped background service controller with shared-runtime startup, periodic health-manifest updates, and predictable shutdown behavior.

Prerequisites: Repo-local `.venv`; installed package and dependencies; a writable data root; network access for the enabled market-data sources; local webhook exposure only if `tradingview.enabled` is true.

Procedure: Activate `.venv`, verify `market-recorder validate-config`, then start the background service with `market-recorder start`. Use `market-recorder status` to confirm the worker PID and effective config, `market-recorder health` to inspect the current runtime-health summary, and `market-recorder stop` or `market-recorder restart` for lifecycle control. Use `market-recorder --config <path> start` or `market-recorder start --config <path>` when the run should use a non-default config or data root.

Validation: Confirm `market-recorder status` reports `State: running`, shows the expected config and data-root paths, and records the repo-scoped control files under `data/service/`. Use `market-recorder health` to confirm the expected enabled components are `running` or `completed`. For bounded validation runs, stop the worker before treating `market-recorder report-data-quality --stale-after-seconds 600` or `validate-raw` as authoritative, because the active `.jsonl.zst` file remains open until shutdown finalizes it.

Notes: The background worker is intentionally still a normal foreground process behind the control surface so future systemd or supervisor integration can manage it cleanly. Repo-scoped control files live under `data/service/` even when `--data-root` changes, while runtime health manifests stay under the effective data root. The default example config currently enables Pyth and Aster, and leaves TradingView disabled. If TradingView is enabled, deploy it behind a reverse proxy or tunnel that exposes an accepted public port instead of assuming direct public binding from a development workstation.

Refs: `45accd3`; `20b70dd`; `docs/operations/monitoring.md`; `docs/phases/raw-recorder/phase7.md`; `src/market_recorder/service_control.py`

## Systemd unit template

Status: implemented

Purpose: Provide a production-oriented systemd template that runs the foreground `service-worker` process directly so systemd owns PID tracking, restart policy, and shutdown while the recorder CLI remains compatible for app-layer status and health inspection.

Prerequisites: systemd-based Linux host; repo checkout with installed dependencies; a valid instance env file at `/etc/market-recorder/<instance>.env`; writable `/var/lib/market-recorder/<instance>`; optional dedicated service account if the repo checkout and virtualenv are owned outside root.

Procedure: Copy `ops/systemd/market-recorder@.service` into `/etc/systemd/system/`, copy `ops/systemd/market-recorder.env.example` to `/etc/market-recorder/<instance>.env`, edit the repo root, Python interpreter, and config path values, then run `systemctl daemon-reload` and `systemctl enable --now market-recorder@<instance>.service`. Use `systemctl status`, `systemctl restart`, and `systemctl stop` for lifecycle control, and use `market-recorder status` plus `market-recorder health` for recorder-level state reporting from the same repo checkout.

Validation: Run `systemd-analyze verify ops/systemd/market-recorder@.service` before install, confirm `systemctl status market-recorder@<instance>.service` reports `active (running)`, confirm `market-recorder status` shows the expected PID and `Data root: /var/lib/market-recorder/<instance>`, and confirm `market-recorder health` reports the expected enabled components. For bounded checks of raw-file integrity, stop the instance before running `validate-raw` or `report-data-quality` so the current output file is finalized.

Notes: The template intentionally uses `Type=simple`, avoids `Type=forking`, and runs the hidden `service-worker` path directly so systemd supervises the real worker process instead of the CLI's detached controller. The unit uses `StateDirectory=market-recorder/%i`, which sets `$STATE_DIRECTORY` to `/var/lib/market-recorder/<instance>` for raw output and health manifests, while repo-scoped control files still live under `<repo>/data/service`. Because the current service-control layer is repo-scoped, one active recorder worker is supported per repo checkout. Use separate checkouts if multiple systemd instances must run concurrently.

Refs: `45accd3`; `ops/systemd/market-recorder@.service`; `ops/systemd/market-recorder.env.example`; `docs/operations/monitoring.md`; `src/market_recorder/service_control.py`

## Recorder decommission

Status: implemented

Purpose: Cleanly stop a running recorder and remove installed assets without orphaning a worker, a lock, or environment files that point at a no-longer-active deployment.

Prerequisites: Operator access to the supervisor that currently owns the worker (the `market-recorder` CLI for repo-scoped background runs, or `systemctl` for a systemd-managed instance); access to remove the installed unit, env file, and any state directory the deployment previously used.

Procedure: For a CLI-managed background recorder, run `market-recorder stop` and then remove the repo-scoped control directory with `rm -rf data/service`; the captured raw output and health manifests under the configured data root are not touched by this step. For a systemd-managed instance, run `sudo systemctl disable --now market-recorder@<instance>.service`, remove `/etc/systemd/system/market-recorder@.service`, remove `/etc/market-recorder/<instance>.env`, run `sudo systemctl daemon-reload`, and delete `/var/lib/market-recorder/<instance>` only after confirming the captured raw data and health manifests are no longer needed. To uninstall the package itself, remove the repo-local virtual environment or run `python -m pip uninstall market-recorder` from the active environment.

Validation: After the CLI path, confirm `market-recorder status` reports `stopped`, the active worker PID is gone, no `.jsonl.zst.open` segments remain under the data root, and `data/service/` is absent. After the systemd path, confirm `systemctl status market-recorder@<instance>.service` reports the unit is no longer loaded, no `market-recorder` worker is running, and the env file and unit file are removed.

Notes: Always stop the worker before removing its state or env files so the writer can finalize the active hour file by atomically sealing `.jsonl.zst.open` to `.jsonl.zst`. Removing files first risks leaving an unsealed active segment behind, which `validate-raw` and `report-data-quality` will treat as `incomplete-active` until manually finalized.

Refs: `ops/systemd/market-recorder@.service`; `README.md`; `docs/operations/monitoring.md`; `src/market_recorder/service_control.py`