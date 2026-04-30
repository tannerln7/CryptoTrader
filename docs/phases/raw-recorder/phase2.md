# Phase 2 — Storage, Rotation, and Raw Validation Foundations

## Overview

This phase creates the first durable recorder output path. It should produce valid raw `.jsonl.zst` files from internal sample data without relying on any external provider.

## Role In Sequence

This is the bridge between runtime scaffolding and live source capture. Later phases should only need to plug provider events into the already-tested storage path.

## Objectives

* Implement the canonical raw path layout.
* Implement append-only compressed writing with predictable rotation behavior.
* Add validation tooling for raw output inspection.
* Prove that the recorder can produce valid raw files before live networking is introduced.

## In Scope

* Path generation aligned with `docs/reference/data-layout.md`.
* Hourly rotation behavior.
* Zstandard-based raw file writing.
* Flush and close semantics suitable for long-running tasks.
* Raw-file validation utilities and sample output checks.
* Sample/demo write path for testing without live APIs.

## Out Of Scope

* Pyth, Aster, or TradingView transport logic.
* External network retries.
* Source-specific parsing.
* Operational dashboards.

## Definitive Ending Spot

At the end of this phase, the repo can generate a representative raw file under the canonical layout, decompress it, and validate that it contains well-formed envelope records.

## Required Validation

* Unit tests or smoke checks for raw path generation.
* Unit tests or smoke checks for file rotation behavior.
* Validation that a sample `.jsonl.zst` file decompresses and contains valid JSON lines.
* Validation that required envelope fields are present in the sample output.
* Validation that shutdown or explicit close flushes data correctly.

## Satisfactory Completion Criteria

* Storage layout is deterministic and matches the docs.
* Writer behavior is safe for append-only long-running capture.
* Validation tooling can inspect raw files without reading everything into memory.
* Live source phases can focus on transport and source handling rather than storage design.

## Notes

* Current Python guidance creates a version-sensitive decision point for zstd support: `compression.zstd` is available in Python 3.14+, while older runtimes may require `python-zstandard`.
* Prefer a streaming/file-oriented write path for append-only event logs rather than building giant buffers in memory.
* If checksum or content-size options are enabled, document the reason and the runtime requirements.

## Docs To Keep In Sync

* `docs/reference/data-layout.md`
* `docs/reference/schemas.md`
* `config/config.example.yaml`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
