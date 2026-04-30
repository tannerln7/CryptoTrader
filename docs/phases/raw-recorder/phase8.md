# Phase 8 — Stability Run and Normalization Handoff

## Overview

This phase closes the raw-recorder buildout by proving the system is stable enough to become the durable source-of-truth layer for later normalization and replay work.

## Role In Sequence

This is the final raw-recorder phase. It should consolidate what the earlier phases produced, document remaining limits, and create a clean handoff into normalization planning.

## Objectives

* Run the recorder long enough to observe realistic behavior.
* Summarize data quality, source quirks, and runtime limits.
* Confirm the raw layer is stable enough that downstream phases can depend on it.
* Record what normalization should assume and what it should not assume.

## In Scope

* Extended soak or stability run.
* Data-quality summaries and representative sample inspection.
* Final provider-doc alignment where live behavior differs from prior assumptions.
* Handoff notes for normalization planning.
* Final cleanup of temporary bootstrap or transitional notes that are no longer true.

## Out Of Scope

* Implementing normalization itself.
* Feature generation.
* Trading logic.
* Retention rollout unless explicitly scoped.

## Definitive Ending Spot

At the end of this phase, the raw recorder is no longer “still taking shape.” It is a stable, documented base layer that downstream work can treat as durable.

## Required Validation

* A meaningful stability run, ideally at least 24 to 48 hours for the required sources.
* Representative file validation across all enabled source types.
* Data-quality summary covering counts, first/last timestamps, gaps, and obvious corruption.
* Confirmation that known limitations and remaining risks are documented.

## Satisfactory Completion Criteria

* The team can begin normalization without changing raw-recorder architecture.
* Known source quirks and operational limits are documented rather than hidden in implementation details.
* Temporary bootstrap notes introduced during early scaffolding are removed if no longer accurate.

## Notes

* This phase is about evidence, not optimism. A recorder that merely ran once is not ready for handoff.
* Use this phase to turn provisional assumptions into explicit documentation.
* If the soak run reveals important source-doc mismatches, update the provider docs before declaring the phase complete.

## Docs To Keep In Sync

* `docs/agent-guidebook.md`
* `docs/reference/providers/*.md`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
