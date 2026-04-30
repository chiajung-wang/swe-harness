## What to build

Implement `src/swe_harness/agents/base.py` — shared base class for all three agents. Owns the Anthropic client, prompt-cache helper, and the instrumented `_call()` method that logs every model call to the tracer and charges the budget.

## Acceptance criteria

- [x] `AnthropicAgent(tracer: Tracer, budget: Budget)` initializes `anthropic.Anthropic()` client
- [x] `_build_cache_block(content: str) -> dict` wraps text as `{"type":"text","text":...,"cache_control":{"type":"ephemeral"}}`
- [x] `_call(system, messages, tools)` calls the Anthropic API, logs a `TraceEntry`, and calls `budget.charge(cost)`
- [x] `_call()` surfaces API errors — no swallowing
- [x] Unit test: mock Anthropic client, assert `TraceEntry` logged and budget charged after `_call()`
- [x] `uv run pytest` passes
- [x] `uv run mypy src/` passes (strict)

## Blocked by

- `01-core-data-models.md` (needs `TraceEntry`)
- `02-budget-accumulator.md` (needs `Budget`)
- `03-structured-trace-writer.md` (needs `Tracer`)
