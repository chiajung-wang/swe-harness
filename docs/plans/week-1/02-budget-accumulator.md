## What to build

Implement `src/swe_harness/budget.py` — spend accumulator with threshold warnings and hard-kill at the $200 limit.

## Acceptance criteria

- [ ] `Budget(limit_usd: float)` class with `.charge(cost: float)` method
- [ ] `.charge()` accumulates spend and raises `BudgetExceeded` as a hard-kill at `limit_usd`
- [ ] Logs a warning (not exception) at $50, $100, $150 thresholds
- [ ] `BudgetExceeded` carries `spent` and `limit` fields so orchestrator can write a partial `RunRecord`
- [ ] Unit tests cover: normal accumulation, each warning threshold, hard-kill
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes (strict)

## Blocked by

None — can start immediately
