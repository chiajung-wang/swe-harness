## What to build

Implement `src/swe_harness/tracer.py` — append-only NDJSON writer that records every model call and tool call as a `TraceEntry`.

## Acceptance criteria

- [ ] `Tracer(run_dir: Path)` opens `<run_dir>/trace.ndjson` on init (creates file if absent)
- [ ] `.log(entry: TraceEntry)` appends one JSON line; no other side effects
- [ ] Anthropic `Usage` object maps to `TraceEntry.tokens` (input + output) and `TraceEntry.cost`
- [ ] `Tracer` is safe to call from multiple agents in sequence (append mode, not overwrite)
- [ ] Unit test: write 3 entries, read back file, assert all 3 present and valid `TraceEntry`
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes (strict)

## Blocked by

- `01-core-data-models.md` (needs `TraceEntry` model)
