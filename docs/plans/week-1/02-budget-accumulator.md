## What to build

Implement `src/swe_harness/budget.py` — spend accumulator with threshold warnings and hard-kill at the $200 limit.

## Acceptance criteria

- [x] `Budget(limit_usd: float)` class with `.charge(cost: float)` method
- [x] `.charge()` accumulates spend and raises `BudgetExceeded` as a hard-kill at `limit_usd`
- [x] Logs a warning (not exception) at $50, $100, $150 thresholds
- [x] `BudgetExceeded` carries `spent` and `limit` fields so orchestrator can write a partial `RunRecord`
- [x] Unit tests cover: normal accumulation, each warning threshold, hard-kill
- [x] `uv run pytest` passes
- [x] `uv run mypy src/` passes (strict)

## Blocked by

None — can start immediately
