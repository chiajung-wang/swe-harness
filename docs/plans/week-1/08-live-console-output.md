## What to build

Add live console output to `swe-harness run` so users can follow every step in real time — Docker setup, each model call with token/cost info, each tool dispatch, and repro check result.

## Acceptance criteria

- [ ] `ProgressReporter = Callable[[str], None]` defined in `orchestrator.py`
- [ ] `orchestrator.run()` accepts optional `reporter`; emits Docker start, Docker ready, and budget-exceeded events
- [ ] `Generator.__init__` accepts optional `reporter`; `Generator.run()` emits per-model-call and per-tool-dispatch lines
- [ ] `cli.py`: `console.status` spinner removed; `RichHandler` logging configured; `reporter=console.print` wired through
- [ ] Output shape matches:
  ```
  ◆ Docker starting (repo=… commit=…)
  ◆ Docker ready (12.4s)
  ◆ Generator started
    [1] model call → 312 in / 89 out  $0.0001
        → read_file src/budget.py  ✓
        → write_file src/budget.py ✓
    [2] model call → 289 in / 124 out $0.0001
        → run_command pytest ...   exit 0
  ◆ Repro passed — done
  ◆ verdict=pass  cost=$0.0003  duration=34.1s
  ```
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes (strict)

## Blocked by

- `07-end-to-end-wire-up.md`
