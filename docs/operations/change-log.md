# Change Log

This file is the repository's durable, concise change history for agents and maintainers.

Use it to record implemented repo changes and meaningful documentation updates in a stable, scan-friendly format. Keep it factual and compact. This file is not a planning document, design diary, or status tracker.

## How To Maintain

* Keep entries newest-first by date.
* Use one bullet per logical change group.
* Prefer commit refs once Git history exists. Before Git is initialized, use a temporary marker such as `pre-git` or `uncommitted`.
* Keep summaries short and concrete. Add a brief second sentence only when the reason matters for future readers.
* Update this file after the relevant code and non-changelog documentation commits already exist.
* When implementation and documentation land separately, list both refs on one line when that makes the history clearer.
* Standalone changelog-only commits do not need their own changelog entry or self-reference.
* Do not duplicate feature status here. Put ongoing subsystem state in `docs/operations/implementation-status.md`.

## Entry Template

```md
## YYYY-MM-DD

- `<ref>` — short summary. Optional second sentence for context.
```

## 2026-04-30

- `2dda61c`, `88be7e6` — fixed `market-recorder validate-config` for non-editable `python -m pip install .` installs by resolving repo-relative config paths from the runtime repo root instead of the installed package path, and recorded the behavior in the implementation status notes.
- `039d147` — aligned the README, deployment, monitoring, and data-layout docs around the active `.jsonl.zst.open` to sealed `.jsonl.zst` lifecycle, sealed-file-only validation wording, and the parent-directory traverse note for service-user access checks.
- `0c7b256`, `858a2b0` — clarified that `ops/install/install.sh --enable` only enables boot-time startup, added a repo-root service-user access check in the installer, and updated the fresh-install docs to create a runtime config first, verify repo and config access, then start through the unprivileged CLI.
- `d8d1084` — sorted the `service.py` imports so the full `ruff check src tests` repo sweep passes cleanly again after the service-control refactor.
- `e8c159b`, `ead387c` — replaced the repo-scoped recorder controller with a shell-installed systemd service, a service-owned control socket, direct `sd_notify` readiness, dedicated install and uninstall scripts, and updated operator docs for the unprivileged CLI workflow plus raw segment permissions.
- `dd3224e`, `360aa23` — verified the install and service-control workflow end-to-end (fresh-install paths, `validate-config`, `write-sample`, sealed-file `validate-raw`, active-segment rejection, `systemd-analyze verify`, and a 3-minute bounded live `start`/`status`/`health`/`stop` cycle), forced `PYTHONUNBUFFERED=1` on the CLI-managed background worker subprocess so its stdout and stderr reach `data/service/recorder-service.log`, and documented runtime versus dev install, an uninstall and disable workflow, a recorder decommission procedure, and the actual content of the recorder-service log surface.
- `cabbd6f` — updated AGENTS and the agent guidebook to require implementation commits first, non-changelog documentation commits second, and changelog updates last with no self-referential changelog-only entries.
- `0c3d0e6` — refactored raw storage to keep the existing per-stream route layout while introducing writer-owned `.jsonl.zst.open` segments, atomic sealing to `.jsonl.zst`, route-resolved age and size rotation policies, sealed-file-first validation, and explicit handling for incomplete or stale active segments.
- `45accd3` — refactored `market-recorder` into a service-first control surface and added a systemd template that supervises the foreground worker directly.
- `13b3a6c` — cleaned stale scaffold metadata and prepared the bounded Phase 8 normalization handoff state for downstream work.
- `20b70dd` — implemented the Phase 7 unattended runtime with a shared service runner, periodic health manifests, and a route-aware raw data quality report.
- `2eaf53a` — implemented the Phase 6 TradingView webhook path with bounded local serving, canonical raw alert storage, and explicit JSON versus plain-text preservation.
- `2e0fe9f` — implemented the Phase 5 Aster depth path with periodic REST snapshots, bounded partial/diff-depth capture, and diff-depth continuity restart detection.
- `5874f41` — implemented the Phase 4 Aster non-depth capture path with combined-stream routing, bounded CLI capture validation, and corrected case-sensitive stream suffix handling based on live behavior.
- `e0dce93` — implemented the Phase 3 Pyth source adapter with live Hermes SSE capture, reconnect-aware looping, and bounded CLI capture validation against the public endpoint.
- `3bc71a4` — implemented the Phase 2 storage foundation with canonical raw-path generation, streaming `.jsonl.zst` writing, hourly rotation, sample output generation, and raw-file validation tooling.
- `242d9aa` — implemented the Phase 1 runtime foundation with typed YAML config loading, raw-envelope helpers, aiohttp-managed lifecycle scaffolding, and CLI/runtime validation coverage.
- `4a88c06` — created the Phase 0 repository baseline, including the canonical docs set, Context7-first agent rules, provider references, project scaffold, example config, package skeleton, and baseline validation hooks.