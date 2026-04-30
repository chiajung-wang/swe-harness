## What to build

Implement `src/swe_harness/models.py` — all Pydantic models that serve as the shared schema layer for every JSON artifact and DB record in the harness.

Models to implement (schemas from `CONTEXT.md`):

- `FixContract` — failing test path, expected behavior, likely-affected files, repro command, confidence (`high|medium|low`)
- `Verdict` — pass/fail, regression flags, hack-detection results, structured feedback
- `SprintContract` — files_to_modify, approach, risks
- `TraceEntry` — ts, agent, event, tokens, cost, duration
- `RunRecord` — run_id, issue_url, config, verdict, rounds, cost_usd, duration_s, ts

## Acceptance criteria

- [x] All 5 models defined in `src/swe_harness/models.py` using Pydantic v2
- [x] Field types match schemas in `CONTEXT.md`
- [x] `FixContract.confidence` is `Literal["high", "medium", "low"]`
- [x] All models serialize/deserialize round-trip via `.model_dump_json()` / `.model_validate_json()`
- [x] `uv run pytest` passes
- [x] `uv run mypy src/` passes (strict)

## Blocked by

None — can start immediately
