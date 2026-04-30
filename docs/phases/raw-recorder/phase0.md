# Phase 0 — Repository Baseline and Execution Scaffold

## Overview

This phase establishes the canonical repo scaffold needed for all later raw-recorder work. It is intentionally light on runtime behavior and heavy on structure, ownership clarity, and documentation alignment.

The goal is to eliminate ambiguity about where code, config, tests, scripts, and operational docs belong before implementation starts.

## Role In Sequence

This is the first implementation phase. Every later phase assumes the repo skeleton, placeholder modules, config locations, and tracking docs created here already exist.

## Objectives

* Create the canonical top-level repo structure defined in `AGENTS.md`.
* Add the initial package and directory placeholders required for future source, storage, and test work.
* Add baseline project metadata and example config files needed for later phases.
* Remove avoidable doc drift between current repo state and the documented canonical layout.
* Leave the repo in a state where later phases can add behavior without restructuring the project.

## In Scope

* Directory scaffolding under `config/`, `src/market_recorder/`, `tests/`, `scripts/`, `ops/`, and `data/`.
* Minimal package placeholder files and doc stubs where they clarify future ownership.
* Initial project metadata such as `README.md`, `pyproject.toml`, `.gitignore`, and `.env.example` if they do not yet exist.
* `config/config.example.yaml` and any safe example source config needed for later phases.
* Removing temporary bootstrap notes once the scaffold they reference actually exists.

## Out Of Scope

* Live API connections.
* Raw file writing.
* Source-specific parsing.
* Webhook handling.
* Replay, normalization, features, or backtests.

## Definitive Ending Spot

At the end of this phase, a future implementer can open the repo and immediately see where recorder code, source adapters, storage code, validation scripts, tests, configs, and operations docs belong.

The repo should be structurally ready for implementation, but no market-data recorder behavior needs to run yet.

## Required Validation

* Confirm the documented canonical directories and placeholder files exist.
* Confirm the docs no longer describe missing scaffold files as if they already exist.
* Confirm the example config files are safe to commit and contain no secrets.
* Run lightweight repo checks appropriate to the created files, such as Markdown diagnostics and Python import/compile smoke once package placeholders exist.

## Satisfactory Completion Criteria

* The repo structure matches the canonical layout closely enough that later phases do not need to reorganize it.
* There are no conflicting “primary” docs describing different structures.
* Operations tracking docs exist and reflect the current bootstrap status.
* Future implementation work can begin by filling in modules rather than inventing new structure.

## Notes

* Keep this phase intentionally boring. It should reduce ambiguity, not introduce architecture.
* Placeholder files are acceptable when they clarify ownership and do not imply implemented behavior.
* If structure decisions change during this phase, update the docs immediately rather than allowing silent drift.

## Docs To Keep In Sync

* `AGENTS.md`
* `docs/agent-guidebook.md`
* `docs/phases/raw-recorder/raw-recorder.md`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
