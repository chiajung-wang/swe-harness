## What to build

Add live console output to `swe-harness run` so users can follow every step in real time — Docker setup, each model call with token/cost info, each tool dispatch, and repro check result.

## Design decisions

- `ProgressReporter = Callable[[str], None]` — Generator formats strings before calling reporter; no structured payload
- `_call()` returns `(Message, TraceEntry)` — base class still writes to tracer; Generator uses returned entry for reporter formatting only
- Tool lines emitted **after** dispatch — single line with result; no pre-dispatch line
- Two output channels — `reporter` for structured progress events; `RichHandler` as safety net for incidental logs (budget warnings, docker errors)
- `reporter = reporter or (lambda _: None)` at each entry point — unconditional call sites throughout
- Orchestrator owns terminal status line — catches `ToolCapExceeded`/`TimeoutExceeded`/`StallDetected` and emits `◆ Repro passed` or failure variant before verdict line

## Acceptance criteria

- [ ] `ProgressReporter = Callable[[str], None]` defined in `orchestrator.py`
- [ ] `orchestrator.run()` accepts optional `reporter`; normalizes to no-op at entry; emits Docker start, Docker ready, Generator started, terminal status, and budget-exceeded events; replaces existing `logger.info` calls for those events
- [ ] `base.AnthropicAgent._call()` returns `(Message, TraceEntry)` in addition to logging the entry internally
- [ ] `Generator.__init__` accepts optional `reporter`; normalizes to no-op at entry; `Generator.run()` emits per-model-call line (using returned `TraceEntry`) and per-tool-dispatch line (after dispatch, with result)
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
