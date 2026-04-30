# Change Log

This file is the repository's durable, concise change history for agents and maintainers.

Use it to record implemented repo changes and meaningful documentation updates in a stable, scan-friendly format. Keep it factual and compact. This file is not a planning document, design diary, or status tracker.

## How To Maintain

* Keep entries newest-first by date.
* Use one bullet per logical change group.
* Prefer commit refs once Git history exists. Before Git is initialized, use a temporary marker such as `pre-git` or `uncommitted`.
* Keep summaries short and concrete. Add a brief second sentence only when the reason matters for future readers.
* When implementation and documentation land separately, list both refs on one line when that makes the history clearer.
* Do not duplicate feature status here. Put ongoing subsystem state in `docs/operations/implementation-status.md`.

## Entry Template

```md
## YYYY-MM-DD

- `<ref>` — short summary. Optional second sentence for context.
```

## 2026-04-30

- `3bc71a4` — implemented the Phase 2 storage foundation with canonical raw-path generation, streaming `.jsonl.zst` writing, hourly rotation, sample output generation, and raw-file validation tooling.
- `242d9aa` — implemented the Phase 1 runtime foundation with typed YAML config loading, raw-envelope helpers, aiohttp-managed lifecycle scaffolding, and CLI/runtime validation coverage.
- `4a88c06` — created the Phase 0 repository baseline, including the canonical docs set, Context7-first agent rules, provider references, project scaffold, example config, package skeleton, and baseline validation hooks.