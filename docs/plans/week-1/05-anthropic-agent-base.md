## What to build

Implement `src/swe_harness/agents/base.py` — shared base class for all three agents. Owns the Anthropic client, prompt-cache helper, and the instrumented `_call()` method that logs every model call to the tracer and charges the budget.

## Acceptance criteria

- [ ] `AnthropicAgent(tracer: Tracer, budget: Budget)` initializes `anthropic.Anthropic()` client
- [ ] `_build_cache_block(content: str) -> dict` wraps text as `{"type":"text","text":...,"cache_control":{"type":"ephemeral"}}`
- [ ] `_call(system, messages, tools)` calls the Anthropic API, logs a `TraceEntry`, and calls `budget.charge(cost)`
- [ ] `_call()` surfaces API errors — no swallowing
- [ ] Unit test: mock Anthropic client, assert `TraceEntry` logged and budget charged after `_call()`
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes (strict)

## Blocked by

- `01-core-data-models.md` (needs `TraceEntry`)
- `02-budget-accumulator.md` (needs `Budget`)
- `03-structured-trace-writer.md` (needs `Tracer`)
