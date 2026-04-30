## What to build

Extend `src/swe_harness/orchestrator.py` to support `config="two_agent"`:

- `run(issue_url, config="two_agent")` executes Reproducer → Generator in sequence
- Generator reads `fix_contract.json` written by Reproducer from `run_dir`
- Container is shared across both agents (not re-cloned between them)
- `RunRecord` written to SQLite after Generator completes

## Acceptance criteria

- [ ] `config="two_agent"` runs Reproducer first, then Generator using the emitted `fix_contract.json`
- [ ] `config="solo"` still works unchanged (Generator only, no Reproducer)
- [ ] Container lifecycle: single `docker.start()` at orchestrator entry, `docker.stop()` at exit (normal or exception)
- [ ] `RunRecord` written with correct `config` field (`"two_agent"`)
- [ ] `pytest` passes

## Blocked by

01-reproducer-agent — Reproducer agent must exist.
