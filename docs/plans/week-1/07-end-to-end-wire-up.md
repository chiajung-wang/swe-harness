## What to build

Wire `orchestrator.py` + `db.py` + `cli.py` into a working `swe-harness run <issue-url>` command. This slice satisfies the week 1 exit criteria: end-to-end run on a real issue with full NDJSON trace written.

## Acceptance criteria

- [x] `db.py`: `init_db()` creates SQLite `runs` table; `upsert_run(record: RunRecord)` inserts or updates by `run_id`
- [x] `orchestrator.run(issue_url, config="solo")`: creates `runs/<ts>-<slug>/` dir, starts Docker, runs `Generator`, writes `RunRecord` to SQLite, tears down container on completion or exception
- [x] Orchestrator catches `BudgetExceeded`, writes partial `RunRecord` with `status=budget_exceeded`, still tears down container
- [x] `cli.py`: `swe-harness run <issue-url> [--config solo]` with Rich progress output; calls `orchestrator.run()`
- [x] End-to-end test: `swe-harness run <real-issue-url>` completes, `runs/*/trace.ndjson` exists and contains ≥1 entry, SQLite row present
- [x] `uv run pytest` passes
- [x] `uv run mypy src/` passes (strict)

## Blocked by

- `06-generator-agent.md`
