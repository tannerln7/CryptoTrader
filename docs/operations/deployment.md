# Deployment Notes

This file records confirmed deployment and runtime operation guidance for repository services and jobs.

Use it for durable operator-facing implementation notes such as service units, runtime prerequisites, startup procedures, environment expectations, filesystem assumptions, and deployment-specific caveats. Keep speculation and unconfirmed ideas out of this file.

## How To Maintain

* Add sections only when a runnable service, job, or deployment target exists.
* Separate confirmed procedures from future ideas or open questions.
* Update this file when entrypoints, ports, environment requirements, service definitions, or operator steps change.
* Link to `docs/operations/monitoring.md` for health checks and to `docs/operations/implementation-status.md` for current readiness.

## Current State

The repo now has a shell-installed systemd deployment path, an unprivileged CLI that controls the installed unit through a service-owned Unix socket, and a development-only foreground `run-service` path.

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

Purpose: Run the enabled live recorder components as a systemd-managed service that exposes a narrow control socket for `market-recorder start`, `status`, `health`, `restart`, and `stop`.

Prerequisites: A systemd-based Linux host; sudo for the one-time installer; a source checkout of this repo to run `ops/install/install.sh`; network access for the enabled market-data sources; local webhook exposure only if `tradingview.enabled` is true.

Procedure: Run `sudo ./ops/install/install.sh` for the default `production` instance, or pass `--instance <instance>` for a named installed instance. The installer manages `python3` and `python3-venv` through `apt-get` when needed on Debian-family hosts, stages an installer-owned virtualenv under `/opt/CryptoTrader/.venv`, installs `/usr/local/bin/market-recorder`, writes the systemd, polkit, and sysusers assets, and provisions `/etc/CryptoTrader/<instance>.yaml`, `/etc/CryptoTrader/<instance>.sources.yaml`, and `/etc/CryptoTrader/<instance>.env` when they are missing. Re-running the installer preserves existing instance files and writes updated defaults to adjacent `.new` files when the shipped templates change. Review the instance config files, then validate them with `market-recorder --instance <instance> validate-config --config /etc/CryptoTrader/<instance>.yaml`. Refresh group membership with `newgrp market-recorder` or by logging out and back in. If you want the unit enabled on future boots, rerun `sudo ./ops/install/install.sh --instance <instance> --enable`; this enables autostart only and does not start the service. Use `market-recorder start` to launch the installed service, `market-recorder status` to confirm the control socket and effective runtime paths, and `market-recorder health`, `stop`, or `restart` for normal lifecycle control.

Validation: Confirm the installer completes its service-user access checks and `validate-config` run before the first start. Then confirm `market-recorder status` reports `State: running`, shows the expected config and data-root paths, and points at `/run/market-recorder/<instance>/control.sock`. Use `market-recorder health` to confirm the expected enabled components are `running` or `completed`. For bounded validation runs, stop the worker before treating `market-recorder report-data-quality --stale-after-seconds 600` or `validate-raw` as authoritative, because those checks skip or refuse active `.jsonl.zst.open` files and are authoritative for sealed `.jsonl.zst` files only.

Notes: The systemd unit runs the hidden `service-worker` path directly and marks readiness with `Type=notify` only after the control socket is bound and the runtime-health surface is ready. The service user is `market-recorder`; operators are added to the same group for control-socket and sealed-data access, but the raw writer still keeps active `.jsonl.zst.open` files service-private and seals final `.jsonl.zst` files non-writable to the operator group. The installed runtime no longer depends on a readable repo checkout after install; it reads the launcher from `/usr/local/bin/market-recorder`, the app root from `/opt/CryptoTrader`, and live instance config only from `/etc/CryptoTrader`. Checkout-mode development is explicit through `scripts/dev/env.sh` and `scripts/dev/market-recorder`.

Refs: `7b56d9f`; `0c7b256`; `e8c159b`; `45accd3`; `20b70dd`; `docs/operations/monitoring.md`; `docs/phases/raw-recorder/phase7.md`; `ops/install/install.sh`; `scripts/dev/market-recorder`; `src/market_recorder/service_control.py`

## Systemd unit template

Status: implemented

Purpose: Provide the installed unit template and troubleshooting guidance for the service-owned control socket model.

Prerequisites: The instance must already be installed with `ops/install/install.sh`; `/usr/local/bin/market-recorder`, `/opt/CryptoTrader`, and `/etc/CryptoTrader/<instance>.env` must exist; `systemd-analyze` and `journalctl` should be available on the host.

Procedure: Use `market-recorder start`, `status`, `health`, `restart`, and `stop` for normal operations. For troubleshooting, inspect `systemctl status market-recorder@<instance>.service`, `journalctl -u market-recorder@<instance>.service`, and `sudo systemd-analyze verify /etc/systemd/system/market-recorder@.service` on an installed host. If you change `/etc/CryptoTrader/<instance>.env` or either instance YAML file, rerun `market-recorder --instance <instance> validate-config --config /etc/CryptoTrader/<instance>.yaml` and then restart the service through the normal CLI path.

Validation: Run `sudo systemd-analyze verify /etc/systemd/system/market-recorder@.service` after install or after copying updated unit assets onto the host. Confirm `systemctl status market-recorder@<instance>.service` reports `active (running)`, confirm `market-recorder status` shows the expected PID and `Data root: /var/lib/market-recorder/<instance>`, and confirm `market-recorder health` reports the expected enabled components. For bounded checks of raw-file integrity, stop the instance before running `validate-raw` or `report-data-quality` so the current output file is finalized.

Notes: The template now uses `Type=notify`, `NotifyAccess=main`, `WorkingDirectory=/opt/CryptoTrader`, `RuntimeDirectory=market-recorder/%i`, and `UMask=0027`. The service-owned control socket lives at `/run/market-recorder/<instance>/control.sock`, is chmodded `0660`, and is group-owned by `market-recorder`. The service continues to use `StateDirectory=market-recorder/%i` for raw output and health manifests while reading its launcher from `/usr/local/bin/market-recorder` and its instance env file from `/etc/CryptoTrader/%i.env`.

Refs: `7b56d9f`; `e8c159b`; `ops/systemd/market-recorder@.service`; `ops/systemd/market-recorder.env.example`; `docs/operations/monitoring.md`; `src/market_recorder/service_control.py`

## Recorder decommission

Status: implemented

Purpose: Cleanly stop a running recorder and remove installed assets without orphaning a worker, a control socket, or environment files that point at a no-longer-active deployment.

Prerequisites: sudo access to run `ops/install/uninstall.sh`; permission to remove `/var/lib/market-recorder/<instance>` when `--purge` is requested.

Procedure: Run `market-recorder stop` if the instance is active, then run `sudo ./ops/install/uninstall.sh --instance <instance>`. Add `--purge` only when you also want to remove `/var/lib/market-recorder/<instance>`. The uninstall script removes `/etc/CryptoTrader/<instance>.env`, `/etc/CryptoTrader/<instance>.yaml`, and `/etc/CryptoTrader/<instance>.sources.yaml` immediately, and removes the shared wrapper, app root, unit, sysusers asset, and polkit rule only when no `/etc/CryptoTrader/*.env` files remain.

Validation: Confirm `market-recorder status` reports `stopped` or that `systemctl status market-recorder@<instance>.service` no longer shows a loaded unit. Confirm the instance env file is removed and, when `--purge` is used, confirm the state directory is gone. Confirm no `.jsonl.zst.open` segments remain under the instance data root before treating the uninstall as complete.

Notes: Always stop the worker before removing its env file so the writer can finalize the active hour file by atomically sealing `.jsonl.zst.open` to `.jsonl.zst`. Removing files first risks leaving an unsealed active segment behind, which `validate-raw` and `report-data-quality` will treat as `incomplete-active` until manually finalized.

Refs: `7b56d9f`; `e8c159b`; `ops/systemd/market-recorder@.service`; `README.md`; `docs/operations/monitoring.md`; `src/market_recorder/service_control.py`