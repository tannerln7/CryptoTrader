# Phase 1 — Runtime Contracts and Recorder Skeleton

## Overview

This phase establishes the recorder's internal contracts and runtime skeleton without yet writing compressed market-data files. It should lock the basic implementation direction so later phases can add behavior without revisiting core runtime choices.

## Role In Sequence

This phase begins the actual recorder codebase. It turns the Phase 0 scaffold into a minimal runnable Python package with defined ownership for config, timestamps, logging, envelopes, and process lifecycle.

## Objectives

* Establish the initial runtime entrypoints for the recorder package.
* Define the shared internal contracts used by all sources.
* Finalize the basic async and compression approach for the codebase.
* Provide config loading and validation good enough for later phases to build on.
* Create a stable place for lifecycle-managed long-running tasks.

## In Scope

* Initial package modules such as `config.py`, `timeutil.py`, `logging.py`, and `cli.py`.
* Config models or validation logic for enabled sources, storage roots, reconnect behavior, and feature toggles.
* Raw-envelope helper definitions aligned with `docs/reference/schemas.md`.
* Basic logging and run-identity conventions.
* Recorder startup and shutdown skeleton.
* Explicit dependency/runtime decisions that later phases depend on.

## Out Of Scope

* Compressed raw file writing.
* External API transport implementation.
* Snapshot scheduling.
* Webhook server behavior.
* Data-quality reporting.

## Definitive Ending Spot

At the end of this phase, the package can start, load config, validate required settings, and initialize recorder components at a structural level. It does not yet need to connect to sources or produce durable raw files.

## Required Validation

* Config parsing smoke tests for valid and invalid example configurations.
* Import or compile smoke checks for the initial package modules.
* CLI or entrypoint smoke check demonstrating clear startup failure on invalid config.
* Unit tests for timestamp and envelope helpers if they are implemented in this phase.

## Satisfactory Completion Criteria

* Shared contracts are explicit enough that later source phases do not need to redesign them.
* The runtime lifecycle has a clear place for startup, long-lived tasks, and cleanup.
* Config shape matches current planning docs.
* Major foundational choices that affect later phases are documented.

## Notes

* Current aiohttp guidance supports a strong single-stack option for HTTP clients, WebSocket clients, and a lightweight webhook server, with `ClientSession` reuse and `cleanup_ctx`-based lifecycle management. If another stack is chosen, document why.
* Avoid locking to outdated helper libraries for SSE. Direct streaming over a maintained async HTTP client is safer unless a helper adds clear value.
* This phase should finalize approach, not over-implement behavior.

## Docs To Keep In Sync

* `docs/agent-guidebook.md`
* `docs/reference/schemas.md`
* `config/config.example.yaml`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
