# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`swe-harness` — multi-agent Python harness for autonomous bug-fixing. Takes a GitHub issue, produces a PR with fix + regression test. Three agents: Reproducer → Generator → Evaluator.

**Status:** Pre-implementation. See `prd.md` for full spec.

## CLI surface (target)

```bash
swe-harness run <issue-url>       # end-to-end run
swe-harness eval <set>            # run an eval set (dev|custom|swebench)
swe-harness traces show <run-id>  # inspect structured trace
```

## Architecture

### Agent roles

| Agent      | Model                            | Role                                                          |
| ---------- | -------------------------------- | ------------------------------------------------------------- |
| Reproducer | Sonnet 4.6                       | Reads issue → writes failing test → emits `fix_contract.json` |
| Generator  | Haiku 4.5 (Sonnet for SWE-bench) | Receives contract → edits code → iterates until test passes   |
| Evaluator  | Sonnet 4.6                       | Runs full suite → checks for hacks → emits `verdict.json`     |

- Generator bounded: 50 tool-call cap, 15-min wall-clock timeout.
- Evaluator can reject and feed structured feedback back to Generator (max 3 retry rounds).
- Sprint-contract negotiation: Generator proposes approach; Evaluator approves before any code changes (2 rounds max).

### Artifacts (disk-based handoffs)

- `fix_contract.json` — failing test path, expected behavior, likely-affected files, repro command
- `verdict.json` — pass/fail, regression flags, hack-detection results, structured feedback

### Sandboxing

Docker per task: Python 3.11, git, pytest, tox, 4GB RAM, no network except PyPI. Repo at `/repo`.

### MCP server: `repo-context-mcp`

Custom server backed by `tree-sitter`/`jedi`. Tools: `find_definition`, `find_usages`, `list_recent_commits`, `get_test_for_function`.

### Logging

Every tool call, model call, token count, and cost → structured JSON trace per run. SQLite for aggregated eval results.

## Cost constraints

- **Total budget: $200.** Hard budget alerts at $50/$100/$150.
- Prompt caching **mandatory** on system prompts and any repo file loaded >1x. Target: 40-60% Generator cost reduction.
- Opus 4.7 reserved for hard cases only.
- Generator forbidden from modifying pre-existing tests (may add new ones).

## Eval sets

- `dev` — 10 SWE-bench Verified bugs, pinned commits (weeks 1-3 iteration)
- `custom` — 15 real OSS bugs not in SWE-bench, graded against gold patches
- `swebench` — 30-instance stratified SWE-bench Verified sample, official Docker grading

## Key constraints from PRD

- Python only (v1 non-goal: other languages)
- No web UI, no fine-tuning, no real-time dashboards
- Evaluator must NOT see the gold patch during grading
- Generator forbidden from modifying pre-existing tests
- Each PR to OSS must disclose agent provenance honestly

## Don't

- Don't modify or delete tests in /eval/datasets/\* — these are pinned ground truth.
- Don't add new top-level dependencies without flagging in your response.
- Don't catch and swallow exceptions; surface them or re-raise with context.
- Don't expand scope beyond the requested change; no "while I'm here" refactors.
- Don't claim a task is complete without running `pytest` and pasting the output.
- Don't write comments that restate the code; explain _why_, not _what_.
- Don't import heavy ML libraries (torch, transformers) — this project uses the Anthropic API only.
