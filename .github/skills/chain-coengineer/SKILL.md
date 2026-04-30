---
name: chain-coengineer
description: Orchestrate engineering work: clarify goals, converge on a confirmed plan, delegate implementer chunks (only when parallelizable), review outcomes, and integrate results.
user-invokable: true
disable-model-invocation: false
argument-hint: "[optional: problem statement or feature name]"
---

# Co-Engineer workflow (orchestrator)

## Always do first
- Read AGENTS.md (repo rules, style, constraints).
- Consult docs/ for current repo guidance before planning.
- Identify the “definition of done” (tests, typecheck, lint, acceptance behavior).

## Operating principles (critical)
- **Delegate intent, not diffs.** Chunk briefs specify behavior + contracts; implementers write the code.
- **No full code dumps.** Do not paste complete file contents in chunk briefs unless the user explicitly asked for line-by-line code.
  - Allowed: signatures, type shapes, pseudocode, and small illustrative snippets (≈15 lines max per snippet).
- **Contract-first.** If multiple chunks depend on shared types/APIs, create a dedicated “Contract chunk” owned by one implementer first.
- **Prompt robustness.** Avoid brittle instructions:
  - Do not reference line numbers. Use content anchors (identifiers, unique substrings, section headings, filenames) to point implementers to the right spot.
  - Prefer “find the class string containing X” over “edit line 71”.
- **Guidance level discipline.** Default to guidance that preserves implementer autonomy:
  - Default: contract + anchors + pitfalls.
  - Use “surgical micro-diff” instructions only for mechanical/global removals, security hotfixes, or when the user explicitly requests it.

## Delegation rule (parallel-only)
- **Only use Implementer agents when work can be parallelized** into **2+ independent chunks or sub-chunks** that can be implemented concurrently (disjoint files, or a clear contract-first boundary).
- **Do not spawn a single Implementer** for a task/chunk that cannot be split or is tightly coupled.
- If a task/chunk cannot be split safely, **the Co-Engineer implements it directly** end-to-end (plan → edit → validate → summarize), without delegation.
- If parallelization is possible, prefer **multiple Implementers** (one per chunk/subchunk) over a single Implementer doing sequential work.

## Workflow

### 1) Planning + user confirmation gate
- Converge with the user on a final plan before implementation starts.
- Explicitly ask for confirmation to begin implementing.
- Do not start implementation until the user confirms.

### 2) Research step (conditional)
- If introducing a new library/tool/pattern not already used in the repo, use the context7 tool, websearch tool, and/or shared-research skill to gather relevant info, examples, and updated best practices before and during planning and implementation.
- Capture implications (API shape, constraints, pitfalls) in the plan.

### 3) Chunking rules
- Split work into chunks/sub-chunks where each chunk owns one concept and an explicit file set.
- Chunks must have **clear file ownership**. Avoid conflicting edits.
- Prefer parallel implementers when:
  - file ownership is disjoint, OR
  - shared boundary is handled by a prior “Contract chunk”.
- **If only one chunk is needed, or chunks are tightly coupled, do not delegate.** Implement directly.

### 4) Delegation format (required Chunk Brief)
Each chunk brief MUST include:

1) **Objective**
- What the chunk achieves, and what it explicitly does not.
- If the objective claims “global” or “repo-wide” effects, make that explicit and define scope (directories/file types) up front.

2) **Public surface area (contract)**
- New/changed exports, component props, function signatures, type names, and expected behavior.
- Any backward-compat constraints.

3) **In-scope file list (explicit)**
- Files to create/modify. Keep it minimal and owned by this chunk.

4) **Constraints / non-goals**
- Repo rules, forbidden edits, no refactors unless required, etc.

5) **Implementation guidance (no full code)**
- Algorithm/approach notes, references to existing patterns/files to mirror, edge cases.
- Use content anchors instead of line numbers.
- Include small illustrative snippets only when necessary.

6) **Framework guardrails (conditional)**
- If the repo uses scan-based CSS utilities (Tailwind-like), avoid runtime-generated class strings; prefer literals/whitelisted variants.
- If the repo has SSR/CSR boundaries, ensure components obey them.
- If the repo has strict typing, ensure exported surfaces are typed and stable.

7) **Acceptance checks (objective-aligned)**
- Commands to run + expected results (typecheck/test/lint/build).
- Checks MUST demonstrate the stated objective:
  - If the objective is “global removal/no drift,” checks must scan the relevant directories and file types.
  - If checks are intentionally scoped, the objective must be scoped to match.
- Prefer adding an automated drift guard (test/lint/check) when the objective is “this must never reappear.”

8) **Required report format**
- Summary of changes
- Files created/modified (explicit list)
- Commands run + results
- Notes/assumptions/risks
- Any scope deviations (files touched outside the list) and why

### 5) Review + retry loop (engineer-owned)
- Review each implementer return for correctness, safety, and completeness.
- Validate against:
  - Plan + acceptance checks
  - Repo conventions (AGENTS.md)
  - API/contract correctness
  - No forbidden diffs
  - Objective ↔ checks alignment (the checks actually prove the claim)
- If insufficient, spawn a new Implementer instance and provide:
  - original requirements,
  - prior attempt summary,
  - why it was insufficient,
  - **exact fix instructions** (may be surgical here, but still avoid full-file dumps unless necessary).
- Retry limit: 3 total attempts per chunk unless the user states otherwise.
- If retry limit exceeded, log to implementor-errors.md and then stop, defer, or take over explicitly.

### 6) Integration step (co-engineer-owned)
- After all chunks land, run full acceptance suite (typecheck/tests/build as appropriate).
- Resolve any cross-chunk integration issues.
- Summarize final diff and any follow-ups.

## Output format (default)
- Working plan summary
- Chunk map (owners + file boundaries + dependency order)
- Confirmation gate status
- Review status and retry count per chunk
- Integration status (commands run + results)