---
name: shared-research
description: Shared research workflow for up-to-date docs. Prefer a curated docs index tool, then web search, then browser emulation. Use when touching a library/tool for the first time in planning or implementation.
user-invokable: true
disable-model-invocation: false
argument-hint: "[library/tool name + goal]"
---

# Shared research workflow

## Purpose
Ensure agents consult up-to-date, authoritative documentation when introducing or changing usage of a library/tool for the first time in the current task.

## Trigger rule
If planning or implementing code involving a library/tool not recently used in this repo/task, do a docs lookup BEFORE coding.

## Step 0: Identify version + constraints (required)
- Determine the library/tool version in use (or intended) from repo config/lockfiles if available.
- Note relevant environment constraints (runtime version, framework/bundler/SSR vs CSR, platform, etc.).
- If version cannot be determined, mark "version unspecified" and prefer docs that clearly match the likely major version.

## Tool order (strict preference)
1) Curated docs index tool (e.g., Context7-like): resolve library ID, then fetch docs
2) Web search (prefer official domains)
3) Browser emulation (for JS-rendered or blocked docs)

## What to look for (required)
- Official docs / API reference
- Changelog / release notes and migration guides (esp. between major versions)
- Minimal canonical examples relevant to our goal
- Known pitfalls: SSR/bundlers, ESM/CJS, peer deps, initialization order, performance, security defaults

## Research output format
- Library/tool name + version (or "version unspecified") + date accessed
- Primary sources (official docs/repo) + secondary sources if needed
- Evidence (2–5 short excerpts/snippets, keep each snippet small)
- Decision: recommended approach/API surface we will use
- Implications for our change (1–5 bullets)
- Confidence: high/med/low + why

## Guardrails
- Do not exceed 5 tool calls without returning partial findings.
- Prefer primary sources; avoid blog/AI-generated summaries unless no primary sources exist.
- If nothing authoritative is found, state exactly what was tried and what is missing.

## Escalation rule
If uncertainty could cause breaking behavior, security risk, or large refactor scope:
- stop and report decision points + options to the Co-Engineer rather than guessing.

## Scope note
This is a shared skill referenced by all agents, not a separate agent.