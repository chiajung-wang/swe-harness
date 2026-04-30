## What to build

Implement `src/swe_harness/tracer.py` — append-only NDJSON writer that records every model call and tool call as a `TraceEntry`.

## Acceptance criteria

- [x] `Tracer(run_dir: Path)` opens `<run_dir>/trace.ndjson` on init (creates file if absent)
- [x] `.log(entry: TraceEntry)` appends one JSON line; no other side effects
- [x] Anthropic `Usage` object maps to `TraceEntry.tokens` (input + output) and `TraceEntry.cost`
- [x] `Tracer` is safe to call from multiple agents in sequence (append mode, not overwrite)
- [x] Unit test: write 3 entries, read back file, assert all 3 present and valid `TraceEntry`
- [x] `uv run pytest` passes
- [x] `uv run mypy src/` passes (strict)

## Blocked by

- `01-core-data-models.md` (needs `TraceEntry` model)
