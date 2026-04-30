# CLAUDE.md

## Project

`swe-harness` — multi-agent Python harness: GitHub issue → PR with fix + regression test. See `CONTEXT.md` for full architecture, artifact schemas, and glossary.

### Implemented

- `src/swe_harness/models.py` — Pydantic v2 models (`FixContract`, `SprintContract`, `Verdict`, `TraceEntry`, `RunRecord`)
- `src/swe_harness/budget.py` — spend accumulator, threshold warnings ($50/$100/$150), hard-kill at limit
- `src/swe_harness/tracer.py` — append-only NDJSON trace writer; `entry_from_usage()` maps Anthropic `Usage` → `TraceEntry`
- `src/swe_harness/docker_manager.py` — container lifecycle: start/exec/stop; shell-injection-safe; integration-tested
- `src/swe_harness/agents/base.py` — `AnthropicAgent` base: Anthropic client, `_build_cache_block()`, instrumented `_call()` (logs `TraceEntry`, charges `Budget`)

## Commands

```bash
uv run pytest       # run tests
uv run mypy src/    # type-check (strict)
uv sync             # install deps
```

## Cost constraints

- **Hard budget: $200.** Warn at $50/$100/$150 (log warnings, not exceptions).
- Prompt caching mandatory on all system prompts and repo files.
- Opus 4.7 reserved for hard cases only.

## Before coding

- State assumptions explicitly. If uncertain, ask — don't pick silently.
- If multiple interpretations exist, present them.
- For multi-step tasks, write a brief plan with verifiable success criteria before starting.

## Coding discipline

- Minimum code that solves the problem. No speculative features, abstractions, or configurability.
- Touch only what you must. Match existing style; don't improve adjacent code.
- Remove imports/variables YOUR changes made unused. Leave pre-existing dead code alone — mention it instead.
- Every changed line must trace to the request.

## Don't

- Don't modify or delete tests in `/eval/datasets/` — pinned ground truth.
- Don't add new top-level dependencies without flagging in your response.
- Don't catch and swallow exceptions; surface or re-raise with context.
- Don't claim a task is complete without running `pytest` and pasting the output.
- Don't write comments that restate the code; explain _why_, not _what_.
- Don't import heavy ML libraries (torch, transformers) — Anthropic API only.
- Generator must not modify pre-existing tests (may add new ones).
- Evaluator must not see the gold patch during grading.

## References

- [`CONTEXT.md`](CONTEXT.md) — canonical glossary, resolved decisions, all artifact schemas
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`docs/plans/PLAN.md`](docs/plans/PLAN.md) — implementation plan
