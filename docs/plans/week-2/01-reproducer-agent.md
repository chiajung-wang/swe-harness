## What to build

`src/swe_harness/agents/reproducer.py` — `Reproducer(issue_url, run_dir, docker, tracer, budget)`.

Agentic loop that:
1. Explores the target repo via `docker.exec()`
2. Writes a failing test to the repo
3. Confirms the test fails via `docker.exec("pytest ...")`
4. Emits `fix_contract.json` to `run_dir` (schema: `FixContract` in `models.py`)

Stall cap: **20 tool calls** (CONTEXT.md). Hard-terminate after cap; write `FixContract` with `reproducer_confidence="low"` and best-effort fields.

## Acceptance criteria

- [ ] `Reproducer` accepts `(issue_url, run_dir, docker, tracer, budget)` — same signature pattern as `Generator`
- [ ] Stall detection fires at 20 tool calls and still emits a valid `fix_contract.json`
- [ ] `reproducer_confidence` is one of `"high" | "medium" | "low"` (Pydantic enforced)
- [ ] All API calls go through `_call()` → logged to tracer, charged to budget
- [ ] `pytest` passes (unit tests with mocked docker/tracer/budget)

## Blocked by

None — can start immediately.
