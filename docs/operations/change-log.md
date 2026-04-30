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

- `pre-git` — added a repo-wide Context7-first research rule for code decisions and implementation, including resolve-first querying guidance for future agents.
- `pre-git` — initialized the operations document scaffolds, normalized the `docs/reference/` path, aligned the internal docs with the repo's docs-first bootstrap state, split the raw-recorder program into detailed phase files, and refreshed the provider reference docs against current external documentation.