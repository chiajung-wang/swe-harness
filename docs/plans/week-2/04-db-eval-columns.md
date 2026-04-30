## What to build

Add `eval_set` and `instance_id` columns to the `runs` table in `src/swe_harness/db.py`.

- `eval_set: str | None` — e.g. `"dev"`, `"custom"`, `"swebench"`, or `None` for ad-hoc runs
- `instance_id: str | None` — SWE-bench or custom instance ID, or `None`
- Both columns nullable; existing `upsert_run()` must handle `None` without error

`RunRecord` in `models.py` must gain these two optional fields (default `None`) so `upsert_run` can read them.

## Acceptance criteria

- [ ] `RunRecord` gains `eval_set: str | None = None` and `instance_id: str | None = None`
- [ ] `init_db()` creates the table with these columns (or migrates if table already exists)
- [ ] `upsert_run(record)` writes both fields correctly
- [ ] Existing runs without these fields are unaffected (nullable)
- [ ] `uv run pytest` passes; `uv run mypy src/` strict passes

## Blocked by

None — can start immediately.
