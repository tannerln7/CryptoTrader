# Phase 7 — Operational Hardening and Unattended Runtime

## Overview

This phase makes the recorder safe to run as a long-lived service rather than a development-only tool.

The focus is operational correctness: lifecycle management, graceful shutdown, health visibility, and practical runbook-level confidence.

## Role In Sequence

This phase should begin only after the required source capture paths are functional. It turns working ingestion into serviceable ingestion.

## Objectives

* Make long-lived recorder processes start, stop, and recover predictably.
* Add clear health and data-quality signals for operators.
* Document deployment and runtime assumptions.
* Reduce the chance that transient failures silently damage the raw dataset.

## In Scope

* Service lifecycle management.
* Graceful shutdown and resource cleanup.
* Health counters, manifests, or lightweight monitoring signals.
* Data-quality scripts or reports for missing/corrupt output detection.
* Deployment and monitoring docs.

## Out Of Scope

* Heavy observability platforms unless explicitly requested.
* Retention or deletion automation.
* Normalization or feature pipelines.

## Definitive Ending Spot

At the end of this phase, the recorder can run unattended for meaningful periods and operators have a practical way to tell whether it is alive, stuck, disconnected, or producing bad output.

## Required Validation

* Graceful shutdown checks for open writers and long-lived tasks.
* Restart and reconnect smoke checks.
* Validation or reporting checks that identify missing, corrupt, or stale outputs.
* Service startup checks if service files or deployment wrappers are added.

## Satisfactory Completion Criteria

* Operators can determine health without reading application code.
* Shutdown and restart behavior do not compromise raw-file integrity.
* Runtime concerns are documented well enough to support longer soak runs.

## Notes

* Current aiohttp guidance favors application-managed lifecycle hooks such as `cleanup_ctx`, startup/cleanup signals, tracked background tasks, and explicit graceful shutdown handling over ad hoc untracked tasks.
* If the webhook receiver remains aiohttp-based, operational deployment should account for reverse-proxy and forwarded-header concerns rather than assuming direct public exposure.
* Hardening should remain lightweight until the recorder proves it needs more infrastructure.

## Docs To Keep In Sync

* `docs/operations/deployment.md`
* `docs/operations/monitoring.md`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
