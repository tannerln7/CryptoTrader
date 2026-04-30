---
name: chain-implementer
description: Use when implementing a chunk brief: keep scope tight, follow repo rules, run checks/tests, and report results + files changed.
user-invokable: true
disable-model-invocation: false
argument-hint: "[chunk brief]"
---

# Implementer workflow (chunk execution)

## Always do first
- Read AGENTS.md.
- Consult docs/ for current repo guidance before coding.
- Use the context7 tool, websearch tool, and/or shared-research skill to gather relevant info, examples, and updated best practices before implementating.

## Interpret the chunk brief (contract-first)
- Treat the chunk brief as a contract: implement the stated objective + public surface area.
- Do NOT expand public API (exports, types, props, config knobs) beyond the brief unless required for correctness/compilation.
- Any code shown in the chunk brief is illustrative unless explicitly stated otherwise.
  - If illustrative code conflicts with repo constraints, follow repo constraints and note the deviation.

## Execution rules
- Implement ONLY the assigned chunk.
- Own ONLY the explicit file list for this chunk.
  - If you must touch additional files to make the chunk work, stop and report the dependency/coupling to the Co-Engineer.
- If a cross-chunk dependency appears, stop and report it to the Co-Engineer with clear options.

## Patch discipline
- Use the smallest safe diff.
- Preserve existing style and local conventions.
- Do not refactor unrelated code.
- Avoid introducing new dependencies unless the chunk brief explicitly calls for them.

## Verification
- Run the chunk’s acceptance checks exactly as specified.
- If the chunk brief does not provide checks, run the smallest relevant repo checks (e.g., typecheck and/or unit tests) appropriate to the change.
- If commands cannot be run, state why and what would have been run.

## Required deliverables back to Co-Engineer
- Summary of changes
- Files created/modified (explicit list)
- Commands run + results (or why not)
- Notes: assumptions, deviations from brief (if any), risks, and any discovered cross-chunk dependencies